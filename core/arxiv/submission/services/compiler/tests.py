"""Tests for :mod:`.compiler`."""

from unittest import TestCase, mock

from flask import Flask

from arxiv.integration.api import status, exceptions

from . import compiler
from ... import domain


class TestRequestCompilation(TestCase):
    """Tests for :mod:`compiler.compile` with mocked responses."""

    def setUp(self):
        """Create an app for context."""
        self.app = Flask('test')
        self.app.config.update({
            'COMPILER_ENDPOINT': 'http://foohost:1234',
            'COMPILER_VERIFY': False
        })

    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_compile(self, mock_Session):
        """Request compilation of an upload workspace."""
        source_id = 42
        checksum = 'asdf1234='
        output_format = domain.compilation.Compilation.Format.PDF
        location = f'http://asdf/{source_id}/{checksum}/{output_format.value}'
        in_progress = domain.compilation.Compilation.Status.IN_PROGRESS.value
        mock_session = mock.MagicMock(
            post=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.ACCEPTED,
                    json=mock.MagicMock(return_value={
                        'source_id': source_id,
                        'checksum': checksum,
                        'output_format': output_format.value,
                        'status': in_progress
                    }),
                    headers={'Location': location}
                )
            ),
            get=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.OK,
                    json=mock.MagicMock(return_value={
                        'source_id': source_id,
                        'checksum': checksum,
                        'output_format': output_format.value,
                        'status': domain.compilation.Compilation.Status.IN_PROGRESS.value
                    }),
                    headers={'Location': location}
                )
            )
        )
        mock_Session.return_value = mock_session

        with self.app.app_context():
            cp = compiler.Compiler.current_session()
            stat = cp.compile(source_id, checksum, 'footok', 'theLabel',
                              'http://the.link')
        self.assertEqual(stat.source_id, source_id)
        self.assertEqual(stat.identifier,
                         f"{source_id}/{checksum}/{output_format.value}")
        self.assertEqual(stat.status,
                         domain.compilation.Compilation.Status.IN_PROGRESS)
        self.assertEqual(mock_session.post.call_count, 1)

    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_compile_redirects(self, mock_Session):
        """Request compilation of an upload workspace already processing."""
        source_id = 42
        checksum = 'asdf1234='
        output_format = domain.compilation.Compilation.Format.PDF
        in_progress = domain.compilation.Compilation.Status.IN_PROGRESS.value
        location = f'http://asdf/{source_id}/{checksum}/{output_format.value}'
        mock_session = mock.MagicMock(
            post=mock.MagicMock(    # Redirected
                return_value=mock.MagicMock(
                    status_code=status.OK,
                    json=mock.MagicMock(
                        return_value={
                            'source_id': source_id,
                            'checksum': checksum,
                            'output_format': output_format.value,
                            'status': in_progress
                        }
                    )
                )
            )
        )
        mock_Session.return_value = mock_session
        with self.app.app_context():
            cp = compiler.Compiler.current_session()
            stat = cp.compile(source_id, checksum, 'footok', 'theLabel',
                              'http://the.link')
        self.assertEqual(stat.source_id, source_id)
        self.assertEqual(stat.identifier,
                         f"{source_id}/{checksum}/{output_format.value}")
        self.assertEqual(stat.status,
                         domain.compilation.Compilation.Status.IN_PROGRESS)
        self.assertEqual(mock_session.post.call_count, 1)


class TestGetTaskStatus(TestCase):
    """Tests for :mod:`compiler.get_status` with mocked responses."""

    def setUp(self):
        """Create an app for context."""
        self.app = Flask('test')
        self.app.config.update({
            'COMPILER_ENDPOINT': 'http://foohost:1234',
            'COMPILER_VERIFY': False
        })

    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_get_status_failed(self, mock_Session):
        """Get the status of a failed task."""
        source_id = 42
        checksum = 'asdf1234='
        output_format = domain.compilation.Compilation.Format.PDF
        failed = domain.compilation.Compilation.Status.FAILED.value
        mock_session = mock.MagicMock(
            get=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.OK,
                    json=mock.MagicMock(
                        return_value={
                            'source_id': source_id,
                            'checksum': checksum,
                            'output_format': output_format.value,
                            'status': failed
                        }
                    )
                )
            )
        )
        mock_Session.return_value = mock_session
        with self.app.app_context():
            cp = compiler.Compiler.current_session()
            stat = cp.get_status(source_id, checksum, 'tok', output_format)
        self.assertEqual(stat.source_id, source_id)
        self.assertEqual(stat.identifier,
                         f"{source_id}/{checksum}/{output_format.value}")
        self.assertEqual(stat.status,
                         domain.compilation.Compilation.Status.FAILED)
        self.assertEqual(mock_session.get.call_count, 1)

    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_get_status_in_progress(self, mock_Session):
        """Get the status of an in-progress task."""
        source_id = 42
        checksum = 'asdf1234='
        output_format = domain.compilation.Compilation.Format.PDF
        in_progress = domain.compilation.Compilation.Status.IN_PROGRESS.value
        mock_session = mock.MagicMock(
            get=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.OK,
                    json=mock.MagicMock(
                        return_value={
                            'source_id': source_id,
                            'checksum': checksum,
                            'output_format': output_format.value,
                            'status': in_progress
                        }
                    )
                )
            )
        )
        mock_Session.return_value = mock_session
        with self.app.app_context():
            cp = compiler.Compiler.current_session()
            stat = cp.get_status(source_id, checksum, 'tok', output_format)
        self.assertEqual(stat.source_id, source_id)
        self.assertEqual(stat.identifier,
                         f"{source_id}/{checksum}/{output_format.value}")
        self.assertEqual(stat.status,
                         domain.compilation.Compilation.Status.IN_PROGRESS)
        self.assertEqual(mock_session.get.call_count, 1)

    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_get_status_completed(self, mock_Session):
        """Get the status of a completed task."""
        source_id = 42
        checksum = 'asdf1234='
        output_format = domain.compilation.Compilation.Format.PDF
        succeeded = domain.compilation.Compilation.Status.SUCCEEDED.value
        mock_session = mock.MagicMock(
            get=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.OK,
                    json=mock.MagicMock(
                        return_value={
                            'source_id': source_id,
                            'checksum': checksum,
                            'output_format': output_format.value,
                            'status': succeeded
                        }
                    )
                )
            )
        )
        mock_Session.return_value = mock_session
        with self.app.app_context():
            cp = compiler.Compiler.current_session()
            stat = cp.get_status(source_id, checksum, 'tok', output_format)
        self.assertEqual(stat.source_id, source_id)
        self.assertEqual(stat.identifier,
                         f"{source_id}/{checksum}/{output_format.value}")
        self.assertEqual(stat.status,
                         domain.compilation.Compilation.Status.SUCCEEDED)
        self.assertEqual(mock_session.get.call_count, 1)

    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_get_status_doesnt_exist(self, mock_Session):
        """Get the status of a task that does not exist."""
        source_id = 42
        checksum = 'asdf1234='
        output_format = domain.compilation.Compilation.Format.PDF
        mock_session = mock.MagicMock(
            get=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.NOT_FOUND,
                    json=mock.MagicMock(
                        return_value={}
                    )
                )
            )
        )
        mock_Session.return_value = mock_session
        with self.app.app_context():
            cp = compiler.Compiler.current_session()
            with self.assertRaises(exceptions.NotFound):
                cp.get_status(source_id, checksum, 'footok', output_format)
