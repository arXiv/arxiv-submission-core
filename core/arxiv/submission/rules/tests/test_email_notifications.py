"""Test sending email notifications."""

from unittest import TestCase, mock
from datetime import datetime
from pytz import UTC, timezone

from flask import Flask

from arxiv import mail
from arxiv.base import Base
from ... import init_app, config
from ...domain.event import FinalizeSubmission
from ...domain.agent import User, System
from ...domain.submission import Submission, SubmissionContent, \
    SubmissionMetadata, Classification
from ..email_notifications import confirm_submission

sys = System(__name__)
eastern = timezone('US/Eastern')


class TestSendEmailOnSubmission(TestCase):
    """Tests for :mod:`.email_notifications`."""

    def setUp(self):
        """We have a submission."""
        self.creator = User(native_id=1234, email='something@else.com',
                            forename='Ross', surname='Perot')
        self.app = Flask(__name__)
        self.app.config.from_object(config)
        Base(self.app)
        mail.init_app(self.app)
        init_app(self.app)

        self.before = mock.MagicMock(
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
            finalized=False
        )
        self.after = mock.MagicMock(
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
            finalized=True
        )

    @mock.patch(f'{mail.__name__}.mail.smtplib.SMTP')
    def test_email_confirmation(self, mock_SMTP):
        """Confirmation email should be sent to the submitter."""
        mock_SMTP_instance = mock.MagicMock()
        mock_SMTP.return_value.__enter__.return_value = mock_SMTP_instance

        event = mock.MagicMock(creator=self.creator, created=datetime.now(UTC))

        with self.app.app_context():
            events = confirm_submission(event, self.before, self.after, sys)

        self.assertEqual(len(list(events)), 0, "Does not produce any events")

        msg = mock_SMTP_instance.send_message.call_args[0][0]
        content = str(msg.get_body(preferencelist=('plain')))

        self.assertEqual(msg['From'], 'noreply@arxiv.org')
        self.assertEqual(msg['To'], self.after.creator.email)

        self.assertIn('Content-Type: text/plain; charset="utf-8"', content,
                      'Content-type header is set')
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
        self.assertIn(f'Categories: {self.after.primary_classification.category}',
                      content)
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
