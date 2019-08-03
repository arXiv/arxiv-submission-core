"""Integration tests for the preview service."""

import io
import os
import time
from unittest import TestCase
from flask import Flask
import docker

from .preview import PreviewService, AlreadyExists, exceptions


class TestPreviewIntegration(TestCase):
    """Integration tests for the preview service module."""

    __test__  = bool(int(os.environ.get('WITH_INTEGRATION', '0')))

    @classmethod
    def setUpClass(cls):
        """Start up the preview service, backed by localstack S3."""
        client = docker.from_env()
        image = f'arxiv/{PreviewService.SERVICE}'
        client.images.pull(image, tag=PreviewService.VERSION)
        cls.network = client.networks.create('test-preview-network')
        cls.localstack = client.containers.run(
            'atlassianlabs/localstack',
            detach=True,
            ports={'4572/tcp': 5572},
            network='test-preview-network',
            name='localstack',
            environment={'USE_SSL': 'true'}
        )
        cls.container = client.containers.run(
            f'{image}:{PreviewService.VERSION}',
            detach=True,
            network='test-preview-network',
            ports={'8000/tcp': 8889},
            environment={'S3_ENDPOINT': 'https://localstack:4572',
                         'S3_VERIFY': '0',
                         'NAMESPACE': 'test'}
        )
        time.sleep(5)

        cls.app = Flask('test')
        cls.app.config.update({
            'PREVIEW_SERVICE_HOST': 'localhost',
            'PREVIEW_SERVICE_PORT': '8889',
            'PREVIEW_PORT_8889_PROTO': 'http',
            'PREVIEW_VERIFY': False,
            'PREVIEW_ENDPOINT': 'http://localhost:8889'

        })
        PreviewService.init_app(cls.app)

    @classmethod
    def tearDownClass(cls):
        """Tear down the preview service and localstack."""
        cls.container.kill()
        cls.container.remove()
        cls.localstack.kill()
        cls.localstack.remove()
        cls.network.remove()

    def test_get_status(self):
        """Get the status endpoint."""
        with self.app.app_context():
            pv = PreviewService.current_session()
            self.assertEqual(pv.get_status(), {'iam': 'ok'})

    def test_is_available(self):
        """Poll for availability."""
        with self.app.app_context():
            pv = PreviewService.current_session()
            self.assertTrue(pv.is_available())

    def test_deposit_retrieve(self):
        """Deposit and retrieve a preview."""
        with self.app.app_context():
            pv = PreviewService.current_session()
            content = io.BytesIO(b'foocontent')
            source_id = 1234
            checksum = 'foochex=='
            token = 'footoken'
            preview = pv.deposit(source_id, checksum, content, token)
            self.assertEqual(preview.source_id, 1234)
            self.assertEqual(preview.source_checksum, 'foochex==')
            self.assertEqual(preview.preview_checksum,
                             '7b0ae08001dd093e79335b947f028b10')
            self.assertEqual(preview.size_bytes, 10)

            stream, preview_checksum = pv.get(source_id, checksum, token)
            self.assertEqual(stream.read(), b'foocontent')
            self.assertEqual(preview_checksum, preview.preview_checksum)

    def test_deposit_conflict(self):
        """Deposit the same preview twice."""
        with self.app.app_context():
            pv = PreviewService.current_session()
            content = io.BytesIO(b'foocontent')
            source_id = 1235
            checksum = 'foochex=='
            token = 'footoken'
            preview = pv.deposit(source_id, checksum, content, token)
            self.assertEqual(preview.source_id, 1235)
            self.assertEqual(preview.source_checksum, 'foochex==')
            self.assertEqual(preview.preview_checksum,
                             '7b0ae08001dd093e79335b947f028b10')
            self.assertEqual(preview.size_bytes, 10)

            with self.assertRaises(AlreadyExists):
                pv.deposit(source_id, checksum, content, token)

    def test_deposit_conflict_force(self):
        """Deposit the same preview twice and explicitly overwrite."""
        with self.app.app_context():
            pv = PreviewService.current_session()
            content = io.BytesIO(b'foocontent')
            source_id = 1236
            checksum = 'foochex=='
            token = 'footoken'
            preview = pv.deposit(source_id, checksum, content, token)
            self.assertEqual(preview.source_id, 1236)
            self.assertEqual(preview.source_checksum, 'foochex==')
            self.assertEqual(preview.preview_checksum,
                             '7b0ae08001dd093e79335b947f028b10')
            self.assertEqual(preview.size_bytes, 10)

            content = io.BytesIO(b'barcontent')
            preview = pv.deposit(source_id, checksum, content, token,
                                 overwrite=True)
            self.assertEqual(preview.source_id, 1236)
            self.assertEqual(preview.source_checksum, 'foochex==')
            self.assertEqual(preview.preview_checksum,
                             'b96f78bbfbb8c5f0c0de5715777e789e')
            self.assertEqual(preview.size_bytes, 10)

    def get_nonexistant_preview(self):
        """Try to get a non-existant preview."""
        with self.assertRaises(exceptions.NotFound):
            pv.get(9876, 'foochex==', 'footoken')