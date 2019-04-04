"""Tests for content size checks."""

from unittest import TestCase, mock
from datetime import datetime, timedelta
from pytz import UTC
import copy

from arxiv.integration.api import status, exceptions
from arxiv.submission.domain.event import SetTitle, SetAbstract, \
    AddMetadataFlag, RemoveFlag, AddHold, RemoveHold
from arxiv.submission.domain.agent import Agent, User
from arxiv.submission.domain.flag import Flag, MetadataFlag
from arxiv.submission.domain.submission import Submission, SubmissionContent, \
    SubmissionMetadata, Classification, Compilation, Hold

from .. import CheckPDFSize, CheckSubmissionSourceSize, Failed, Recoverable
from .. import size_limits
from ...domain import Trigger
from ...factory import create_app
from .data import titles
from .util import raise_http_exception


class TestCheckSubmissionSourceSize(TestCase):
    """Test :func:`.CheckSubmissionSourceSize.check`."""

    def setUp(self):
        """We have a submission."""
        self.creator = User(native_id=1234, email='something@else.com')
        self.submission = Submission(
            submission_id=2347441,
            creator=self.creator,
            owner=self.creator,
            created=datetime.now(UTC)
        )
        self.process = CheckSubmissionSourceSize(self.submission.submission_id)

    def test_no_source(self):
        """Submission has no source."""
        trigger = Trigger(before=self.submission, after=self.submission,
                          params={'UNCOMPRESSED_PACKAGE_MAX': 40_003_932,
                                  'COMPRESSED_PACKAGE_MAX': 3_039_303})
        events = []
        with self.assertRaises(Failed):
            self.process.check(None, trigger, events.append)

    def test_small_source(self):
        """The submission source content is quite small."""
        self.submission.source_content = SubmissionContent(
            identifier='5678',
            source_format=SubmissionContent.Format('pdf'),
            checksum='a1b2c3d4',
            uncompressed_size=593,
            compressed_size=53
        )
        trigger = Trigger(before=self.submission, after=self.submission,
                          params={'UNCOMPRESSED_PACKAGE_MAX': 40_003_932,
                                  'COMPRESSED_PACKAGE_MAX': 3_039_303})
        events = []
        self.process.check(None, trigger, events.append)
        self.assertEqual(len(events), 0, 'No events generated')

    def test_small_source_previous_hold(self):
        """The submission has a hold, but this source content is OK."""
        self.submission.source_content = SubmissionContent(
            identifier='5678',
            source_format=SubmissionContent.Format('pdf'),
            checksum='a1b2c3d4',
            uncompressed_size=593,
            compressed_size=53
        )
        self.submission.holds['asdf1234'] = Hold(
            event_id='asdf1234',
            creator=self.creator,
            hold_type=Hold.Type.SOURCE_OVERSIZE
        )
        trigger = Trigger(before=self.submission, after=self.submission,
                          params={'UNCOMPRESSED_PACKAGE_MAX': 40_003_932,
                                  'COMPRESSED_PACKAGE_MAX': 3_039_303})
        events = []
        self.process.check(None, trigger, events.append)
        self.assertIsInstance(events[0], RemoveHold, 'Removes a hold')
        self.assertEqual(events[0].hold_event_id, 'asdf1234')
        self.assertEqual(events[0].hold_type, Hold.Type.SOURCE_OVERSIZE)

    def test_huge_uncompressed_size(self):
        """The submission source is huge uncompressed."""
        self.submission.source_content = SubmissionContent(
            identifier='5678',
            source_format=SubmissionContent.Format('pdf'),
            checksum='a1b2c3d4',
            uncompressed_size=593_032_039,
            compressed_size=53
        )
        trigger = Trigger(before=self.submission, after=self.submission,
                          params={'UNCOMPRESSED_PACKAGE_MAX': 40_003_932,
                                  'COMPRESSED_PACKAGE_MAX': 3_039_303})
        events = []
        self.process.check(None, trigger, events.append)
        self.assertIsInstance(events[0], AddHold, 'Adds a hold')
        self.assertEqual(events[0].hold_type, Hold.Type.SOURCE_OVERSIZE)

    def test_huge_previous_holds(self):
        """The submission has a hold, and this source content is too big."""
        self.submission.source_content = SubmissionContent(
            identifier='5678',
            source_format=SubmissionContent.Format('pdf'),
            checksum='a1b2c3d4',
            uncompressed_size=593_032_039,
            compressed_size=593_032_039
        )
        self.submission.holds['asdf1234'] = Hold(
            event_id='asdf1234',
            creator=self.creator,
            hold_type=Hold.Type.SOURCE_OVERSIZE
        )
        trigger = Trigger(before=self.submission, after=self.submission,
                          params={'UNCOMPRESSED_PACKAGE_MAX': 40_003_932,
                                  'COMPRESSED_PACKAGE_MAX': 3_039_303})
        events = []
        self.process.check(None, trigger, events.append)
        self.assertEqual(len(events), 0, 'Generates no holds')

    def test_huge_compressed_size(self):
        """The submission source is huge compressed."""
        self.submission.source_content = SubmissionContent(
            identifier='5678',
            source_format=SubmissionContent.Format('pdf'),
            checksum='a1b2c3d4',
            uncompressed_size=493,
            compressed_size=593_032_039     # Something is very wrong...
        )
        trigger = Trigger(before=self.submission, after=self.submission,
                          params={'UNCOMPRESSED_PACKAGE_MAX': 40_003_932,
                                  'COMPRESSED_PACKAGE_MAX': 3_039_303})
        events = []
        self.process.check(None, trigger, events.append)
        self.assertIsInstance(events[0], AddHold, 'Adds a hold')
        self.assertEqual(events[0].hold_type, Hold.Type.SOURCE_OVERSIZE)


