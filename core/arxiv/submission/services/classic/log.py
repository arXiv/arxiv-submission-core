"""Interface to the classic admin log."""

from typing import Optional, Iterable, Dict, Callable

from . import models, util
from ...domain import event
from ...domain.submission import Submission
from ...domain.agent import Agent


def log_unfinalize(event: event.UnFinalizeSubmission, before: Submission,
                   after: Submission) -> None:
    """Create a log entry when a user pulls their submission for changes."""
    admin_log(__name__, "unfinalize", "user has pulled submission for editing",
              username=event.creator.username,
              hostname=event.creator.hostname,
              submission_id=after.submission_id,
              paper_id=after.arxiv_id)


ON_EVENT: Dict[type, Callable[[event.Event, Submission, Submission], None]] = {
    event.UnFinalizeSubmission: log_unfinalize,
}
"""Logging functions to call when an event is comitted."""


def handle(event: event.Event, before: Submission, after: Submission) -> None:
    """
    Generate an admin log entry for an event that is being committed.

    Looks for a logging function in :ref:`.ON_EVENT` and, if found, calls it
    with the passed parameters.

    Parameters
    ----------
    event : :class:`event.Event`
        The event being committed.
    before : :class:`.Submission`
        State of the submission before the event.
    after : :class:`.Submission`
        State of the submission after the event.

    """
    if type(event) in ON_EVENT:
        ON_EVENT[type(event)](event, before, after)


def admin_log(program: str, command: str, text: str, notify: bool = False,
              username: Optional[str] = None,
              hostname: Optional[str] = None,
              submission_id: Optional[int] = None,
              paper_id: Optional[str] = None,
              document_id: Optional[int] = None) -> None:
    """
    Add an entry to the admin log.

    Parameters
    ----------
    program : str
        Name of the application generating the log entry.
    command : str
        Name of the command generating the log entry.
    text : str
        Content of the admin log entry.
    notify : bool
    username : str
    hostname : str
        Hostname or IP address of the client.
    submission_id : int
    paper_id : str
    document_id : int

    """
    with util.transaction() as session:
        session.add(
            models.AdminLogEntry(
                paper_id=paper_id,
                username=username,
                host=hostname,
                program=program,
                command=command,
                logtext=text,
                document_id=document_id,
                submission_id=submission_id,
                notify=notify
            )
        )
