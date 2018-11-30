"""
Core event-centric data abstraction for the submission & moderation subsystem.

This package provides an event-based API for mutating submissions. Instead of
representing submissions as objects, and mutating them directly in web
controllers and other places, we represent a submission as a stream of commands
or events. This ensures that we have a precise and complete record of
activities concerning submissions, and provides an explicit and consistent
definition of operations that can be performed within the arXiv submission
system.

Command/event classes are defined in :mod:`arxiv.submission.domain.event`, and
are accessible from the root namespace of this package. Each event type defines
a transformation/operation on a single submission, and defines the data
required to perform that operation. Events are played forward, in order, to
derive the state of a submission. For more information about how event types
are defined, see :class:`arxiv.submission.domain.event.Event`.

.. note::

   One major difference between the event stream and the classic submission
   database table is that in the former model, there is only one submission id
   for all versions/mutations. In the legacy system, new rows are created in
   the submission table for things like creating a replacement, adding a DOI,
   or requesting a withdrawal. The :ref:`legacy-integration` handles the
   interchange between these two models.


Using commands/events
=====================

Commands/events types are `PEP 557 data classes
<https://www.python.org/dev/peps/pep-0557/>`_. Each command/event inherits from
:class:`.Event`, and may add additional fields. See :class:`.Event` for more
information about common fields.

To create a new command/event, initialize the class with the relevant
data, and commit it using :func:`.save`. For example:

.. code-block:: python

   >>> from arxiv.submission import User, SetTitle, save
   >>> user = User(123, "joe@bloggs.com")
   >>> update = SetTitle(creator=user, title='A new theory of foo')
   >>> submission = save(creation, submission_id=12345)


If the commands/events are for a submission that already exists, the latest
state of that submission will be obtained by playing forward past events. New
events will be validated and applied to the submission in the order that they
were passed to :func:`.save`.

- If an event is invalid (e.g. the submission is not in an appropriate state
  for the operation), an :class:`.InvalidEvent` exception will be raised.
  Note that at this point nothing has been changed in the database; the
  attempt is simply abandoned.
- The command/event is stored, as is the latest state of the
  submission. Events and the resulting state of the submission are stored
  atomically.
- If the notification service is configured, a message about the event is
  propagated as a Kinesis event on the configured stream. See
  :mod:`arxiv.submission.services.notification` for details.

Special case: creation
----------------------
Note that if the first event is a :class:`.CreateSubmission` the
submission ID need not be provided, as we won't know what it is yet. For
example:

.. code-block:: python

   from arxiv.submission import User, CreateSubmission, SetTitle, save

   >>> user = User(123, "joe@bloggs.com")
   >>> creation = CreateSubmission(creator=user)
   >>> update = SetTitle(creator=user, title='A new theory of foo')
   >>> submission, events = save(creation, update)
   >>> submission.submission_id
   40032


.. _legacy-integration:

Integration with the legacy system
==================================
The :mod:`classic` service module provides integration with the classic
database. See the documentation for that module for details. As we migrate
off of the classic database, we will swap in a new service module with the
same API.

"""

from typing import Optional, List, Tuple
from arxiv.base import logging
from .domain.submission import Submission, SubmissionMetadata, Author
from .domain.agent import Agent, User, System, Client
from .domain.event import *
from .domain.rule import RuleCondition, RuleConsequence, EventRule
from .services import classic
from .exceptions import InvalidEvent, InvalidStack, NoSuchSubmission, SaveError

logger = logging.getLogger(__name__)


def load(submission_id: int) -> Tuple[Submission, List[Event]]:
    """
    Load a submission and its history.

    This loads all events for the submission, and generates the most
    up-to-date representation based on those events.

    Parameters
    ----------
    submission_id : str
        Submission identifier.

    Returns
    -------
    :class:`.Submission`
        The current state of the submission.
    list
        Items are :class:`.Event`s, in order of their occurrence.

    Raises
    ------
    :class:`.NoSuchSubmission`
        Raised when a submission with the passed ID cannot be found.
    """
    try:
        return classic.get_submission(submission_id)
    except classic.NoSuchSubmission as e:
        raise NoSuchSubmission(f'No submission with id {submission_id}') from e


def load_submissions_for_user(user_id: int) -> List[Submission]:
    """
    Load active :class:`.Submission`s for a specific user.

    Parameters
    ----------
    user_id : int
        Unique identifier for the user.

    Returns
    -------
    list
        Items are :class:`.Submission` instances.

    """
    return classic.get_user_submissions_fast(user_id)


def load_fast(submission_id: int) -> Submission:
    """
    Load a :class:`.Submission` from its last projected state.

    This does not load and apply past events. The most recent stored submission
    state is loaded directly from the database.

    Parameters
    ----------
    submission_id : str
        Submission identifier.

    Returns
    -------
    :class:`.Submission`
        The current state of the submission.

    """
    try:
        return classic.get_submission_fast(submission_id)
    except classic.NoSuchSubmission as e:
        raise NoSuchSubmission(f'No submission with id {submission_id}') from e


def save(*events: Event, submission_id: Optional[str] = None) \
        -> Tuple[Submission, List[Event]]:
    """
    Commit a set of new :class:`.Event`s for a submission.

    This will persist the events to the database, along with the final
    state of the submission, and generate external notification(s) on the
    appropriate channels.

    Parameters
    ----------
    events : :class:`.Event`
        Events to apply and persist.
    submission_id : int
        The unique ID for the submission, if available. If not provided, it is
        expected that ``events`` includes a :class:`.CreateSubmission`.

    Returns
    -------
    :class:`arxiv.submission.domain.submission.Submission`
        The state of the submission after all events (including rule-derived
        events) have been applied. Updated with the submission ID, if a
        :class:`.CreateSubmission` was included.
    list
        A list of :class:`.Event` instances applied to the submission. Note
        that this list may contain more events than were passed, if event
        rules were triggered.

    Raises
    ------
    :class:`.NoSuchSubmission`
        Raised if ``submission_id`` is not provided and the first event is not
        a :class:`.CreateSubmission`, or ``submission_id`` is provided but
        no such submission exists.
    :class:`.InvalidEvent`
        If an invalid event is encountered, the entire operation is aborted
        and this exception is raised.
    :class:`.SaveError`
        There was a problem persisting the events and/or submission state
        to the database.

    """
    if len(events) == 0:
        raise ValueError('Must pass at least one event')
    events = list(events)   # Coerce to list so that we can index.
    prior: List[Event] = []
    before: Optional[Submission] = None

    # Get the current state of the submission from past events.
    if submission_id is not None:
        before, prior = classic.get_submission(submission_id)

    # Either we need a submission ID, or the first event must be a creation.
    elif events[0].submission_id is None \
            and not isinstance(events[0], CreateSubmission):
        raise NoSuchSubmission('Unable to determine submission')

    events = sorted(list(set(prior) | set(events)), key=lambda e: e.created)

    # Apply the events from the end of the existing stream.
    for i, event in enumerate(list(events)):
        # Fill in event IDs, if they are missing.
        if event.submission_id is None and submission_id is not None:
            event.submission_id = submission_id

        # Mutation happens here; raises InvalidEvent.
        after = event.apply(before)
        if not event.committed:
            event, after = classic.store_event(event, before, after)

        # TODO: <-- emit event here.
        # TODO: <-- apply rules here.
        events[i] = event
        before = after
    return after, events    # Return the whole stack.
