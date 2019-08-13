"""Provides the base event class."""

import copy
import hashlib
from collections import defaultdict
from datetime import datetime
from functools import wraps
from typing import Optional, Callable, Tuple, Iterable, List, ClassVar, \
    Mapping, Type, Any, overload

from dataclasses import field, asdict
from flask import current_app
from pytz import UTC

from arxiv.base import logging
from arxiv.base.globals import get_application_config

from ...exceptions import InvalidEvent
from ..agent import Agent, System, agent_factory
from ..submission import Submission
from ..util import get_tzaware_utc_now
from .util import dataclass
from .versioning import EventData, map_to_current_version

logger = logging.getLogger(__name__)
logger.propagate = False

Events = Iterable['Event']
Condition = Callable[['Event', Optional[Submission], Submission], bool]
Callback = Callable[['Event', Optional[Submission], Submission], Events]
Decorator = Callable[[Callable], Callable]
Rule = Tuple[Condition, Callback]
Store = Callable[['Event', Optional[Submission], Submission],
                 Tuple['Event', Submission]]


class EventType(type):
    """Metaclass for :class:`.Event`\."""


@dataclass()
class Event(metaclass=EventType):
    """
    Base class for submission-related events/commands.

    An event represents a change to a :class:`.domain.submission.Submission`.
    Rather than changing submissions directly, an application should create
    (and store) events. Each event class must inherit from this base class,
    extend it with whatever data is needed for the event, and define methods
    for validation and projection (changing a submission):

    - ``validate(self, submission: Submission) -> None`` should raise
      :class:`.InvalidEvent` if the event instance has invalid data.
    - ``project(self, submission: Submission) -> Submission`` should perform
      changes to the :class:`.domain.submission.Submission` and return it.

    An event class also provides a hook for doing things automatically when the
    submission changes. To register a function that gets called when an event
    is committed, use the :func:`bind` method.
    """

    NAME = 'base event'
    NAMED = 'base event'

    creator: Agent
    """
    The agent responsible for the operation represented by this event.

    This is **not** necessarily the creator of the submission.
    """

    created: Optional[datetime] = field(default=None)   # get_tzaware_utc_now
    """The timestamp when the event was originally committed."""

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

    event_type: str = field(default_factory=str)
    event_version: str = field(default_factory=str)

    _hooks: ClassVar[Mapping[type, List[Rule]]] = defaultdict(list)

    def __post_init__(self) -> None:
        """Make sure data look right."""
        self.event_type = self.get_event_type()
        self.event_version = self.get_event_version()
        if self.client and isinstance(self.client, dict):
            self.client = agent_factory(**self.client)
        if self.creator and isinstance(self.creator, dict):
            self.creator = agent_factory(**self.creator)
        if self.proxy and isinstance(self.proxy, dict):
            self.proxy = agent_factory(**self.proxy)
        if self.before and isinstance(self.before, dict):
            self.before = Submission(**self.before)
        if self.after and isinstance(self.after, dict):
            self.after = Submission(**self.after)

    @staticmethod
    def get_event_version() -> str:
        return str(get_application_config().get('CORE_VERSION', '0.0.0'))

    @classmethod
    def get_event_type(cls) -> str:
        """Get the name of the event type."""
        return cls.__name__

    @property
    def event_id(self) -> str:
        """Unique ID for this event."""
        if not self.created:
            raise RuntimeError('Event not yet committed')
        return self.get_id(self.created, self.event_type, self.creator)

    @staticmethod
    def get_id(created: datetime, event_type: str, creator: Agent) -> str:
        h = hashlib.new('sha1')
        h.update(b'%s:%s:%s' % (created.isoformat().encode('utf-8'),
                                event_type.encode('utf-8'),
                                creator.agent_identifier.encode('utf-8')))
        return h.hexdigest()

    def apply(self, submission: Optional[Submission] = None) -> Submission:
        """Apply the projection for this :class:`.Event` instance."""
        self.before = copy.deepcopy(submission)
        # See comment on CreateSubmission, below.
        self.validate(submission)    # type: ignore
        if submission is not None:
            self.after = self.project(copy.deepcopy(submission))
        else:   # See comment on CreateSubmission, below.
            self.after = self.project(None)    # type: ignore
        assert self.after is not None
        self.after.updated = self.created

        # Make sure that the submission has its own ID, if we know what it is.
        if self.after.submission_id is None and self.submission_id is not None:
            self.after.submission_id = self.submission_id
        if self.submission_id is None and self.after.submission_id is not None:
            self.submission_id = self.after.submission_id
        return self.after

    @classmethod
    def bind(cls, condition: Optional[Condition] = None) -> Decorator:
        """
        Generate a decorator to bind a callback to an event type.

        To register a function that will be called whenever an event is
        committed, decorate it like so:

        .. code-block:: python

           @MyEvent.bind()
           def say_hello(event: MyEvent, before: Submission,
                         after: Submission) -> Iterable[Event]:
               yield SomeOtherEvent(...)

        The callback function will be passed the event that triggered it, the
        state of the submission before and after the triggering event was
        applied, and a :class:`.System` agent that can be used as the creator
        of subsequent events. It should return an iterable of other
        :class:`.Event` instances, either by yielding them, or by
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
                      after: Submission) -> Iterable[Event]:
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
            def _creator_is_not_system(e: Event, *ar: Any, **kw: Any) -> bool:
                return type(e.creator) is not System
            condition = _creator_is_not_system

        def decorator(func: Callback) -> Callback:
            """Register a callback for an event type and condition."""
            name = f'{cls.__name__}::{func.__module__}.{func.__name__}'
            sys = System(name)
            setattr(func, '__name__', name)

            @wraps(func)
            def do(event: Event, before: Submission, after: Submission,
                   creator: Agent = sys, **kwargs: Any) -> Iterable['Event']:
                """Perform the callback. Here in case we need to hook in."""
                return func(event, before, after)

            assert condition is not None
            cls._add_callback(condition, do)
            return do
        return decorator

    @classmethod
    def _add_callback(cls: Type['Event'], condition: Condition,
                      callback: Callback) -> None:
        cls._hooks[cls].append((condition, callback))

    def _get_callbacks(self) -> Iterable[Tuple[Condition, Callback]]:
        return ((condition, callback) for cls in type(self).__mro__[::-1]
                for condition, callback in self._hooks[cls])

    def _should_apply_callbacks(self) -> bool:
        config = get_application_config()
        return bool(int(config.get('ENABLE_CALLBACKS', '0')))

    def validate(self, submission: Submission) -> None:
        """Validate this event and its data against a submission."""
        raise NotImplementedError('Must be implemented by subclass')

    def project(self, submission: Submission) -> Submission:
        """Apply this event and its data to a submission."""
        raise NotImplementedError('Must be implemented by subclass')

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
        assert self.after is not None
        _, after = store(self, self.before, self.after)
        self.committed = True
        if not self._should_apply_callbacks():
            return self.after, []
        consequences: List[Event] = []
        for condition, callback in self._get_callbacks():
            assert self.after is not None
            if condition(self, self.before, self.after):
                for consequence in callback(self, self.before, self.after):
                    consequence.created = datetime.now(UTC)
                    self.after = consequence.apply(self.after)
                    consequences.append(consequence)
                    self.after, addl_consequences = consequence.commit(store)
                    for addl in addl_consequences:
                        consequences.append(addl)
        assert self.after is not None
        return self.after, consequences


def _get_subclasses(klass: Type[Event]) -> List[Type[Event]]:
    _subclasses = klass.__subclasses__()
    if _subclasses:
        return _subclasses + [sub for klass in _subclasses
                              for sub in _get_subclasses(klass)]
    return _subclasses


def event_factory(event_type: str, created: datetime, **data: Any) -> Event:
    """
    Generate an :class:`Event` instance from raw :const:`EventData`.

    Parameters
    ----------
    event_type : str
        Should be the name of a :class:`.Event` subclass.
    data : kwargs
        Keyword parameters passed to the event constructor.

    Returns
    -------
    :class:`.Event`
        An instance of an :class:`.Event` subclass.

    """
    etypes = {klas.get_event_type(): klas for klas in _get_subclasses(Event)}
    # TODO: typing on version_data is not very good right now. This is not an
    # error, but we have two competing ways of using the data that gets passed
    # in that need to be reconciled.
    version_data: EventData = data   # type: ignore
    version_data.update({'event_type': event_type})
    data = map_to_current_version(version_data)    # type: ignore
    event_version = data.pop("event_version", None)
    data['created'] = created
    if event_type in etypes:
        # Mypy gives a spurious 'Too many arguments for "Event"'.
        return etypes[event_type](**data)    # type: ignore
    raise RuntimeError('Unknown event type: %s' % event_type)
