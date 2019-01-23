"""Events related to external or long-running processes."""

from typing import Optional

from dataclasses import field

from ...exceptions import InvalidEvent
from ..submission import Submission
from ..process import ProcessStatus
from .event import Event
from .util import dataclass


@dataclass()
class AddProcessStatus(Event):
    """Add the status of an external/long-running process to a submission."""

    Statuses = ProcessStatus.Statuses
    Processes = ProcessStatus.Processes

    status: Statuses = field(default=Statuses.REQUESTED)
    process: Processes = field(default=Processes.NONE)
    service: Optional[str] = field(default=None)
    version: Optional[str] = field(default=None)
    identifier: Optional[str] = field(default=None)
    reason: Optional[str] = field(default=None)

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
            status=self.status,
            process_service=self.service,
            process_version=self.version,
            process_identifier=self.identifier,
            reason=self.reason
        ))
        return submission
