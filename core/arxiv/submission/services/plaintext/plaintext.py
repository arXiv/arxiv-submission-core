"""
Provides integration with the plaintext extraction service.

This integration is focused on usage patterns required by the submission
system. Specifically:

1. Must be able to request an extraction for a compiled submission.
2. Must be able to poll whether the extraction has completed.
3. Must be able to retrieve the raw binary content from when the extraction
   has finished successfully.
4. Encounter an informative exception if something goes wrong.

This represents only a subset of the functionality provided by the plaintext
service itself.
"""

from typing import Tuple, List, Any, Union, NamedTuple, Optional, Dict
from urllib.parse import urlparse, urlunparse, urlencode
from enum import Enum
from math import exp, log
import json
from functools import wraps

from arxiv import status
from arxiv.taxonomy import Category
from arxiv.base.globals import get_application_config, get_application_global

import requests
from requests.packages.urllib3.util.retry import Retry

VERSION = 0.3
"""Version of the plain text service for which this module is implemented."""


class RequestFailed(IOError):
    """The plain text extraction service returned an unexpected status code."""

    def __init__(self, msg: str, data: dict = {}) -> None:
        """Attach (optional) data to the exception."""
        self.data = data
        super(RequestFailed, self).__init__(msg)


class DoesNotExist(RequestFailed):
    """The requested resource does not exist."""


class ExtractionInProgress(RequestFailed):
    """An extraction is already in progress."""


class RequestUnauthorized(RequestFailed):
    """Client/user is not authenticated."""


class RequestForbidden(RequestFailed):
    """Client/user is not allowed to perform this request."""


class BadRequest(RequestFailed):
    """The request was malformed or otherwise improper."""


class BadResponse(RequestFailed):
    """The response from the plain text extraction service was malformed."""


class ConnectionFailed(IOError):
    """Could not connect to the plain text extraction service."""


class SecurityException(ConnectionFailed):
    """Raised when SSL connection fails."""


class ExtractionFailed(RuntimeError):
    """The plain text extraction service failed to extract text."""


