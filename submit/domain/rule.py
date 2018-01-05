"""Conditional business logic as data."""

from datetime import datetime
from typing import Callable, TypeVar
from submit.domain.agent import Agent, System
from submit.domain.event import Event, event_factory
from submit.domain.submission import Submission
from submit.domain.data import Data, Property


EventRuleType = TypeVar('EventRuleType', bound='EventRule')


class RuleCondition(Data):
    """Evaluate whether or not the rule applies to an event."""

    def __call__(self, submission: Submission, event: Event) -> bool:
        """Evaluate whether or not the rule applies to an event."""
        return self.event_type == event.event_type and \
            self._callable_from_condition(submission, event) \
            and (self.submission_id is None
                 or self.submission_id == submission.submission_id)

    submission_id = Property('submission_id', int, null=True)
    event_type = Property('event_type', str)
    extra_condition = Property('extra_condition', dict, null=True)

    # TODO: implement some kind of DSL for evaluating submission state.
    @property
    def _callable_from_condition(self) -> Callable:
        return lambda sub, event: True


class RuleConsequence(Data):
    """Generate a new event as a result of the rule."""

    def __call__(self, submission: Submission, event: Event) -> Event:
        """Generate a new event as a result of the rule."""
        self.event_data.update({'created': datetime.now()})
        new_event = event_factory(self.event_type, **self.event_data)
        if new_event.submission_id is None:
            new_event.submission_id = submission.submission_id
        if new_event.creator is None:
            new_event.creator = self.event_creator
        return new_event

    event_creator = Property('creator', Agent, System())
    """The agent responsible for the consequent event."""

    event_type = Property('event_type', str)
    """The type of event to apply when the rule is triggered."""
    event_data = Property('event_data', dict)
    """Data for the event applied when the rule is triggered."""


class EventRule(Data):
    """Expresses conditional business logic to generate automated events."""

    rule_id = Property('rule_id', int, null=True)
    creator = Property('creator', Agent)
    created = Property('created', datetime)

    applied = Property('applied', bool, False)
    """Whether or not the rule has already been triggered and applied."""

    condition = Property('condition', RuleCondition)
    consequence = Property('consequence', RuleConsequence)
