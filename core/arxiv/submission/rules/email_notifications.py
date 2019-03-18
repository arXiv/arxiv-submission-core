"""Rules for sending e-mail notifications."""

from typing import Iterable

from flask import render_template

from arxiv import mail

from ..domain.event import Event, FinalizeSubmission
from ..domain.submission import Submission
from ..domain.agent import Agent
from .. import schedule
from ..tasks import is_async


@FinalizeSubmission.bind()
@is_async
def confirm_submission(event: FinalizeSubmission, before: Submission,
                       after: Submission, creator: Agent) -> Iterable[Event]:
    """Send a confirmation e-mail when the submission is finalized."""
    context = {
        'submission_id': after.submission_id,
        'submission': after,
        'arxiv_id': f'submit/{after.submission_id}',
        'announce_time': schedule.next_announcement_time(after.submitted),
        'freeze_time': schedule.next_freeze_time(after.submitted),
    }
    mail.send(event.creator.email, "Submission to arXiv received",
              render_template("submission-core/confirmation-email.txt", **context),
              render_template("submission-core/confirmation-email.html", **context))
    return []
