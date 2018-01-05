"""Responsible for emitting internal events to other services, via Kinesis."""

import boto3
from submit.domain.event import Event
from submit.domain.submission import Submission


def emit_event(event: Event, submission: Submission) -> None:
    """
    Emit a system notification for an internal submission event.

    Parameters
    ----------
    event : :class:`.Event`
        The event for which the notification should be emitted.
    submission : :class:`.Submission`
        The state of the submission upon application of the event.

    Raises
    ------
    IOError
        Raised when unable to emit the system notification.
    """
    # TODO: implement this!
    return
