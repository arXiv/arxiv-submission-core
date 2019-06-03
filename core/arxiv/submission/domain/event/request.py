"""Commands/events related to user requests."""

from typing import Optional, List
import hashlib
from dataclasses import field
from .util import dataclass

from arxiv import taxonomy

from . import validators
from .base import Event
from ..submission import Submission, Classification, WithdrawalRequest, \
    CrossListClassificationRequest, UserRequest
from ...exceptions import InvalidEvent


@dataclass()
class ApproveRequest(Event):
    """Approve a user request."""

    NAME = "approve user request"
    NAMED = "user request approved"

    request_id: Optional[str] = field(default=None)

    def __hash__(self) -> int:
        """Use event ID as object hash."""
        return hash(self.event_id)

    def __eq__(self, other: Event) -> bool:
        """Compare this event to another event."""
        return hash(self) == hash(other)

    def validate(self, submission: Submission) -> None:
        if self.request_id not in submission.user_requests:
            raise InvalidEvent(self, "No such request")

    def project(self, submission: Submission) -> Submission:
        submission.user_requests[self.request_id].status = UserRequest.APPROVED
        return submission


@dataclass()
class RejectRequest(Event):
    NAME = "reject user request"
    NAMED = "user request rejected"

    request_id: Optional[str] = field(default=None)

    def __hash__(self) -> int:
        """Use event ID as object hash."""
        return hash(self.event_id)

    def __eq__(self, other: Event) -> bool:
        """Compare this event to another event."""
        return hash(self) == hash(other)

    def validate(self, submission: Submission) -> None:
        if self.request_id not in submission.user_requests:
            raise InvalidEvent(self, "No such request")

    def project(self, submission: Submission) -> Submission:
        submission.user_requests[self.request_id].status = UserRequest.REJECTED
        return submission


@dataclass()
class CancelRequest(Event):
    NAME = "cancel user request"
    NAMED = "user request cancelled"

    request_id: Optional[str] = field(default=None)

    def __hash__(self) -> int:
        """Use event ID as object hash."""
        return hash(self.event_id)

    def __eq__(self, other: Event) -> bool:
        """Compare this event to another event."""
        return hash(self) == hash(other)

    def validate(self, submission: Submission) -> None:
        if self.request_id not in submission.user_requests:
            raise InvalidEvent(self, "No such request")

    def project(self, submission: Submission) -> Submission:
        submission.user_requests[self.request_id].status = \
            UserRequest.CANCELLED
        return submission


@dataclass()
class ApplyRequest(Event):
    NAME = "apply user request"
    NAMED = "user request applied"

    request_id: Optional[str] = field(default=None)

    def __hash__(self) -> int:
        """Use event ID as object hash."""
        return hash(self.event_id)

    def __eq__(self, other: Event) -> bool:
        """Compare this event to another event."""
        return hash(self) == hash(other)

    def validate(self, submission: Submission) -> None:
        if self.request_id not in submission.user_requests:
            raise InvalidEvent(self, "No such request")

    def project(self, submission: Submission) -> Submission:
        user_request = submission.user_requests[self.request_id]
        if hasattr(user_request, 'apply'):
            submission = user_request.apply(submission)
        user_request.status = UserRequest.APPLIED
        submission.user_requests[self.request_id] = user_request
        return submission


@dataclass()
class RequestCrossList(Event):
    """Request that a secondary classification be added after announcement."""

    NAME = "request cross-list classification"
    NAMED = "cross-list classification requested"

    categories: List[taxonomy.Category] = field(default_factory=list)

    def __hash__(self) -> int:
        """Use event ID as object hash."""
        return hash(self.event_id)

    def __eq__(self, other: Event) -> bool:
        """Compare this event to another event."""
        return hash(self) == hash(other)

    def validate(self, submission: Submission) -> None:
        """Validate the cross-list request."""
        validators.no_active_requests(self, submission)
        if not submission.is_announced:
            raise InvalidEvent(self, "Submission must already be announced")
        for category in self.categories:
            validators.must_be_a_valid_category(self, category, submission)
            validators.cannot_be_primary(self, category, submission)
            validators.cannot_be_secondary(self, category, submission)

    def project(self, submission: Submission) -> Submission:
        """Create a cross-list request."""
        classifications = [
            Classification(category=category) for category in self.categories
        ]

        req_id = CrossListClassificationRequest.generate_request_id(submission)
        user_request = CrossListClassificationRequest(
            request_id=req_id,
            creator=self.creator,
            created=self.created,
            status=WithdrawalRequest.PENDING,
            classifications=classifications
        )
        submission.user_requests[req_id] = user_request
        return submission


@dataclass()
class RequestWithdrawal(Event):
    """Request that a paper be withdrawn."""

    NAME = "request withdrawal"
    NAMED = "withdrawal requested"

    reason: str = field(default_factory=str)

    MAX_LENGTH = 400

    def __hash__(self) -> int:
        """Use event ID as object hash."""
        return hash(self.event_id)

    def __eq__(self, other: Event) -> bool:
        """Compare this event to another event."""
        return hash(self) == hash(other)

    def validate(self, submission: Submission) -> None:
        """Make sure that a reason was provided."""
        validators.no_active_requests(self, submission)
        if not self.reason:
            raise InvalidEvent(self, "Provide a reason for the withdrawal")
        if len(self.reason) > self.MAX_LENGTH:
            raise InvalidEvent(self, "Reason must be 400 characters or less")
        if not submission.is_announced:
            raise InvalidEvent(self, "Submission must already be announced")

    def project(self, submission: Submission) -> Submission:
        """Update the submission status and withdrawal reason."""
        req_id = WithdrawalRequest.generate_request_id(submission)
        user_request = WithdrawalRequest(
            request_id=req_id,
            creator=self.creator,
            created=self.created,
            updated=self.created,
            status=WithdrawalRequest.PENDING,
            reason_for_withdrawal=self.reason
        )
        submission.user_requests[req_id] = user_request
        return submission
