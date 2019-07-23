"""Tests for :mod:`.compiler`."""

from unittest import TestCase, mock

from . import compiler
from ... import domain

from arxiv.integration.api import status, exceptions


mock_app = mock.MagicMock(config={
    'COMPILER_ENDPOINT': 'http://foohost:1234',
    'COMPILER_VERIFY': False
})


class TestRequestCompilation(TestCase):
    """Tests for :mod:`compiler.compile` with mocked responses."""

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_compile(self, mock_Session):
        """Request compilation of an upload workspace."""
        source_id = 42
        checksum = 'asdf1234='
        output_format = domain.compilation.Compilation.Format.PDF
        location = f'http://asdf/{source_id}/{checksum}/{output_format.value}'
        mock_session = mock.MagicMock(
            post=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.ACCEPTED,
                    json=mock.MagicMock(return_value={
                        'source_id': source_id,
                        'checksum': checksum,
                        'output_format': output_format.value,
                        'status': domain.compilation.Compilation.Status.IN_PROGRESS.value
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

        comp_status = compiler.Compiler.compile(source_id, checksum, 'footok',
                                                'theLabel', 'http://the.link')
        self.assertEqual(comp_status.source_id, source_id)
        self.assertEqual(comp_status.identifier,
                         f"{source_id}/{checksum}/{output_format.value}")
        self.assertEqual(comp_status.status,
                         domain.compilation.Compilation.Status.IN_PROGRESS)
        self.assertEqual(mock_session.post.call_count, 1)

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_compile_redirects(self, mock_Session):
        """Request compilation of an upload workspace already processing."""
        source_id = 42
        checksum = 'asdf1234='
        output_format = domain.compilation.Compilation.Format.PDF

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
                            'status': domain.compilation.Compilation.Status.IN_PROGRESS.value
                        }
                    )
                )
            )
        )
        mock_Session.return_value = mock_session
        comp_status = compiler.Compiler.compile(source_id, checksum, 'footok',
                                                'theLabel', 'http://the.link')
        self.assertEqual(comp_status.source_id, source_id)
        self.assertEqual(comp_status.identifier,
                         f"{source_id}/{checksum}/{output_format.value}")
        self.assertEqual(comp_status.status,
                         domain.compilation.Compilation.Status.IN_PROGRESS)
        self.assertEqual(mock_session.post.call_count, 1)


class TestGetTaskStatus(TestCase):
    """Tests for :mod:`compiler.get_status` with mocked responses."""

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_get_status_failed(self, mock_Session):
        """Get the status of a failed task."""
        source_id = 42
        checksum = 'asdf1234='
        output_format = domain.compilation.Compilation.Format.PDF

        mock_session = mock.MagicMock(
            get=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.OK,
                    json=mock.MagicMock(
                        return_value={
                            'source_id': source_id,
                            'checksum': checksum,
                            'output_format': output_format.value,
                            'status': domain.compilation.Compilation.Status.FAILED.value
                        }
                    )
                )
            )
        )
        mock_Session.return_value = mock_session
        comp_status = compiler.Compiler.get_status(source_id, checksum,
                                                          'tok', output_format)
        self.assertEqual(comp_status.source_id, source_id)
        self.assertEqual(comp_status.identifier,
                         f"{source_id}/{checksum}/{output_format.value}")
        self.assertEqual(comp_status.status, domain.compilation.Compilation.Status.FAILED)
        self.assertEqual(mock_session.get.call_count, 1)

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_get_status_in_progress(self, mock_Session):
        """Get the status of an in-progress task."""
        source_id = 42
        checksum = 'asdf1234='
        output_format = domain.compilation.Compilation.Format.PDF
        mock_session = mock.MagicMock(
            get=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.OK,
                    json=mock.MagicMock(
                        return_value={
                            'source_id': source_id,
                            'checksum': checksum,
                            'output_format': output_format.value,
                            'status': domain.compilation.Compilation.Status.IN_PROGRESS.value
                        }
                    )
                )
            )
        )
        mock_Session.return_value = mock_session
        comp_status = compiler.Compiler.get_status(source_id, checksum,
                                                          'tok', output_format)
        self.assertEqual(comp_status.source_id, source_id)
        self.assertEqual(comp_status.identifier,
                         f"{source_id}/{checksum}/{output_format.value}")
        self.assertEqual(comp_status.status, domain.compilation.Compilation.Status.IN_PROGRESS)
        self.assertEqual(mock_session.get.call_count, 1)

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_get_status_completed(self, mock_Session):
        """Get the status of a completed task."""
        source_id = 42
        checksum = 'asdf1234='
        output_format = domain.compilation.Compilation.Format.PDF

        mock_session = mock.MagicMock(
            get=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.OK,
                    json=mock.MagicMock(
                        return_value={
                            'source_id': source_id,
                            'checksum': checksum,
                            'output_format': output_format.value,
                            'status': domain.compilation.Compilation.Status.SUCCEEDED.value
                        }
                    )
                )
            )
        )
        mock_Session.return_value = mock_session
        comp_status = compiler.Compiler.get_status(source_id, checksum,
                                                          'tok', output_format)
        self.assertEqual(comp_status.source_id, source_id)
        self.assertEqual(comp_status.identifier,
                         f"{source_id}/{checksum}/{output_format.value}")
        self.assertEqual(comp_status.status, domain.compilation.Compilation.Status.SUCCEEDED)
        self.assertEqual(mock_session.get.call_count, 1)

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
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
        with self.assertRaises(exceptions.NotFound):
            compiler.Compiler.get_status(source_id, checksum, 'footok',
                                                output_format)
