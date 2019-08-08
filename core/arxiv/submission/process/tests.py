"""Tests for :mod:`.process.process_source`."""

import io
from datetime import datetime
from unittest import TestCase, mock

from pytz import UTC

from arxiv.integration.api.exceptions import RequestFailed, NotFound

from ..domain import Submission, SubmissionContent, User, Client
from ..domain.event import ConfirmSourceProcessed, UnConfirmSourceProcessed
from ..domain.preview import Preview
from . import process_source
from .. import SaveError
from .process_source import start, check, SUCCEEDED, FAILED, IN_PROGRESS, \
    NOT_STARTED

PDF = SubmissionContent.Format.PDF
TEX = SubmissionContent.Format.TEX


def raise_RequestFailed(*args, **kwargs):
    raise RequestFailed('foo', mock.MagicMock())


def raise_NotFound(*args, **kwargs):
    raise NotFound('foo', mock.MagicMock())


class PDFFormatTest(TestCase):
    """Test case for PDF format processing."""

    def setUp(self):
        """We have a submission with a PDF source package."""
        self.content = mock.MagicMock(spec=SubmissionContent,
                                      identifier=1234,
                                      checksum='foochex==',
                                      source_format=PDF)
        self.submission = mock.MagicMock(spec=Submission,
                                         submission_id=42,
                                         source_content=self.content,
                                         is_source_processed=False,
                                         preview=None)
        self.user = mock.MagicMock(spec=User)
        self.client = mock.MagicMock(spec=Client)
        self.token = 'footoken'


class TestStartProcessingPDF(PDFFormatTest):
    """Test :const:`.PDFProcess`."""

    @mock.patch(f'{process_source.__name__}.save')
    @mock.patch(f'{process_source.__name__}.PreviewService')
    @mock.patch(f'{process_source.__name__}.Filemanager')
    def test_start(self, mock_Filemanager, mock_PreviewService, mock_save):
        """Start processing the PDF source."""
        mock_preview_service = mock.MagicMock()
        mock_preview_service.has_preview.return_value = False
        mock_preview_service.deposit.return_value = mock.MagicMock(
            spec=Preview,
            source_id=1234,
            source_checksum='foochex==',
            preview_checksum='foochex==',
            size_bytes=1234578,
            added=datetime.now(UTC)
        )
        mock_PreviewService.current_session.return_value = mock_preview_service

        mock_filemanager = mock.MagicMock()
        stream = io.BytesIO(b'fakecontent')
        mock_filemanager.get_single_file.return_value = (
            stream,
            'foochex==',
            'contentchex=='
        )
        mock_Filemanager.current_session.return_value = mock_filemanager

        mock_save.return_value = (self.submission, [])

        data = start(self.submission, self.user, self.client, self.token)
        self.assertEqual(data.status, SUCCEEDED, "Processing succeeded")

        mock_preview_service.deposit.assert_called_once_with(
            self.content.identifier,
            self.content.checksum,
            stream,
            self.token,
            content_checksum='contentchex==',
            overwrite=True
        )

        mock_save.assert_called_once()
        args, kwargs = mock_save.call_args
        self.assertIsInstance(args[0], ConfirmSourceProcessed)
        self.assertEqual(kwargs['submission_id'],
                         self.submission.submission_id)

    @mock.patch(f'{process_source.__name__}.save')
    @mock.patch(f'{process_source.__name__}.PreviewService')
    @mock.patch(f'{process_source.__name__}.Filemanager')
    def test_already_done(self, mock_Filemanager, mock_PreviewService,
                          mock_save):
        """Attempt to start processing a source that is already processed."""
        self.submission.is_source_processed = True
        self.submission.preview = mock.MagicMock()
        self.submission.source_content.checksum = 'foochex=='

        mock_preview_service = mock.MagicMock()
        mock_preview_service.has_preview.return_value = False
        mock_preview_service.deposit.return_value = mock.MagicMock(
            spec=Preview,
            source_id=1234,
            source_checksum='foochex==',
            preview_checksum='pvwchex==',
            size_bytes=1234578,
            added=datetime.now(UTC)
        )
        mock_PreviewService.current_session.return_value = mock_preview_service

        mock_filemanager = mock.MagicMock()
        stream = io.BytesIO(b'fakecontent')
        mock_filemanager.get_single_file.return_value = (
            stream,
            'foochex==',
            'pvwchex=='
        )
        mock_Filemanager.current_session.return_value = mock_filemanager

        mock_save.return_value = (self.submission, [])

        data = start(self.submission, self.user, self.client, self.token)

        self.assertEqual(data.status, SUCCEEDED, "Processing succeeded")

        # Evaluate deposit to preview service.
        mock_preview_service.deposit.assert_called_once_with(
            self.content.identifier,
            self.content.checksum,
            stream,
            self.token,
            content_checksum='pvwchex==',
            overwrite=True
        )

        # Evaluate calls to save()
        self.assertEqual(mock_save.call_count, 2, 'Save called twice')
        calls = mock_save.call_args_list
        # First call is to unconfirm processing.
        args, kwargs = calls[0]
        self.assertIsInstance(args[0], UnConfirmSourceProcessed)
        self.assertEqual(kwargs['submission_id'],
                         self.submission.submission_id)

        # Second call is to confirm processing.
        args, kwargs = calls[1]
        self.assertIsInstance(args[0], ConfirmSourceProcessed)
        self.assertEqual(kwargs['submission_id'],
                         self.submission.submission_id)

    @mock.patch(f'{process_source.__name__}.Filemanager')
    def test_start_preview_fails(self, mock_Filemanager):
        """No single PDF file available to use."""
        mock_filemanager = mock.MagicMock()
        stream = io.BytesIO(b'fakecontent')
        mock_filemanager.get_single_file.side_effect = raise_NotFound
        mock_Filemanager.current_session.return_value = mock_filemanager

        data = start(self.submission, self.user, self.client, self.token)
        self.assertEqual(data.status, FAILED, 'Failed to start')

        mock_filemanager.get_single_file.assert_called_once_with(
            self.content.identifier,
            self.token
        )


