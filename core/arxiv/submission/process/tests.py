import io
from unittest import TestCase, mock

from arxiv.integration.api.exceptions import RequestFailed, NotFound

from ..domain import Submission, SubmissionContent, User, Client
from ..domain.event import ConfirmSourceProcessed
from . import process_source
from .. import SaveError
from .process_source import start, check, summarize, \
    SUCCEEDED, FAILED, IN_PROGRESS

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
                                         is_source_processed=False)
        self.user = mock.MagicMock(spec=User)
        self.client = mock.MagicMock(spec=Client)
        self.token = 'footoken'


class TestStartProcessingPDF(PDFFormatTest):
    """Test :const:`.PDFProcess`."""

    @mock.patch(f'{process_source.__name__}.PreviewService')
    @mock.patch(f'{process_source.__name__}.Filemanager')
    def test_start(self, mock_Filemanager, mock_PreviewService):
        """Start processing the PDF source."""
        mock_preview_service = mock.MagicMock()
        mock_PreviewService.current_session.return_value = mock_preview_service
        mock_filemanager = mock.MagicMock()
        stream = io.BytesIO(b'fakecontent')
        mock_filemanager.get_single_file.return_value = \
            stream, 'foochex==', 'barchex=='
        mock_Filemanager.current_session.return_value = mock_filemanager

        self.assertEqual(
            start(self.submission, self.user, self.client, self.token),
            IN_PROGRESS,
            "Processing is in progress"
        )
        mock_filemanager.get_single_file.assert_called_once_with(
            self.content.identifier,
            self.token
        )
        mock_preview_service.deposit.assert_called_once_with(
            self.content.identifier,
            self.content.checksum,
            stream,
            self.token,
            overwrite=True
        )

    @mock.patch(f'{process_source.__name__}.PreviewService')
    @mock.patch(f'{process_source.__name__}.Filemanager')
    def test_start_preview_fails(self, mock_Filemanager, mock_PreviewService):
        """Depositing the preview fails"""
        mock_preview_service = mock.MagicMock()
        mock_preview_service.deposit.side_effect = raise_RequestFailed
        mock_PreviewService.current_session.return_value = mock_preview_service
        mock_filemanager = mock.MagicMock()
        stream = io.BytesIO(b'fakecontent')
        mock_filemanager.get_single_file.return_value = \
            stream, 'foochex==', 'barchex=='
        mock_Filemanager.current_session.return_value = mock_filemanager

        with self.assertRaises(process_source.FailedToStart):
            start(self.submission, self.user, self.client, self.token)

        mock_filemanager.get_single_file.assert_called_once_with(
            self.content.identifier,
            self.token
        )
        mock_preview_service.deposit.assert_called_once_with(
            self.content.identifier,
            self.content.checksum,
            stream,
            self.token,
            overwrite=True
        )

    @mock.patch(f'{process_source.__name__}.PreviewService')
    @mock.patch(f'{process_source.__name__}.Filemanager')
    def test_start_filemanager_fails(self, mock_Filemanager,
                                     mock_PreviewService):
        """Retrieiving the PDF fails"""
        mock_preview_service = mock.MagicMock()
        mock_PreviewService.current_session.return_value = mock_preview_service
        mock_filemanager = mock.MagicMock()
        mock_filemanager.get_single_file.side_effect = raise_RequestFailed
        mock_Filemanager.current_session.return_value = mock_filemanager

        with self.assertRaises(process_source.FailedToStart):
            start(self.submission, self.user, self.client, self.token)

        mock_filemanager.get_single_file.assert_called_once_with(
            self.content.identifier,
            self.token
        )
        mock_preview_service.deposit.assert_not_called()


class TestCheckPDF(PDFFormatTest):
    """Test :const:`.PDFProcess`."""

    @mock.patch(f'{process_source.__name__}.save')
    @mock.patch(f'{process_source.__name__}.PreviewService')
    def test_check_successful(self, mock_PreviewService, mock_save):
        """Check status of processing the PDF source after successful start."""
        mock_preview_service = mock.MagicMock()
        mock_preview_service.has_preview.return_value = True
        mock_PreviewService.current_session.return_value = mock_preview_service
        self.assertEqual(
            check(self.submission, self.user, self.client, self.token),
            SUCCEEDED,
        )

        mock_preview_service.has_preview.assert_called_once_with(
            self.content.identifier,
            self.content.checksum,
            self.token
        )
        mock_save.assert_called_once()
        args, kwargs = mock_save.call_args
        self.assertIsInstance(args[0], ConfirmSourceProcessed)
        self.assertEqual(kwargs['submission_id'],
                         self.submission.submission_id)

    @mock.patch(f'{process_source.__name__}.save')
    @mock.patch(f'{process_source.__name__}.PreviewService')
    def test_check_failed(self, mock_PreviewService, mock_save):
        """Check status of processing the PDF source after failed transfer."""
        mock_preview_service = mock.MagicMock()
        mock_preview_service.has_preview.return_value = False
        mock_PreviewService.current_session.return_value = mock_preview_service
        self.assertEqual(
            check(self.submission, self.user, self.client, self.token),
            FAILED,
        )
        mock_preview_service.has_preview.assert_called_once_with(
            self.content.identifier,
            self.content.checksum,
            self.token
        )
        mock_save.assert_not_called()


