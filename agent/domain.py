from typing import Any, Optional, List, Dict
from dataclasses import dataclass, field

from arxiv.submission.domain.submission import Submission
from arxiv.submission.domain.event import Event
from arxiv.submission.domain.agent import Agent


@dataclass
class Trigger:
    event: Optional[Event] = field(default=None)
    before: Optional[Submission] = field(default=None)
    after: Optional[Submission] = field(default=None)
    actor: Optional[Agent] = field(default=None)
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProcessData:
    submission_id: int
    trigger: Trigger
    results: List[Any]

    def get_last_result(self) -> Any:
        return self.results[-1]

    def add_result(self, result: Any) -> None:
        self.results.append(result)
