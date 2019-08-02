"""Tests for :mod:`agent.services.filesystem`."""

import docker
import io
import os
import tarfile
import tempfile
import time
from base64 import urlsafe_b64encode
from hashlib import md5
from unittest import TestCase

from flask import Flask

from . import Filesystem, ValidationFailed


class TestFilesystemIntegration(TestCase):
    """Integration tests for legacy filesystem service."""

    __test__ = bool(int(os.environ.get('WITH_INTEGRATION', '0')))

    @classmethod
    def setUpClass(cls):
        """Start up the filesystem service."""
        cls.JWT_SECRET = 'foosecret'

        # Legacy filesystem will mount this, so we can inspect what happens
        # behind the curtain.
        cls.VOLUME = tempfile.mkdtemp()
        print(cls.VOLUME)

        os.environ['JWT_SECRET'] = cls.JWT_SECRET
        client = docker.from_env()
        client.images.pull(f'arxiv/{Filesystem.SERVICE}',
                           tag=Filesystem.VERSION)
        cls.filesystem = client.containers.run(
            f'arxiv/{Filesystem.SERVICE}:{Filesystem.VERSION}',
            detach=True,
            environment={
                'JWT_SECRET': cls.JWT_SECRET,
                'LOGLEVEL': 10,
                'LEGACY_FILESYSTEM_ROOT': '/data'
            },
            volumes={cls.VOLUME: {'bind': '/data', 'mode': 'rw'}},
            ports={'8000/tcp': 8021}
        )
        time.sleep(2)

    @classmethod
    def tearDownClass(cls):
        """Stop and remove the filesystem service."""
        cls.filesystem.kill()
        cls.filesystem.remove()

    def setUp(self):
        """Create a Flask app for context."""
        self.app = Flask('foo')
        self.app.config.update({
            'FILESYSTEM_ENDPOINT': 'http://localhost:8021'
        })
        Filesystem.init_app(self.app)

    def test_get_status(self):
        """Get the status endpoint."""
        with self.app.app_context():
            fs = Filesystem.current_session()
            self.assertDictEqual(fs.get_status(), {})

    def test_is_available(self):
        """Get the status endpoint."""
        with self.app.app_context():
            fs = Filesystem.current_session()
            self.assertTrue(fs.is_available())

    def test_does_source_exist_nonexistant(self):
        """Check for a source that does not exist."""
        with self.app.app_context():
            fs = Filesystem.current_session()
            self.assertFalse(fs.does_source_exist(1234))

    def test_does_preview_exist_nonexistant(self):
        """Check for a preview that does not exist."""
        with self.app.app_context():
            fs = Filesystem.current_session()
            self.assertFalse(fs.does_source_exist(1234))

    def test_deposit_preview(self):
        """Deposit a preview successfully."""
        with self.app.app_context():
            fs = Filesystem.current_session()
            self.assertFalse(fs.does_preview_exist(123567))

            content = io.BytesIO(b'fake pdf content')
            self.assertIsNone(
                fs.deposit_preview(123567, content, 'bNmNEmoWNzA6LEaKswzI6w==')
            )

            self.assertTrue(fs.does_preview_exist(123567))

        # Verify content on disk.
        pdf_path = os.path.join(self.VOLUME, '1235', '123567', '123567.pdf')
        self.assertTrue(os.path.exists(pdf_path),
                        'Preview is deposited in the correct location')
        content.seek(0)
        with open(pdf_path, 'rb') as f:
            self.assertEqual(f.read(), content.read(),
                             'Content was transferred with fidelity')

    def test_deposit_preview_validation_fails(self):
        """Deposit a preview with failed checksum validation."""
        with self.app.app_context():
            fs = Filesystem.current_session()
            content = io.BytesIO(b'fake pdf content')
            with self.assertRaises(ValidationFailed):
                fs.deposit_preview(1236, content, 'cNmNEmoWNzA6LEaKswzI6w==')

    def test_deposit_source(self):
        """Deposit a source package successfully."""
        with self.app.app_context():
            fs = Filesystem.current_session()
            self.assertFalse(fs.does_source_exist(223567))

            _, content_path = tempfile.mkstemp(suffix='.pdf')
            with open(content_path, 'wb') as f:
                f.write(b'fake pdf content')

            _, source_path = tempfile.mkstemp(suffix='.tar.gz')
            with tarfile.open(source_path, "w:gz") as tf:
                with open(content_path, 'rb') as f:
                    info = tarfile.TarInfo('foo.pdf')
                    f.seek(0, io.SEEK_END)
                    info.size = f.tell()    # Must set size here.
                    f.seek(0, io.SEEK_SET)
                    tf.addfile(info, f)

            with open(source_path, 'rb') as f:
                chx = urlsafe_b64encode(md5(f.read()).digest()).decode('utf-8')
                f.seek(0)
                self.assertIsNone(fs.deposit_source(223567, f, chx))

            self.assertTrue(fs.does_source_exist(223567))


        # Verify content on disk.
        legacy_source_path = os.path.join(
            self.VOLUME, '2235', '223567', '223567.tar.gz'
        )
        legacy_content_path = os.path.join(
            self.VOLUME, '2235', '223567', 'src', 'foo.pdf'
        )
        self.assertTrue(os.path.exists(legacy_source_path),
                        'Source is deposited in the correct location')
        self.assertTrue(os.path.exists(legacy_content_path),
                        'Source content is deposited in the correct location')

        with open(legacy_source_path, 'rb') as f:
            with open(source_path, 'rb') as g:
                self.assertEqual(f.read(), g.read(),
                                'Content was transferred with fidelity')
        # content.seek(0)
        with open(legacy_content_path, 'rb') as f:
            with open(content_path, 'rb') as g:
                self.assertEqual(f.read(), g.read(),
                                'Content was transferred with fidelity')



