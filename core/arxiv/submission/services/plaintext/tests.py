"""Tests for :mod:`arxiv.submission.services.plaintext`."""

from unittest import TestCase, mock

from arxiv import status

from . import plaintext


class TestPlainTextService(TestCase):
    """Tests for :class:`.plaintext.PlainTextService`."""

    @mock.patch(f'{plaintext.__name__}.requests.Session')
    def test_already_in_progress(self, mock_Session):
        """A plaintext extraction is already in progress."""
        mock_post = mock.MagicMock(
            return_value=mock.MagicMock(
                status_code=status.HTTP_303_SEE_OTHER,
                json=mock.MagicMock(return_value={}),
                headers={'Location': '...'}
            )
        )
        mock_Session.return_value = mock.MagicMock(post=mock_post)
        upload_id = '132456'
        service = plaintext.PlainTextService('foohost', 8123)
        with self.assertRaises(plaintext.ExtractionInProgress):
            service.request_extraction(upload_id)

    @mock.patch(f'{plaintext.__name__}.requests.Session')
    def test_request_extraction(self, mock_Session):
        """Extraction is successfully requested."""
        mock_post = mock.MagicMock(
            return_value=mock.MagicMock(
                status_code=status.HTTP_202_ACCEPTED,
                json=mock.MagicMock(return_value={
                    'reason': 'fulltext extraction in process'
                }),
                headers={'Location': '...'}
            )
        )
        mock_Session.return_value = mock.MagicMock(post=mock_post)
        upload_id = '132456'
        service = plaintext.PlainTextService('foohost', 8123)
        self.assertIsNone(service.request_extraction(upload_id))
        self.assertEqual(
            mock_post.call_args[0][0],
            'https://foohost:8123/submission/132456'
        )

    @mock.patch(f'{plaintext.__name__}.requests.Session')
    def test_request_extraction_bad_request(self, mock_Session):
        """Service returns 400 Bad Request."""
        mock_Session.return_value = mock.MagicMock(
            post=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    json=mock.MagicMock(return_value={
                        'reason': 'something is not quite right'
                    })
                )
            )
        )
        upload_id = '132456'
        service = plaintext.PlainTextService('foohost', 8000)
        with self.assertRaises(plaintext.BadRequest):
            service.request_extraction(upload_id)

    @mock.patch(f'{plaintext.__name__}.requests.Session')
    def test_request_extraction_server_error(self, mock_Session):
        """Service returns 500 Internal Server Error."""
        mock_Session.return_value = mock.MagicMock(
            post=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    json=mock.MagicMock(return_value={
                        'reason': 'something is not quite right'
                    })
                )
            )
        )
        upload_id = '132456'
        service = plaintext.PlainTextService('foohost', 8000)
        with self.assertRaises(plaintext.RequestFailed):
            service.request_extraction(upload_id)

    @mock.patch(f'{plaintext.__name__}.requests.Session')
    def test_request_extraction_unauthorized(self, mock_Session):
        """Service returns 401 Unauthorized."""
        mock_Session.return_value = mock.MagicMock(
            post=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    json=mock.MagicMock(return_value={
                        'reason': 'who are you'
                    })
                )
            )
        )
        upload_id = '132456'
        service = plaintext.PlainTextService('foohost', 8000)
        with self.assertRaises(plaintext.RequestUnauthorized):
            service.request_extraction(upload_id)

    @mock.patch(f'{plaintext.__name__}.requests.Session')
    def test_request_extraction_forbidden(self, mock_Session):
        """Service returns 403 Forbidden."""
        mock_Session.return_value = mock.MagicMock(
            post=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.HTTP_403_FORBIDDEN,
                    json=mock.MagicMock(return_value={
                        'reason': 'you do not have sufficient authz'
                    })
                )
            )
        )
        upload_id = '132456'
        service = plaintext.PlainTextService('foohost', 8000)
        with self.assertRaises(plaintext.RequestForbidden):
            service.request_extraction(upload_id)

    @mock.patch(f'{plaintext.__name__}.requests.Session')
    def test_extraction_is_complete(self, mock_Session):
        """Extraction is indeed complete."""
        mock_get = mock.MagicMock(
            return_value=mock.MagicMock(
                status_code=status.HTTP_303_SEE_OTHER,
                json=mock.MagicMock(return_value={}),
                headers={'Location': '...'}
            )
        )
        mock_Session.return_value = mock.MagicMock(get=mock_get)
        upload_id = '132456'
        service = plaintext.PlainTextService('foohost', 8123)
        self.assertTrue(service.extraction_is_complete(upload_id))
        self.assertEqual(
            mock_get.call_args[0][0],
            'https://foohost:8123/submission/132456/status'
        )

    @mock.patch(f'{plaintext.__name__}.requests.Session')
    def test_extraction_in_progress(self, mock_Session):
        """Extraction is still in progress."""
        mock_get = mock.MagicMock(
            return_value=mock.MagicMock(
                status_code=status.HTTP_200_OK,
                json=mock.MagicMock(return_value={'status': 'in_progress'})
            )
        )
        mock_Session.return_value = mock.MagicMock(get=mock_get)
        upload_id = '132456'
        service = plaintext.PlainTextService('foohost', 8123)
        self.assertFalse(service.extraction_is_complete(upload_id))
        self.assertEqual(
            mock_get.call_args[0][0],
            'https://foohost:8123/submission/132456/status'
        )

    @mock.patch(f'{plaintext.__name__}.requests.Session')
    def test_extraction_failed(self, mock_Session):
        """Extraction failed."""
        mock_get = mock.MagicMock(
            return_value=mock.MagicMock(
                status_code=status.HTTP_200_OK,
                json=mock.MagicMock(return_value={'status': 'failed'})
            )
        )
        mock_Session.return_value = mock.MagicMock(get=mock_get)
        upload_id = '132456'
        service = plaintext.PlainTextService('foohost', 8123)
        with self.assertRaises(plaintext.ExtractionFailed):
            self.assertFalse(service.extraction_is_complete(upload_id))

    @mock.patch(f'{plaintext.__name__}.requests.Session')
    def test_complete_unauthorized(self, mock_Session):
        """Service returns 401 Unauthorized."""
        mock_Session.return_value = mock.MagicMock(
            get=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    json=mock.MagicMock(return_value={
                        'reason': 'who are you'
                    })
                )
            )
        )
        upload_id = '132456'
        service = plaintext.PlainTextService('foohost', 8000)
        with self.assertRaises(plaintext.RequestUnauthorized):
            service.extraction_is_complete(upload_id)

    @mock.patch(f'{plaintext.__name__}.requests.Session')
    def test_complete_forbidden(self, mock_Session):
        """Service returns 403 Forbidden."""
        mock_Session.return_value = mock.MagicMock(
            get=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.HTTP_403_FORBIDDEN,
                    json=mock.MagicMock(return_value={
                        'reason': 'you do not have sufficient authz'
                    })
                )
            )
        )
        upload_id = '132456'
        service = plaintext.PlainTextService('foohost', 8000)
        with self.assertRaises(plaintext.RequestForbidden):
            service.extraction_is_complete(upload_id)

    @mock.patch(f'{plaintext.__name__}.requests.Session')
    def test_retrieve_unauthorized(self, mock_Session):
        """Service returns 401 Unauthorized."""
        mock_Session.return_value = mock.MagicMock(
            get=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    json=mock.MagicMock(return_value={
                        'reason': 'who are you'
                    })
                )
            )
        )
        upload_id = '132456'
        service = plaintext.PlainTextService('foohost', 8000)
        with self.assertRaises(plaintext.RequestUnauthorized):
            service.retrieve_content(upload_id)

    @mock.patch(f'{plaintext.__name__}.requests.Session')
    def test_retrieve_forbidden(self, mock_Session):
        """Service returns 403 Forbidden."""
        mock_Session.return_value = mock.MagicMock(
            get=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.HTTP_403_FORBIDDEN,
                    json=mock.MagicMock(return_value={
                        'reason': 'you do not have sufficient authz'
                    })
                )
            )
        )
        upload_id = '132456'
        service = plaintext.PlainTextService('foohost', 8000)
        with self.assertRaises(plaintext.RequestForbidden):
            service.retrieve_content(upload_id)

    @mock.patch(f'{plaintext.__name__}.requests.Session')
    def test_retrieve(self, mock_Session):
        """Retrieval is successful."""
        content = b'thisisthecontent'
        mock_get = mock.MagicMock(
            return_value=mock.MagicMock(
                status_code=status.HTTP_200_OK,
                content=content
            )
        )
        mock_Session.return_value = mock.MagicMock(get=mock_get)
        upload_id = '132456'
        service = plaintext.PlainTextService('foohost', 8123)
        self.assertEqual(service.retrieve_content(upload_id), content,
                         "Returns binary content as received")
        self.assertEqual(
            mock_get.call_args[0][0],
            'https://foohost:8123/submission/132456'
        )

    @mock.patch(f'{plaintext.__name__}.requests.Session')
    def test_retrieve_nonexistant(self, mock_Session):
        """There is no such plaintext resource."""
        mock_get = mock.MagicMock(
            return_value=mock.MagicMock(
                status_code=status.HTTP_404_NOT_FOUND,
                json=mock.MagicMock(return_value={'reason': 'no such thing'})
            )
        )
        mock_Session.return_value = mock.MagicMock(get=mock_get)
        upload_id = '132456'
        service = plaintext.PlainTextService('foohost', 8123)
        with self.assertRaises(plaintext.DoesNotExist):
            service.retrieve_content(upload_id)

    @mock.patch(f'{plaintext.__name__}.requests.Session')
    def test_retrieve_in_progress(self, mock_Session):
        """There is no such plaintext resource."""
        mock_get = mock.MagicMock(
            return_value=mock.MagicMock(
                status_code=status.HTTP_303_SEE_OTHER,
                json=mock.MagicMock(return_value={}),
                headers={'Location': '...'}
            )
        )
        mock_Session.return_value = mock.MagicMock(get=mock_get)
        upload_id = '132456'
        service = plaintext.PlainTextService('foohost', 8123)
        with self.assertRaises(plaintext.ExtractionInProgress):
            service.retrieve_content(upload_id)


