"""
Core event-centric data abstraction for the submission & moderation subsystem.

This package provides an event-based API for CRUD operations on submissions
and submission-related (meta)data. Management of submission content (i.e.
source files) is out of scope.

Rather than perform CRUD operations directly on submission objects, all
operations that modify submission data are performed through the creation of
submission events. This ensures that we have a precise and complete record of
activities concerning submissions, and provides an explicit definition of
operations that can be performed within the arXiv submission system.

Event classes are defined in :mod:`arxiv.submission.domain.event`, and are accessible
from the root namespace of this package. Each event type defines a
transformation/operation on a single submission, and defines the data required
to perform that operation. Events are played forward, in order, to derive the
state of a submission. For more information about how event types are defined,
see :class:`arxiv.submission.domain.event.Event`.

Using events
============

Event types are `PEP 557 data classes
<https://www.python.org/dev/peps/pep-0557/>`_. Each event type inherits from
:class:`.Event`, and may add additional fields. See :class:`.Event` for more
information about common fields.

To create a new event, initialize the class with the relevant
data, and commit the event using :func:`.save`. For example:

.. code-block:: python

   >>> from arxiv.submission import User, SetTitle, save
   >>> user = User(123, "joe@bloggs.com")
   >>> update = SetTitle(creator=user, title='A new theory of foo')
   >>> submission = save(creation, submission_id=12345)


Several things will occur:

1. If the events are for a submission that already exists, the latest state of
   that submission will be obtained.
2. New events will be validated and applied to the submission in the order that
   they were passed to :func:`.save`. If an event is invalid (e.g. the
   submission is not in an appropriate state for the operation), an
   :class:`.InvalidEvent` exception will be raised. Note that at this point
   nothing has been changed in the database; the attempt is simply abandoned.
3. The new events are stored in the database, as is the latest state of the
   submission. Creation of events and creation/update of the submission are
   performed as a single atomic transaction. If anything goes wrong during the
   update operation, all changes are abandoned and a :class:`.RuntimeError`
   exception is raised.
4. If the notification service is configured, a message about the event is
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
   >>> submission = save(creation, update)
   >>> submission.submission_id
   40032


"""

from typing import Optional, List, Tuple
from arxiv.base import logging
from .domain.submission import Submission, SubmissionMetadata, Author
from .domain.agent import Agent, User, System, Client
from .domain.event import (
    Event, CreateSubmission, RemoveSubmission, VerifyContactInformation,
    AssertAuthorship, AcceptPolicy, SetPrimaryClassification,
    AddSecondaryClassification, RemoveSecondaryClassification, SelectLicense,
    SetUploadPackage, UpdateAuthors, CreateComment, DeleteComment,
    AddDelegate, RemoveDelegate, FinalizeSubmission, UnFinalizeSubmission,
    SetTitle, SetAbstract, SetDOI, SetComments, SetReportNumber,
    SetMSCClassification, SetACMClassification, SetJournalReference
)
from .domain.rule import RuleCondition, RuleConsequence, EventRule
from .services import classic
from .exceptions import InvalidEvent, InvalidStack, NoSuchSubmission, SaveError

logger = logging.getLogger(__name__)


def load(submission_id: str) -> Tuple[Submission, List[Event]]:
    """
    Load a submission and its history.

    Parameters
    ----------
    submission_id : str
        Submission identifier.

    Returns
    -------
    :class:`arxiv.submission.domain.submission.Submission`
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

    # Do some sanity checks before proceeding.
    for event in events:
        if submission_id is not None:
            if event.submission_id is None:
                event.submission_id = submission_id
            if event.submission_id != submission_id:
                raise InvalidEvent(event,
                                   "Can't mix events for multiple submissions")

    # We want to play events from the beginning.
    if submission_id is not None:
        existing_events = classic.get_events(submission_id)
    else:
        existing_events = []
    combined = existing_events + list(events)

    # Load any relevant event rules for this submission.
    rules = []  # database.get_rules(submission_id)

    # Calculate the state of the submission from old and new events.
    submission, combined = _apply_events(combined, rules)

    # Update the submission ID to ensure the existing submission is updated.
    if submission.submission_id is None:
        submission.submission_id = submission_id    # May still be None.

    # Persist in database; submission ID is updated after transaction.
    try:
        submission = classic.store_events(*combined, submission=submission)
    except classic.CommitFailed as e:
        logger.debug('Encountered CommitFailed exception: %s', str(e))
        raise SaveError('Failed to store events') from e

    for event in combined:
        event.submission_id = submission.submission_id
    return submission, combined


def _apply_rules(submission: Submission, event: Event,
                 rules: List[EventRule]) -> List[Event]:
    """Generate new event(s) by applying rules to a submission event."""
    def _apply(rule: EventRule) -> bool:
        return rule.condition(submission, event)
    return [
        rule.consequence(submission, event) for rule in filter(_apply, rules)
    ]


def _apply_events(events: List[Event], rules: List[EventRule],
                  submission: Optional[Submission] = None) \
         -> Tuple[Submission, List[Event]]:
    """
    Apply a set of events in order.

    Parameters
    ----------
    events : list
        Items are :class:`.Event` instances.
    rules : list
        Items are :class:`.EventRule` instances.
    submission : :class:`.Submission` or None
        Starting state from which to begin applying ``events``. If
        ``submission`` is not provided, ``events`` must contain a
        :class:`.CreateSubmission`.

    Returns
    -------
    :class:`.Submission`
        Submission state after events have been applied.
    list
        Items are :class:`.Event`s that have been applied, including any
        additional events generated by ``rules``.

    Raises
    ------
    :class:`.NoSuchSubmission`
        If ``submission`` is not provided, and the first event is not a
        :class:`.CreateSubmission`, there's not much else to go on.
    :class:`.InvalidStack`
        If at least one invalid event is encountered, this exception is raised.

    """
    events = sorted(events, key=lambda e: e.created)

    # Need either a creation event or a submission state from which to start.
    if not isinstance(events[0], CreateSubmission) and submission is None:
        raise NoSuchSubmission('No creation, and submission not provided')

    extra_events: List[Event] = []    # Generated by applied rules.

    invalid_events: List[InvalidEvent] = []
    for event in events:
        try:
            event.validate(submission)      # Will throw InvalidEvent.
        except InvalidEvent as e:
            invalid_events.append(e)
            continue

        if isinstance(event, CreateSubmission):
            submission = event.apply()
        else:
            submission = event.apply(submission)

        if not event.committed:   # Don't create duplicate rule-derived events.
            # Any rule-derived events should be applied before moving on.
            _extra = _apply_rules(submission, event, rules)
            if len(_extra) > 0:
                try:
                    submission, _extra = _apply_events(_extra, rules, submission)
                    extra_events += _extra
                except InvalidStack as e:
                    # TODO: Handle merging of stacks
                    invalid_events.extend(e.event_exceptions)

    if invalid_events:
        raise InvalidStack(invalid_events)

    return submission, sorted(events + extra_events, key=lambda e: e.created)
