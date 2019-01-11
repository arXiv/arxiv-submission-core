
from ..domain.event import Event
from ..domain.submission import Submission
from ..domain.agent import Agent, User, System


def system_event(event: Event, before: Submission, after: Submission) -> bool:
    return type(event.creator) is System


def true(event: Event, before: Submission, after: Submission) -> bool:
    return True