class TestPDFGetSize(TestCase):
    """Test :func:`.CheckPDFSize.get_size`."""

    def setUp(self):
        """We have a submission."""
        self.creator = User(native_id=1234, email='something@else.com')
        self.submission = Submission(
            submission_id=2347441,
            creator=self.creator,
            owner=self.creator,
            created=datetime.now(UTC),
            source_content=SubmissionContent(
                identifier='5678',
                source_format=SubmissionContent.Format('pdf'),
                checksum='a1b2c3d4',
                uncompressed_size=58493,
                compressed_size=58493
            )
        )
        self.process = CheckPDFSize(self.submission.submission_id)

    def test_get_size_no_source(self):
        """The submission has no source content."""
        self.submission.source_content = None
        events = []
        trigger = Trigger(before=self.submission, after=self.submission,
                          actor=self.creator)
        with self.assertRaises(Failed):
            self.process.get_size(None, trigger, events.append)

    @mock.patch(f'{size_limits.__name__}.get_system_token',
                mock.MagicMock(return_value='footoken'))
    @mock.patch(f'{size_limits.__name__}.compiler.Compiler.get_status')
    def test_get_size_server_error(self, mock_get_status):
        """The compiler service flakes out."""
        mock_get_status.side_effect = \
            raise_http_exception(exceptions.RequestFailed, 500)
        events = []
        trigger = Trigger(before=self.submission, after=self.submission,
                          actor=self.creator)
        with self.assertRaises(Recoverable):
            self.process.get_size(None, trigger, events.append)

    @mock.patch(f'{size_limits.__name__}.get_system_token',
                mock.MagicMock(return_value='footoken'))
    @mock.patch(f'{size_limits.__name__}.compiler.Compiler.get_status')
    def test_get_size_compilation_in_progress(self, mock_get_status):
        """The submission has a compilation but it is not finished."""
        mock_get_status.return_value = mock.MagicMock(
            status=Compilation.Status.IN_PROGRESS
        )

        events = []
        trigger = Trigger(before=self.submission, after=self.submission,
                          actor=self.creator)
        with self.assertRaises(Recoverable):
            self.process.get_size(None, trigger, events.append)

    @mock.patch(f'{size_limits.__name__}.get_system_token',
                mock.MagicMock(return_value='footoken'))
    @mock.patch(f'{size_limits.__name__}.compiler.Compiler.get_status')
    def test_get_size_compilation_failed(self, mock_get_status):
        """The submission has a compilation but it failed."""
        mock_get_status.return_value = mock.MagicMock(
            status=Compilation.Status.FAILED
        )

        events = []
        trigger = Trigger(before=self.submission, after=self.submission,
                          actor=self.creator)
        with self.assertRaises(Failed):
            self.process.get_size(None, trigger, events.append)

    @mock.patch(f'{size_limits.__name__}.get_system_token',
                mock.MagicMock(return_value='footoken'))
    @mock.patch(f'{size_limits.__name__}.compiler.Compiler.get_status')
    def test_get_size(self, mock_get_status):
        """The submission has a compilation."""
        size_bytes = 50_030_299_399
        mock_get_status.return_value = mock.MagicMock(
            status=Compilation.Status.SUCCEEDED,
            size_bytes=size_bytes
        )

        events = []
        trigger = Trigger(before=self.submission, after=self.submission,
                          actor=self.creator)

        self.assertEqual(self.process.get_size(None, trigger, events.append),
                         size_bytes, 'Gets the compilation size in bytes')


