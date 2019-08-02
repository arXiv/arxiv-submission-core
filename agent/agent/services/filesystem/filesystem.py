"""Integration with the legacy filesystem shim."""

from http import HTTPStatus as status
from typing import Tuple, List, Any, Union, Optional, IO

from urllib3.util.retry import Retry

from arxiv.base import logging
from arxiv.integration.api import service
from arxiv.integration.api.exceptions import NotFound

logger = logging.getLogger(__name__)


class ValidationFailed(Exception):
    """Validation of the deposit failed."""


class Filesystem(service.HTTPIntegration):
    """Represents an interface to the legacy filesystem."""

    SERVICE = 'legacy-filesystem'
    VERSION = 'b2996fcb034080b8a2adb5c769a44ad366b3f9b1'

    class Meta:
        """Configuration for :class:`Filesystem` integration."""

        service_name = "filesystem"

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

    def deposit_source(self, submission_id: int, pointer: IO[bytes],
                       checksum: str) -> None:
        """
        Deposit a source package for ``submission_id``.

        Verifies the integrity of the transferred file by comparing the content
        of the ``ETag`` response  header to ``checksum``.
        """
        response = self.request('post', f'/{submission_id}/source',
                                data=pointer, expected_code=[status.CREATED])
        etag = response.headers.get('ETag')
        if etag != checksum:
            raise ValidationFailed(f'Expected {checksum}, got {etag}')

    def deposit_preview(self, submission_id: int, pointer: IO[bytes],
                        checksum: str) -> None:
        """
        Deposit a PDF preview for ``submission_id``.

        Verifies the integrity of the transferred file by comparing the content
        of the ``ETag`` response  header to ``checksum``.
        """
        response = self.request('post', f'/{submission_id}/preview',
                                data=pointer, expected_code=[status.CREATED])
        etag = response.headers.get('ETag')
        if etag != checksum:
            raise ValidationFailed(f'Expected {checksum}, got {etag}')

    def does_source_exist(self, submission_id: int,
                          checksum: Optional[str] = None) -> bool:
        """
        Verify that the source for a submission exists.

        If ``checksum`` is provided, verifies the integrity of the remote
        file by comparing the content of the ``ETag`` response  header to
        ``checksum``.
        """
        try:
            response = self.request('head', f'/{submission_id}/source')
        except NotFound:
            return False
        if checksum is not None:
            etag = response.headers.get('ETag')
            if etag != checksum:
                raise ValidationFailed(f'Expected {checksum}, got {etag}')
        return bool(response.status_code == status.OK)

    def does_preview_exist(self, submission_id: int,
                           checksum: Optional[str] = None) -> bool:
        """
        Verify that the preview for a submission exists.

        If ``checksum`` is provided, verifies the integrity of the remote
        file by comparing the content of the ``ETag`` response  header to
        ``checksum``.
        """
        try:
            response = self.request('head', f'/{submission_id}/preview')
        except NotFound:
            return False
        if checksum is not None:
            etag = response.headers.get('ETag')
            if etag != checksum:
                raise ValidationFailed(f'Expected {checksum}, got {etag}')
        return bool(response.status_code == status.OK)

