"""
Integration with the :mod:`compiler` service API.

The compiler is responsible for building PDF, DVI, and other goodies from
LaTeX sources. In the submission UI, we specifically want to build a PDF so
that the user can preview their submission. Additionally, we want to show the
submitter the TeX log so that they can identify any potential problems with
their sources.
"""
from typing import Tuple, Optional, List, Union, NamedTuple
import json
import io
import re
from enum import Enum
from functools import wraps
from collections import defaultdict
from urllib.parse import urlparse, urlunparse, urlencode

import dateutil.parser
import requests
from requests.packages.urllib3.util.retry import Retry


from werkzeug.datastructures import FileStorage

from arxiv import status
from arxiv.base import logging
from arxiv.base.globals import get_application_config, get_application_global

logger = logging.getLogger(__name__)

VERSION = "0.1"
"""Verison of the compiler service with which we are integrating."""

NAME = "arxiv-compiler"
"""Name of the compiler service with which we are integrating."""


# This is intended as a fixed class attributes, not a slot.
class Status(Enum):      # type: ignore
    """Acceptable compilation process statuses."""

    SUCCEEDED = "completed"
    IN_PROGRESS = "in_progress"
    FAILED = "failed"


class Format(Enum):      # type: ignore
    """Supported compilation output formats."""

    PDF = "pdf"
    DVI = "dvi"
    PS = "ps"


class CompilationStatus(NamedTuple):
    """The state of a compilation attempt from the :mod:`.compiler` service."""

    # Here are the actual slots/fields.
    upload_id: str
    """This is the upload workspace identifier."""
    status: Status
    """The status of the compilation."""
    checksum: str
    """Checksum of the source package that we are compiling."""
    output_format: Format = Format.PDF
    """The requested output format."""

    @property
    def identifier(self):
        """Get the task identifier."""
        return f"{self.upload_id}::{self.checksum}::{self.output_format.value}"

    @property
    def content_type(self):
        """Get the MIME type for the compilation product."""
        _ctypes = {
            Format.PDF: 'application/pdf',
            Format.DVI: 'application/x-dvi',
            Format.PS: 'application/postscript'
        }
        return _ctypes[self.output_format]

    def to_dict(self) -> dict:
        """Generate a dict representation of this object."""
        return {
            'upload_id': self.upload_id,
            'format': self.output_format.value,
            'checksum': self.checksum,
            'status': self.status.value
        }


class CompilationProduct(NamedTuple):
    """Content of a compilation product itself."""

    stream: io.BytesIO
    """Readable buffer with the product content."""

    status: Optional[CompilationStatus] = None
    """Status information about the product."""

    checksum: Optional[str] = None
    """The B64-encoded MD5 hash of the compilation product."""


class RequestFailed(IOError):
    """The compiler service returned an unexpected status code."""

    def __init__(self, msg: str, data: dict = {}) -> None:
        """Attach (optional) data to the exception."""
        self.data = data
        super(RequestFailed, self).__init__(msg)


class RequestUnauthorized(RequestFailed):
    """Client/user is not authenticated."""


class RequestForbidden(RequestFailed):
    """Client/user is not allowed to perform this request."""


class BadRequest(RequestFailed):
    """The request was malformed or otherwise improper."""


class BadResponse(RequestFailed):
    """The response from the compiler service was malformed."""


class ConnectionFailed(IOError):
    """Could not connect to the compiler service."""


class SecurityException(ConnectionFailed):
    """Raised when SSL connection fails."""


class NoSuchResource(RequestFailed):
    """The requested resource does not exist."""


class CompilationFailed(RuntimeError):
    """The compilation service failed to compile the source package."""


class Download(object):
    """Wrapper around response content."""

    def __init__(self, response: requests.Response) -> None:
        """Initialize with a :class:`requests.Response` object."""
        self._response = response

    def read(self) -> bytes:
        """Read response content."""
        return self._response.content


