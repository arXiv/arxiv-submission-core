from typing import Callable, List, Dict, Mapping, Tuple, Iterable, Optional
from functools import wraps
from collectionts import defaultdict

from .domain.event import Event
from .domain.submission import Submission
from .domain.agent import Agent, User, System

Events = Iterable[Event]
Condition = Callable[[Event, Submission, Submission], bool]
Callback = Callable[[Event, Submission, Submission, Agent], Events]
Decorator = Callable[[Callable], Callable]
Rule = Tuple[Condition, Callback]


BINDINGS: Mapping[type, List[Rule]] = defaultdict(list)


def true(event: Event, before: Submission, after: Submission) -> bool:
    return True


def bind_event(event_type: type, condition: Condition = true) -> Decorator:
    def decorator(func: Callback) -> Callback:
        system = System(f'{__name__}::{func.__module__}.{func.__name__}')

        @wraps(func)
        def do(event: Event, before: Submission, after: Submission) -> Events:
            func(event, before, after, system)

        BINDINGS[event_type].append((condition, do))
        return do
    return decorator


def get_bound_functions(event: Event, before: Submission, after: Submission) \
        -> Iterable[Callback]:
    return (f for c, f in BINDINGS[type(event)] if c(event, before, after))


def apply_rules(event: Event, before: Submission, after: Submission) -> Events:
    return (event
            for callback in get_bound_functions(event, before, after)
            for event in callback(event, before, after))
