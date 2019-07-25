"""Integration with the legacy filesystem shim."""

from typing import Tuple, List, Any, Union, Optional, IO
from http import HTTPStatus as status

from arxiv.base import logging
from arxiv.integration.api import service

logger = logging.getLogger(__name__)


class ValidationFailed(Exception):
    """Validation of the deposit failed."""


class Filesystem(service.HTTPIntegration):
    """Represents an interface to the legacy filesystem."""

    VERSION = '0.0'
    SERVICE = 'filesystem'

    class Meta:
        """Configuration for :class:`Filesystem` integration."""

        service_name = "filesystem"

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
                                data=pointer)
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
                                data=pointer)
        etag = response.headers.get('ETag')
        if etag != checksum:
            raise ValidationFailed(f'Expected {checksum}, got {etag}')

    def source_exists(self, submission_id: int,
                      checksum: Optional[str] = None) -> bool:
        """
        Verify that the source for a submission exists.

        If ``checksum`` is provided, verifies the integrity of the remote
        file by comparing the content of the ``ETag`` response  header to
        ``checksum``.
        """
        response = self.request('head', f'/{submission_id}/source')
        if checksum is not None:
            etag = response.headers.get('ETag')
            if etag != checksum:
                raise ValidationFailed(f'Expected {checksum}, got {etag}')
        return bool(response.status_code == status.OK)

    def preview_exists(self, submission_id: int,
                       checksum: Optional[str] = None) -> bool:
        """
        Verify that the preview for a submission exists.

        If ``checksum`` is provided, verifies the integrity of the remote
        file by comparing the content of the ``ETag`` response  header to
        ``checksum``.
        """
        response = self.request('head', f'/{submission_id}/preview')
        if checksum is not None:
            etag = response.headers.get('ETag')
            if etag != checksum:
                raise ValidationFailed(f'Expected {checksum}, got {etag}')
        return bool(response.status_code == status.OK)