class TestCheckPDF(PDFFormatTest):
    """Test :const:`.PDFProcess`."""

    @mock.patch(f'{process_source.__name__}.PreviewService')
    def test_check_successful(self, mock_PreviewService):
        """Source is processed and a preview is present."""
        self.submission.is_source_processed = True
        self.submission.preview = mock.MagicMock(
            spec=Preview,
            source_id=1234,
            source_checksum='foochex==',
            preview_checksum='foochex==',
            size_bytes=1234578,
            added=datetime.now(UTC)
        )

        mock_preview_service = mock.MagicMock()
        mock_preview_service.has_preview.return_value = True
        mock_PreviewService.current_session.return_value = mock_preview_service

        data = check(self.submission, self.user, self.client, self.token)
        self.assertEqual(data.status, SUCCEEDED)
        self.assertIn('preview', data.extra)

        mock_preview_service.has_preview.assert_called_once_with(
            self.submission.source_content.identifier,
            self.submission.source_content.checksum,
            self.token,
            self.submission.preview.preview_checksum
        )

    @mock.patch(f'{process_source.__name__}.PreviewService')
    def test_check_preview_not_found(self, mock_PreviewService):
        """Source is not processed, and there is no preview."""
        mock_preview_service = mock.MagicMock()
        mock_preview_service.has_preview.return_value = False
        mock_preview_service.get_metadata.side_effect = raise_NotFound
        mock_PreviewService.current_session.return_value = mock_preview_service

        data = check(self.submission, self.user, self.client, self.token)
        self.assertEqual(data.status, NOT_STARTED)
        self.assertNotIn('preview', data.extra)

        mock_preview_service.get_metadata.assert_called_once_with(
            self.submission.source_content.identifier,
            self.submission.source_content.checksum,
            self.token
        )


