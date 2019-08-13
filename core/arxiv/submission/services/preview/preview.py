"""Integration with the submission preview service."""

import io
from datetime import datetime
from http import HTTPStatus as status
from typing import Tuple, Any, IO, Callable, Iterator, Optional
from urllib3.util.retry import Retry

from backports.datetime_fromisoformat import MonkeyPatch
from mypy_extensions import TypedDict
from typing_extensions import Literal

from arxiv.base import logging
from arxiv.integration.api import service, exceptions

from ...domain.preview import Preview
from ..util import ReadWrapper


MonkeyPatch.patch_fromisoformat()
logger = logging.getLogger(__name__)


class AlreadyExists(exceptions.BadRequest):
    """An attempt was made to deposit a preview that already exists."""


class PreviewMeta(TypedDict):
    added: str
    size_bytes: int
    checksum: str


class PreviewService(service.HTTPIntegration):
    """Represents an interface to the submission preview."""

    VERSION = '17057e6'
    SERVICE = 'preview'

    class Meta:
        """Configuration for :class:`PreviewService` integration."""

        service_name = 'preview'

    def get_retry_config(self) -> Retry:
        """
        Configure to only retry on connection errors.

        We are likely to be sending non-seakable streams, so retry should be
        handled at the application level.
        """
        return Retry(
            total=10,
            read=0,
            connect=10,
            status=0,
            backoff_factor=0.5
        )

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
        """
        Retrieve the content of the PDF preview for a submission.

        Parameters
        ----------
        source_id : int
            Unique identifier of the source package from which the preview was
            generated.
        checksum : str
            URL-safe base64-encoded MD5 hash of the source package content.
        token : str
            Authnz token for the request.

        Returns
        -------
        :class:`io.BytesIO`
            Streaming content of the preview.
        str
            URL-safe base64-encoded MD5 hash of the preview content.

        """
        response = self.request('get', f'/{source_id}/{checksum}/content',
                                token)
        preview_checksum = str(response.headers['ETag'])
        stream = ReadWrapper(response.iter_content,
                             int(response.headers['Content-Length']))
        return stream, preview_checksum

    def get_metadata(self, source_id: int, checksum: str, token: str) \
            -> Preview:
        """
        Retrieve metadata about a preview.

        Parameters
        ----------
        source_id : int
            Unique identifier of the source package from which the preview was
            generated.
        checksum : str
            URL-safe base64-encoded MD5 hash of the source package content.
        token : str
            Authnz token for the request.

        Returns
        -------
        :class:`.Preview`

        """
        response = self.request('get', f'/{source_id}/{checksum}', token)
        response_data: PreviewMeta = response.json()
        # fromisoformat() is backported from 3.7.
        added: datetime = datetime.fromisoformat(response_data['added'])  # type: ignore
        return Preview(source_id=source_id,
                       source_checksum=checksum,
                       preview_checksum=response_data['checksum'],
                       added=added,
                       size_bytes=response_data['size_bytes'])

    def deposit(self, source_id: int, checksum: str, stream: IO[bytes],
                token: str, overwrite: bool = False,
                content_checksum: Optional[str] = None) -> Preview:
        """
        Deposit a preview.

        Parameters
        ----------
        source_id : int
            Unique identifier of the source package from which the preview was
            generated.
        checksum : str
            URL-safe base64-encoded MD5 hash of the source package content.
        stream : :class:`.io.BytesIO`
            Streaming content of the preview.
        token : str
            Authnz token for the request.
        overwrite : bool
            If ``True``, any existing preview will be overwritten.

        Returns
        -------
        :class:`.Preview`

        Raises
        ------
        :class:`AlreadyExists`
            Raised when ``overwrite`` is ``False`` and a preview already exists
            for the provided ``source_id`` and ``checksum``.

        """
        headers = {'Overwrite': 'true' if overwrite else 'false'}
        if content_checksum is not None:
            headers['ETag'] = content_checksum

        # print('here is what we are about to put to the preview service')
        # raw_content = stream.read()
        # print('data length:: ', len(raw_content))

        try:
            response = self.request('put', f'/{source_id}/{checksum}/content',
                                    token, data=stream, #io.BytesIO(raw_content),       #stream
                                    headers=headers,
                                    expected_code=[status.CREATED],
                                    allow_2xx_redirects=False)
        except exceptions.BadRequest as e:
            if e.response.status_code == status.CONFLICT:
                raise AlreadyExists('Preview already exists', e.response) from e
            raise
        response_data: PreviewMeta = response.json()
        # fromisoformat() is backported from 3.7.
        added: datetime = datetime.fromisoformat(response_data['added'])  # type: ignore
        return Preview(source_id=source_id,
                       source_checksum=checksum,
                       preview_checksum=response_data['checksum'],
                       added=added,
                       size_bytes=response_data['size_bytes'])

    def has_preview(self, source_id: int, checksum: str, token: str,
                    content_checksum: Optional[str] = None) -> bool:
        """
        Check whether a preview exists for a specific source package.

        Parameters
        ----------
        source_id : int
            Unique identifier of the source package from which the preview was
            generated.
        checksum : str
            URL-safe base64-encoded MD5 hash of the source package content.
        token : str
            Authnz token for the request.
        content_checksum : str or None
            URL-safe base64-encoded MD5 hash of the preview content. If
            provided, will return ``True`` only if this value matches the
            value of the ``ETag`` header returned by the preview service.

        Returns
        -------
        bool

        """
        try:
            response = self.request('head', f'/{source_id}/{checksum}', token)
        except exceptions.NotFound:
            return False
        if content_checksum is not None:
            if response.headers.get('ETag') != content_checksum:
                return False
        return True