class CompilerService(object):
    """Encapsulates a connection with the compiler service."""

    class Compilers(Enum):
        """Compilers known to be supported by the compiler service."""

        foo = 'foo'

    def __init__(self, endpoint: str, verify_cert: bool = True,
                 headers: dict = {}) -> None:
        """
        Initialize an HTTP session.

        Parameters
        ----------
        endpoints : str
            One or more endpoints for metadata retrieval. If more than one
            are provided, calls to :meth:`.retrieve` will cycle through those
            endpoints for each call.
        verify_cert : bool
            Whether or not SSL certificate verification should enforced.
        headers : dict
            Headers to be included on all requests.

        """
        logger.debug('New CompilerService with endpoint %s', endpoint)
        self._session = requests.Session()
        self._verify_cert = verify_cert
        self._retry = Retry(  # type: ignore
            total=10,
            read=10,
            connect=10,
            status=10,
            backoff_factor=0.5
        )
        self._adapter = requests.adapters.HTTPAdapter(max_retries=self._retry)
        self._session.mount(f'{urlparse(endpoint).scheme}://', self._adapter)
        if not endpoint.endswith('/'):
            endpoint += '/'
        self._endpoint = endpoint
        self._session.headers.update(headers)

        self.output_format = Format.PDF

    def _parse_compilation_status(self, data: dict) -> CompilationStatus:

        return CompilationStatus(

        )

    def _parse_task_id(self, task_uri: str) -> str:
        parts = urlparse(task_uri)
        task_id = re.match(r'^/task/([^/]+)', parts.path).group(1)
        return task_id

    def _path(self, path: str, query: dict = {}) -> str:
        o = urlparse(self._endpoint)
        path = path.lstrip('/')
        return urlunparse((
            o.scheme, o.netloc, f"{o.path}{path}",
            None, urlencode(query), None
        ))

    def _make_request(self, method: str, path: str,
                      expected_codes: List[int] = [200], **kw) \
            -> requests.Response:
        kw.update({'allow_redirects': False})
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
            logger.debug(resp.json())
            raise NoSuchResource('Resource does not exist', data=resp.json())
        elif resp.status_code >= status.HTTP_400_BAD_REQUEST:
            raise BadRequest(f'Bad request: {resp.content}',
                             data=resp.content)
        elif resp.status_code not in expected_codes:
            raise RequestFailed(f'Unexpected status code: {resp.status_code}')
        return resp

    def set_auth_token(self, token: str) -> None:
        """Set the authn/z token to use in subsequent requests."""
        self._session.headers.update({'Authorization': token})

    def request(self, method: str, path: str, expected_codes: int = 200,
                **kwargs) -> Tuple[dict, dict]:
        """Perform an HTTP request, and handle any exceptions."""
        resp = self._make_request(method, path, expected_codes, **kwargs)

        # There should be nothing in a 204 response.
        if resp.status_code is status.HTTP_204_NO_CONTENT:
            return {}, resp.headers
        try:
            return resp.json(), resp.headers
        except json.decoder.JSONDecodeError as e:
            raise BadResponse('Could not decode: {resp.content}') from e

    def get_service_status(self) -> dict:
        """Get the status of the compiler service."""
        return self.request('get', 'status')

    def request_compilation(self, upload_id: str, checksum: str,
                            compiler: Optional[Compilers] = None) \
            -> CompilationStatus:
        """
        Request compilation for an upload workspace.

        Parameters
        ----------
        upload_id : int
            Unique identifier for the upload workspace.
        compiler : str or None
            Name of the preferred compiler.

        Returns
        -------
        :class:`CompilationStatus`
            The current state of the compilation.

        """
        logger.debug("Requesting compilation for %s: %s",
                     upload_id, self.output_format)
        payload = {
            'source_id': upload_id,
            'checksum': checksum,
            'format': self.output_format.value
        }
        data, headers = self.request('post', f'/',
                                     json=payload,
                                     expected_codes=[
                                        status.HTTP_202_ACCEPTED,
                                        status.HTTP_302_FOUND,
                                        status.HTTP_303_SEE_OTHER,
                                     ])
        return CompilationStatus(
            upload_id=upload_id,
            checksum=checksum,
            output_format=self.output_format,
            status=Status.IN_PROGRESS
        )

    def get_compilation_product(self, upload_id: str, checksum: str,
                                output_format: Format) \
            -> Union[CompilationStatus, CompilationProduct]:
        """
        Get the compilation product for an upload workspace, if it exists.

        The file management service will check its latest PDF product against
        the checksum of the upload workspace. If there is a match, it returns
        the file. Otherwise, if there is a compilation task with a matching
        checksum, redirects to the task status endpoint. Otherwise, a 404 is
        returned resulting in :class:`NoSuchResource` exception.
        """
        expected_codes = [
           status.HTTP_200_OK,
           status.HTTP_302_FOUND
        ]
        endpoint = f'/task/{upload_id}/{checksum}/{output_format.value}'
        logger.debug('GET %s', endpoint)
        response = self._make_request('get', endpoint, expected_codes,
                                      stream=True)

        if 'Location' in response.headers:
            task_id = self._parse_task_id(response.headers['Location'])
            return get_status(upload_id, task_id)
        return CompilationProduct(
            upload_id=upload_id,
            stream=Download(response)
        )

    def get_status(self, upload_id: str, checksum: str,
                   output_format: Format) -> CompilationStatus:
        """Get the status of a compilation task."""
        endpoint = f'/task/{upload_id}/{checksum}/{output_format.value}'
        logger.debug('GET %s', endpoint)
        data, headers = self.request('get', endpoint, expected_codes=[
                                        status.HTTP_200_OK,
                                        status.HTTP_303_SEE_OTHER
                                     ])
        return CompilationStatus(
            upload_id=upload_id,
            checksum=checksum,
            output_format=output_format,
            status=Status(data['status']['status'])
        )

    def compilation_is_complete(self, upload_id: str, checksum: str,
                                output_format: Format) -> bool:
        """Check whether compilation has completed successfully."""
        stat = self.get_status(upload_id, checksum, output_format)
        if stat.status is Status.SUCCEEDED:
            return True
        elif stat.status is Status.FAILED:
            raise CompilationFailed('Compilation failed')
        return False


