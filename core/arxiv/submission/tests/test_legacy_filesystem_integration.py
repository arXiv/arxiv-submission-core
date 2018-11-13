"""Tests for :mod:`arxiv.submission.services.filesystem`."""

from unittest import TestCase, mock
import os
import tempfile
from ..services import filesystem

data_path = os.path.join(os.path.split(os.path.abspath(__file__))[0], 'data')


class TestStoreSource(TestCase):
    """Deposit source content and compilation product on the filesystem."""

    def setUp(self):
        """We have a source package, PDF, and source log."""
        self.submission_id = 12345678
        self.source_path = os.path.join(data_path, '12345678.tar.gz')
        self.pdf_path = os.path.join(data_path, '12345678.pdf')
        self.log_path = os.path.join(data_path, 'source.log')
        self.legacy_root = tempfile.mkdtemp()

    @mock.patch(f'{filesystem.__name__}.store.current_app')
    def test_deposit(self, mock_app):
        """Deposit a source package, PDF, and source log file."""
        dir_mode = 17917
        file_mode = 33204
        uid = os.geteuid()
        gid = os.getegid()
        mock_app.config = {
            'LEGACY_FILESYSTEM_ROOT': self.legacy_root,
            'LEGACY_FILESYSTEM_SOURCE_DIR_MODE': dir_mode,
            'LEGACY_FILESYSTEM_SOURCE_MODE': file_mode,
            'LEGACY_FILESYSTEM_SOURCE_UID': uid,
            'LEGACY_FILESYSTEM_SOURCE_GID': gid
        }
        filesystem.store_source(self.submission_id, self.source_path,
                                self.pdf_path, self.log_path)

        sbm_dir = os.path.join(self.legacy_root,
                               str(self.submission_id)[:4],
                               str(self.submission_id))
        self.assertTrue(os.path.exists(sbm_dir),
                        "A directory is created for the submission content,")
        self.assertTrue(os.path.exists(os.path.join(sbm_dir, "src")),
                        "and a src directory is created inside of that.")
        self.assertTrue(os.path.exists(os.path.join(sbm_dir, "source.log")),
                        "The source.log is added to the submission directory,")
        self.assertTrue(
            os.path.exists(os.path.join(sbm_dir, f"{self.submission_id}.pdf")),
            "along with the compiled PDF."
        )

        for path, dirs, files in os.walk(sbm_dir):
            for fname in files:
                s = os.stat(os.path.join(path, fname))
                self.assertEqual(s.st_mode, file_mode,
                                 "Permissions are set on each file.")
                self.assertEqual(s.st_uid, uid, "The uid is set on each file.")
                self.assertEqual(s.st_gid, gid, "The gid is set on each file.")
            for dname in dirs:
                s = os.stat(os.path.join(path, dname))
                self.assertEqual(s.st_mode, dir_mode,
                                 "Permissions are set on each dir.")
                self.assertEqual(s.st_uid, uid, "The uid is set on each dir.")
                self.assertEqual(s.st_gid, gid, "The gid is set on each dir.")

    @mock.patch(f'{filesystem.__name__}.store.current_app')
    def test_deposit_without_config(self, mock_app):
        """Attempt to deposit without configuring the application."""
        mock_app.config = {}    # Whoops!
        with self.assertRaises(filesystem.ConfigurationError):
            filesystem.store_source(self.submission_id, self.source_path,
                                    self.pdf_path, self.log_path)
