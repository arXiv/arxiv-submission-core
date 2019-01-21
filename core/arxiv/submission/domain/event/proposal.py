"""Commands for working with :class:`.Proposal`s on submissions."""

import hashlib
import re
import copy
from datetime import datetime
from pytz import UTC
from typing import Optional, TypeVar, List, Tuple, Any, Dict
from urllib.parse import urlparse
from dataclasses import field, asdict
from .util import dataclass
import bleach

from arxiv.util import schema
from arxiv import taxonomy, identifier
from arxiv.base import logging

from ..agent import Agent
from ..submission import Submission, SubmissionMetadata, Author, \
    Classification, License, Delegation,  \
    SubmissionContent, WithdrawalRequest, CrossListClassificationRequest
from ..proposal import Proposal
from ..annotation import Comment

from ...exceptions import InvalidEvent
from ..util import get_tzaware_utc_now
from .event import Event
from .request import RequestCrossList, RequestWithdrawal, ApplyRequest, \
    RejectRequest, ApproveRequest
from . import validators

logger = logging.getLogger(__name__)


@dataclass()
class AddProposal(Event):
    """Add a new proposal to a :class:`Submission`."""

    proposal: Optional[Proposal] = field(default=None)
    # proposed_event_type: Optional[type] = field(default=None)
    # proposed_event_data: dict = field(default_factory=dict)
    # comment: str = field(default_factory=str)

    def validate(self, submission: Submission) -> None:
        """Simulate applying the proposal to check for validity."""
        if self.proposal is None:
            raise InvalidEvent(self, f"Proposal is required")
        if self.proposal.proposed_event_type is None:
            raise InvalidEvent(self, f"Event type is required")
        proposed_event_data = copy.deepcopy(self.proposal.proposed_event_data)
        proposed_event_data.update({'creator': self.creator})
        event = self.proposal.proposed_event_type(**proposed_event_data)
        event.validate(submission)

    def project(self, submission: Submission) -> Submission:
        """Add the proposal to the submission."""
        submission.proposals[self.proposal.proposal_id] = self.proposal
        return submission


@dataclass()
class RejectProposal(Event):
    """Reject a :class:`.Proposal` on a submission."""

    proposal_id: Optional[str] = field(default=None)
    comment: Optional[str] = field(default=None)

    def validate(self, submission: Submission) -> None:
        """Ensure that the proposal isn't already approved or rejected."""
        if self.proposal_id not in submission.proposals:
            raise InvalidEvent(self, f"No such proposal {self.proposal_id}")
        elif submission.proposals[self.proposal_id].is_rejected():
            raise InvalidEvent(self, f"{self.proposal_id} is already rejected")
        elif submission.proposals[self.proposal_id].is_accepted():
            raise InvalidEvent(self, f"{self.proposal_id} is accepted")

    def project(self, submission: Submission) -> Submission:
        """Set the status of the proposal to rejected."""
        submission.proposals[self.proposal_id].status = Proposal.REJECTED
        if self.comment:
            submission.proposals[self.proposal_id].comments.append(
                Comment(creator=self.creator, proxy=self.proxy,
                        body=self.comment)
            )
        return submission


@dataclass()
class AcceptProposal(Event):
    """Accept a :class:`.Proposal` on a submission."""

    proposal_id: Optional[str] = field(default=None)
    comment: Optional[str] = field(default=None)

    def validate(self, submission: Submission) -> None:
        """Ensure that the proposal isn't already approved or rejected."""
        if self.proposal_id not in submission.proposals:
            raise InvalidEvent(self, f"No such proposal {self.proposal_id}")
        elif submission.proposals[self.proposal_id].is_rejected():
            raise InvalidEvent(self, f"{self.proposal_id} is rejected")
        elif submission.proposals[self.proposal_id].is_accepted():
            raise InvalidEvent(self, f"{self.proposal_id} is already accepted")

    def project(self, submission: Submission) -> Submission:
        """Apply the proposed event to the submission."""
        proposal = submission.proposals[self.proposal_id]
        proposed_event_data = copy.deepcopy(proposal.proposed_event_data)
        proposed_event_data.update({'creator': self.creator})
        event = proposal.proposed_event_type(**proposed_event_data)
        submission.proposals[self.proposal_id].status = Proposal.ACCEPTED
        if self.comment:
            submission.proposals[self.proposal_id].comments.append(
                Comment(creator=self.creator, proxy=self.proxy,
                        body=self.comment)
            )
        return submission
