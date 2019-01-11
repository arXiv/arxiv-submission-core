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

from .domain.event import *
from .core import save, load, load_fast, init_app
from .domain.submission import Submission, SubmissionMetadata, Author
from .domain.agent import Agent, User, System, Client
from .services import classic
