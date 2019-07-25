"""Integration with the submission preview service."""

from typing import Tuple, List, Any, Union, Optional, IO, Callable, Iterator
from http import HTTPStatus as status

from arxiv.base import logging
from arxiv.integration.api import service

logger = logging.getLogger(__name__)


class ReadWrapper:
    """Wraps a response body streaming iterator to provide ``read()``."""
    def __init__(self, iter_content: Callable[[int], Iterator[bytes]],
                 size: int = 4096) -> None:
        """Initialize the streaming iterator."""
        self._iter_content = iter_content(size)

    def read(self, *args: Any, **kwargs: Any) -> bytes:
        """
        Read the next chunk of the content stream.

        Arguments are ignored, since the chunk size must be set at the start.
        """
        return next(self._iter_content, b'')


class Preview(service.HTTPIntegration):
    """Represents an interface to the submission preview."""

    VERSION = '0.0'
    SERVICE = 'preview'

    class Meta:
        """Configuration for :class:`Preview` integration."""

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

    def get_preview(self, submission_id: str, checksum: str, token: str) \
            -> Tuple[ReadWrapper, str]:
        """Retrieve the content of the PDF preview for a submission."""
        ...