class TeXFormatTestCase(TestCase):
    """Test case for TeX format processing."""

    def setUp(self):
        """We have a submission with a TeX source package."""
        self.content = mock.MagicMock(spec=SubmissionContent,
                                      identifier=1234,
                                      checksum='foochex==',
                                      source_format=TEX)
        self.submission = mock.MagicMock(spec=Submission,
                                         submission_id=42,
                                         source_content=self.content,
                                         is_source_processed=False,
                                         preview=None)
        self.submission.primary_classification.category = 'cs.DL'
        self.user = mock.MagicMock(spec=User)
        self.client = mock.MagicMock(spec=Client)
        self.token = 'footoken'


class TestStartTeX(TeXFormatTestCase):
    """Test the start of processing a TeX source."""

    @mock.patch(f'{process_source.__name__}.Compiler')
    def test_start(self, mock_Compiler):
        """Start is successful, in progress."""
        mock_compiler = mock.MagicMock()
        mock_compiler.compile.return_value = mock.MagicMock(is_failed=False,
                                                            is_succeeded=False)
        mock_Compiler.current_session.return_value = mock_compiler
        data = start(self.submission, self.user, self.client, self.token)
        self.assertEqual(data.status, IN_PROGRESS, "Processing is in progress")

        mock_compiler.compile.assert_called_once_with(
            self.content.identifier,
            self.content.checksum,
            self.token,
            'arXiv:submit/42 [cs.DL]',
            '/42/preview.pdf',
            force=True
        )

    @mock.patch(f'{process_source.__name__}.Compiler')
    def test_start_failed(self, mock_Compiler):
        """Compilation starts, but fails immediately."""
        mock_compiler = mock.MagicMock()
        mock_compiler.compile.return_value = mock.MagicMock(is_failed=True,
                                                            is_succeeded=False)
        mock_Compiler.current_session.return_value = mock_compiler
        with self.assertRaises(process_source.FailedToStart):
            start(self.submission, self.user, self.client, self.token)

        mock_compiler.compile.assert_called_once_with(
            self.content.identifier,
            self.content.checksum,
            self.token,
            'arXiv:submit/42 [cs.DL]',
            '/42/preview.pdf',
            force=True
        )


