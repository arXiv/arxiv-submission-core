"""Commands/events related to user requests."""

from typing import Optional, List

from dataclasses import dataclass, field

from . import validators
from .event import Event
from ..submission import Submission, Classification, WithdrawalRequest, \
    CrossListClassificationRequest, UserRequest
from ...exceptions import InvalidEvent


@dataclass
class ApproveRequest(Event):
    """Approve a user request."""

    NAME = "approve user request"
    NAMED = "user request approved"

    def __hash__(self):
        """Use event ID as object hash."""
        return hash(self.event_id)

    request_id: Optional[str] = field(default=None)

    def validate(self, submission: Submission) -> None:
        if self.request_id not in submission.user_requests:
            raise InvalidEvent(self, "No such request")

    def project(self, submission: Submission) -> Submission:
        submission.user_requests[self.request_id].status = UserRequest.APPROVED
        return submission


@dataclass
class RejectRequest(Event):
    NAME = "reject user request"
    NAMED = "user request rejected"

    def __hash__(self):
        """Use event ID as object hash."""
        return hash(self.event_id)

    request_id: Optional[str] = field(default=None)

    def validate(self, submission: Submission) -> None:
        if self.request_id not in submission.user_requests:
            raise InvalidEvent(self, "No such request")

    def project(self, submission: Submission) -> Submission:
        submission.user_requests[self.request_id].status = UserRequest.REJECTED
        return submission


@dataclass
class ApplyRequest(Event):
    NAME = "apply user request"
    NAMED = "user request applied"

    def __hash__(self):
        """Use event ID as object hash."""
        return hash(self.event_id)

    request_id: Optional[str] = field(default=None)

    def validate(self, submission: Submission) -> None:
        if self.request_id not in submission.user_requests:
            raise InvalidEvent(self, "No such request")

    def project(self, submission: Submission) -> Submission:
        submission.user_requests[self.request_id].status = UserRequest.APPLIED
        return submission


@dataclass
class RequestCrossList(Event):
    """Request that a secondary classification be added after announcement."""

    NAME = "request cross-list classification"
    NAMED = "cross-list classification requested"

    def __hash__(self):
        """Use event ID as object hash."""
        return hash(self.event_id)

    categories: List[str] = field(default_factory=list)

    def validate(self, submission: Submission) -> None:
        """Validate the cross-list request."""
        validators.no_active_requests(self, submission)
        if not submission.published:
            raise InvalidEvent(self, "Submission must already be published")
        for category in self.categories:
            validators.must_be_a_valid_category(self, category, submission)
            validators.cannot_be_primary(self, category, submission)
            validators.cannot_be_secondary(self, category, submission)

    def project(self, submission: Submission) -> Submission:
        """Create a cross-list request."""
        classifications = [
            Classification(category=category) for category in self.categories
        ]
        submission.add_user_request(
            CrossListClassificationRequest(creator=self.creator,
                                           created=self.created,
                                           status=WithdrawalRequest.PENDING,
                                           classifications=classifications))
        return submission


@dataclass
class RequestWithdrawal(Event):
    """Request that a paper be withdrawn."""

    NAME = "request withdrawal"
    NAMED = "withdrawal requested"

    def __hash__(self):
        """Use event ID as object hash."""
        return hash(self.event_id)

    reason: str = field(default_factory=str)

    MAX_LENGTH = 400

    def validate(self, submission: Submission) -> None:
        """Make sure that a reason was provided."""
        validators.no_active_requests(self, submission)
        if not self.reason:
            raise InvalidEvent(self, "Provide a reason for the withdrawal")
        if len(self.reason) > self.MAX_LENGTH:
            raise InvalidEvent(self, "Reason must be 400 characters or less")
        if not submission.published:
            raise InvalidEvent(self, "Submission must already be published")

    def project(self, submission: Submission) -> Submission:
        """Update the submission status and withdrawal reason."""
        submission.add_user_request(
            WithdrawalRequest(creator=self.creator,
                              created=self.created,
                              updated=self.created,
                              status=WithdrawalRequest.PENDING,
                              reason_for_withdrawal=self.reason))
        return submission
