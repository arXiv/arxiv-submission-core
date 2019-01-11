from collections import defaultdict
from functools import wraps
from typing import Callable, List, Dict, Mapping, Tuple, Iterable, Optional

from ..domain.submission import Submission, SubmissionMetadata, Author
from ..domain.agent import Agent, User, System, Client
from ..domain.event import Event

from .generic import true
from .celery import execute_async

from arxiv.base.globals import get_application_config

Events = Iterable[Event]
Condition = Callable[[Event, Submission, Submission], bool]
Callback = Callable[[Event, Submission, Submission, Agent], Events]
Decorator = Callable[[Callable], Callable]
Rule = Tuple[Condition, Callback]

BINDINGS: Mapping[type, List[Rule]] = defaultdict(list)
CALLBACKS: Mapping[str, Callback] = {}

save: Callable = lambda *a: None


def set_save_func(func: Callable) -> None:
    save = func


def name_for_callback(event_type: type, func: Callable) -> str:
    return f'{event_type.__name__}::{func.__module__}.{func.__name__}'


def bind_event(event_type: type, condition: Condition = true,
               is_async: bool = False) -> Decorator:
    """
    Generate a decorator to bind a callback to an event type.

    Parameters
    ----------
    event_type : :class:`type`
        The event class to which the callback should be bound.
    condition : Callable
        A callable with the signature
        ``(event: Event, before: Submission, after: Submission) -> bool``.
        If this callable returns ``True``, the callback will be triggered when
        the event to which it is bound is saved.
    is_async : bool
        If ``True``, the callback will be executed and its results will be
        applied/stored asynchronously. If ``False``, the callback will be
        executed and its results will be applied and stored immediately.

    Returns
    -------
    Callable
        Decorator for a callback function, with signature
        ``(event: Event, before: Submission, after: Submission, creator: Agent
        = system) -> Iterable[Event]``.

    """
    def decorator(func: Callback) -> Callback:
        """Register a callback for an event type and condition."""
        callback_name = name_for_callback(event_type, func)
        system = System(f'{__name__}::{callback_name}')

        @wraps(func)
        def do(event: Event, before: Submission, after: Submission,
               creator: Agent = system) -> Events:
            """Perform the callback. Here in case we need to hook in."""
            return func(event, before, after, creator)

        CALLBACKS[callback_name] = do
        BINDINGS[event_type].append((condition, callback_name, is_async))
        return do
    return decorator


def apply(event: Event, before: Submission, after: Submission) -> Tuple[Submission, Events]:
    consequent_events: List[Event] = []
    for condition, callback_name, is_async in BINDINGS[type(event)]:
        print('callback_name', callback_name)
        if condition(event, before, after):
            print('do')
            if is_async:
                print('is_async')
                execute_async('execute_callback',
                              callback_name, event, before, after)
                # execute_callback.delay(callback_name, event, before, after)
                return after, []
            callback = CALLBACKS[callback_name]
            for consequent_event in callback(event, before, after):
                consequent_events.append(consequent_event)
    if consequent_events:
        after, consequent_events = save(*consequent_events,
                                        submission_id=after.submission_id)
    return after, consequent_events


def should_apply_rules() -> bool:
    return bool(int(get_application_config().get('APPLY_RULES', 1)))


def execute_callback(callback_name: str, event: Event, before: Submission,
                     after: Submission) -> None:
    save(*CALLBACKS[callback_name](event, before, after))
