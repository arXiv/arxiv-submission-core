"""Events related to external or long-running processes."""

from typing import Optional

from dataclasses import field

from ...exceptions import InvalidEvent
from ..submission import Submission
from ..process import ProcessStatus
from .base import Event
from .util import dataclass


@dataclass()
class AddProcessStatus(Event):
    """Add the status of an external/long-running process to a submission."""

    NAME = "add status of a process"
    NAMED = "added status of a process"

    Status = ProcessStatus.Status

    process: Optional[str] = field(default=None)
    step: Optional[str] = field(default=None)
    status: Status = field(default=Status.PENDING)
    reason: Optional[str] = field(default=None)

    def __post_init__(self) -> None:
        """Make sure our enums are in order."""
        super(AddProcessStatus, self).__post_init__()
        self.status = self.Status(self.status)

    def validate(self, submission: Submission) -> None:
        """Verify that we have a :class:`.ProcessStatus`."""
        if self.process is None:
            raise InvalidEvent(self, "Must include process")

    def project(self, submission: Submission) -> Submission:
        """Add the process status to the submission."""
        submission.processes.append(ProcessStatus(
            creator=self.creator,
            created=self.created,
            process=self.process,
            step=self.step,
            status=self.status,
            reason=self.reason
        ))
        return submission
