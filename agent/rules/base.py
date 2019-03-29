from typing import Mapping, List, Callable, Dict, Any
from collections import defaultdict
from dataclasses import dataclass

from arxiv.submission.domain import Submission
from arxiv.submission.domain.event import Event, EventType
from ..process import ProcessType

Condition = Callable[[Event, Submission, Submission], bool]
ParamFunc = Callable[[Event, Submission, Submission], Dict[str, Any]]

REGISTRY: Mapping[EventType, List['Rule']] = defaultdict(list)


@dataclass
class Rule:
    event_type: EventType
    condition: Condition
    params: ParamFunc
    process: ProcessType
    name: str

    def __post_init__(self):
        """Register this instance."""
        REGISTRY[self.event_type].append(self)
