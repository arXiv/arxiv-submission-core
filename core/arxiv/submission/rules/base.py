from collections import defaultdict
from functools import wraps
from typing import Callable, List, Dict, Mapping, Tuple, Iterable, Optional

from ..domain.submission import Submission, SubmissionMetadata, Author
from ..domain.agent import Agent, User, System, Client
from ..domain.event import Event

from .generic import true
from .tasks import execute_async, register_async

from arxiv.base.globals import get_application_config

Events = Iterable[Event]
Condition = Callable[[Event, Submission, Submission], bool]
Callback = Callable[[Event, Submission, Submission, Agent], Events]
Decorator = Callable[[Callable], Callable]
Rule = Tuple[Condition, Callback]

BINDINGS: Mapping[type, List[Rule]] = defaultdict(list)
CALLBACKS: Mapping[str, Callback] = {}




def apply(event: Event, before: Submission, after: Submission) -> Tuple[Submission, Events]:
    consequent_events: List[Event] = []
    for condition, callback_name, is_async in BINDINGS[type(event)]:
        print('callback_name', callback_name)
        if condition(event, before, after):
            print('do')
            if is_async:
                print('is_async')
                execute_async(callback_name, event, before, after)
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
