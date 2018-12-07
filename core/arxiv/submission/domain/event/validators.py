import re

from arxiv import taxonomy, identifier

from .event import Event
from ..submission import Submission
from ...exceptions import InvalidEvent


def submission_is_not_finalized(event: Event, submission: Submission) -> None:
    """
    Verify that the submission is not finalized.

    Parameters
    ----------
    event : :class:`.Event`
    submission : :class:`.Submission`

    Raises
    ------
    :class:`.InvalidEvent`
        Raised if the submission is finalized.

    """
    if submission.finalized:
        raise InvalidEvent(event, "Cannot apply to a finalized submission")


def no_trailing_period(event: Event, submission: Submission,
                       value: str) -> None:
    """
    Verify that there are no trailing periods in ``value`` except ellipses.
    """
    if re.search(r"(?<!\.\.)\.$", value):
        raise InvalidEvent(event, "Must not contain trailing periods except"
                                  " ellipses.")


def must_be_a_valid_category(event: Event, category: str,
                             submission: Submission) -> None:
    """Valid arXiv categories are defined in :mod:`arxiv.taxonomy`."""
    if not category or category not in taxonomy.CATEGORIES_ACTIVE:
        raise InvalidEvent(event, "Not a valid category")


def cannot_be_primary(event: Event, category: str, submission: Submission) \
        -> None:
    """The category can't already be set as a primary classification."""
    if submission.primary_classification is None:
        return
    if category == submission.primary_classification.category:
        raise InvalidEvent(event, "The same category cannot be used as both"
                                  " the primary and a secondary category.")


def cannot_be_secondary(event: Event, category: str, submission: Submission) \
        -> None:
    """The same category cannot be added as a secondary twice."""
    if category in submission.secondary_categories:
        raise InvalidEvent(event, f"Secondary {category} already set on this"
                                  f" submission.")


def no_active_requests(event: Event, submission: Submission) -> None:
    if submission.has_active_requests:
        raise InvalidEvent(event, "Must not have active requests.")
