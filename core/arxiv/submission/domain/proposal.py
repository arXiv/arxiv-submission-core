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

from arxiv.taxonomy import Category

from .annotation import Comment
from .util import get_tzaware_utc_now
from .agent import Agent


@dataclass
class Proposal:
    """Represents a proposal to apply an event to a submission."""

    PENDING = 'pending'
    REJECTED = 'rejected'
    ACCEPTED = 'accepted'

    creator: Agent
    created: datetime = field(default_factory=get_tzaware_utc_now)
    # scope: str      # TODO: document this.
    proxy: Optional[Agent] = field(default=None)

    proposed_event_type: Optional[type] = field(default=None)
    proposed_event_data: dict = field(default_factory=dict)
    comments: List[Comment] = field(default_factory=list)
    status: str = field(default=PENDING)

    @property
    def proposal_type(self) -> str:
        """Name (str) of the type of annotation."""
        return self.proposed_event_type.__name__

    @property
    def proposal_id(self) -> str:
        """The unique identifier for a :class:`.Proposal` instance."""
        h = hashlib.new('sha1')
        h.update(b'%s:%s:%s' % (self.created.isoformat().encode('utf-8'),
                                self.proposal_type.encode('utf-8'),
                                self.creator.agent_identifier.encode('utf-8')))
        return h.hexdigest()

    def to_dict(self) -> dict:
        """Generate a dict representation of this :class:`.Proposal`."""
        data = asdict(self)
        data['proposal_type'] = self.proposal_type
        data['proposal_id'] = self.proposal_id
        return data

    def is_rejected(self):
        return self.status == self.REJECTED

    def is_accepted(self):
        return self.status == self.ACCEPTED

    def is_pending(self):
        return self.status == self.PENDING
