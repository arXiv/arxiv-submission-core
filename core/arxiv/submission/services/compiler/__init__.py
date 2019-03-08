"""
Integration with the compiler service API.

The compiler is responsible for building PDF, DVI, and other goodies from
LaTeX sources. In the submission UI, we specifically want to build a PDF so
that the user can preview their submission. Additionally, we want to show the
submitter the TeX log so that they can identify any potential problems with
their sources.
"""
from typing import Tuple, Optional, List, Union, NamedTuple, Mapping
import json
import io
import re
from enum import Enum
from functools import wraps
from collections import defaultdict
from urllib.parse import urlparse, urlunparse, urlencode

import dateutil.parser

from werkzeug.datastructures import FileStorage
import requests

from arxiv.base import logging
from arxiv.integration.api import status, service

logger = logging.getLogger(__name__)


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

    @property
    def content_type(self):
        """Get the MIME type for the compilation product."""
        _ctypes = {
            Format.PDF: 'application/pdf',
            Format.DVI: 'application/x-dvi',
            Format.PS: 'application/postscript'
        }
        return _ctypes[self]


class Compiler(Enum):
    """Compiler known to be supported by the compiler service."""

    PDFLATEX = 'pdflatex'


class Reason(Enum):
    """Specific reasons for a (usually failure) outcome."""

    AUTHORIZATION = "auth_error"
    MISSING = "missing_source"
    SOURCE_TYPE = "invalid_source_type"
    CORRUPTED = "corrupted_source"
    CANCELLED = "cancelled"
    ERROR = "compilation_errors"
    NETWORK = "network_error"
    STORAGE = "storage"
    NONE = None


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
    reason: Reason = Reason.NONE
    """The specific reason for the :attr:`.status`."""
    description: Optional[str] = None
    """Additional detail about the :attr:`.status`."""
    size_bytes: int = 0
    """The size of the compilation product in bytes."""

    @property
    def identifier(self):
        """Get the task identifier."""
        return f"{self.upload_id}/{self.checksum}/{self.output_format.value}"

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
            'status': self.status.value,
            'size_bytes': self.size_bytes
        }


class CompilationProduct(NamedTuple):
    """Content of a compilation product itself."""

    stream: io.BytesIO
    """Readable buffer with the product content."""

    content_type: str
    """MIME-type of the stream."""

    status: Optional[CompilationStatus] = None
    """Status information about the product."""

    checksum: Optional[str] = None
    """The B64-encoded MD5 hash of the compilation product."""


class CompilationLog(NamedTuple):
    """Content of a compilation log."""

    stream: io.BytesIO
    """Readable buffer with the product content."""

    status: Optional[CompilationStatus] = None
    """Status information about the log."""

    checksum: Optional[str] = None
    """The B64-encoded MD5 hash of the log."""

    content_type: str = 'text/plain'
    """MIME-type of the stream."""


class CompilationFailed(RuntimeError):
    """The compilation service failed to compile the source package."""


class Download(object):
    """Wrapper around response content."""

    def __init__(self, response: requests.Response) -> None:
        """Initialize with a :class:`requests.Response` object."""
        self._response = response

    def read(self, *args, **kwargs) -> bytes:
        """Read response content."""
        return self._response.content