class TestSummarizePDF(PDFFormatTest):
    """Test :const:`.PDFProcess`."""

    @mock.patch(f'{process_source.__name__}.PreviewService')
    def test_summarize_successful(self, mock_PreviewService):
        """Get summarization of processing the PDF."""
        mock_preview_service = mock.MagicMock()
        mock_preview = mock.MagicMock()
        mock_preview_service.get_metadata.return_value = mock_preview
        mock_PreviewService.current_session.return_value = mock_preview_service

        data = summarize(self.submission, self.user, self.client, self.token)

        self.assertEqual(data['preview'], mock_preview)
        mock_preview_service.get_metadata.assert_called_once_with(
            self.content.identifier,
            self.content.checksum,
            self.token
        )

    @mock.patch(f'{process_source.__name__}.PreviewService')
    def test_summarize_preview_unavailable(self, mock_PreviewService):
        """Preview service returns an error PDF."""
        mock_preview_service = mock.MagicMock()
        mock_preview_service.get_metadata.side_effect = raise_RequestFailed
        mock_PreviewService.current_session.return_value = mock_preview_service

        with self.assertRaises(process_source.FailedToGetResult):
            summarize(self.submission, self.user, self.client, self.token)

        mock_preview_service.get_metadata.assert_called_once_with(
            self.content.identifier,
            self.content.checksum,
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
                                         is_source_processed=False)
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
        self.assertEqual(
            start(self.submission, self.user, self.client, self.token),
            IN_PROGRESS,
            "Processing is in progress"
        )
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
        self.assertEqual(
            check(self.submission, self.user, self.client, self.token),
            IN_PROGRESS,
            "Processing is in progress"
        )
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
        with self.assertRaises(process_source.NoProcessToCheck):
            check(self.submission, self.user, self.client, self.token)
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
        self.assertEqual(
            check(self.submission, self.user, self.client, self.token),
            FAILED,
            "Processing failed"
        )
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
        mock_PreviewService.current_session.return_value = mock_preview_service
        mock_compiler = mock.MagicMock()
        mock_compilation = mock.MagicMock(is_succeeded=True,
                                          is_failed=False)
        mock_compiler.get_status.return_value = mock_compilation
        stream = io.BytesIO(b'foobytes')
        mock_compiler.get_product.return_value = mock.MagicMock(stream=stream,
                                                                checksum='chx')
        mock_Compiler.current_session.return_value = mock_compiler
        self.assertEqual(
            check(self.submission, self.user, self.client, self.token),
            SUCCEEDED,
            "Processing succeeded"
        )
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
            overwrite=True
        )
        mock_save.assert_called_once()
        args, kwargs = mock_save.call_args
        self.assertIsInstance(args[0], ConfirmSourceProcessed)
        self.assertEqual(kwargs['submission_id'],
                         self.submission.submission_id)



class TestSummarizeTeX(TeXFormatTestCase):
    """Test :const:`.TeXProcess`."""

    @mock.patch(f'{process_source.__name__}.Compiler')
    @mock.patch(f'{process_source.__name__}.PreviewService')
    def test_summarize_successful(self, mock_PreviewService, mock_Compiler):
        """Get summarization of processing the TeX."""
        mock_preview_service = mock.MagicMock()
        mock_preview = mock.MagicMock()
        mock_preview_service.get_metadata.return_value = mock_preview
        mock_PreviewService.current_session.return_value = mock_preview_service

        mock_compiler = mock.MagicMock()
        stream = io.BytesIO(b'foologoutput')
        mock_compiler.get_log.return_value = mock.MagicMock(stream=stream)
        mock_Compiler.current_session.return_value = mock_compiler

        data = summarize(self.submission, self.user, self.client, self.token)

        self.assertEqual(data['preview'], mock_preview)
        self.assertEqual(data['log_output'], 'foologoutput')
        mock_preview_service.get_metadata.assert_called_once_with(
            self.content.identifier,
            self.content.checksum,
            self.token
        )

    @mock.patch(f'{process_source.__name__}.Compiler')
    @mock.patch(f'{process_source.__name__}.PreviewService')
    def test_summarize_preview_unavailable(self, mock_PreviewService,
                                           mock_Compiler):
        """Preview service returns an error."""
        mock_preview_service = mock.MagicMock()
        mock_preview_service.get_metadata.side_effect = raise_RequestFailed
        mock_PreviewService.current_session.return_value = mock_preview_service

        mock_compiler = mock.MagicMock()
        stream = io.BytesIO(b'foologoutput')
        mock_compiler.get_log.return_value = mock.MagicMock(stream=stream)
        mock_Compiler.current_session.return_value = mock_compiler

        with self.assertRaises(process_source.FailedToGetResult):
            summarize(self.submission, self.user, self.client, self.token)

        mock_preview_service.get_metadata.assert_called_once_with(
            self.content.identifier,
            self.content.checksum,
            self.token
        )

    @mock.patch(f'{process_source.__name__}.Compiler')
    @mock.patch(f'{process_source.__name__}.PreviewService')
    def test_summarize_log_unavailable(self, mock_PreviewService,
                                       mock_Compiler):
        """Preview service returns an error."""
        mock_preview_service = mock.MagicMock()
        mock_PreviewService.current_session.return_value = mock_preview_service

        mock_compiler = mock.MagicMock()
        stream = io.BytesIO(b'foologoutput')
        mock_compiler.get_log.side_effect = raise_RequestFailed
        mock_Compiler.current_session.return_value = mock_compiler

        with self.assertRaises(process_source.FailedToGetResult):
            summarize(self.submission, self.user, self.client, self.token)