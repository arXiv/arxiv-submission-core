"""Status information for external or long-running processes."""

from typing import Optional
from enum import Enum
from datetime import datetime

from dataclasses import dataclass, field

from .agent import Agent
from .util import get_tzaware_utc_now


@dataclass
class ProcessStatus:
    """Base class for process status information."""

    class Status(Enum):
        """Supported statuses."""

        REQUESTED = "requested"
        SUCCEEDED = "succeeded"
        FAILED = "failed"

    class Process(Enum):
        """Supported processes."""

        NONE = None
        PLAIN_TEXT_EXTRACTION = 'plaintext'
        CLASSIFICATION = 'classification'
        OVERLAP_DETECTION = 'overlap'

    creator: Agent
    created: datetime
    """Time when the process status was created (not the process itself)."""
    process: Process
    status: Status = field(default=Status.REQUESTED)
    process_service: Optional[str] = field(default=None)
    process_version: Optional[str] = field(default=None)
    reason: Optional[str] = field(default=None)
