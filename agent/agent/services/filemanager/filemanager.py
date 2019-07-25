"""Provides an integration with the file management service."""

from typing import Tuple, List, Any, Union, Optional, IO, Callable, Iterator
from http import HTTPStatus as status

from arxiv.base import logging
from arxiv.integration.api import service


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



class Filemanager(service.HTTPIntegration):
    """Encapsulates a connection with the file management service."""

    VERSION = '0.0'
    SERVICE = 'filemanager'

    class Meta:
        """Configuration for :class:`FileManager`."""

        service_name = "filemanager"

    def is_available(self, **kwargs: Any) -> bool:
        """Check our connection to the filemanager service."""
        timeout: float = kwargs.get('timeout', 0.2)
        try:
            response = self.request('get', 'status', timeout=timeout)
            return bool(response.status_code == 200)
        except Exception as e:
            return False
        return True

    def get_source_package(self, upload_id: str, token: str) \
            -> Tuple[ReadWrapper, str]:
        """
        Retrieve the sanitized/processed upload package.

        Parameters
        ----------
        upload_id : str
            Unique long-lived identifier for the upload.
        token : str
            Auth token to include in the request.

        Returns
        -------
        callable
            When called with ``chunk_size: int``, returns an iterator over
            bytes in the response body.
        str
            Checksum of the source package from the ``ETag`` response header.

        """
        path = f'/{upload_id}/content'
        response = self.request('get', path, token, stream=True)
        return ReadWrapper(response.iter_content), response.headers.get('ETag')