class CompilerService(service.HTTPIntegration):
    """Encapsulates a connection with the compiler service."""

    VERSION = "0.1"
    """Verison of the compiler service with which we are integrating."""

    NAME = "arxiv-compiler"
    """Name of the compiler service with which we are integrating."""

    class Meta:
        """Configuration for :class:`Classifier`."""

        service_name = "compiler"

    def _parse_status_response(self, data: dict) -> CompilationStatus:
        return CompilationStatus(
            upload_id=data['source_id'],
            checksum=data['checksum'],
            output_format=Format(data['output_format']),
            status=Status(data['status']),
            reason=Reason(data['reason']) if 'reason' in data else None,
            description=data.get('description', None),
            size_bytes=data.get('size_bytes', 0)
        )

    def _parse_loc(self, headers: Mapping) -> str:
        return urlparse(headers['Location']).path

    def get_service_status(self) -> dict:
        """Get the status of the compiler service."""
        return self.json('get', 'status')[0]

    def compile(self, upload_id: str, checksum: str, token: str,
                compiler: Optional[Compiler] = None,
                output_format: Format = Format.PDF,
                force: bool = False) -> CompilationStatus:
        """
        Request compilation for an upload workspace.

        Unless ``force`` is ``True``, the compiler service will only attempt
        to compile a source ID + checksum + format combo once. If there is
        already a compilation underway or complete for the parameters in this
        request, the service will redirect to the corresponding status URI.
        Hence the data returned by this function may be from the response to
        the initial POST request, or from the status endpoint after being
        redirected.

        Parameters
        ----------
        upload_id : int
            Unique identifier for the upload workspace.
        checksum : str
            State up of the upload workspace.
        compiler : :class:`.Compiler` or None
            Name of the preferred compiler.
        output_format : :class:`.Format`
            Defaults to :attr:`.Format.PDF`.
        force : bool
            If True, compilation will be forced even if it has been attempted
            with these parameters previously. Default is ``False``.

        Returns
        -------
        :class:`CompilationStatus`
            The current state of the compilation.

        """
        logger.debug("Requesting compilation for %s @ %s: %s",
                     upload_id, checksum, output_format)
        payload = {'source_id': upload_id, 'checksum': checksum,
                   'format': output_format.value, 'force': force}
        endpoint = '/'
        expected_codes = [status.HTTP_200_OK, status.HTTP_202_ACCEPTED,
                          status.HTTP_303_SEE_OTHER, status.HTTP_302_FOUND]
        data, headers = self.json('post', endpoint, token, json=payload,
                                  expected_code=expected_codes)
        return self._parse_status_response(data)

    def get_status(self, upload_id: str, checksum: str, token: str,
                   output_format: Format = Format.PDF) -> CompilationStatus:
        """
        Get the status of a compilation.

        Parameters
        ----------
        upload_id : int
            Unique identifier for the upload workspace.
        checksum : str
            State up of the upload workspace.
        output_format : :class:`.Format`
            Defaults to :attr:`.Format.PDF`.

        Returns
        -------
        :class:`CompilationStatus`
            The current state of the compilation.

        """
        endpoint = f'/{upload_id}/{checksum}/{output_format.value}'
        data, headers = self.json('get', endpoint, token)
        return self._parse_status_response(data)

    def compilation_is_complete(self, upload_id: str, checksum: str,
                                token: str, output_format: Format) -> bool:
        """Check whether compilation has completed successfully."""
        stat = self.get_status(upload_id, checksum, token, output_format)
        if stat.status is Status.SUCCEEDED:
            return True
        elif stat.status is Status.FAILED:
            raise CompilationFailed('Compilation failed')
        return False

    def get_product(self, upload_id: str, checksum: str, token: str,
                    output_format: Format = Format.PDF) -> CompilationProduct:
        """
        Get the compilation product for an upload workspace, if it exists.

        Parameters
        ----------
        upload_id : int
            Unique identifier for the upload workspace.
        checksum : str
            State up of the upload workspace.
        output_format : :class:`.Format`
            Defaults to :attr:`.Format.PDF`.

        Returns
        -------
        :class:`CompilationProduct`
            The compilation product itself.

        """
        endpoint = f'/{upload_id}/{checksum}/{output_format.value}/product'
        response = self.json('get', endpoint, token, stream=True)
        return CompilationProduct(content_type=output_format.content_type,
                                  stream=io.BytesIO(response.content))

    def get_log(self, upload_id: str, checksum: str, token: str,
                output_format: Format = Format.PDF) -> CompilationLog:
        """
        Get the compilation log for an upload workspace, if it exists.

        Parameters
        ----------
        upload_id : int
            Unique identifier for the upload workspace.
        checksum : str
            State up of the upload workspace.
        output_format : :class:`.Format`
            Defaults to :attr:`.Format.PDF`.

        Returns
        -------
        :class:`CompilationProduct`
            The compilation product itself.

        """
        endpoint = f'/{upload_id}/{checksum}/{output_format.value}/log'
        response = self.json('get', endpoint, token, stream=True)
        return CompilationLog(stream=io.BytesIO(response.content))


def get_task_id(upload_id: str, checksum: str, output_format: Format) -> str:
    """Generate a key for a /checksum/format combination."""
    return f"{upload_id}/{checksum}/{output_format.value}"


def split_task_id(task_id: str) -> Tuple[str, str, Format]:
    upload_id, checksum, format_value = task_id.split("/")
    return upload_id, checksum, Format(format_value)
