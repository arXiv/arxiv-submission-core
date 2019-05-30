"""Rule condition helpers."""

from arxiv.submission.domain.event import Event, AddFeature
from arxiv.submission.domain.submission import Submission
from arxiv.submission.domain.agent import Agent, User, System
from arxiv.submission.domain.annotation import Feature

from .base import Condition


def is_system_event(event: Event, before: Submission,
                    after: Submission) -> bool:
    """Only for system-created events."""
    return type(event.creator) is System


def is_user_event(event: Event, before: Submission, after: Submission) -> bool:
    """Only for user-created events."""
    return type(event.creator) is User


def is_always(event: Event, before: Submission, after: Submission) -> bool:
    """Return ``True``. Always means always."""
    return True


def is_feature_type(feature_type: Feature.Type) -> Condition:
    """Generate a condition based on feature type."""
    def condition(event: AddFeature, before: Submission,
                  after: Submission) -> bool:
        return event.feature_type is feature_type
    return condition
