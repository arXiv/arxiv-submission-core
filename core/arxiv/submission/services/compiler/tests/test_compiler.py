from unittest import TestCase, mock
from arxiv import status
from ... import compiler
from .... import domain


class TestRequestCompilation(TestCase):
    """Tests for :mod:`compiler.request_compilation` with mocked responses."""

    @mock.patch(f'{compiler.__name__}.requests.Session')
    def test_request_compilation(self, mock_Session):
        """Request compilation of an upload workspace."""
        upload_id = 42
        task_id = 'qwer-1234-tyui-5678'
        mock_session = mock.MagicMock(
            post=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.HTTP_202_ACCEPTED,
                    json=mock.MagicMock(return_value={}),
                    headers={'Location': f'http://asdf/task/{task_id}/'}
                )
            ),
            get=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.HTTP_200_OK,
                    json=mock.MagicMock(
                        return_value={
                            'task_id': task_id,
                            'status': 'in_progress'
                        }
                    )
                )
            )
        )
        mock_Session.return_value = mock_session
        comp_status = compiler.request_compilation(upload_id)
        self.assertEqual(comp_status.upload_id, upload_id)
        self.assertEqual(comp_status.task_id, task_id)
        self.assertEqual(comp_status.status,
                         domain.CompilationStatus.Status.IN_PROGRESS)
        self.assertEqual(mock_session.post.call_count, 1)
        self.assertEqual(mock_session.get.call_count, 1)

    @mock.patch(f'{compiler.__name__}.requests.Session')
    def test_request_compilation_redirects(self, mock_Session):
        """Request compilation of an upload workspace already processing."""
        upload_id = 42
        task_id = 'qwer-1234-tyui-5678'
        mock_session = mock.MagicMock(
            post=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.HTTP_302_FOUND,
                    json=mock.MagicMock(return_value={}),
                    headers={'Location': f'http://asdf/task/{task_id}/'}
                )
            ),
            get=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.HTTP_200_OK,
                    json=mock.MagicMock(
                        return_value={
                            'task_id': task_id,
                            'status': 'in_progress'
                        }
                    )
                )
            )
        )
        mock_Session.return_value = mock_session
        comp_status = compiler.request_compilation(upload_id)
        self.assertEqual(comp_status.upload_id, upload_id)
        self.assertEqual(comp_status.task_id, task_id)
        self.assertEqual(comp_status.status,
                         domain.CompilationStatus.Status.IN_PROGRESS)
        self.assertEqual(mock_session.post.call_count, 1)
        self.assertEqual(mock_session.get.call_count, 1)


class TestGetTaskStatus(TestCase):
    """Tests for :mod:`compiler.get_status` with mocked responses."""

    @mock.patch(f'{compiler.__name__}.requests.Session')
    def test_get_status_failed(self, mock_Session):
        """Get the status of a failed task."""
        upload_id = 42
        task_id = 'qwer-1234-tyui-5678'
        mock_session = mock.MagicMock(
            get=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.HTTP_200_OK,
                    json=mock.MagicMock(
                        return_value={
                            'task_id': task_id,
                            'status': 'failed'
                        }
                    )
                )
            )
        )
        mock_Session.return_value = mock_session
        comp_status = compiler.get_status(upload_id, task_id)
        self.assertEqual(comp_status.upload_id, upload_id)
        self.assertEqual(comp_status.task_id, task_id)
        self.assertEqual(comp_status.status,
                         domain.CompilationStatus.Status.FAILED)
        self.assertEqual(mock_session.get.call_count, 1)

    @mock.patch(f'{compiler.__name__}.requests.Session')
    def test_get_status_in_progress(self, mock_Session):
        """Get the status of an in-progress task."""
        upload_id = 42
        task_id = 'qwer-1234-tyui-5678'
        mock_session = mock.MagicMock(
            get=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.HTTP_200_OK,
                    json=mock.MagicMock(
                        return_value={
                            'task_id': task_id,
                            'status': 'in_progress'
                        }
                    )
                )
            )
        )
        mock_Session.return_value = mock_session
        comp_status = compiler.get_status(upload_id, task_id)
        self.assertEqual(comp_status.upload_id, upload_id)
        self.assertEqual(comp_status.task_id, task_id)
        self.assertEqual(comp_status.status,
                         domain.CompilationStatus.Status.IN_PROGRESS)
        self.assertEqual(mock_session.get.call_count, 1)

    @mock.patch(f'{compiler.__name__}.requests.Session')
    def test_get_status_completed(self, mock_Session):
        """Get the status of a completed task."""
        upload_id = 42
        task_id = 'qwer-1234-tyui-5678'
        mock_session = mock.MagicMock(
            get=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.HTTP_200_OK,
                    json=mock.MagicMock(
                        return_value={
                            'task_id': task_id,
                            'status': 'completed'
                        }
                    )
                )
            )
        )
        mock_Session.return_value = mock_session
        comp_status = compiler.get_status(upload_id, task_id)
        self.assertEqual(comp_status.upload_id, upload_id)
        self.assertEqual(comp_status.task_id, task_id)
        self.assertEqual(comp_status.status,
                         domain.CompilationStatus.Status.SUCCEEDED)
        self.assertEqual(mock_session.get.call_count, 1)

    @mock.patch(f'{compiler.__name__}.requests.Session')
    def test_get_status_doesnt_exist(self, mock_Session):
        """Get the status of a task that does not exist."""
        upload_id = 42
        task_id = 'qwer-1234-tyui-5678'
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
            compiler.get_status(upload_id, task_id)
