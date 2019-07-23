"""Tests for :mod:`arxiv.submission.services.plaintext`."""

from unittest import TestCase, mock

from arxiv.integration.api import exceptions, status
from . import plaintext

mock_app = mock.MagicMock(config={
    'PLAINTEXT_ENDPOINT': 'http://foohost:5432',
    'PLAINTEXT_VERIFY': False
})


class TestPlainTextService(TestCase):
    """Tests for :class:`.plaintext.PlainTextService`."""

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_already_in_progress(self, mock_Session):
        """A plaintext extraction is already in progress."""
        mock_post = mock.MagicMock(
            return_value=mock.MagicMock(
                status_code=status.SEE_OTHER,
                json=mock.MagicMock(return_value={}),
                headers={'Location': '...'}
            )
        )
        mock_Session.return_value = mock.MagicMock(post=mock_post)
        source_id = '132456'
        service = plaintext.PlainTextService('http://foohost:8123')
        with self.assertRaises(plaintext.ExtractionInProgress):
            service.request_extraction(source_id)

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_request_extraction(self, mock_Session):
        """Extraction is successfully requested."""
        mock_session = mock.MagicMock(**{
            'post': mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.ACCEPTED,
                    json=mock.MagicMock(return_value={}),
                    content='',
                    headers={'Location': '/somewhere'}
                )
            ),
            'get': mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.OK,
                    json=mock.MagicMock(
                        return_value={'reason': 'extraction in process'}
                    ),
                    content="{'reason': 'fulltext extraction in process'}",
                    headers={}
                )
            )
        })
        mock_Session.return_value = mock_session
        source_id = '132456'
        service = plaintext.PlainTextService('http://foohost:8123')
        self.assertIsNone(service.request_extraction(source_id))
        self.assertEqual(
            mock_session.post.call_args[0][0],
            'http://foohost:8123/submission/132456'
        )

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_request_extraction_bad_request(self, mock_Session):
        """Service returns 400 Bad Request."""
        mock_Session.return_value = mock.MagicMock(
            post=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.BAD_REQUEST,
                    json=mock.MagicMock(return_value={
                        'reason': 'something is not quite right'
                    })
                )
            )
        )
        source_id = '132456'
        service = plaintext.PlainTextService('foohost', 8000)
        with self.assertRaises(exceptions.BadRequest):
            service.request_extraction(source_id)

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_request_extraction_server_error(self, mock_Session):
        """Service returns 500 Internal Server Error."""
        mock_Session.return_value = mock.MagicMock(
            post=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.INTERNAL_SERVER_ERROR,
                    json=mock.MagicMock(return_value={
                        'reason': 'something is not quite right'
                    })
                )
            )
        )
        source_id = '132456'
        service = plaintext.PlainTextService('foohost', 8000)
        with self.assertRaises(exceptions.RequestFailed):
            service.request_extraction(source_id)

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_request_extraction_unauthorized(self, mock_Session):
        """Service returns 401 Unauthorized."""
        mock_Session.return_value = mock.MagicMock(
            post=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.UNAUTHORIZED,
                    json=mock.MagicMock(return_value={
                        'reason': 'who are you'
                    })
                )
            )
        )
        source_id = '132456'
        service = plaintext.PlainTextService('foohost', 8000)
        with self.assertRaises(exceptions.RequestUnauthorized):
            service.request_extraction(source_id)

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_request_extraction_forbidden(self, mock_Session):
        """Service returns 403 Forbidden."""
        mock_Session.return_value = mock.MagicMock(
            post=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.FORBIDDEN,
                    json=mock.MagicMock(return_value={
                        'reason': 'you do not have sufficient authz'
                    })
                )
            )
        )
        source_id = '132456'
        service = plaintext.PlainTextService('foohost', 8000)
        with self.assertRaises(exceptions.RequestForbidden):
            service.request_extraction(source_id)

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_extraction_is_complete(self, mock_Session):
        """Extraction is indeed complete."""
        mock_get = mock.MagicMock(
            return_value=mock.MagicMock(
                status_code=status.SEE_OTHER,
                json=mock.MagicMock(return_value={}),
                headers={'Location': '...'}
            )
        )
        mock_Session.return_value = mock.MagicMock(get=mock_get)
        source_id = '132456'
        service = plaintext.PlainTextService('http://foohost:8123')
        self.assertTrue(service.extraction_is_complete(source_id))
        self.assertEqual(
            mock_get.call_args[0][0],
            'http://foohost:8123/submission/132456/status'
        )

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_extraction_in_progress(self, mock_Session):
        """Extraction is still in progress."""
        mock_get = mock.MagicMock(
            return_value=mock.MagicMock(
                status_code=status.OK,
                json=mock.MagicMock(return_value={'status': 'in_progress'})
            )
        )
        mock_Session.return_value = mock.MagicMock(get=mock_get)
        source_id = '132456'
        service = plaintext.PlainTextService('http://foohost:8123')
        self.assertFalse(service.extraction_is_complete(source_id))
        self.assertEqual(
            mock_get.call_args[0][0],
            'http://foohost:8123/submission/132456/status'
        )

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_extraction_failed(self, mock_Session):
        """Extraction failed."""
        mock_get = mock.MagicMock(
            return_value=mock.MagicMock(
                status_code=status.OK,
                json=mock.MagicMock(return_value={'status': 'failed'})
            )
        )
        mock_Session.return_value = mock.MagicMock(get=mock_get)
        source_id = '132456'
        service = plaintext.PlainTextService('http://foohost:8123')
        with self.assertRaises(plaintext.ExtractionFailed):
            self.assertFalse(service.extraction_is_complete(source_id))

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_complete_unauthorized(self, mock_Session):
        """Service returns 401 Unauthorized."""
        mock_Session.return_value = mock.MagicMock(
            get=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.UNAUTHORIZED,
                    json=mock.MagicMock(return_value={
                        'reason': 'who are you'
                    })
                )
            )
        )
        source_id = '132456'
        service = plaintext.PlainTextService('foohost', 8000)
        with self.assertRaises(exceptions.RequestUnauthorized):
            service.extraction_is_complete(source_id)

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_complete_forbidden(self, mock_Session):
        """Service returns 403 Forbidden."""
        mock_Session.return_value = mock.MagicMock(
            get=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.FORBIDDEN,
                    json=mock.MagicMock(return_value={
                        'reason': 'you do not have sufficient authz'
                    })
                )
            )
        )
        source_id = '132456'
        service = plaintext.PlainTextService('foohost', 8000)
        with self.assertRaises(exceptions.RequestForbidden):
            service.extraction_is_complete(source_id)

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_retrieve_unauthorized(self, mock_Session):
        """Service returns 401 Unauthorized."""
        mock_Session.return_value = mock.MagicMock(
            get=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.UNAUTHORIZED,
                    json=mock.MagicMock(return_value={
                        'reason': 'who are you'
                    })
                )
            )
        )
        source_id = '132456'
        service = plaintext.PlainTextService('foohost', 8000)
        with self.assertRaises(exceptions.RequestUnauthorized):
            service.retrieve_content(source_id)

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_retrieve_forbidden(self, mock_Session):
        """Service returns 403 Forbidden."""
        mock_Session.return_value = mock.MagicMock(
            get=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.FORBIDDEN,
                    json=mock.MagicMock(return_value={
                        'reason': 'you do not have sufficient authz'
                    })
                )
            )
        )
        source_id = '132456'
        service = plaintext.PlainTextService('foohost', 8000)
        with self.assertRaises(exceptions.RequestForbidden):
            service.retrieve_content(source_id)

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_retrieve(self, mock_Session):
        """Retrieval is successful."""
        content = b'thisisthecontent'
        mock_get = mock.MagicMock(
            return_value=mock.MagicMock(
                status_code=status.OK,
                content=content
            )
        )
        mock_Session.return_value = mock.MagicMock(get=mock_get)
        source_id = '132456'
        service = plaintext.PlainTextService('http://foohost:8123')
        self.assertEqual(service.retrieve_content(source_id), content,
                         "Returns binary content as received")
        self.assertEqual(
            mock_get.call_args[0][0],
            'http://foohost:8123/submission/132456'
        )

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_retrieve_nonexistant(self, mock_Session):
        """There is no such plaintext resource."""
        mock_get = mock.MagicMock(
            return_value=mock.MagicMock(
                status_code=status.NOT_FOUND,
                json=mock.MagicMock(return_value={'reason': 'no such thing'})
            )
        )
        mock_Session.return_value = mock.MagicMock(get=mock_get)
        source_id = '132456'
        service = plaintext.PlainTextService('http://foohost:8123')
        with self.assertRaises(exceptions.NotFound):
            service.retrieve_content(source_id)

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_retrieve_in_progress(self, mock_Session):
        """There is no such plaintext resource."""
        mock_get = mock.MagicMock(
            return_value=mock.MagicMock(
                status_code=status.SEE_OTHER,
                json=mock.MagicMock(return_value={}),
                headers={'Location': '...'}
            )
        )
        mock_Session.return_value = mock.MagicMock(get=mock_get)
        source_id = '132456'
        service = plaintext.PlainTextService('http://foohost:8123')
        with self.assertRaises(plaintext.ExtractionInProgress):
            service.retrieve_content(source_id)


