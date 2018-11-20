"""
Conditional business logic as data.

This is here for demonstration purposes only, and is likely to change
substantially in the short term.
"""

from datetime import datetime
from typing import Callable, TypeVar, Optional
from pytz import UTC
from dataclasses import dataclass, field
from dataclasses import asdict

from .agent import Agent, System
from .event import Event, event_factory
from .submission import Submission
from .util import get_tzaware_utc_now


EventRuleType = TypeVar('EventRuleType', bound='EventRule')


@dataclass
class RuleCondition:
    """Evaluate whether or not the rule applies to an event."""

    event_type: type
    submission_id: Optional[int] = None
    extra_condition: Optional[dict] = None

    def __call__(self, submission: Submission, event: Event) -> bool:
        """Evaluate whether or not the rule applies to an event."""
        return type(event) is self.event_type and \
            self._callable_from_condition(submission, event) \
            and (self.submission_id is None
                 or self.submission_id == submission.submission_id)

    # TODO: implement some kind of DSL for evaluating submission state?
    @property
    def _callable_from_condition(self) -> Callable:
        return lambda sub, event: True


@dataclass
class RuleConsequence:
    """Generate a new event as a result of the rule."""

    event_type: type
    """The type of event to apply when the rule is triggered."""
    event_data: dict
    """Data for the event applied when the rule is triggered."""

    event_creator: Agent = field(default_factory=System)
    """The agent responsible for the consequent event."""

    def __call__(self, submission: Submission, event: Event) -> Event:
        """Generate a new event as a result of the rule."""
        data = {    # These are effectively defaults.
            'creator': self.event_creator,
            'proxy': None,
            'submission_id': submission.submission_id
        }
        data.update(self.event_data)
        data['created'] = datetime.now(UTC)
        # new_event = event_factory(self.event_type, **data)
        new_event = self.event_type(**data)
        if new_event.submission_id is None:
            new_event.submission_id = submission.submission_id
        if new_event.creator is None:
            new_event.creator = self.event_creator
        return new_event


@dataclass
class EventRule:
    """Expresses conditional business logic to generate automated events."""

    creator: Agent
    condition: RuleCondition
    consequence: RuleConsequence
    rule_id: Optional[int] = None
    proxy: Optional[Agent] = None
    created: datetime = field(default_factory=get_tzaware_utc_now)
    applied: bool = False
    """Whether or not the rule has already been triggered and applied."""
