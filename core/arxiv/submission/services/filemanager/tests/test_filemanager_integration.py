import io
import os
import subprocess
import time
from unittest import TestCase, mock

import docker
from flask import Flask, Config
from werkzeug.datastructures import FileStorage

from arxiv.base.globals import get_application_config
from arxiv.integration.api import exceptions
from arxiv.users.auth import scopes
from arxiv.users.helpers import generate_token

from ..filemanager import Filemanager
from ....domain.uploads import Upload, FileStatus, FileError

mock_app = Flask('test')
mock_app.config.update({
    'FILEMANAGER_ENDPOINT': 'http://localhost:8003/filemanager/api',
    'FILEMANAGER_VERIFY': False
})
Filemanager.init_app(mock_app)


class TestFilemanagerIntegration(TestCase):

    __test__ = int(bool(os.environ.get('WITH_INTEGRATION', False)))

    @classmethod
    def setUpClass(cls):
        """Start up the file manager service."""
        print('starting file management service')
        client = docker.from_env()
        image = f'arxiv/{Filemanager.SERVICE}'
        # client.images.pull(image, tag=Filemanager.VERSION)

        cls.filemanager = client.containers.run(
            f'{image}:{Filemanager.VERSION}',
            detach=True,
            ports={'8000/tcp': 8003},
            environment={
                'NAMESPACE': 'test',
                'JWT_SECRET': 'foosecret'
            },
            command='/bin/bash -c "python bootstrap.py && uwsgi --ini /opt/arxiv/uwsgi.ini"'
        )

        time.sleep(5)

        os.environ['JWT_SECRET'] = 'foosecret'
        cls.token = generate_token('1', 'u@ser.com', 'theuser',
                                   scope=[scopes.WRITE_UPLOAD,
                                          scopes.READ_UPLOAD])

    @classmethod
    def tearDownClass(cls):
        """Tear down file management service once all tests have run."""
        cls.filemanager.kill()
        cls.filemanager.remove()

    def setUp(self):
        """Create a new app for config and context."""
        self.app = Flask('test')
        self.app.config.update({
            'FILEMANAGER_ENDPOINT': 'http://localhost:8003',
        })

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    def test_upload_package(self):
        """Upload a new package."""
        fm = Filemanager.current_session()
        fpath = os.path.join(os.path.split(os.path.abspath(__file__))[0],
                             'data', 'test.zip')
        pointer = FileStorage(open(fpath, 'rb'), filename='test.zip',
                              content_type='application/tar+gz')
        data = fm.upload_package(pointer, self.token)
        self.assertIsInstance(data, Upload)
        self.assertEqual(data.status, Upload.Status.ERRORS)
        self.assertEqual(data.lifecycle, Upload.LifecycleStates.ACTIVE)
        self.assertFalse(data.locked)

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    def test_upload_package_without_authorization(self):
        """Upload a new package without authorization."""
        fm = Filemanager.current_session()
        fpath = os.path.join(os.path.split(os.path.abspath(__file__))[0],
                             'data', 'test.zip')
        pointer = FileStorage(open(fpath, 'rb'), filename='test.zip',
                              content_type='application/tar+gz')
        token = generate_token('1', 'u@ser.com', 'theuser',
                               scope=[scopes.READ_UPLOAD])
        with self.assertRaises(exceptions.RequestForbidden):
            fm.upload_package(pointer, token)

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    def test_upload_package_without_authentication_token(self):
        """Upload a new package without an authentication token."""
        fm = Filemanager.current_session()
        fpath = os.path.join(os.path.split(os.path.abspath(__file__))[0],
                             'data', 'test.zip')
        pointer = FileStorage(open(fpath, 'rb'), filename='test.zip',
                              content_type='application/tar+gz')
        with self.assertRaises(exceptions.RequestUnauthorized):
            fm.upload_package(pointer, '')

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    def test_get_upload_status(self):
        """Get the status of an upload."""
        fm = Filemanager.current_session()
        fpath = os.path.join(os.path.split(os.path.abspath(__file__))[0],
                             'data', 'test.zip')
        pointer = FileStorage(open(fpath, 'rb'), filename='test.zip',
                              content_type='application/tar+gz')
        data = fm.upload_package(pointer, self.token)

        status = fm.get_upload_status(data.identifier, self.token)
        self.assertIsInstance(status, Upload)
        self.assertEqual(status.status, Upload.Status.ERRORS)
        self.assertEqual(status.lifecycle, Upload.LifecycleStates.ACTIVE)
        self.assertFalse(status.locked)

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    def test_get_upload_status_without_authorization(self):
        """Get the status of an upload without the right scope."""
        fm = Filemanager.current_session()
        fpath = os.path.join(os.path.split(os.path.abspath(__file__))[0],
                             'data', 'test.zip')
        pointer = FileStorage(open(fpath, 'rb'), filename='test.zip',
                              content_type='application/tar+gz')
        token = generate_token('1', 'u@ser.com', 'theuser',
                               scope=[scopes.WRITE_UPLOAD])
        data = fm.upload_package(pointer, self.token)

        with self.assertRaises(exceptions.RequestForbidden):
            fm.get_upload_status(data.identifier, token)

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    def test_get_upload_status_nacho_upload(self):
        """Get the status of someone elses' upload."""
        fm = Filemanager.current_session()
        fpath = os.path.join(os.path.split(os.path.abspath(__file__))[0],
                             'data', 'test.zip')
        pointer = FileStorage(open(fpath, 'rb'), filename='test.zip',
                              content_type='application/tar+gz')

        data = fm.upload_package(pointer, self.token)

        token = generate_token('2', 'other@ser.com', 'theotheruser',
                               scope=[scopes.READ_UPLOAD])
        with self.assertRaises(exceptions.RequestForbidden):
            fm.get_upload_status(data.identifier, token)

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    def test_add_file_to_upload(self):
        """Add a file to an existing upload workspace."""
        fm = Filemanager.current_session()

        fpath = os.path.join(os.path.split(os.path.abspath(__file__))[0],
                             'data', 'test.zip')
        pointer = FileStorage(open(fpath, 'rb'), filename='test.zip',
                              content_type='application/tar+gz')
        data = fm.upload_package(pointer, self.token)

        fpath2 = os.path.join(os.path.split(os.path.abspath(__file__))[0],
                              'data', 'test.txt')
        pointer2 = FileStorage(open(fpath2, 'rb'), filename='test.txt',
                               content_type='text/plain')

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    def test_pdf_only_upload(self):
        """Upload a PDF."""
        fm = Filemanager.current_session()

        fpath = os.path.join(os.path.split(os.path.abspath(__file__))[0],
                             'data', 'test.pdf')
        pointer = FileStorage(io.BytesIO(MINIMAL_PDF.encode('utf-8')),
                              filename='test.pdf',
                              content_type='application/pdf')
        data = fm.upload_package(pointer, self.token)
        upload_id = data.identifier
        content, source_chex, file_chex = fm.get_single_file(upload_id, self.token)
        self.assertEqual(source_chex, data.checksum)
        self.assertEqual(len(content.read()), len(MINIMAL_PDF.encode('utf-8')),
                         'Size of the original content is preserved')
        self.assertEqual(file_chex, 'Copxu8SRHajXOfeK8_1h7w==')


# From https://brendanzagaeski.appspot.com/0004.html
MINIMAL_PDF = """
%PDF-1.1
%¥±ë

1 0 obj
  << /Type /Catalog
     /Pages 2 0 R
  >>
endobj

2 0 obj
  << /Type /Pages
     /Kids [3 0 R]
     /Count 1
     /MediaBox [0 0 300 144]
  >>
endobj

3 0 obj
  <<  /Type /Page
      /Parent 2 0 R
      /Resources
       << /Font
           << /F1
               << /Type /Font
                  /Subtype /Type1
                  /BaseFont /Times-Roman
               >>
           >>
       >>
      /Contents 4 0 R
  >>
endobj

4 0 obj
  << /Length 55 >>
stream
  BT
    /F1 18 Tf
    0 0 Td
    (Hello World) Tj
  ET
endstream
endobj

xref
0 5
0000000000 65535 f
0000000018 00000 n
0000000077 00000 n
0000000178 00000 n
0000000457 00000 n
trailer
  <<  /Root 1 0 R
      /Size 5
  >>
startxref
565
%%EOF
"""