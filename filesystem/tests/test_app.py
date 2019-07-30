"""Tests for :mod:`arxiv.submission.services.filesystem`."""

from unittest import TestCase, mock
from http import HTTPStatus
import os
import tempfile


from filesystem.factory import create_app
from filesystem import store

data_path = os.path.join(os.path.split(os.path.abspath(__file__))[0], 'data')


class TestBase(TestCase):
    """Deposit source content and compilation product on the filesystem."""

    def setUp(self):
        """We have a source package, PDF, and source log."""
        self.submission_id = 12345678
        self.source_file = os.path.join(data_path, '12345678.tar.gz')
        self.pdf_file = os.path.join(data_path, '12345678.pdf')
        self.root = tempfile.mkdtemp()

        self.dir_mode = 17917
        self.file_mode = 33204
        self.uid = os.geteuid()
        self.gid = os.getegid()

        self.app = create_app()
        self.app.config.update({
            'LEGACY_FILESYSTEM_ROOT': self.root,
            'LEGACY_FILESYSTEM_SOURCE_DIR_MODE': self.dir_mode,
            'LEGACY_FILESYSTEM_SOURCE_MODE': self.file_mode,
            'LEGACY_FILESYSTEM_SOURCE_UID': self.uid,
            'LEGACY_FILESYSTEM_SOURCE_GID': self.gid,
            'LEGACY_FILESYSTEM_SOURCE_PREFIX': 'src'
        })
        self.client = self.app.test_client()


class TestCheckSourceExists(TestBase):
    """Test support for HEAD requests to check if source package exists."""

    def test_existant_source(self):
        """A source package already exists."""
        submission_id = 1234567891
        with self.app.app_context():
            package_path = store._source_package_path(submission_id)
            os.makedirs(os.path.split(package_path)[0])
            with open(package_path, 'wb') as f:
                f.write(b'')
            response = self.client.head(f'/{submission_id}/source')
        self.assertEqual(response.status_code, HTTPStatus.OK, 'Returns 200 OK')
        self.assertIn('ETag', response.headers)
        self.assertEqual(response.headers['ETag'], '1B2M2Y8AsgTpgAmY7PhCfg==')

    def test_nonexistant_source(self):
        """A source package does not exist."""
        with self.app.app_context():
            response = self.client.head('/12345/source')
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND,
                         'Returns 404 Not Found')


class TestDepositPreview(TestBase):
    """Test depositing a PDF preview."""

    def test_deposit_with_bad_id(self):
        """Deposit a preview with an ID that is not an integer."""
        submission_id = 'qwerty'
        with open(self.pdf_file, 'rb') as f:
            with self.app.app_context():
                response = self.client.post(f'/{submission_id}/preview',
                                            data=f)
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND,
                         'Returns 404 Not Found')

    def test_deposit_preview(self):
        """Deposit a PDF preview."""
        submission_id = 123456
        with open(self.pdf_file, 'rb') as f:
            with self.app.app_context():
                response = self.client.post(f'/{submission_id}/preview',
                                            data=f)
        self.assertEqual(response.status_code, HTTPStatus.CREATED,
                         'Returns 201 Created')

        self.assertIn('123456.pdf',
                      os.listdir(os.path.join(self.root, '1234', '123456')),
                      'Preview ends up in the right location')
        self.assertEqual(response.headers['ETag'], '6OJd0ylj4j-HRNSZpWDJig==',
                         'Preview checksum is included in ETag response'
                         ' header')


class TestDepositSource(TestBase):
    """Test depositing a source package."""

    def test_deposit_with_bad_id(self):
        """Deposit a source package with an ID that is not an integer."""
        submission_id = 'qwerty'
        with open(self.source_file, 'rb') as f:
            with self.app.app_context():
                response = self.client.post(f'/{submission_id}/source', data=f)
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND,
                         'Returns 404 Not Found')

    def test_deposit_source(self):
        """Deposit a source package."""
        submission_id = 123456
        with open(self.source_file, 'rb') as f:
            with self.app.app_context():
                response = self.client.post(f'/{submission_id}/source', data=f)
        self.assertEqual(response.status_code, HTTPStatus.CREATED,
                         'Returns 201 Created')

        self.assertListEqual(
            os.listdir(os.path.join(self.root, '1234', '123456')),
            ['123456.tar.gz', 'src'],
            'Source package ends up in the right location'
        )
        self.assertListEqual(
            os.listdir(os.path.join(self.root, '1234', '123456', 'src')),
            [
                'agn_lumhist.ps',
                'agn_spectra.ps_page_1',
                'agn_spectra.ps_page_2',
                'agn_spectra.ps_page_3',
                'agn_spectra.ps_page_4',
                'chip_images',
                'draft.tex',
                'eccentricity.ps',
                'igm_spectra.ps_page_1',
                'igm_spectra.ps_page_2',
                'igm_spectra.ps_page_3',
                'ism_spectra.ps_page_1',
                'ism_spectra.ps_page_2',
                'ism_spectra.ps_page_3',
                'optical_alignment.ps',
                'radio_alignment_igm.ps',
                'radio_alignment_ism.ps'
            ],
            'Source files end up in the right place.'
        )
        self.assertEqual(response.headers['ETag'], 'kdvzx8Zb1brWshPG_o7s4w==',
                         'Source package checksum is included in ETag response'
                         ' header')


class TestCheckPreviewExists(TestBase):
    """Test support for HEAD requests to check if preview exists."""

    def test_existant_preview(self):
        """A preview already exists."""
        submission_id = 1234567891
        with self.app.app_context():
            preview_path = store._preview_path(submission_id)
            os.makedirs(os.path.split(preview_path)[0])
            with open(preview_path, 'wb') as f:
                f.write(b'')
            response = self.client.head(f'/{submission_id}/preview')
        self.assertEqual(response.status_code, HTTPStatus.OK, 'Returns 200 OK')
        self.assertIn('ETag', response.headers)
        self.assertEqual(response.headers['ETag'], '1B2M2Y8AsgTpgAmY7PhCfg==')

    def test_nonexistant_preview(self):
        """A preview does not exist."""
        with self.app.app_context():
            response = self.client.head('/12345/preview')
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND,
                         'Returns 404 Not Found')