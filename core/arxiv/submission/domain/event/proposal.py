"""Commands for working with :class:`.Proposal` instances on submissions."""

import hashlib
import re
import copy
from datetime import datetime
from pytz import UTC
from typing import Optional, TypeVar, List, Tuple, Any, Dict, Iterable
from urllib.parse import urlparse
from dataclasses import field, asdict
from .util import dataclass
import bleach

from arxiv.util import schema
from arxiv import taxonomy
from arxiv.base import logging

from ..agent import Agent
from ..submission import Submission, SubmissionMetadata, Author, \
    Classification, License, Delegation,  \
    SubmissionContent, WithdrawalRequest, CrossListClassificationRequest
from ..proposal import Proposal
from ..annotation import Comment

from ...exceptions import InvalidEvent
from ..util import get_tzaware_utc_now
from .base import Event
from .request import RequestCrossList, RequestWithdrawal, ApplyRequest, \
    RejectRequest, ApproveRequest
from . import validators

logger = logging.getLogger(__name__)


@dataclass()
class AddProposal(Event):
    """Add a new proposal to a :class:`Submission`."""

    NAME = 'add proposal'
    NAMED = 'proposal added'

    proposed_event_type: Optional[type] = field(default=None)
    proposed_event_data: dict = field(default_factory=dict)
    comment: Optional[str] = field(default=None)

    def validate(self, submission: Submission) -> None:
        """Simulate applying the proposal to check for validity."""
        if self.proposed_event_type is None:
            raise InvalidEvent(self, f"Proposed event type is required")
        proposed_event_data = copy.deepcopy(self.proposed_event_data)
        proposed_event_data.update({'creator': self.creator})
        event = self.proposed_event_type(**proposed_event_data)
        event.validate(submission)

    def project(self, submission: Submission) -> Submission:
        """Add the proposal to the submission."""
        assert self.created is not None
        submission.proposals[self.event_id] = Proposal(
            event_id=self.event_id,
            creator=self.creator,
            created=self.created,
            proxy=self.proxy,
            proposed_event_type=self.proposed_event_type,
            proposed_event_data=self.proposed_event_data,
            comments=[Comment(event_id=self.event_id, creator=self.creator,
                              created=self.created, proxy=self.proxy,
                              body=self.comment or '')],
            status=Proposal.Status.PENDING
        )
        return submission


@dataclass()
class RejectProposal(Event):
    """Reject a :class:`.Proposal` on a submission."""

    NAME = 'reject proposal'
    NAMED = 'proposal rejected'

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
        assert self.proposal_id is not None
        assert self.created is not None
        submission.proposals[self.proposal_id].status = Proposal.Status.REJECTED
        if self.comment:
            submission.proposals[self.proposal_id].comments.append(
                Comment(event_id=self.event_id, creator=self.creator,
                        created=self.created, proxy=self.proxy,
                        body=self.comment))
        return submission


@dataclass()
class AcceptProposal(Event):
    """Accept a :class:`.Proposal` on a submission."""

    NAME = 'accept proposal'
    NAMED = 'proposal accepted'

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
        """Mark the proposal as accepted."""
        assert self.created is not None
        assert self.proposal_id is not None
        submission.proposals[self.proposal_id].status \
            = Proposal.Status.ACCEPTED
        if self.comment:
            submission.proposals[self.proposal_id].comments.append(
                Comment(event_id=self.event_id, creator=self.creator,
                        created=self.created, proxy=self.proxy,
                        body=self.comment))
        return submission


@AcceptProposal.bind()
def apply_proposal(event: AcceptProposal, before: Submission,
                   after: Submission, creator: Agent) -> Iterable[Event]:
    """Apply an accepted proposal."""
    assert event.proposal_id is not None
    proposal = after.proposals[event.proposal_id]
    proposed_event_data = copy.deepcopy(proposal.proposed_event_data)
    proposed_event_data.update({'creator': creator})

    assert proposal.proposed_event_type is not None
    event = proposal.proposed_event_type(**proposed_event_data)
    yield event