class TestEvaluatePDFSize(TestCase):
    """Test :func:`.CheckPDFSize.evaluate_size`."""

    def setUp(self):
        """We have a submission."""
        self.creator = User(native_id=1234, email='something@else.com')
        self.submission = Submission(
            submission_id=2347441,
            creator=self.creator,
            owner=self.creator,
            created=datetime.now(UTC),
            source_content=SubmissionContent(
                identifier='5678',
                source_format=SubmissionContent.Format('pdf'),
                checksum='a1b2c3d4',
                uncompressed_size=58493,
                compressed_size=58493
            )
        )
        self.process = CheckPDFSize(self.submission.submission_id)

    def test_huge_pdf(self):
        """The PDF is huge."""
        trigger = Trigger(before=self.submission, after=self.submission,
                          actor=self.creator, params={'PDF_LIMIT': 5_000_000})
        size_bytes = 50_030_299_399
        events = []
        self.process.evaluate_size(size_bytes, trigger, events.append)
        self.assertIsInstance(events[0], AddHold, 'Adds a hold')
        self.assertEqual(events[0].hold_type, Hold.Type.PDF_OVERSIZE,
                         'Adds a PDF oversize hold')

    def test_small_pdf(self):
        """The PDF is quite small."""
        trigger = Trigger(before=self.submission, after=self.submission,
                          actor=self.creator, params={'PDF_LIMIT': 5_000_000})
        size_bytes = 549
        events = []
        self.process.evaluate_size(size_bytes, trigger, events.append)
        self.assertEqual(len(events), 0, 'No holds are generated')

    def test_existing_hold(self):
        """The submission already has an oversize hold, and this PDF is OK."""
        self.submission.holds['asdf1234'] = Hold(
            event_id='asdf1234',
            creator=self.creator,
            hold_type=Hold.Type.PDF_OVERSIZE
        )
        trigger = Trigger(before=self.submission, after=self.submission,
                          actor=self.creator, params={'PDF_LIMIT': 5_000_000})
        size_bytes = 549
        events = []
        self.process.evaluate_size(size_bytes, trigger, events.append)
        self.assertIsInstance(events[0], RemoveHold, 'Removes a hold')
        self.assertEqual(events[0].hold_type, Hold.Type.PDF_OVERSIZE,
                         'Removes a PDF oversize hold')
        self.assertEqual(events[0].hold_event_id, 'asdf1234',
                         'Removes the existing PDF oversize hold')

    def test_existing_hold_still_huge(self):
        """The submission already has a hold, and this PDF is still huge."""
        self.submission.holds['asdf1234'] = Hold(
            event_id='asdf1234',
            creator=self.creator,
            hold_type=Hold.Type.PDF_OVERSIZE
        )
        trigger = Trigger(before=self.submission, after=self.submission,
                          actor=self.creator, params={'PDF_LIMIT': 5_000_000})
        size_bytes = 50_030_299_399
        events = []
        self.process.evaluate_size(size_bytes, trigger, events.append)
        self.assertEqual(len(events), 0, 'No events are generated')
