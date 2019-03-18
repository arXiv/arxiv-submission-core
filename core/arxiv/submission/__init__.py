"""
Core event-centric data abstraction for the submission & moderation subsystem.

This package provides an event-based API for mutating submissions. Instead of
representing submissions as objects and mutating them directly in web
controllers and other places, we represent a submission as a stream of commands
or events. This ensures that we have a precise and complete record of
activities concerning submissions, and provides an explicit and consistent
definition of operations that can be performed within the arXiv submission
system.

Overview
========

Event types are defined in :mod:`.domain.event`. The base class for all events
is :class:`.domain.event.event.Event`. Each event type defines additional
required data, and have ``validate`` and ``project`` methods that implement its
logic. Events operate on :class:`.domain.submission.Submission` instances.

.. code-block:: python

   from arxiv.submission import CreateSubmission, User, Submission
   user = User(1345, 'foo@user.com')
   creation = CreateSubmission(creator=user)


:mod:`.core` defines the persistence API for submission data.
:func:`.core.save` is used to commit new events. :func:`.core.load` retrieves
events for a submission and plays them forward to get the current state,
whereas :func:`.core.load_fast` retrieves the latest projected state of the
submission (faster, theoretically less reliable).

.. code-block:: python

   from arxiv.submission import save, SetTitle
   submission, events = save(creation, SetTitle(creator=user, title='Title!'))


Watch out for :class:`.exceptions.InvalidEvent` to catch validation-related
problems (e.g. bad data, submission in wrong state). Watch for
:class:`.SaveError` to catch problems with persisting events.

Callbacks can be attached to event types in order to execute routines
automatically when specific events are committed, using
:func:`.domain.Event.bind`.

.. code-block:: python

   from typing import Iterable

   @SetTitle.bind()
   def flip_title(event: SetTitle, before: Submissionm, after: Submission,
                  creator: Agent) -> Iterable[SetTitle]:
       yield SetTitle(creator=creator, title=f"(╯°□°）╯︵ ┻━┻ {event.title}")


Quality control processes and policies are defined in :mod:`.rules` using
bound callbacks. This includes things like calling the auto-classifier,
checking titles for weirdness, etc.

Some callbacks take too long to perform in the context of an HTTP request, and
so we perform them concurrently in the :ref:`submission-worker`. Callbacks
that should be run by the worker are decorated with :func:`.tasks.is_async`.
This registers the callback by name with the worker, and performs magic so that
when the callback is executed a task is dispatched the worker queue rather than
running the callback in the current thread. See also :mod:`.worker`.

.. code-block:: python

   from ..tasks import is_async

   @SetTitle.bind()
   @is_async
   def flip_title(event: SetTitle, before: Submissionm, after: Submission,
                  creator: Agent) -> Iterable[SetTitle]:
       time.sleep(30)    # *yawn*
       yield SetTitle(creator=creator, title=f"(╯°□°）╯︵ ┻━┻ {event.title}")


Finally, :mod:`.services.classic` provides integration with the classic
submission database. We use the classic database to store events (new table),
and also keep its legacy tables up to date so that other legacy components
continue to work as expected.


Using commands/events
=====================

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


.. _versioning-overview:

Versioning events
=================
Handling changes to this software in a way that does not break past data is a
non-trivial problem. In a traditional relational database arrangement we would
leverage a database migration tool to do things like apply ``ALTER`` statements
to tables when upgrading software versions. The premise of the event data
model, however, is that events are immutable -- we won't be going back to
modify past events whenever we make a change to the software.

The strategy for version management around event data is implemented in
:mod:`arxiv.submission.domain.events.versioning`. When event data is stored,
it is tagged with the current version of this software. When
event data are loaded from the store in this software, prior to instantiating
the appropriate :class:`.Event` subclass, the data are mapped to the current
software version using any defined version mappings for that event type.
This happens on the fly, in :func:`.domain.event.event_factory`.


.. _legacy-integration:

Integration with the legacy system
==================================
The :mod:`classic` service module provides integration with the classic
database. See the documentation for that module for details. As we migrate
off of the classic database, we will swap in a new service module with the
same API.

"""
import os
from flask import Flask, Blueprint

from .domain.event import *
from .core import *
from .domain.submission import Submission, SubmissionMetadata, Author
from .domain.agent import Agent, User, System, Client
from .services import classic
from . import rules


def init_app(app: Flask) -> None:
    template_folder = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                   'templates')
    app.register_blueprint(
        Blueprint('submission-core', __name__, template_folder=template_folder)
    )