class TestCheckTeX(TeXFormatTestCase):
    """Test the status check for processing a TeX source."""

    @mock.patch(f'{process_source.__name__}.Compiler')
    def test_check_in_progress(self, mock_Compiler):
        """Check processing, still in progress"""
        mock_compiler = mock.MagicMock()
        mock_compilation = mock.MagicMock(is_succeeded=False,
                                          is_failed=False)
        mock_compiler.get_status.return_value = mock_compilation
        mock_Compiler.current_session.return_value = mock_compiler

        data = check(self.submission, self.user, self.client, self.token)
        self.assertEqual(data.status, IN_PROGRESS, "Processing is in progress")
        mock_compiler.get_status.assert_called_once_with(
            self.content.identifier,
            self.content.checksum,
            self.token
        )

    @mock.patch(f'{process_source.__name__}.Compiler')
    def test_check_nonexistant(self, mock_Compiler):
        """Check processing for no such compilation."""
        mock_compiler = mock.MagicMock()
        mock_compiler.get_status.side_effect = raise_NotFound
        mock_Compiler.current_session.return_value = mock_compiler
        data = check(self.submission, self.user, self.client, self.token)
        self.assertEqual(data.status, NOT_STARTED, 'Process not started')
        mock_compiler.get_status.assert_called_once_with(
            self.content.identifier,
            self.content.checksum,
            self.token
        )

    @mock.patch(f'{process_source.__name__}.Compiler')
    def test_check_exception(self, mock_Compiler):
        """Compiler service raises an exception"""
        mock_compiler = mock.MagicMock()
        mock_compiler.get_status.side_effect = RuntimeError
        mock_Compiler.current_session.return_value = mock_compiler
        with self.assertRaises(process_source.FailedToCheckStatus):
            check(self.submission, self.user, self.client, self.token)
        mock_compiler.get_status.assert_called_once_with(
            self.content.identifier,
            self.content.checksum,
            self.token
        )

    @mock.patch(f'{process_source.__name__}.Compiler')
    def test_check_failed(self, mock_Compiler):
        """Check processing, compilation failed."""
        mock_compiler = mock.MagicMock()
        mock_compilation = mock.MagicMock(is_succeeded=False,
                                          is_failed=True)
        mock_compiler.get_status.return_value = mock_compilation
        mock_Compiler.current_session.return_value = mock_compiler

        data = check(self.submission, self.user, self.client, self.token)
        self.assertEqual(data.status, FAILED, "Processing failed")
        mock_compiler.get_status.assert_called_once_with(
            self.content.identifier,
            self.content.checksum,
            self.token
        )

    @mock.patch(f'{process_source.__name__}.save')
    @mock.patch(f'{process_source.__name__}.PreviewService')
    @mock.patch(f'{process_source.__name__}.Compiler')
    def test_check_succeeded(self, mock_Compiler, mock_PreviewService,
                             mock_save):
        """Check processing, compilation succeeded."""
        mock_preview_service = mock.MagicMock()
        mock_preview_service.has_preview.return_value = False
        mock_PreviewService.current_session.return_value = mock_preview_service
        mock_compiler = mock.MagicMock()
        mock_compilation = mock.MagicMock(is_succeeded=True,
                                          is_failed=False)
        mock_compiler.get_status.return_value = mock_compilation
        stream = io.BytesIO(b'foobytes')
        mock_compiler.get_product.return_value = mock.MagicMock(
            stream=stream,
            checksum='chx'
        )
        mock_Compiler.current_session.return_value = mock_compiler

        mock_save.return_value = (self.submission, [])

        data = check(self.submission, self.user, self.client, self.token)

        self.assertEqual(data.status, SUCCEEDED, "Processing succeeded")
        mock_compiler.get_status.assert_called_once_with(
            self.content.identifier,
            self.content.checksum,
            self.token
        )
        mock_compiler.get_product.assert_called_once_with(
            self.content.identifier,
            self.content.checksum,
            self.token
        )
        mock_preview_service.deposit.assert_called_once_with(
            self.content.identifier,
            self.content.checksum,
            stream,
            self.token,
            content_checksum='chx',
            overwrite=True
        )
        mock_save.assert_called_once()
        args, kwargs = mock_save.call_args
        self.assertIsInstance(args[0], ConfirmSourceProcessed)
        self.assertEqual(kwargs['submission_id'],
                         self.submission.submission_id)

    @mock.patch(f'{process_source.__name__}.save')
    @mock.patch(f'{process_source.__name__}.PreviewService')
    @mock.patch(f'{process_source.__name__}.Compiler')
    def test_succeeded_preview_shipped_not_marked(self, mock_Compiler,
                                                  mock_PreviewService,
                                                  mock_save):
        """Preview already shipped, but submission not updated."""
        mock_preview_service = mock.MagicMock()
        mock_preview_service.has_preview.return_value = True
        mock_PreviewService.current_session.return_value = mock_preview_service
        mock_compiler = mock.MagicMock()
        mock_compilation = mock.MagicMock(is_succeeded=True,
                                          is_failed=False)
        mock_compiler.get_status.return_value = mock_compilation
        stream = io.BytesIO(b'foobytes')
        mock_compiler.get_product.return_value = mock.MagicMock(stream=stream,
                                                                checksum='chx')
        mock_Compiler.current_session.return_value = mock_compiler

        mock_save.return_value = (self.submission, [])

        data = check(self.submission, self.user, self.client, self.token)

        self.assertEqual(data.status, SUCCEEDED, "Processing succeeded")

        mock_compiler.get_status.assert_called_once_with(
            self.content.identifier,
            self.content.checksum,
            self.token
        )

        mock_compiler.get_product.assert_called_once_with(
            self.content.identifier,
            self.content.checksum,
            self.token
        )
        mock_preview_service.deposit.assert_called_once_with(
            self.content.identifier,
            self.content.checksum,
            stream,
            self.token,
            content_checksum='chx',
            overwrite=True
        )

        mock_save.assert_called_once()
        args, kwargs = mock_save.call_args
        self.assertIsInstance(args[0], ConfirmSourceProcessed)
        self.assertEqual(kwargs['submission_id'],
                         self.submission.submission_id)

    @mock.patch(f'{process_source.__name__}.save')
    @mock.patch(f'{process_source.__name__}.PreviewService')
    @mock.patch(f'{process_source.__name__}.Compiler')
    def test_succeeded_preview_shipped_and_marked(self, mock_Compiler,
                                                  mock_PreviewService,
                                                  mock_save):
        """Preview already shipped and submission is up to date."""
        self.submission.preview = mock.MagicMock(
            source_id=self.content.identifier,
            checksum=self.content.checksum,
            preview_checksum='chx'
        )
        self.submission.is_source_processed = True

        mock_preview_service = mock.MagicMock()
        mock_preview_service.has_preview.return_value = True
        mock_PreviewService.current_session.return_value = mock_preview_service
        mock_compiler = mock.MagicMock()
        mock_compilation = mock.MagicMock(is_succeeded=True,
                                          is_failed=False)
        mock_compiler.get_status.return_value = mock_compilation
        stream = io.BytesIO(b'foobytes')
        mock_compiler.get_product.return_value = mock.MagicMock(stream=stream,
                                                                checksum='chx')
        mock_Compiler.current_session.return_value = mock_compiler

        mock_save.return_value = (self.submission, [])

        data = check(self.submission, self.user, self.client, self.token)

        self.assertEqual(data.status, SUCCEEDED, "Processing succeeded")

        mock_compiler.get_status.assert_not_called()
        mock_compiler.get_product.assert_not_called()
        mock_preview_service.deposit.assert_not_called()
        mock_save.assert_not_called()

    @mock.patch(f'{process_source.__name__}.save')
    @mock.patch(f'{process_source.__name__}.PreviewService')
    @mock.patch(f'{process_source.__name__}.Compiler')
    def test_check_succeeded_save_error(self, mock_Compiler,
                                        mock_PreviewService,
                                        mock_save):
        """Compilation succeeded, but could not save event."""
        mock_preview_service = mock.MagicMock()
        mock_PreviewService.current_session.return_value = mock_preview_service
        mock_compiler = mock.MagicMock()
        mock_compilation = mock.MagicMock(is_succeeded=True,
                                          is_failed=False)
        mock_compiler.get_status.return_value = mock_compilation
        stream = io.BytesIO(b'foobytes')
        mock_compiler.get_product.return_value = mock.MagicMock(stream=stream,
                                                                checksum='chx')
        mock_Compiler.current_session.return_value = mock_compiler

        mock_save.side_effect = SaveError

        with self.assertRaises(process_source.FailedToCheckStatus):
            check(self.submission, self.user, self.client, self.token)

        mock_compiler.get_status.assert_called_once_with(
            self.content.identifier,
            self.content.checksum,
            self.token
        )
        mock_compiler.get_product.assert_called_once_with(
            self.content.identifier,
            self.content.checksum,
            self.token
        )
        mock_preview_service.deposit.assert_called_once_with(
            self.content.identifier,
            self.content.checksum,
            stream,
            self.token,
            content_checksum='chx',
            overwrite=True
        )
        mock_save.assert_called_once()
        args, kwargs = mock_save.call_args
        self.assertIsInstance(args[0], ConfirmSourceProcessed)
        self.assertEqual(kwargs['submission_id'],
                         self.submission.submission_id)