"""Status information for external or long-running processes."""

from typing import Optional
from enum import Enum
from datetime import datetime

from dataclasses import dataclass, field

from .agent import Agent
from .util import get_tzaware_utc_now


@dataclass
class ProcessStatus:
    """Represents the status of a long-running remote process."""

    class Status(Enum):
        """Supported statuses."""

        REQUESTED = "requested"
        SUCCEEDED = "succeeded"
        FAILED = "failed"

    class Process(Enum):
        """Supported processes."""

        NONE = None
        COMPILATION = 'compilation'
        PLAIN_TEXT_EXTRACTION = 'plaintext'
        CLASSIFICATION = 'classification'
        OVERLAP_DETECTION = 'overlap'

    creator: Agent
    created: datetime
    """Time when the process status was created (not the process itself)."""
    process: Process
    status: Status = field(default=Status.REQUESTED)
    process_service: Optional[str] = field(default=None)
    """The service running the process."""
    process_version: Optional[str] = field(default=None)
    """The version of the service running the process."""
    process_identifier: Optional[str] = field(default=None)
    """Unique identifier in the context of the service running the process."""
    reason: Optional[str] = field(default=None)
    """Optional context or explanatory details related to the status."""
    monitoring_task: Optional[str] = field(default=None)
    """identifier of the task used to monitor the status of this process."""
