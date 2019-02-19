"""Rules for sending e-mail notifications."""

from typing import Iterable
from arxiv import mail

from ..domain.event import Event, FinalizeSubmission
from ..domain.submission import Submission
from ..domain.agent import Agent
from ..tasks import is_async


@FinalizeSubmission.bind()
@is_async
def confirm_submission(event: FinalizeSubmission, before: Submission,
                       after: Submission, creator: Agent) -> Iterable[Event]:
    """Send a confirmation e-mail when the submission is finalized."""
    pass    # TODO: implement this when the template is available.
