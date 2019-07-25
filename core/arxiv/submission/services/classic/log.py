"""Interface to the classic admin log."""

from typing import Optional, Iterable, Dict, Callable

from . import models, util
from ...domain.event import Event, UnFinalizeSubmission, AcceptProposal, \
    AddSecondaryClassification, AddMetadataFlag, AddContentFlag
from ...domain.annotation import ClassifierResults
from ...domain.submission import Submission
from ...domain.agent import Agent, System
from ...domain.flag import MetadataFlag, ContentFlag


def log_unfinalize(event: UnFinalizeSubmission, before: Submission,
                   after: Submission) -> None:
    """Create a log entry when a user pulls their submission for changes."""
    admin_log(event.creator.username, "unfinalize",
              "user has pulled submission for editing",
              username=event.creator.username,
              hostname=event.creator.hostname,
              submission_id=after.submission_id,
              paper_id=after.arxiv_id)


def log_accept_system_cross(event: AcceptProposal, before: Submission,
                            after: Submission) -> None:
    """Create a log entry when a system cross is accepted."""
    proposal = after.proposals[event.proposal_id]
    if type(event.creator) is System:
        if proposal.proposed_event_type is AddSecondaryClassification:
            category = proposal.proposed_event_data["category"]
            admin_log(event.creator.username, "admin comment",
                      f"Added {category} as secondary: {event.comment}",
                      username="system",
                      submission_id=after.submission_id,
                      paper_id=after.arxiv_id)


def log_stopwords(event: AddContentFlag, before: Submission,
                  after: Submission) -> None:
    """Create a log entry when there is a problem with stopword content."""
    if event.flag_type is ContentFlag.Type.LOW_STOP:
        admin_log(event.creator.username, "admin comment",
                  event.comment,
                  username="system",
                  submission_id=after.submission_id,
                  paper_id=after.arxiv_id)


def log_classifier_failed(event: AddMetadataFlag, before: Submission,
                          after: Submission) -> None:
    """Create a log entry when the classifier returns no suggestions."""
    if type(event.annotation) is not ClassifierResults:
        return
    if not event.annotation.results:
        admin_log(event.creator.username, "admin comment",
                  "Classifier failed to return results for submission",
                  username="system",
                  submission_id=after.submission_id,
                  paper_id=after.arxiv_id)


ON_EVENT: Dict[type, Callable[[Event, Submission, Submission], None]] = {
    UnFinalizeSubmission: [log_unfinalize],
    AcceptProposal: [log_accept_system_cross],
    AddContentFlag: [log_stopwords]

}
"""Logging functions to call when an event is comitted."""


def handle(event: Event, before: Submission, after: Submission) -> None:
    """
    Generate an admin log entry for an event that is being committed.

    Looks for a logging function in :const:`.ON_EVENT` and, if found, calls it
    with the passed parameters.

    Parameters
    ----------
    event : :class:`event.Event`
        The event being committed.
    before : :class:`.domain.submission.Submission`
        State of the submission before the event.
    after : :class:`.domain.submission.Submission`
        State of the submission after the event.

    """
    if type(event) in ON_EVENT:
        for callback in ON_EVENT[type(event)]:
            callback(event, before, after)


def admin_log(program: str, command: str, text: str, notify: bool = False,
              username: Optional[str] = None,
              hostname: Optional[str] = None,
              submission_id: Optional[int] = None,
              paper_id: Optional[str] = None,
              document_id: Optional[int] = None) -> models.AdminLogEntry:
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
    if paper_id is None and submission_id is not None:
        paper_id = f'submit/{submission_id}'
    with util.transaction() as session:
        entry = models.AdminLogEntry(
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
        session.add(entry)
        return entry