def init_app(app: object = None) -> None:
    """Set default configuration parameters for an application instance."""
    config = get_application_config(app)
    config.setdefault('COMPILER_ENDPOINT', 'http://compiler-api:8100/')
    config.setdefault('COMPILER_VERIFY', True)


def get_session(app: object = None) -> CompilerService:
    """Get a new session with the compiler endpoint."""
    config = get_application_config(app)
    endpoint = config.get('COMPILER_ENDPOINT', 'http://compiler-api:8100/')
    verify_cert = config.get('COMPILER_VERIFY', True)
    logger.debug('Create CompilerService with endpoint %s', endpoint)
    return CompilerService(endpoint, verify_cert=verify_cert)


def current_session() -> CompilerService:
    """Get/create :class:`.CompilerService` for this context."""
    g = get_application_global()
    if not g:
        return get_session()
    elif 'filemanager' not in g:
        g.filemanager = get_session()   # type: ignore
    return g.filemanager    # type: ignore


@wraps(CompilerService.set_auth_token)
def set_auth_token(token: str) -> None:
    """See :meth:`CompilerService.set_auth_token`."""
    return current_session().set_auth_token(token)


@wraps(CompilerService.get_compilation_product)
def get_compilation_product(upload_id: str) -> \
        Union[CompilationStatus, CompilationProduct]:
    """See :meth:`CompilerService.get_compilation_product`."""
    return current_session().get_compilation_product(upload_id)


@wraps(CompilerService.request_compilation)
def request_compilation(upload_id: str, checksum: str,
                        compiler: Optional[CompilerService.Compilers] = None) \
        -> CompilationStatus:
    """See :meth:`CompilerService.request_compilation`."""
    return current_session().request_compilation(upload_id, checksum, compiler=compiler)


@wraps(CompilerService.get_status)
def get_status(upload_id: str, checksum: str, fmt: str) -> CompilationStatus:
    """See :meth:`CompilerService.get_status`."""
    return current_session().get_status(upload_id, checksum, fmt)


@wraps(CompilerService.compilation_is_complete)
def compilation_is_complete(upload_id: str, checksum: str, fmt: str) -> bool:
    """See :meth:`CompilerService.compilation_is_complete`."""
    return current_session().compilation_is_complete(upload_id, checksum, fmt)


def get_task_id(upload_id: str, checksum: str, output_format: Format) -> str:
    """Generate a key for a /checksum/format combination."""
    return f"{upload_id}::{checksum}::{output_format.value}"


def split_task_id(task_id: str) -> Tuple[str, str, Format]:
    upload_id, checksum, format_value = task_id.split("::")
    return upload_id, checksum, Format(format_value)
