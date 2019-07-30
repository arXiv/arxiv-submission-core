"""Integration with the submission preview service."""

import io
from typing import Tuple, List, Any, Union, Optional, IO, Callable, Iterator, \
    IO
from http import HTTPStatus as status
from datetime import datetime

from typing_extensions import Literal
from mypy_extensions import TypedDict
from backports.datetime_fromisoformat import MonkeyPatch

from arxiv.base import logging
from arxiv.integration.api import service, exceptions

from ...domain.preview import Preview

MonkeyPatch.patch_fromisoformat()
logger = logging.getLogger(__name__)


class AlreadyExists(exceptions.BadRequest):
    """An attempt was made to deposit a preview that already exists."""


class PreviewMeta(TypedDict):
    added: str
    size_bytes: int
    checksum: str


class ReadWrapper(io.BytesIO):
    """Wraps a response body streaming iterator to provide ``read()``."""

    def __init__(self, iter_content: Callable[[int], Iterator[bytes]],
                 size: int = 4096) -> None:
        """Initialize the streaming iterator."""
        self._iter_content = iter_content(size)

    def seekable(self) -> Literal[False]:
        """Indicate that this is a non-seekable stream."""
        return False

    def readable(self) -> Literal[True]:
        """Indicate that it *is* a readable stream."""
        return True

    def read(self, *args: Any, **kwargs: Any) -> bytes:
        """
        Read the next chunk of the content stream.

        Arguments are ignored, since the chunk size must be set at the start.
        """
        return next(self._iter_content, b'')


class PreviewService(service.HTTPIntegration):
    """Represents an interface to the submission preview."""

    VERSION = '0.0'
    SERVICE = 'preview'

    class Meta:
        """Configuration for :class:`PreviewService` integration."""

        service_name = 'preview'

    def is_available(self, **kwargs: Any) -> bool:
        """Check our connection to the filesystem service."""
        timeout: float = kwargs.get('timeout', 0.2)
        try:
            response = self.request('head', '/status', timeout=timeout)
        except Exception as e:
            logger.error('Encountered error calling filesystem: %s', e)
            return False
        return bool(response.status_code == status.OK)

    def get(self, source_id: int, checksum: str, token: str) \
            -> Tuple[IO[bytes], str]:
        """Retrieve the content of the PDF preview for a submission."""
        response = self.request('get', f'/{source_id}/{checksum}/content',
                                token)
        preview_checksum = str(response.headers['ETag'])
        return ReadWrapper(response.iter_content), preview_checksum

    def deposit(self, source_id: int, checksum: str, stream: IO[bytes],
                token: str, overwrite: bool = False) -> Preview:
        headers = {'Content-type': 'application/pdf',
                   'Overwrite': 'true' if overwrite else 'false'}
        try:
            response = self.request('put', f'/{source_id}/{checksum}/content',
                                    token, data=stream,
                                    headers=headers,
                                    expected_code=[status.CREATED],
                                    allow_2xx_redirects=False)
        except exceptions.BadRequest as e:
            if e.response.status_code == status.CONFLICT:
                raise AlreadyExists('Preview already exists', e.response) from e
            raise
        response_data: PreviewMeta = response.json()
        added: datetime = datetime.fromisoformat(response_data['added'])
        return Preview(source_id=source_id,
                       source_checksum=checksum,
                       preview_checksum=response_data['checksum'],
                       added=added,
                       size_bytes=response_data['size_bytes'])
