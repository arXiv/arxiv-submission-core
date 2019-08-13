"""Provides the core representation of a rule."""

from typing import Mapping, List, Callable, Dict, Any
from collections import defaultdict
from dataclasses import dataclass

from arxiv.submission.domain import Submission
from arxiv.submission.domain.event import Event, EventType
from ..process import ProcessType

Condition = Callable[[Event, Submission, Submission], bool]
ParamFunc = Callable[[Event, Submission, Submission], Dict[str, Any]]

REGISTRY: Mapping[EventType, List['Rule']] = defaultdict(list)
"""
Registry for :class:`.Rule` instances.

We keep a reference here so that we can easily look up all rules that apply
to a particular event type.
"""


@dataclass
class Rule:
    """
    Represents an event rule for a process.

    A **rule** defines the circumstances under which a process should be
    carried out. Specifically, a rule is associated with a particular type of
    event, and a function that determines whether the process should be carried
    out based on the event properties and/or the state of the submission.
    """

    event_type: EventType
    """The event type (class) on which the rule should be evaluated."""

    condition: Condition
    """
    Conditions under which to run :attr:`.process`.

    This is a function that evaluates the event, and the state of the
    submission prior to and after the event. It is only called for an event of
    type :attr:`.event_type`. If the function returns True, then
    :attr:`.process` should be carried out.
    """

    params: ParamFunc
    """
    Provides the runtime configuration parameters for :attr:`.process`.

    This is a function that evaluates the event, and the state of the
    submission prior to and after the event, and returns a dict of
    configuration parameters. Those parameters are passed to the process when
    it is run.
    """

    process: ProcessType
    """
    The process (class) to carry out.

    This should be carried out iff :attr:`.event_type` and :attr:`.condition`
    are satisfied.
    """

    name: str
    """The name of the process."""

    def __post_init__(self) -> None:
        """Register this instance."""
        REGISTRY[self.event_type].append(self)
