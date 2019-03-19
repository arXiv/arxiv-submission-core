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

    NAME = "add status of a process"
    NAMED = "added status of a process"

    Status = ProcessStatus.Status
    Process = ProcessStatus.Process

    status: Status = field(default=Status.REQUESTED)
    process: Process = field(default=Process.NONE)
    service: Optional[str] = field(default=None)
    version: Optional[str] = field(default=None)
    identifier: Optional[str] = field(default=None)
    reason: Optional[str] = field(default=None)
    monitoring_task: Optional[str] = field(default=None)

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
            reason=self.reason,
            monitoring_task=self.monitoring_task
        ))
        return submission

    @classmethod
    def from_dict(cls, **data: dict) -> 'AddProcessStatus':
        if 'process' in data:
            data['process'] = cls.Process(data['process'])
        if 'status' in data:
            data['status'] = cls.Status(data['status'])
        return cls(**data)
