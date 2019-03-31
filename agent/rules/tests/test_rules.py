"""Test that expected processes are called under different conditions."""

from unittest import TestCase, mock
from datetime import datetime
from pytz import UTC, timezone

from arxiv.submission.domain.event import FinalizeSubmission, ConfirmPreview
from arxiv.submission.domain.agent import User, System
from arxiv.submission.domain.submission import Submission, SubmissionContent, \
    SubmissionMetadata, Classification


from ...services import database
from .. import process
from ...domain import Trigger
from ...factory import create_app
from ... import rules


class TestFinalizeSubmission(TestCase):
    """Test that expected rules are triggered in response to events."""

    def setUp(self):
        """We have a submission."""
        self.creator = User(native_id=1234, email='something@else.com',
                            forename='Ross', surname='Perot')
        self.app = create_app()

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

    def _get_call_data(self, mock_Runner):
        passed = []
        triggers = {}
        for i in range(0, len(mock_Runner.mock_calls), 2):
            name, args, kwargs = mock_Runner.mock_calls[i]
            self.assertEqual(name, '', 'First call is to constructor')
            process_inst = args[0]
            self.assertIsInstance(process_inst, process.Process,
                                  'Process is passed')
            passed.append(type(process_inst))

            name, args, kwargs = mock_Runner.mock_calls[i+1]
            self.assertEqual(name, '().run', 'Second call is to run method')
            trigger = args[0]
            self.assertIsInstance(trigger, Trigger, 'Trigger is passed')
            triggers[type(process_inst)] = trigger
        return passed, triggers

    @mock.patch(f'{rules.__name__}.AsyncProcessRunner')
    def test_confirm_preview(self, mock_Runner):
        """The submitter confirms their preview."""
        event = ConfirmPreview(creator=self.creator, created=datetime.now(UTC))

        with self.app.app_context():
            rules.evaluate(event, self.before, self.after)

        passed, triggers = self._get_call_data(mock_Runner)

        self.assertIn(process.RunAutoclassifier, passed,
                      'Autoclassifier process is started')
        self.assertIn(process.CheckPDFSize, passed,
                      'PDF size check is started')

    @mock.patch(f'{rules.__name__}.AsyncProcessRunner')
    def test_finalize(self, mock_Runner):
        """The submission is finalized."""
        event = FinalizeSubmission(creator=self.creator,
                                   created=datetime.now(UTC))

        with self.app.app_context():
            rules.evaluate(event, self.before, self.after)

        passed, triggers = self._get_call_data(mock_Runner)

        self.assertIn(process.SendConfirmationEmail, passed,
                      'Email confirmation process is started')
        self.assertIn(process.ProposeCrossListFromPrimaryCategory, passed,
                      'Propose cross-list process is started')
