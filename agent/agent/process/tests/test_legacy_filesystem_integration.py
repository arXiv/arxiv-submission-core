"""Tests for :mod:`.process.legacy_filesystem_integration`."""

import os
from unittest import TestCase, mock
from datetime import datetime, timedelta
from pytz import UTC
import copy
from http import HTTPStatus as status

from arxiv.integration.api import status, exceptions
from arxiv.submission.domain.event import SetUploadPackage, \
    UpdateUploadPackage, ConfirmCompiledPreview
from arxiv.submission.domain.agent import Agent, User
from arxiv.submission.domain.flag import Flag, MetadataFlag
from arxiv.submission.domain.submission import Submission, SubmissionContent, \
    SubmissionMetadata, Classification, Compilation, Hold

from .. import Failed, Recoverable
from .. import legacy_filesystem_integration as lfsi
from .. import size_limits
from ...domain import Trigger
from ...factory import create_app
from ...services import filesystem
from .util import raise_http_exception

os.environ['JWT_SECRET'] = 'foosecret'


class TestCopySourceToLegacy(TestCase):
    """Test :class:`.CopySourceToLegacy`."""

    def setUp(self):
        """We have a submission."""
        self.checksum = 'bar=='
        self.submission_id = 2347441
        self.creator = User(native_id=1234, email='something@else.com')
        self.submission = Submission(
            submission_id=self.submission_id,
            creator=self.creator,
            owner=self.creator,
            created=datetime.now(UTC),
            source_content=SubmissionContent(
                identifier=1234,
                checksum=self.checksum,
                uncompressed_size=5_000,
                compressed_size=2_000
            )
        )
        self.event = SetUploadPackage(creator=self.creator)
        self.process = lfsi.CopySourceToLegacy(self.submission.submission_id)

    @mock.patch(f'{lfsi.__name__}.filesystem.Filesystem')
    @mock.patch(f'{lfsi.__name__}.filemanager.Filemanager')
    def test_source_info_missing(self, MockFilemanager, MockFilesystem):
        """The submission does not have a source package set."""
        submission = Submission(
            submission_id=2347441,
            creator=self.creator,
            owner=self.creator,
            created=datetime.now(UTC)
        )

        mock_filemanager = mock.MagicMock()
        mock_filemanager.get_source_package.return_value \
            = (mock.MagicMock, self.checksum)
        mock_filesystem = mock.MagicMock()
        MockFilemanager.current_session.return_value = mock_filemanager
        MockFilesystem.current_session.return_value = mock_filesystem

        trigger = Trigger(event=self.event, actor=self.creator,
                          before=submission, after=submission)

        with self.assertRaises(Failed):
            self.process.copy_source_content(None, trigger, mock.MagicMock())

    @mock.patch(f'{lfsi.__name__}.filesystem.Filesystem')
    @mock.patch(f'{lfsi.__name__}.filemanager.Filemanager')
    def test_source_checksum_not_match(self, MockFilemanager, MockFilesystem):
        """The submission source checksum does not match the FM checksum."""
        mock_filemanager = mock.MagicMock()
        mock_filemanager.get_source_package.return_value \
            = (mock.MagicMock, 'foo==')
        mock_filesystem = mock.MagicMock()
        MockFilemanager.current_session.return_value = mock_filemanager
        MockFilesystem.current_session.return_value = mock_filesystem

        trigger = Trigger(event=self.event, actor=self.creator,
                          before=self.submission, after=self.submission)

        with self.assertRaises(Failed):
            self.process.copy_source_content(None, trigger, mock.MagicMock())
        self.assertEqual(mock_filesystem.deposit_source.call_count, 0,
                         'Filesystem integration is not called')

    @mock.patch(f'{lfsi.__name__}.filesystem.Filesystem')
    @mock.patch(f'{lfsi.__name__}.filemanager.Filemanager')
    def test_fm_not_available(self, MockFilemanager, MockFilesystem):
        """The filemanager service is not available."""
        mock_filemanager = mock.MagicMock()
        mock_filemanager.get_source_package.side_effect = \
            raise_http_exception(exceptions.RequestFailed,
                                 status.INTERNAL_SERVER_ERROR)
        mock_filesystem = mock.MagicMock()
        MockFilemanager.current_session.return_value = mock_filemanager
        MockFilesystem.current_session.return_value = mock_filesystem

        trigger = Trigger(event=self.event, actor=self.creator,
                          before=self.submission, after=self.submission)

        with self.assertRaises(Recoverable):
            self.process.copy_source_content(None, trigger, mock.MagicMock())
        self.assertEqual(mock_filesystem.deposit_source.call_count, 0,
                         'Filesystem integration is not called')

    @mock.patch(f'{lfsi.__name__}.filesystem.Filesystem')
    @mock.patch(f'{lfsi.__name__}.filemanager.Filemanager')
    def test_fm_not_authorized(self, MockFilemanager, MockFilesystem):
        """We are not authorized to access this resource."""
        mock_filemanager = mock.MagicMock()
        mock_filemanager.get_source_package.side_effect = \
            raise_http_exception(exceptions.RequestForbidden, status.FORBIDDEN)
        mock_filesystem = mock.MagicMock()
        MockFilemanager.current_session.return_value = mock_filemanager
        MockFilesystem.current_session.return_value = mock_filesystem

        trigger = Trigger(event=self.event, actor=self.creator,
                          before=self.submission, after=self.submission)

        with self.assertRaises(Failed):
            self.process.copy_source_content(None, trigger, mock.MagicMock())
        self.assertEqual(mock_filesystem.deposit_source.call_count, 0,
                         'Filesystem integration is not called')

    @mock.patch(f'{lfsi.__name__}.filesystem.Filesystem')
    @mock.patch(f'{lfsi.__name__}.filemanager.Filemanager')
    def test_filesystem_not_available(self, MockFilemanager, MockFilesystem):
        """The filesystem shim service is not available."""
        mock_filemanager = mock.MagicMock()
        mock_filemanager.get_source_package.return_value = \
            (mock.MagicMock, self.checksum)
        mock_filesystem = mock.MagicMock()
        mock_filesystem.deposit_source.side_effect = \
            raise_http_exception(exceptions.RequestFailed,
                                 status.INTERNAL_SERVER_ERROR)
        MockFilemanager.current_session.return_value = mock_filemanager
        MockFilesystem.current_session.return_value = mock_filesystem

        trigger = Trigger(event=self.event, actor=self.creator,
                          before=self.submission, after=self.submission)

        with self.assertRaises(Recoverable):
            self.process.copy_source_content(None, trigger, mock.MagicMock())
        self.assertEqual(mock_filesystem.deposit_source.call_count, 1,
                         'Filesystem integration is called')

    @mock.patch(f'{lfsi.__name__}.filesystem.Filesystem')
    @mock.patch(f'{lfsi.__name__}.filemanager.Filemanager')
    def test_integrity_check_fails(self, MockFilemanager, MockFilesystem):
        """The source is deposited, but received checksum does not match."""
        mock_filemanager = mock.MagicMock()
        mock_reader = mock.MagicMock()
        mock_filemanager.get_source_package.return_value = \
            (mock_reader, self.checksum)
        mock_filesystem = mock.MagicMock()
        mock_filesystem.deposit_source.side_effect \
            = filesystem.ValidationFailed
        MockFilemanager.current_session.return_value = mock_filemanager
        MockFilesystem.current_session.return_value = mock_filesystem

        trigger = Trigger(event=self.event, actor=self.creator,
                          before=self.submission, after=self.submission)

        with self.assertRaises(Recoverable):
            self.process.copy_source_content(None, trigger, mock.MagicMock())
        self.assertEqual(mock_filesystem.deposit_source.call_count, 1,
                         'Filesystem integration is called')
        mock_filesystem.deposit_source.assert_called_with(2347441, mock_reader,
                                                          self.checksum)

    @mock.patch(f'{lfsi.__name__}.filesystem.Filesystem')
    @mock.patch(f'{lfsi.__name__}.filemanager.Filemanager')
    def test_deposit_source(self, MockFilemanager, MockFilesystem):
        """The source is deposited successfully."""
        mock_filemanager = mock.MagicMock()
        mock_reader = mock.MagicMock()
        mock_filemanager.get_source_package.return_value = \
            (mock_reader, self.checksum)
        mock_filesystem = mock.MagicMock()
        MockFilemanager.current_session.return_value = mock_filemanager
        MockFilesystem.current_session.return_value = mock_filesystem

        trigger = Trigger(event=self.event, actor=self.creator,
                          before=self.submission, after=self.submission)

        self.process.copy_source_content(None, trigger, mock.MagicMock())
        self.assertEqual(mock_filesystem.deposit_source.call_count, 1,
                         'Filesystem integration is called')
        mock_filesystem.deposit_source.assert_called_with(self.submission_id,
                                                          mock_reader,
                                                          self.checksum)