class TestPlainTextServiceModule(TestCase):
    """Tests for :mod:`.services.plaintext`."""

    def session(self, status_code=status.OK, method="get", json={},
                content="", headers={}):
        """Make a mock session."""
        return mock.MagicMock(**{
            method: mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status_code,
                    json=mock.MagicMock(
                        return_value=json
                    ),
                    content=content,
                    headers=headers
                )
            )
        })

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_already_in_progress(self, mock_Session):
        """A plaintext extraction is already in progress."""
        mock_Session.return_value = self.session(
            status_code=status.SEE_OTHER,
            method='post',
            headers={'Location': '...'}
        )

        source_id = '132456'
        with self.assertRaises(plaintext.ExtractionInProgress):
            plaintext.PlainTextService.request_extraction(source_id)

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_request_extraction(self, mock_Session):
        """Extraction is successfully requested."""
        mock_session = mock.MagicMock(**{
            'post': mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.ACCEPTED,
                    json=mock.MagicMock(return_value={}),
                    content='',
                    headers={'Location': '/somewhere'}
                )
            ),
            'get': mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.OK,
                    json=mock.MagicMock(
                        return_value={'reason': 'extraction in process'}
                    ),
                    content="{'reason': 'fulltext extraction in process'}",
                    headers={}
                )
            )
        })
        mock_Session.return_value = mock_session
        source_id = '132456'
        self.assertIsNone(
            plaintext.PlainTextService.request_extraction(source_id)
        )
        self.assertEqual(mock_session.post.call_args[0][0],
                         'http://foohost:5432/submission/132456')

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_extraction_bad_request(self, mock_Session):
        """Service returns 400 Bad Request."""
        mock_Session.return_value = self.session(
            status_code=status.BAD_REQUEST,
            method='post',
            json={'reason': 'something is not quite right'}
        )
        source_id = '132456'
        with self.assertRaises(exceptions.BadRequest):
            plaintext.PlainTextService.request_extraction(source_id)

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_extraction_server_error(self, mock_Session):
        """Service returns 500 Internal Server Error."""
        mock_Session.return_value = self.session(
            status_code=status.INTERNAL_SERVER_ERROR,
            method='post',
            json={'reason': 'something is not quite right'}
        )
        source_id = '132456'
        with self.assertRaises(exceptions.RequestFailed):
            plaintext.PlainTextService.request_extraction(source_id)

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_extraction_unauthorized(self, mock_Session):
        """Service returns 401 Unauthorized."""
        mock_Session.return_value = self.session(
            status_code=status.UNAUTHORIZED,
            method='post',
            json={'reason': 'who are you'}
        )
        source_id = '132456'
        with self.assertRaises(exceptions.RequestUnauthorized):
            plaintext.PlainTextService.request_extraction(source_id)

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_request_extraction_forbidden(self, mock_Session):
        """Service returns 403 Forbidden."""
        mock_Session.return_value = self.session(
            status_code=status.FORBIDDEN,
            method='post',
            json={'reason': 'you do not have sufficient authz'}
        )
        source_id = '132456'
        with self.assertRaises(exceptions.RequestForbidden):
            plaintext.PlainTextService.request_extraction(source_id)

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_extraction_is_complete(self, mock_Session):
        """Extraction is indeed complete."""
        mock_session = self.session(
            status_code=status.SEE_OTHER,
            headers={'Location': '...'}
        )
        mock_Session.return_value = mock_session
        source_id = '132456'
        self.assertTrue(plaintext.PlainTextService.extraction_is_complete(source_id))
        self.assertEqual(mock_session.get.call_args[0][0],
                         'http://foohost:5432/submission/132456/status')

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_extraction_in_progress(self, mock_Session):
        """Extraction is still in progress."""
        mock_session = self.session(
            json={'status': 'in_progress'}
        )
        mock_Session.return_value = mock_session
        source_id = '132456'
        self.assertFalse(plaintext.PlainTextService.extraction_is_complete(source_id))
        self.assertEqual(mock_session.get.call_args[0][0],
                         'http://foohost:5432/submission/132456/status')

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_extraction_failed(self, mock_Session):
        """Extraction failed."""
        mock_Session.return_value = self.session(json={'status': 'failed'})
        source_id = '132456'
        with self.assertRaises(plaintext.ExtractionFailed):
            self.assertFalse(plaintext.PlainTextService.extraction_is_complete(source_id))

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_complete_unauthorized(self, mock_Session):
        """Service returns 401 Unauthorized."""
        mock_Session.return_value = self.session(
            status_code=status.UNAUTHORIZED,
            json={'reason': 'who are you'}
        )
        source_id = '132456'
        with self.assertRaises(exceptions.RequestUnauthorized):
            plaintext.PlainTextService.extraction_is_complete(source_id)

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_complete_forbidden(self, mock_Session):
        """Service returns 403 Forbidden."""
        mock_Session.return_value = self.session(
            status_code=status.FORBIDDEN,
            json={'reason': 'you do not have sufficient authz'}
        )
        source_id = '132456'
        with self.assertRaises(exceptions.RequestForbidden):
            plaintext.PlainTextService.extraction_is_complete(source_id)

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_retrieve_unauthorized(self, mock_Session):
        """Service returns 401 Unauthorized."""
        mock_Session.return_value = self.session(
            status_code=status.UNAUTHORIZED,
            json={'reason': 'who are you'}
        )
        source_id = '132456'
        with self.assertRaises(exceptions.RequestUnauthorized):
            plaintext.PlainTextService.retrieve_content(source_id)

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_retrieve_forbidden(self, mock_Session):
        """Service returns 403 Forbidden."""
        mock_Session.return_value = self.session(
            status_code=status.FORBIDDEN,
            json={'reason': 'you do not have sufficient authz'}
        )
        source_id = '132456'
        with self.assertRaises(exceptions.RequestForbidden):
            plaintext.PlainTextService.retrieve_content(source_id)

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_retrieve(self, mock_Session):
        """Retrieval is successful."""
        content = b'thisisthecontent'
        mock_get = mock.MagicMock(
            return_value=mock.MagicMock(
                status_code=status.OK,
                content=content
            )
        )
        mock_Session.return_value = mock.MagicMock(get=mock_get)
        source_id = '132456'
        self.assertEqual(
            plaintext.PlainTextService.retrieve_content(source_id),
            content,
            "Returns binary content as received"
        )
        self.assertEqual(mock_get.call_args[0][0],
                         'http://foohost:5432/submission/132456')

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_retrieve_nonexistant(self, mock_Session):
        """There is no such plaintext resource."""
        mock_Session.return_value = self.session(
            status_code=status.NOT_FOUND,
            json={'reason': 'no such thing'}
        )
        source_id = '132456'
        with self.assertRaises(exceptions.NotFound):
            plaintext.PlainTextService.retrieve_content(source_id)

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_retrieve_in_progress(self, mock_Session):
        """There is no such plaintext resource."""
        mock_Session.return_value = self.session(
            status_code=status.SEE_OTHER,
            headers={'Location': '...'}
        )
        source_id = '132456'
        with self.assertRaises(plaintext.ExtractionInProgress):
            plaintext.PlainTextService.retrieve_content(source_id)
