"""Status information for external or long-running processes."""

from typing import Optional
from enum import Enum
from datetime import datetime

from dataclasses import dataclass, field, asdict

from .agent import Agent, agent_factory
from .util import get_tzaware_utc_now


@dataclass
class ProcessStatus:
    """Represents the status of a long-running remote process."""

    class Status(Enum):
        """Supported statuses."""

        PENDING = 'pending'
        """The process is waiting to start."""
        IN_PROGRESS = 'in_progress'
        """Process has started, and is running remotely."""
        FAILED_TO_START = 'failed_to_start'
        """Could not start the process."""
        FAILED = 'failed'
        """The process failed while running."""
        FAILED_TO_END = 'failed_to_end'
        """The process ran, but failed to end gracefully."""
        SUCCEEDED = 'succeeded'
        """The process ended successfully."""
        TERMINATED = 'terminated'
        """The process was terminated, e.g. cancelled by operator."""

    creator: Agent
    created: datetime
    """Time when the process status was created (not the process itself)."""
    process: str
    step: Optional[str] = field(default=None)
    status: Status = field(default=Status.PENDING)
    reason: Optional[str] = field(default=None)
    """Optional context or explanatory details related to the status."""

    def __post_init__(self):
        """Check our enums and agents."""
        if self.creator and type(self.creator) is dict:
            self.creator = agent_factory(**self.creator)
        self.status = self.Status(self.status)