class PlainTextService(object):
    """Represents an interface to the plain text extraction service."""

    class Status(Enum):
        """Task statuses."""

        IN_PROGRESS = 'in_progress'
        SUCCEEDED = 'succeeded'
        FAILED = 'failed'

    def __init__(self, host: str, port: int, scheme: str = 'https',
                 headers: Dict[str, str] = {}) -> None:
        """Set connection details for the service."""
        self._host = host
        self._port = port
        self._scheme = scheme
        self._session = requests.Session()
        self._retry = Retry(  # type: ignore
            total=10,
            read=10,
            connect=10,
            status=10,
            backoff_factor=0.5
        )
        self._adapter = requests.adapters.HTTPAdapter(max_retries=self._retry)
        self._session.mount(self._scheme, self._adapter)
        self._session.headers.update(headers)

    def _make_request(self, method: str, path: str, **kw) -> requests.Response:
        try:
            resp = getattr(self._session, method)(self._path(path), **kw)
        except requests.exceptions.SSLError as e:
            raise SecurityException('SSL failed: %s' % e) from e
        except requests.exceptions.ConnectionError as e:
            raise ConnectionFailed('Could not connect: %s' % e) from e
        if resp.status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
            raise RequestFailed(f'Status: {resp.status_code}; {resp.content}')
        elif resp.status_code == status.HTTP_401_UNAUTHORIZED:
            raise RequestUnauthorized(f'Not authorized: {resp.content}')
        elif resp.status_code == status.HTTP_403_FORBIDDEN:
            raise RequestForbidden(f'Forbidden: {resp.content}')
        elif resp.status_code == status.HTTP_404_NOT_FOUND:
            raise DoesNotExist(f'No such resource: {resp.content}')
        elif resp.status_code >= status.HTTP_400_BAD_REQUEST:
            raise BadRequest(f'Bad request: {resp.content}',
                             data=resp.content)
        return resp

    def set_auth_token(self, token: str) -> None:
        """Set the authn/z token to use in subsequent requests."""
        self._session.headers.update({'Authorization': token})

    @property
    def _base_endpoint(self) -> str:
        return f'{self._scheme}://{self._host}:{self._port}'

    def _path(self, path: str, query: dict = {}) -> str:
        o = urlparse(self._base_endpoint)
        path = path.lstrip('/')
        return urlunparse((
            o.scheme, o.netloc, f"{o.path}{path}",
            None, urlencode(query), None
        ))

    def endpoint(self, upload_id: str):
        """Get the URL of the classifier endpoint."""
        return f'/submission/{upload_id}'

    def status_endpoint(self, upload_id: str):
        """Get the URL of the classifier endpoint."""
        return f'/submission/{upload_id}/status'

    def request(self, method: str, path: str, **kw) -> Tuple[dict, int, dict]:
        """Perform an HTTP request, and handle any exceptions."""
        resp = self._make_request(method, path, **kw)

        # There should be nothing in a 204 response.
        if resp.status_code is status.HTTP_204_NO_CONTENT:
            return {},  resp.status_code, resp.headers
        try:
            return resp.json(), resp.status_code, resp.headers
        except json.decoder.JSONDecodeError as e:
            raise BadResponse('Could not decode: {resp.content}') from e

    def request_extraction(self, upload_id: str) -> None:
        """
        Make a request for plaintext extraction using the submission upload ID.

        Parameters
        ----------
        upload_id : str
            ID of the submission upload workspace.

        """
        data, code, headers = self.request('post', self.endpoint(upload_id))
        if code == status.HTTP_303_SEE_OTHER:
            raise ExtractionInProgress('An extraction already exists')
        elif code != status.HTTP_202_ACCEPTED:
            raise RequestFailed(f'Got status {code}')
        return

    def extraction_is_complete(self, upload_id: str) -> bool:
        """
        Check the status of an extraction task by submission upload ID.

        Parameters
        ----------
        upload_id : str
            ID of the submission upload workspace.

        Returns
        -------
        bool

        Raises
        ------
        :class:`ExtractionFailed`
            Raised if the task is in a failed state, or an unexpected condition
            is encountered.

        """
        endpoint = self.status_endpoint(upload_id)
        resp, code, hdrs = self.request('get', endpoint, allow_redirects=False)
        if code == status.HTTP_303_SEE_OTHER:
            return True
        elif self.Status(resp['status']) is self.Status.IN_PROGRESS:
            return False
        elif self.Status(resp['status']) is self.Status.FAILED:
            raise ExtractionFailed('Extraction failed: %s' % resp)
        raise ExtractionFailed('Unexpected state: %s' % resp)

    def retrieve_content(self, upload_id: str) -> bytes:
        """
        Retrieve plain text content by submission upload ID.

        Parameters
        ----------
        upload_id : str
            ID of the submission upload workspace.

        Returns
        -------
        bytes
            Raw text content.

        Raises
        ------
        :class:`RequestFailed`
            Raised if an unexpected status was encountered.
        :class:`ExtractionInProgress`
            Raised if an extraction is currently in progress
        """
        resp = self._make_request('get', self.endpoint(upload_id))
        if resp.status_code == status.HTTP_303_SEE_OTHER:
            raise ExtractionInProgress('An extraction is in progress')
        elif resp.status_code != status.HTTP_200_OK:
            raise RequestFailed(f'Got status {resp.status_code}')
        return resp.content


def init_app(app: object=None) -> None:
    """Configure an application instance."""
    config = get_application_config(app)
    config.setdefault('PLAINTEXT_HOST', 'localhost')
    config.setdefault('PLAINTEXT_PORT', 8000)
    config.setdefault('PLAINTEXT_SCHEME', 'https')


def get_instance(app: object=None) -> PlainTextService:
    """Create a new :class:`.PlainTextService` instance."""
    config = get_application_config()
    host = config.get('PLAINTEXT_HOST', 'localhost')
    port = config.get('PLAINTEXT_PORT', 8000)
    scheme = config.get('PLAINTEXT_SCHEME', 'https')
    return PlainTextService(host, port, scheme)


def current_instance():
    """Get/create :class:`.PlainTextService` instance for this context."""
    g = get_application_global()
    if g is None:
        return get_instance()
    if 'plaintext' not in g:
        g.plaintext = get_instance()
    return g.plaintext


@wraps(PlainTextService.request_extraction)
def request_extraction(upload_id: str) -> None:
    """Make a request to the plain text extraction service."""
    return current_instance().request_extraction(upload_id)


@wraps(PlainTextService.extraction_is_complete)
def extraction_is_complete(upload_id: str) -> bool:
    """Check the status of an extraction task by submission upload ID."""
    return current_instance().extraction_is_complete(upload_id)


@wraps(PlainTextService.retrieve_content)
def retrieve_content(upload_id: str) -> bytes:
    """Retrieve plain text content by submission upload ID."""
    return current_instance().retrieve_content(upload_id)
