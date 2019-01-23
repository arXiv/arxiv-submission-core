"""
Proposals provide a mechanism for suggesting changes to submissions.

The primary use-case in the classic submission & moderation system is for
suggesting changes to the primary or cross-list classification. Such proposals
are generated both automatically based on the results of the classifier and
manually by moderators.
"""

from typing import Optional, Union, List
from datetime import datetime
import hashlib

from dataclasses import dataclass, asdict, field
from enum import Enum

from arxiv.taxonomy import Category

from .annotation import Comment
from .util import get_tzaware_utc_now
from .agent import Agent


@dataclass
class Proposal:
    """Represents a proposal to apply an event to a submission."""

    class Status(Enum):
        PENDING = 'pending'
        REJECTED = 'rejected'
        ACCEPTED = 'accepted'

    event_id: str
    creator: Agent
    created: datetime = field(default_factory=get_tzaware_utc_now)
    # scope: str      # TODO: document this.
    proxy: Optional[Agent] = field(default=None)

    proposed_event_type: Optional[type] = field(default=None)
    proposed_event_data: dict = field(default_factory=dict)
    comments: List[Comment] = field(default_factory=list)
    status: Status = field(default=Status.PENDING)

    @property
    def proposal_type(self) -> str:
        """Name (str) of the type of annotation."""
        return self.proposed_event_type.__name__

    def to_dict(self) -> dict:
        """Generate a dict representation of this :class:`.Proposal`."""
        data = asdict(self)
        data['proposal_type'] = self.proposal_type
        return data

    def is_rejected(self):
        return self.status == self.Status.REJECTED

    def is_accepted(self):
        return self.status == self.Status.ACCEPTED

    def is_pending(self):
        return self.status == self.Status.PENDING
