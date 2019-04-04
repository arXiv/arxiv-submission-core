"""Test sending email notifications."""

from unittest import TestCase, mock
from datetime import datetime
from pytz import UTC, timezone

from flask import Flask

from arxiv import mail
from arxiv.submission.domain.event import FinalizeSubmission
from arxiv.submission.domain.agent import User, System
from arxiv.submission.domain.submission import Submission, SubmissionContent, \
    SubmissionMetadata, Classification

from .. import SendConfirmationEmail
from .. import email_notifications
from .. import Failed
from ...domain import Trigger
from ...runner import ProcessRunner
from ...factory import create_app

sys = System(__name__)
eastern = timezone('US/Eastern')


class TestSendConfirmationEmail(TestCase):
    """Test the :class:`.SendConfirmationEmail` process."""

    def setUp(self):
        """We have a submission."""
        self.app = create_app()
        self.creator = User(native_id=1234, email='something@else.com',
                            forename='Ross', surname='Perot')
        self.submission_id = 12345
        self.before = Submission(
            submission_id=self.submission_id,
            metadata=mock.MagicMock(
                title="The best title",
                authors_display="Frank Underwood (POTUS)",
                abstract="Pork loin meatloaf meatball in cow et. Tail pork ut velit, eu prosciutto pork chop pariatur ad non hamburger bacon cupidatat. Short loin nulla aute esse spare ribs eiusmod consequat anim capicola chuck cupim labore alcatra strip steak tail. Lorem short ribs andouille leberkas pork belly. Andouille fatback ham hock burgdoggen, ham pork belly labore doner aute esse.",
                comments="Aliqua ham capicola minim filet mignon tenderloin voluptate bacon biltong shank in chuck do pig in. Id pariatur jowl ad ham pork chop doner buffalo laboris sed ut",
                msc_class="14J60 (Primary), 14F05, 14J26 (Secondary)",
                acm_class="F.2.2; I.2.7",
                journal_ref="Nature 2021 39202:32-12",
                report_num="Report 1234",
                doi="10.00123/43463"
            ),
            source_content=mock.MagicMock(uncompressed_size=392019),
            version=1,
            primary_classification=mock.MagicMock(category='cs.DL'),
            license=mock.MagicMock(uri='http://some.license/v2'),
            creator=self.creator,
            owner=self.creator,
            created=datetime(2018, 3, 4, 18, 34, 2, tzinfo=UTC),
            submitted=datetime(2018, 3, 4, 19, 34, 2, tzinfo=UTC),
            status=Submission.WORKING
        )
        self.after = Submission(
            submission_id=12345,
            metadata=mock.MagicMock(
                title="The best title",
                authors_display="Frank Underwood (POTUS)",
                abstract="Pork loin meatloaf meatball in cow et. Tail pork ut velit, eu prosciutto pork chop pariatur ad non hamburger bacon cupidatat. Short loin nulla aute esse spare ribs eiusmod consequat anim capicola chuck cupim labore alcatra strip steak tail. Lorem short ribs andouille leberkas pork belly. Andouille fatback ham hock burgdoggen, ham pork belly labore doner aute esse.",
                comments="Aliqua ham capicola minim filet mignon tenderloin voluptate bacon biltong shank in chuck do pig in. Id pariatur jowl ad ham pork chop doner buffalo laboris sed ut",
                msc_class="14J60 (Primary), 14F05, 14J26 (Secondary)",
                acm_class="F.2.2; I.2.7",
                journal_ref="Nature 2021 39202:32-12",
                report_num="Report 1234",
                doi="10.00123/43463"
            ),
            source_content=mock.MagicMock(uncompressed_size=392019),
            version=1,
            primary_classification=mock.MagicMock(category='cs.DL'),
            license=mock.MagicMock(uri='http://some.license/v2'),
            creator=self.creator,
            owner=self.creator,
            created=datetime(2018, 3, 4, 18, 34, 2, tzinfo=UTC),
            submitted=datetime(2018, 3, 4, 19, 34, 2, tzinfo=UTC),
            status=Submission.SUBMITTED
        )
        self.event = FinalizeSubmission(creator=self.creator,
                                        created=datetime.now(UTC))
        self.process = SendConfirmationEmail(self.submission_id)

    @mock.patch(f'{email_notifications.__name__}.mail')
    def test_bad_trigger(self, mock_mail):
        """The trigger lacks sufficient data to send an email."""
        trigger = Trigger()
        events = []
        with self.app.app_context():
            with self.assertRaises(Failed):     # The process explicitly fails.
                self.process.send(None, trigger, events.append)

    @mock.patch(f'{email_notifications.__name__}.mail')
    def test_email_confirmation(self, mock_mail):
        """Confirmation email should be sent to the submitter."""
        trigger = Trigger(event=self.event, actor=self.creator,
                          before=self.before, after=self.after)
        events = []
        with self.app.app_context():
            self.process.send(None, trigger, events.append)

        recipient, subject, content, html = mock_mail.send.call_args[0]
        self.assertIn('We have received your submission to arXiv.', content)
        self.assertIn('Your article is scheduled to be announced at Mon, 5 Mar'
                      ' 2018 20:00:00 ET', content)
        self.assertIn('Updates before Mon, 5 Mar 2018 14:00:00 ET will not'
                      ' delay announcement.', content)

        self.assertIn(f'From: {self.creator.name} <{self.creator.email}>',
                      content)
        self.assertIn('Date: Sun, 4 Mar 2018 13:34:02 ET   (392.019 KB)',
                      content)
        self.assertIn(f'Title: {self.after.metadata.title}', content)
        self.assertIn(f'Authors: {self.after.metadata.authors_display}',
                      content)
        self.assertIn(
            f'Categories: {self.after.primary_classification.category}',
            content
        )
        self.assertIn(f'MSC classes: {self.after.metadata.msc_class}', content)
        self.assertIn(f'ACM classes: {self.after.metadata.acm_class}', content)
        self.assertIn(f'Journal reference: {self.after.metadata.journal_ref}',
                      content)
        self.assertIn(f'Report number: {self.after.metadata.report_num}',
                      content)
        self.assertIn(f'License: {self.after.license.uri}', content)

        for line in content.split('\n'):
            self.assertLess(len(line), 80,
                            "No line is longer than 79 characters")
