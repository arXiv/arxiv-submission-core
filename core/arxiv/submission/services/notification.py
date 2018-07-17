"""
The notication service provides integration with the notification broker.

Brokered notifications provide an event-based integration strategy for other
arXiv submission and moderation services, including the webhook service (to
notify external-to-arXiv services).
"""

from ..domain import Event, Submission


def emit(event: Event, submission: Submission) -> None:
    """
    Emit an event to the notification broker.

    Parameters
    ----------
    event : :class:`.Event`
    submission : :class:`.Submission`

    Raises
    ------
    NotificationFailed
    """
    # TODO: implement me!
