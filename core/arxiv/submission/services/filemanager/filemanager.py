"""Provides an integration with the file management service."""

from typing import Tuple, List, Any, Union, Optional, IO, Callable, Iterator
from http import HTTPStatus as status

from arxiv.base import logging
from arxiv.integration.api import service

from ...domain import SubmissionContent
from ..util import ReadWrapper


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
            -> Tuple[IO[bytes], str]:
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

    def is_single_file(self, upload_id: str, token: str) \
            -> Tuple[bool, SubmissionContent.Format, str]:
        """
        Determine whether or not the source is comprised of a single file.

        Parameters
        ----------
        upload_id : str
            Unique long-lived identifier for the upload.
        token : str
            Auth token to include in the request.

        Returns
        -------
        bool
            ``True`` if the source package consists of a single file. ``False``
            otherwise.
        :class:`SubmissionContent.Format`
            The submission source format.
        str
            The checksum of the source package.

        """

    def get_single_file(self, upload_id: str, token: str) \
            -> Tuple[IO[bytes], SubmissionContent.Format, str, str]:
        """
        Get a single file.

        Parameters
        ----------
        upload_id : str
            Unique long-lived identifier for the upload.
        token : str
            Auth token to include in the request.

        Returns
        -------
        :class:`io.BytesIO`
            The content of the preview.
        :class:`SubmissionContent.Format`
            The submission source format.
        str
            The checksum of the source package.
        str
            The checksum of the preview content.

        """