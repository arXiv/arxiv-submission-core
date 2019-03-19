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
        upload_id = 42
        checksum = 'asdf1234='
        output_format = domain.compilation.Format.PDF
        location = f'http://asdf/{upload_id}/{checksum}/{output_format.value}'
        mock_session = mock.MagicMock(
            post=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.ACCEPTED,
                    json=mock.MagicMock(return_value={
                        'source_id': upload_id,
                        'checksum': checksum,
                        'output_format': output_format.value,
                        'status': domain.compilation.Status.IN_PROGRESS.value
                    }),
                    headers={'Location': location}
                )
            ),
            get=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.OK,
                    json=mock.MagicMock(return_value={
                        'source_id': upload_id,
                        'checksum': checksum,
                        'output_format': output_format.value,
                        'status': domain.compilation.Status.IN_PROGRESS.value
                    }),
                    headers={'Location': location}
                )
            )
        )
        mock_Session.return_value = mock_session

        comp_status = compiler.Compiler.compile(upload_id, checksum, 'footok')
        self.assertEqual(comp_status.upload_id, upload_id)
        self.assertEqual(comp_status.identifier,
                         f"{upload_id}/{checksum}/{output_format.value}")
        self.assertEqual(comp_status.status,
                         domain.compilation.Status.IN_PROGRESS)
        self.assertEqual(mock_session.post.call_count, 1)

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_compile_redirects(self, mock_Session):
        """Request compilation of an upload workspace already processing."""
        upload_id = 42
        checksum = 'asdf1234='
        output_format = domain.compilation.Format.PDF

        location = f'http://asdf/{upload_id}/{checksum}/{output_format.value}'
        mock_session = mock.MagicMock(
            post=mock.MagicMock(    # Redirected
                return_value=mock.MagicMock(
                    status_code=status.OK,
                    json=mock.MagicMock(
                        return_value={
                            'source_id': upload_id,
                            'checksum': checksum,
                            'output_format': output_format.value,
                            'status': domain.compilation.Status.IN_PROGRESS.value
                        }
                    )
                )
            )
        )
        mock_Session.return_value = mock_session
        comp_status = compiler.Compiler.compile(upload_id, checksum,
                                                       'footok')
        self.assertEqual(comp_status.upload_id, upload_id)
        self.assertEqual(comp_status.identifier,
                         f"{upload_id}/{checksum}/{output_format.value}")
        self.assertEqual(comp_status.status,
                         domain.compilation.Status.IN_PROGRESS)
        self.assertEqual(mock_session.post.call_count, 1)


class TestGetTaskStatus(TestCase):
    """Tests for :mod:`compiler.get_status` with mocked responses."""

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_get_status_failed(self, mock_Session):
        """Get the status of a failed task."""
        upload_id = 42
        checksum = 'asdf1234='
        output_format = domain.compilation.Format.PDF

        mock_session = mock.MagicMock(
            get=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.OK,
                    json=mock.MagicMock(
                        return_value={
                            'source_id': upload_id,
                            'checksum': checksum,
                            'output_format': output_format.value,
                            'status': domain.compilation.Status.FAILED.value
                        }
                    )
                )
            )
        )
        mock_Session.return_value = mock_session
        comp_status = compiler.Compiler.get_status(upload_id, checksum,
                                                          'tok', output_format)
        self.assertEqual(comp_status.upload_id, upload_id)
        self.assertEqual(comp_status.identifier,
                         f"{upload_id}/{checksum}/{output_format.value}")
        self.assertEqual(comp_status.status, domain.compilation.Status.FAILED)
        self.assertEqual(mock_session.get.call_count, 1)

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_get_status_in_progress(self, mock_Session):
        """Get the status of an in-progress task."""
        upload_id = 42
        checksum = 'asdf1234='
        output_format = domain.compilation.Format.PDF
        mock_session = mock.MagicMock(
            get=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.OK,
                    json=mock.MagicMock(
                        return_value={
                            'source_id': upload_id,
                            'checksum': checksum,
                            'output_format': output_format.value,
                            'status': domain.compilation.Status.IN_PROGRESS.value
                        }
                    )
                )
            )
        )
        mock_Session.return_value = mock_session
        comp_status = compiler.Compiler.get_status(upload_id, checksum,
                                                          'tok', output_format)
        self.assertEqual(comp_status.upload_id, upload_id)
        self.assertEqual(comp_status.identifier,
                         f"{upload_id}/{checksum}/{output_format.value}")
        self.assertEqual(comp_status.status, domain.compilation.Status.IN_PROGRESS)
        self.assertEqual(mock_session.get.call_count, 1)

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_get_status_completed(self, mock_Session):
        """Get the status of a completed task."""
        upload_id = 42
        checksum = 'asdf1234='
        output_format = domain.compilation.Format.PDF

        mock_session = mock.MagicMock(
            get=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.OK,
                    json=mock.MagicMock(
                        return_value={
                            'source_id': upload_id,
                            'checksum': checksum,
                            'output_format': output_format.value,
                            'status': domain.compilation.Status.SUCCEEDED.value
                        }
                    )
                )
            )
        )
        mock_Session.return_value = mock_session
        comp_status = compiler.Compiler.get_status(upload_id, checksum,
                                                          'tok', output_format)
        self.assertEqual(comp_status.upload_id, upload_id)
        self.assertEqual(comp_status.identifier,
                         f"{upload_id}/{checksum}/{output_format.value}")
        self.assertEqual(comp_status.status, domain.compilation.Status.SUCCEEDED)
        self.assertEqual(mock_session.get.call_count, 1)

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_get_status_doesnt_exist(self, mock_Session):
        """Get the status of a task that does not exist."""
        upload_id = 42
        checksum = 'asdf1234='
        output_format = domain.compilation.Format.PDF
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
            compiler.Compiler.get_status(upload_id, checksum, 'footok',
                                                output_format)
