from typing import Any, Optional, List, Dict
from dataclasses import dataclass, field

from arxiv.submission.domain.submission import Submission
from arxiv.submission.domain.event import Event, event_factory
from arxiv.submission.domain.agent import Agent, agent_factory


@dataclass
class Trigger:
    """
    Represents a trigger for a process.

    This will usually be an :class:`.Event`, but may also be directly triggered
    by an actor (e.g. manually starting a process via an UI).
    """

    event: Optional[Event] = field(default=None)
    """The event (if any) that triggered the process."""
    before: Optional[Submission] = field(default=None)
    """The state of the submission prior to the :attr:`.event` (if any)."""
    after: Optional[Submission] = field(default=None)
    """
    The state of the submission after to the :attr:`.event` (if any).

    If the process was triggered directly by an :attr:`.actor`, this should
    be the state of the submission at the time the process was triggered.
    """
    actor: Optional[Agent] = field(default=None)
    """The actor (if any) responsible for starting the process directly."""
    params: Dict[str, Any] = field(default_factory=dict)
    """Configuration parameters for the process."""

    def __post_init__(self) -> None:
        """Make sure that all refs are domain objects."""
        if self.event and not isinstance(self.event, Event):
            self.event = event_factory(**self.event)
        if self.before and not isinstance(self.before, Submission):
            self.before = Submission(**self.before)
        if self.after and not isinstance(self.after, Submission):
            self.after = Submission(**self.after)
        if self.actor and not isinstance(self.actor, Agent):
            self.actor = agent_factory(**self.actor)


@dataclass
class ProcessData:
    """
    Represents data associated with a (possibly multi-step) process.

    As steps are completed, their return values are appended to
    :attr:`.results`.
    """

    submission_id: int
    """Identifier of the submission upon which the process is operating."""

    process_id: str
    """Unique identifier of a specific process instance."""

    trigger: Trigger
    """The original trigger condition for the process."""

    results: List[Any]
    """The results of each step in the process, in order."""

    def __post_init__(self):
        """Make sure that all refs are domain objects."""
        if not isinstance(self.trigger, Trigger):
            self.trigger = Trigger(**self.trigger)

    def get_last_result(self) -> Any:
        """Get the result of the most recent successful step."""
        return self.results[-1]

    def add_result(self, result: Any) -> None:
        """Add a result from a successful step."""
        self.results.append(result)