class TestCopyPDFPreviewToLegacy(TestCase):
    """Test :class:`.CopyPDFPreviewToLegacy`."""

    def setUp(self):
        """We have a submission."""
        self.checksum = 'bar=='
        self.submission_id = 2347441
        self.creator = User(native_id=1234, email='something@else.com')
        self.submission = Submission(
            submission_id=self.submission_id,
            creator=self.creator,
            owner=self.creator,
            created=datetime.now(UTC),
            source_content=SubmissionContent(
                identifier=1234,
                checksum=self.checksum,
                uncompressed_size=5_000,
                compressed_size=2_000
            )
        )
        self.event = ConfirmCompiledPreview(creator=self.creator)
        self.process = lfsi.CopyPDFPreviewToLegacy(self.submission_id)

    @mock.patch(f'{lfsi.__name__}.filesystem.Filesystem')
    @mock.patch(f'{lfsi.__name__}.preview.Preview')
    def test_source_info_missing(self, MockPreview, MockFilesystem):
        """The submission does not have a source package set."""
        submission = Submission(
            submission_id=2347441,
            creator=self.creator,
            owner=self.creator,
            created=datetime.now(UTC)
        )

        mock_preview = mock.MagicMock()
        mock_filesystem = mock.MagicMock()
        MockPreview.current_session.return_value = mock_preview
        MockFilesystem.current_session.return_value = mock_filesystem

        trigger = Trigger(event=self.event, actor=self.creator,
                          before=submission, after=submission)

        with self.assertRaises(Failed):
            self.process.copy_preview(None, trigger, mock.MagicMock())
        self.assertEqual(mock_preview.get_preview.call_count, 0,
                         'Preview is not retrieved')
        self.assertEqual(mock_filesystem.deposit_preview.call_count, 0,
                         'Filesystem is not invoked')

    @mock.patch(f'{lfsi.__name__}.filesystem.Filesystem')
    @mock.patch(f'{lfsi.__name__}.preview.Preview')
    def test_preview_not_available(self, MockPreview, MockFilesystem):
        """The preview service is not available."""
        mock_preview = mock.MagicMock()
        mock_preview.get_preview.side_effect = \
            raise_http_exception(exceptions.RequestFailed,
                                 status.INTERNAL_SERVER_ERROR)
        mock_filesystem = mock.MagicMock()
        MockPreview.current_session.return_value = mock_preview
        MockFilesystem.current_session.return_value = mock_filesystem

        trigger = Trigger(event=self.event, actor=self.creator,
                          before=self.submission, after=self.submission)

        with self.assertRaises(Recoverable):
            self.process.copy_preview(None, trigger, mock.MagicMock())
        self.assertEqual(mock_filesystem.deposit_preview.call_count, 0,
                         'Filesystem integration is not called')

    @mock.patch(f'{lfsi.__name__}.filesystem.Filesystem')
    @mock.patch(f'{lfsi.__name__}.preview.Preview')
    def test_fm_not_authorized(self, MockPreview, MockFilesystem):
        """We are not authorized to access this resource."""
        mock_preview = mock.MagicMock()
        mock_preview.get_preview.side_effect = \
            raise_http_exception(exceptions.RequestForbidden, status.FORBIDDEN)
        mock_filesystem = mock.MagicMock()
        MockPreview.current_session.return_value = mock_preview
        MockFilesystem.current_session.return_value = mock_filesystem

        trigger = Trigger(event=self.event, actor=self.creator,
                          before=self.submission, after=self.submission)

        with self.assertRaises(Failed):
            self.process.copy_preview(None, trigger, mock.MagicMock())
        self.assertEqual(mock_filesystem.deposit_preview.call_count, 0,
                         'Filesystem integration is not called')

    @mock.patch(f'{lfsi.__name__}.filesystem.Filesystem')
    @mock.patch(f'{lfsi.__name__}.preview.Preview')
    def test_filesystem_not_available(self, MockPreview, MockFilesystem):
        """The filesystem shim service is not available."""
        mock_preview = mock.MagicMock()
        mock_preview.get_preview.return_value = (mock.MagicMock, self.checksum)
        mock_filesystem = mock.MagicMock()
        mock_filesystem.deposit_preview.side_effect = \
            raise_http_exception(exceptions.RequestFailed,
                                 status.INTERNAL_SERVER_ERROR)
        MockPreview.current_session.return_value = mock_preview
        MockFilesystem.current_session.return_value = mock_filesystem

        trigger = Trigger(event=self.event, actor=self.creator,
                          before=self.submission, after=self.submission)

        with self.assertRaises(Recoverable):
            self.process.copy_preview(None, trigger, mock.MagicMock())
        self.assertEqual(mock_filesystem.deposit_preview.call_count, 1,
                         'Filesystem integration is called')

    @mock.patch(f'{lfsi.__name__}.filesystem.Filesystem')
    @mock.patch(f'{lfsi.__name__}.preview.Preview')
    def test_integrity_check_fails(self, MockPreview, MockFilesystem):
        """The preview is deposited, but received checksum does not match."""
        mock_preview = mock.MagicMock()
        mock_reader = mock.MagicMock()
        mock_preview.get_preview.return_value = \
            (mock_reader, self.checksum)
        mock_filesystem = mock.MagicMock()
        mock_filesystem.deposit_preview.side_effect \
            = filesystem.ValidationFailed
        MockPreview.current_session.return_value = mock_preview
        MockFilesystem.current_session.return_value = mock_filesystem

        trigger = Trigger(event=self.event, actor=self.creator,
                          before=self.submission, after=self.submission)

        with self.assertRaises(Recoverable):
            self.process.copy_preview(None, trigger, mock.MagicMock())
        self.assertEqual(mock_filesystem.deposit_preview.call_count, 1,
                         'Filesystem integration is called')
        mock_filesystem.deposit_preview.assert_called_with(2347441,
                                                           mock_reader,
                                                           self.checksum)

    @mock.patch(f'{lfsi.__name__}.filesystem.Filesystem')
    @mock.patch(f'{lfsi.__name__}.preview.Preview')
    def test_deposited(self, MockPreview, MockFilesystem):
        """The preview is deposited."""
        mock_preview = mock.MagicMock()
        mock_reader = mock.MagicMock()
        mock_preview.get_preview.return_value = \
            (mock_reader, self.checksum)
        mock_filesystem = mock.MagicMock()
        MockPreview.current_session.return_value = mock_preview
        MockFilesystem.current_session.return_value = mock_filesystem

        trigger = Trigger(event=self.event, actor=self.creator,
                          before=self.submission, after=self.submission)

        self.process.copy_preview(None, trigger, mock.MagicMock())
        self.assertEqual(mock_filesystem.deposit_preview.call_count, 1,
                         'Filesystem integration is called')
        mock_filesystem.deposit_preview.assert_called_with(2347441,
                                                           mock_reader,
                                                           self.checksum)