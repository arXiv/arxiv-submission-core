"""Provides the base command/event class, :class:`Event`."""

from typing import Optional, Callable, Tuple, Iterable, List, ClassVar, Mapping
from collections import defaultdict
from datetime import datetime
import hashlib
import copy
from functools import wraps
from flask import current_app
from dataclasses import field, asdict
from .util import dataclass

from arxiv.base import logging
from arxiv.base.globals import get_application_config

from ..agent import Agent, System
from ...exceptions import InvalidEvent
from ..util import get_tzaware_utc_now
from ..submission import Submission

logger = logging.getLogger(__name__)
logger.propagate = False


Events = Iterable['Event']
Condition = Callable[['Event', Submission, Submission], bool]
Callback = Callable[['Event', Submission, Submission, Agent], Events]
Decorator = Callable[[Callable], Callable]
Rule = Tuple[Condition, Callback]
Store = Callable[['Event', Submission, Submission], Tuple['Event', Submission]]


@dataclass()
class Event:
    """
    Base class for submission-related events/commands.

    An event represents a change to a :class:`.domain.Submission`. Rather than
    changing submissions directly, an application should create (and store)
    events. Each event class must inherit from this base class, extend it with
    whatever data is needed for the event, and define methods for validation
    and projection (changing a submission):

    - ``validate(self, submission: Submission) -> None`` should raise
      :class:`.InvalidEvent` if the event instance has invalid data.
    - ``project(self, submission: Submission) -> Submission`` should perform
      changes to the :class:`.domain.Submission` and return it.

    An event class also provides a hook for doing things automatically when the
    submission changes. To register a function that gets called when an event
    is committed, use the :func:`bind` method.
    """

    creator: Agent
    """
    The agent responsible for the operation represented by this event.

    This is **not** necessarily the creator of the submission.
    """

    created: datetime = field(default_factory=get_tzaware_utc_now)
    """
    The timestamp when the event was originally committed.

    This should generally not be set from outside this package.
    """

    proxy: Optional[Agent] = field(default=None)
    """
    The agent who facilitated the operation on behalf of the :attr:`.creator`.

    This may be an API client, or another user who has been designated as a
    proxy. Note that proxy implies that the creator was not directly involved.
    """

    client: Optional[Agent] = field(default=None)
    """
    The client through which the :attr:`.creator` performed the operation.

    If the creator was directly involved in the operation, this property should
    be the client that facilitated the operation.
    """

    submission_id: Optional[int] = field(default=None)
    """
    The primary identifier of the submission being operated upon.

    This is defined as optional to support creation events, and to facilitate
    chaining of events with creation events in the same transaction.
    """

    committed: bool = field(default=False)
    """
    Indicates whether the event has been committed to the database.

    This should generally not be set from outside this package.
    """

    before: Optional[Submission] = None
    """The state of the submission prior to the event."""

    after: Optional[Submission] = None
    """The state of the submission after the event."""

    _hooks: ClassVar[Mapping[type, List[Rule]]] = defaultdict(list)

    @property
    def event_type(self) -> str:
        """Name of the event type."""
        return self.get_event_type()

    @classmethod
    def get_event_type(cls) -> str:
        """Get the name of the event type."""
        return cls.__name__

    @property
    def event_id(self) -> str:
        """Unique ID for this event."""
        h = hashlib.new('sha1')
        h.update(b'%s:%s:%s' % (self.created.isoformat().encode('utf-8'),
                                self.event_type.encode('utf-8'),
                                self.creator.agent_identifier.encode('utf-8')))
        return h.hexdigest()

    def apply(self, submission: Optional[Submission] = None) -> Submission:
        """Apply the projection for this :class:`.Event` instance."""
        self.before = copy.deepcopy(submission)
        self.validate(submission)
        if submission is not None:
            self.after = self.project(copy.deepcopy(submission))
        else:
            logger.debug('Submission is None; project without submission.')
            self.after = self.project()
        self.after.updated = self.created

        # Make sure that the submission has its own ID, if we know what it is.
        if self.after.submission_id is None and self.submission_id is not None:
            self.after.submission_id = self.submission_id
        if self.submission_id is None and self.after.submission_id is not None:
            self.submission_id = self.after.submission_id
        return self.after

    def to_dict(self):
        """Generate a dict representation of this :class:`.Event`."""
        data = asdict(self)
        data.update({'event_type': self.event_type})
        data.pop('before')
        data.pop('after')
        return data

    @classmethod
    def bind(cls, condition: Optional[Condition] = None) -> Decorator:
        """
        Generate a decorator to bind a callback to an event type.

        To register a function that will be called whenever an event is
        committed, decorate it like so:

        .. code-block:: python

           @MyEvent.bind()
           def say_hello(event: MyEvent, before: Submission,
                         after: Submission, creator: Agent) -> Iterable[Event]:
               yield SomeOtherEvent(...)

        The callback function will be passed the event that triggered it, the
        state of the submission before and after the triggering event was
        applied, and a :class:`.System` agent that can be used as the creator
        of subsequent events. It should return an iterable of other
        :class:`.Event` instances, either by ``yield``\ing them, or by
        returning an iterable object of some kind.

        By default, callbacks will only be called if the creator of the
        trigger event is not a :class:`.System` instance. This makes it less
        easy to define infinite chains of callbacks. You can pass a custom
        condition to the decorator, for example:

        .. code-block:: python

           def jill_created_an_event(event: MyEvent, before: Submission,
                                     after: Submission) -> bool:
               return event.creator.username == 'jill'


           @MyEvent.bind(jill_created_an_event)
           def say_hi(event: MyEvent, before: Submission,
                      after: Submission, creator: Agent) -> Iterable[Event]:
               yield SomeOtherEvent(...)

        Note that the condition signature is ``(event: MyEvent, before:
        Submission, after: Submission) -> bool``\.

        Parameters
        ----------
        condition : Callable
            A callable with the signature ``(event: Event, before: Submission,
            after: Submission) -> bool``. If this callable returns ``True``,
            the callback will be triggered when the event to which it is bound
            is saved. The default condition is that the event was not created
            by :class:`System`

        Returns
        -------
        Callable
            Decorator for a callback function, with signature ``(event: Event,
            before: Submission, after: Submission, creator: Agent =
            System(...)) -> Iterable[Event]``.

        """
        if condition is None:
            def _creator_is_not_system(e: Event, *args, **kwargs) -> bool:
                return type(e.creator) is not System
            condition = _creator_is_not_system

        def decorator(func: Callback) -> Callback:
            """Register a callback for an event type and condition."""
            name = f'{cls.__name__}::{func.__module__}.{func.__name__}'
            sys = System(name)
            setattr(func, '__name__', name)

            @wraps(func)
            def do(event: Event, before: Submission, after: Submission,
                   creator: Agent = sys, **kwargs) -> Iterable['Event']:
                """Perform the callback. Here in case we need to hook in."""
                return func(event, before, after, creator, **kwargs)

            cls._add_callback(condition, do)
            return do
        return decorator

    @classmethod
    def _add_callback(cls: type, condition: Condition,
                      callback: Callback) -> None:
        cls._hooks[cls].append((condition, callback))

    def _get_callbacks(self) -> List[Tuple[Condition, Callback]]:
        return ((condition, callback) for cls in type(self).__mro__[::-1]
                for condition, callback in self._hooks[cls])

    def _should_apply_callbacks(self) -> bool:
        config = get_application_config()
        return bool(int(config.get('ENABLE_CALLBACKS', '0')))

    def commit(self, store: Store) -> Tuple[Submission, Events]:
        """
        Persist this event instance using an injected store method.

        Parameters
        ----------
        save : Callable
            Should have signature ``(*Event, submission_id: int) ->
            Tuple[Event, Submission]``.

        Returns
        -------
        :class:`Submission`
            State of the submission after storage. Some changes may have been
            made to ensure consistency with the underlying datastore.
        list
            Items are :class:`Event` instances.

        """
        _, after = store(self, self.before, self.after)
        self.committed = True
        if not self._should_apply_callbacks():
            return self.after, []
        consequences: List[Event] = []
        for condition, callback in self._get_callbacks():
            if condition(self, self.before, self.after):
                for consequence in callback(self, self.before, self.after):
                    self.after = consequence.apply(self.after)
                    consequences.append(consequence)
                    self.after, addl_consequences = consequence.commit(store)
                    for addl in addl_consequences:
                        consequences.append(addl)
        return self.after, consequences
