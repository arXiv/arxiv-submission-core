"""Rules for sending e-mail notifications."""

from typing import Iterable, Optional, Callable

from flask import render_template

from arxiv import mail
from arxiv.base import logging
from arxiv.base.globals import get_application_config

from arxiv.submission.domain.event import Event, FinalizeSubmission
from arxiv.submission.domain.submission import Submission
from arxiv.submission.domain.agent import Agent
from arxiv.submission import schedule

from ..process import Process, step
from ..domain import Trigger

logger = logging.getLogger(__name__)


class SendConfirmationEmail(Process):
    """Send a confirmation e-mail to the submitter."""

    @step(max_retries=None, backoff=4)
    def send(self, previous: Optional, trigger: Trigger,
             emit: Callable) -> None:
        """Send the e-mail."""
        try:
            submission_id = trigger.after.submission_id
            recipient = trigger.event.creator
        except AttributeError as exc:
            logger.error('Missing event or post-event submission state')
            self.fail(exc, 'Missing event or post-event submission state')

        context = {
            'submission_id': submission_id,
            'submission': trigger.after,
            'arxiv_id': f'submit/{submission_id}',
            'announce_time':
                schedule.next_announcement_time(trigger.after.submitted),
            'freeze_time': schedule.next_freeze_time(trigger.after.submitted),
        }
        logger.info('Sending confirmation email to %s for submission %i',
                    recipient.email, submission_id)
        mail.send(recipient.email,
                  "Submission to arXiv received",
                  render_template("submission-core/confirmation-email.txt",
                                  **context),
                  render_template("submission-core/confirmation-email.html",
                                  **context))