class TestPlainTextServiceModule(TestCase):
    """Tests for :mod:`.services.plaintext`."""

    @mock.patch(f'{plaintext.__name__}.get_application_config')
    @mock.patch(f'{plaintext.__name__}.requests.Session')
    def test_already_in_progress(self, mock_Session, mock_get_config):
        """A plaintext extraction is already in progress."""
        mock_get_config.return_value = {
            'PLAINTEXT_HOST': 'foohost',
            'PLAINTEXT_PORT': 5432,
            'PLAINTEXT_SCHEME': 'http'
        }
        mock_post = mock.MagicMock(
            return_value=mock.MagicMock(
                status_code=status.HTTP_303_SEE_OTHER,
                json=mock.MagicMock(return_value={}),
                headers={'Location': '...'}
            )
        )
        mock_Session.return_value = mock.MagicMock(post=mock_post)
        upload_id = '132456'
        with self.assertRaises(plaintext.ExtractionInProgress):
            plaintext.request_extraction(upload_id)

    @mock.patch(f'{plaintext.__name__}.get_application_config')
    @mock.patch(f'{plaintext.__name__}.requests.Session')
    def test_request_extraction(self, mock_Session, mock_get_config):
        """Extraction is successfully requested."""
        mock_get_config.return_value = {
            'PLAINTEXT_HOST': 'foohost',
            'PLAINTEXT_PORT': 5432,
            'PLAINTEXT_SCHEME': 'http'
        }
        mock_post = mock.MagicMock(
            return_value=mock.MagicMock(
                status_code=status.HTTP_202_ACCEPTED,
                json=mock.MagicMock(return_value={
                    'reason': 'fulltext extraction in process'
                }),
                headers={'Location': '...'}
            )
        )
        mock_Session.return_value = mock.MagicMock(post=mock_post)
        upload_id = '132456'
        self.assertIsNone(plaintext.request_extraction(upload_id))
        self.assertEqual(
            mock_post.call_args[0][0],
            'http://foohost:5432/submission/132456'
        )

    @mock.patch(f'{plaintext.__name__}.get_application_config')
    @mock.patch(f'{plaintext.__name__}.requests.Session')
    def test_extraction_bad_request(self, mock_Session, mock_get_config):
        """Service returns 400 Bad Request."""
        mock_get_config.return_value = {
            'PLAINTEXT_HOST': 'foohost',
            'PLAINTEXT_PORT': 5432,
            'PLAINTEXT_SCHEME': 'http'
        }
        mock_Session.return_value = mock.MagicMock(
            post=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    json=mock.MagicMock(return_value={
                        'reason': 'something is not quite right'
                    })
                )
            )
        )
        upload_id = '132456'
        with self.assertRaises(plaintext.BadRequest):
            plaintext.request_extraction(upload_id)

    @mock.patch(f'{plaintext.__name__}.get_application_config')
    @mock.patch(f'{plaintext.__name__}.requests.Session')
    def test_extraction_server_error(self, mock_Session, mock_get_config):
        """Service returns 500 Internal Server Error."""
        mock_get_config.return_value = {
            'PLAINTEXT_HOST': 'foohost',
            'PLAINTEXT_PORT': 5432,
            'PLAINTEXT_SCHEME': 'http'
        }
        mock_Session.return_value = mock.MagicMock(
            post=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    json=mock.MagicMock(return_value={
                        'reason': 'something is not quite right'
                    })
                )
            )
        )
        upload_id = '132456'
        with self.assertRaises(plaintext.RequestFailed):
            plaintext.request_extraction(upload_id)

    @mock.patch(f'{plaintext.__name__}.get_application_config')
    @mock.patch(f'{plaintext.__name__}.requests.Session')
    def test_extraction_unauthorized(self, mock_Session, mock_get_config):
        """Service returns 401 Unauthorized."""
        mock_get_config.return_value = {
            'PLAINTEXT_HOST': 'foohost',
            'PLAINTEXT_PORT': 5432,
            'PLAINTEXT_SCHEME': 'http'
        }
        mock_Session.return_value = mock.MagicMock(
            post=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    json=mock.MagicMock(return_value={
                        'reason': 'who are you'
                    })
                )
            )
        )
        upload_id = '132456'
        with self.assertRaises(plaintext.RequestUnauthorized):
            plaintext.request_extraction(upload_id)

    @mock.patch(f'{plaintext.__name__}.get_application_config')
    @mock.patch(f'{plaintext.__name__}.requests.Session')
    def test_request_extraction_forbidden(self, mock_Session, mock_get_config):
        """Service returns 403 Forbidden."""
        mock_get_config.return_value = {
            'PLAINTEXT_HOST': 'foohost',
            'PLAINTEXT_PORT': 5432,
            'PLAINTEXT_SCHEME': 'http'
        }
        mock_Session.return_value = mock.MagicMock(
            post=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.HTTP_403_FORBIDDEN,
                    json=mock.MagicMock(return_value={
                        'reason': 'you do not have sufficient authz'
                    })
                )
            )
        )
        upload_id = '132456'
        with self.assertRaises(plaintext.RequestForbidden):
            plaintext.request_extraction(upload_id)

    @mock.patch(f'{plaintext.__name__}.get_application_config')
    @mock.patch(f'{plaintext.__name__}.requests.Session')
    def test_extraction_is_complete(self, mock_Session, mock_get_config):
        """Extraction is indeed complete."""
        mock_get_config.return_value = {
            'PLAINTEXT_HOST': 'foohost',
            'PLAINTEXT_PORT': 5432,
            'PLAINTEXT_SCHEME': 'http'
        }
        mock_get = mock.MagicMock(
            return_value=mock.MagicMock(
                status_code=status.HTTP_303_SEE_OTHER,
                json=mock.MagicMock(return_value={}),
                headers={'Location': '...'}
            )
        )
        mock_Session.return_value = mock.MagicMock(get=mock_get)
        upload_id = '132456'
        self.assertTrue(plaintext.extraction_is_complete(upload_id))
        self.assertEqual(
            mock_get.call_args[0][0],
            'http://foohost:5432/submission/132456/status'
        )

    @mock.patch(f'{plaintext.__name__}.get_application_config')
    @mock.patch(f'{plaintext.__name__}.requests.Session')
    def test_extraction_in_progress(self, mock_Session, mock_get_config):
        """Extraction is still in progress."""
        mock_get_config.return_value = {
            'PLAINTEXT_HOST': 'foohost',
            'PLAINTEXT_PORT': 5432,
            'PLAINTEXT_SCHEME': 'http'
        }
        mock_get = mock.MagicMock(
            return_value=mock.MagicMock(
                status_code=status.HTTP_200_OK,
                json=mock.MagicMock(return_value={'status': 'in_progress'})
            )
        )
        mock_Session.return_value = mock.MagicMock(get=mock_get)
        upload_id = '132456'
        self.assertFalse(plaintext.extraction_is_complete(upload_id))
        self.assertEqual(
            mock_get.call_args[0][0],
            'http://foohost:5432/submission/132456/status'
        )

    @mock.patch(f'{plaintext.__name__}.get_application_config')
    @mock.patch(f'{plaintext.__name__}.requests.Session')
    def test_extraction_failed(self, mock_Session, mock_get_config):
        """Extraction failed."""
        mock_get_config.return_value = {
            'PLAINTEXT_HOST': 'foohost',
            'PLAINTEXT_PORT': 5432,
            'PLAINTEXT_SCHEME': 'http'
        }
        mock_get = mock.MagicMock(
            return_value=mock.MagicMock(
                status_code=status.HTTP_200_OK,
                json=mock.MagicMock(return_value={'status': 'failed'})
            )
        )
        mock_Session.return_value = mock.MagicMock(get=mock_get)
        upload_id = '132456'
        with self.assertRaises(plaintext.ExtractionFailed):
            self.assertFalse(plaintext.extraction_is_complete(upload_id))

    @mock.patch(f'{plaintext.__name__}.get_application_config')
    @mock.patch(f'{plaintext.__name__}.requests.Session')
    def test_complete_unauthorized(self, mock_Session, mock_get_config):
        """Service returns 401 Unauthorized."""
        mock_get_config.return_value = {
            'PLAINTEXT_HOST': 'foohost',
            'PLAINTEXT_PORT': 5432,
            'PLAINTEXT_SCHEME': 'http'
        }
        mock_Session.return_value = mock.MagicMock(
            get=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    json=mock.MagicMock(return_value={
                        'reason': 'who are you'
                    })
                )
            )
        )
        upload_id = '132456'
        with self.assertRaises(plaintext.RequestUnauthorized):
            plaintext.extraction_is_complete(upload_id)

    @mock.patch(f'{plaintext.__name__}.get_application_config')
    @mock.patch(f'{plaintext.__name__}.requests.Session')
    def test_complete_forbidden(self, mock_Session, mock_get_config):
        """Service returns 403 Forbidden."""
        mock_get_config.return_value = {
            'PLAINTEXT_HOST': 'foohost',
            'PLAINTEXT_PORT': 5432,
            'PLAINTEXT_SCHEME': 'http'
        }
        mock_Session.return_value = mock.MagicMock(
            get=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.HTTP_403_FORBIDDEN,
                    json=mock.MagicMock(return_value={
                        'reason': 'you do not have sufficient authz'
                    })
                )
            )
        )
        upload_id = '132456'
        with self.assertRaises(plaintext.RequestForbidden):
            plaintext.extraction_is_complete(upload_id)

    @mock.patch(f'{plaintext.__name__}.get_application_config')
    @mock.patch(f'{plaintext.__name__}.requests.Session')
    def test_retrieve_unauthorized(self, mock_Session, mock_get_config):
        """Service returns 401 Unauthorized."""
        mock_get_config.return_value = {
            'PLAINTEXT_HOST': 'foohost',
            'PLAINTEXT_PORT': 5432,
            'PLAINTEXT_SCHEME': 'http'
        }
        mock_Session.return_value = mock.MagicMock(
            get=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    json=mock.MagicMock(return_value={
                        'reason': 'who are you'
                    })
                )
            )
        )
        upload_id = '132456'
        with self.assertRaises(plaintext.RequestUnauthorized):
            plaintext.retrieve_content(upload_id)

    @mock.patch(f'{plaintext.__name__}.get_application_config')
    @mock.patch(f'{plaintext.__name__}.requests.Session')
    def test_retrieve_forbidden(self, mock_Session, mock_get_config):
        """Service returns 403 Forbidden."""
        mock_get_config.return_value = {
            'PLAINTEXT_HOST': 'foohost',
            'PLAINTEXT_PORT': 5432,
            'PLAINTEXT_SCHEME': 'http'
        }
        mock_Session.return_value = mock.MagicMock(
            get=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.HTTP_403_FORBIDDEN,
                    json=mock.MagicMock(return_value={
                        'reason': 'you do not have sufficient authz'
                    })
                )
            )
        )
        upload_id = '132456'
        with self.assertRaises(plaintext.RequestForbidden):
            plaintext.retrieve_content(upload_id)

    @mock.patch(f'{plaintext.__name__}.get_application_config')
    @mock.patch(f'{plaintext.__name__}.requests.Session')
    def test_retrieve(self, mock_Session, mock_get_config):
        """Retrieval is successful."""
        mock_get_config.return_value = {
            'PLAINTEXT_HOST': 'foohost',
            'PLAINTEXT_PORT': 5432,
            'PLAINTEXT_SCHEME': 'http'
        }
        content = b'thisisthecontent'
        mock_get = mock.MagicMock(
            return_value=mock.MagicMock(
                status_code=status.HTTP_200_OK,
                content=content
            )
        )
        mock_Session.return_value = mock.MagicMock(get=mock_get)
        upload_id = '132456'
        self.assertEqual(plaintext.retrieve_content(upload_id), content,
                         "Returns binary content as received")
        self.assertEqual(
            mock_get.call_args[0][0],
            'http://foohost:5432/submission/132456'
        )

    @mock.patch(f'{plaintext.__name__}.get_application_config')
    @mock.patch(f'{plaintext.__name__}.requests.Session')
    def test_retrieve_nonexistant(self, mock_Session, mock_get_config):
        """There is no such plaintext resource."""
        mock_get_config.return_value = {
            'PLAINTEXT_HOST': 'foohost',
            'PLAINTEXT_PORT': 5432,
            'PLAINTEXT_SCHEME': 'http'
        }
        mock_get = mock.MagicMock(
            return_value=mock.MagicMock(
                status_code=status.HTTP_404_NOT_FOUND,
                json=mock.MagicMock(return_value={'reason': 'no such thing'})
            )
        )
        mock_Session.return_value = mock.MagicMock(get=mock_get)
        upload_id = '132456'
        with self.assertRaises(plaintext.DoesNotExist):
            plaintext.retrieve_content(upload_id)

    @mock.patch(f'{plaintext.__name__}.get_application_config')
    @mock.patch(f'{plaintext.__name__}.requests.Session')
    def test_retrieve_in_progress(self, mock_Session, mock_get_config):
        """There is no such plaintext resource."""
        mock_get_config.return_value = {
            'PLAINTEXT_HOST': 'foohost',
            'PLAINTEXT_PORT': 5432,
            'PLAINTEXT_SCHEME': 'http'
        }
        mock_get = mock.MagicMock(
            return_value=mock.MagicMock(
                status_code=status.HTTP_303_SEE_OTHER,
                json=mock.MagicMock(return_value={}),
                headers={'Location': '...'}
            )
        )
        mock_Session.return_value = mock.MagicMock(get=mock_get)
        upload_id = '132456'
        with self.assertRaises(plaintext.ExtractionInProgress):
            plaintext.retrieve_content(upload_id)
