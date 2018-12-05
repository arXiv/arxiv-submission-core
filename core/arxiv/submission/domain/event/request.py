from typing import Optional

from dataclasses import dataclass, field

from . import validators
from .event import Event
from ..submission import Submission, Classification, WithdrawalRequest, \
    CrossListClassificationRequest
from ...exceptions import InvalidEvent


@dataclass
class RequestCrossList(Event):
    """Request that a secondary classification be added after announcement."""

    NAME = "request cross-list classification"
    NAMED = "cross-list classification requested"

    def __hash__(self):
        """Use event ID as object hash."""
        return hash(self.event_id)

    category: Optional[str] = field(default=None)

    def validate(self, submission: Submission) -> None:
        """Validate the cross-list request."""
        validators.no_active_requests(self, submission)
        if not submission.published:
            raise InvalidEvent(self, "Submission must already be published")
        validators.must_be_a_valid_category(self, self.category, submission)
        validators.cannot_be_primary(self, self.category, submission)
        validators.cannot_be_secondary(self, self.category, submission)

    def project(self, submission: Submission) -> Submission:
        """Create a cross-list request."""
        classification = Classification(category=self.category)
        submission.add_user_request(
            CrossListClassificationRequest(creator=self.creator,
                                           created=self.created,
                                           status=WithdrawalRequest.PENDING,
                                           classification=classification))
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
                              status=WithdrawalRequest.PENDING,
                              reason_for_withdrawal=self.reason))
        return submission
