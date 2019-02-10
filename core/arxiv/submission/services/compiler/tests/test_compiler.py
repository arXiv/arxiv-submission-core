from unittest import TestCase, mock
from arxiv import status
from ... import compiler
from .... import domain


class TestRequestCompilation(TestCase):
    """Tests for :mod:`compiler.compile` with mocked responses."""

    @mock.patch(f'{compiler.__name__}.requests.Session')
    def test_compile(self, mock_Session):
        """Request compilation of an upload workspace."""
        upload_id = 42
        checksum = 'asdf1234='
        output_format = compiler.Format.PDF
        location = f'http://asdf/{upload_id}/{checksum}/{output_format.value}'
        mock_session = mock.MagicMock(
            post=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.HTTP_202_ACCEPTED,
                    json=mock.MagicMock(return_value={
                        'status': {
                            'source_id': upload_id,
                            'checksum': checksum,
                            'output_format': output_format.value,
                            'status': compiler.Status.IN_PROGRESS.value
                        }
                    }),
                    headers={'Location': location}
                )
            )
        )
        mock_Session.return_value = mock_session

        comp_status = compiler.compile(upload_id, checksum)
        self.assertEqual(comp_status.upload_id, upload_id)
        self.assertEqual(comp_status.identifier,
                         f"{upload_id}::{checksum}::{output_format.value}")
        self.assertEqual(comp_status.status,
                         compiler.Status.IN_PROGRESS)
        self.assertEqual(mock_session.post.call_count, 1)

    @mock.patch(f'{compiler.__name__}.requests.Session')
    def test_compile_redirects(self, mock_Session):
        """Request compilation of an upload workspace already processing."""
        upload_id = 42
        checksum = 'asdf1234='
        output_format = compiler.Format.PDF

        location = f'http://asdf/{upload_id}/{checksum}/{output_format.value}'
        mock_session = mock.MagicMock(
            post=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.HTTP_302_FOUND,
                    json=mock.MagicMock(return_value={}),
                    headers={'Location': location}
                )
            ),
            get=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.HTTP_200_OK,
                    json=mock.MagicMock(
                        return_value={
                            'status': {
                                'source_id': upload_id,
                                'checksum': checksum,
                                'output_format': output_format.value,
                                'status': compiler.Status.IN_PROGRESS.value
                            }
                        }
                    )
                )
            )
        )
        mock_Session.return_value = mock_session
        comp_status = compiler.compile(upload_id, checksum)
        self.assertEqual(comp_status.upload_id, upload_id)
        self.assertEqual(comp_status.identifier,
                         f"{upload_id}::{checksum}::{output_format.value}")
        self.assertEqual(comp_status.status,
                         compiler.Status.IN_PROGRESS)
        self.assertEqual(mock_session.post.call_count, 1)
        self.assertEqual(mock_session.get.call_count, 1)


class TestGetTaskStatus(TestCase):
    """Tests for :mod:`compiler.get_status` with mocked responses."""

    @mock.patch(f'{compiler.__name__}.requests.Session')
    def test_get_status_failed(self, mock_Session):
        """Get the status of a failed task."""
        upload_id = 42
        checksum = 'asdf1234='
        output_format = compiler.Format.PDF

        mock_session = mock.MagicMock(
            get=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.HTTP_200_OK,
                    json=mock.MagicMock(
                        return_value={
                            'status': {
                                'source_id': upload_id,
                                'checksum': checksum,
                                'output_format': output_format.value,
                                'status': compiler.Status.FAILED.value
                            }
                        }
                    )
                )
            )
        )
        mock_Session.return_value = mock_session
        comp_status = compiler.get_status(upload_id, checksum, output_format)
        self.assertEqual(comp_status.upload_id, upload_id)
        self.assertEqual(comp_status.identifier,
                         f"{upload_id}::{checksum}::{output_format.value}")
        self.assertEqual(comp_status.status, compiler.Status.FAILED)
        self.assertEqual(mock_session.get.call_count, 1)

    @mock.patch(f'{compiler.__name__}.requests.Session')
    def test_get_status_in_progress(self, mock_Session):
        """Get the status of an in-progress task."""
        upload_id = 42
        checksum = 'asdf1234='
        output_format = compiler.Format.PDF
        mock_session = mock.MagicMock(
            get=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.HTTP_200_OK,
                    json=mock.MagicMock(
                        return_value={
                            'status': {
                                'source_id': upload_id,
                                'checksum': checksum,
                                'output_format': output_format.value,
                                'status': compiler.Status.IN_PROGRESS.value
                            }
                        }
                    )
                )
            )
        )
        mock_Session.return_value = mock_session
        comp_status = compiler.get_status(upload_id, checksum, output_format)
        self.assertEqual(comp_status.upload_id, upload_id)
        self.assertEqual(comp_status.identifier,
                         f"{upload_id}::{checksum}::{output_format.value}")
        self.assertEqual(comp_status.status, compiler.Status.IN_PROGRESS)
        self.assertEqual(mock_session.get.call_count, 1)

    @mock.patch(f'{compiler.__name__}.requests.Session')
    def test_get_status_completed(self, mock_Session):
        """Get the status of a completed task."""
        upload_id = 42
        checksum = 'asdf1234='
        output_format = compiler.Format.PDF

        mock_session = mock.MagicMock(
            get=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.HTTP_200_OK,
                    json=mock.MagicMock(
                        return_value={
                            'status': {
                                'source_id': upload_id,
                                'checksum': checksum,
                                'output_format': output_format.value,
                                'status': compiler.Status.SUCCEEDED.value
                            }
                        }
                    )
                )
            )
        )
        mock_Session.return_value = mock_session
        comp_status = compiler.get_status(upload_id, checksum, output_format)
        self.assertEqual(comp_status.upload_id, upload_id)
        self.assertEqual(comp_status.identifier,
                         f"{upload_id}::{checksum}::{output_format.value}")
        self.assertEqual(comp_status.status, compiler.Status.SUCCEEDED)
        self.assertEqual(mock_session.get.call_count, 1)

    @mock.patch(f'{compiler.__name__}.requests.Session')
    def test_get_status_doesnt_exist(self, mock_Session):
        """Get the status of a task that does not exist."""
        upload_id = 42
        checksum = 'asdf1234='
        output_format = compiler.Format.PDF
        mock_session = mock.MagicMock(
            get=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.HTTP_404_NOT_FOUND,
                    json=mock.MagicMock(
                        return_value={}
                    )
                )
            )
        )
        mock_Session.return_value = mock_session
        with self.assertRaises(compiler.NoSuchResource):
            compiler.get_status(upload_id, checksum, output_format)
