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

from enum import Enum
from typing import Any

from arxiv.base import logging
from arxiv.integration.api import status, exceptions, service
from arxiv.taxonomy import Category

logger = logging.getLogger(__name__)


class ExtractionFailed(exceptions.RequestFailed):
    """The plain text extraction service failed to extract text."""


class ExtractionInProgress(exceptions.RequestFailed):
    """An extraction is already in progress."""


class PlainTextService(service.HTTPIntegration):
    """Represents an interface to the plain text extraction service."""

    VERSION = 0.3
    """Version of the service for which this module is implemented."""

    class Meta:
        """Configuration for :class:`Classifier`."""

        service_name = "plaintext"

    class Status(Enum):
        """Task statuses."""

        IN_PROGRESS = 'in_progress'
        SUCCEEDED = 'succeeded'
        FAILED = 'failed'

    @property
    def _base_endpoint(self) -> str:
        return f'{self._scheme}://{self._host}:{self._port}'

    def is_available(self, **kwargs: Any) -> bool:
        """Check our connection to the plain text service."""
        try:
            response = self.request('head', '/status')
        except Exception as e:
            logger.error('Encountered error calling plain text service: %s', e)
            return False
        if response.status_code != status.OK:
            logger.error('Got unexpected status: %s', response.status_code)
            return False
        return True

    def endpoint(self, source_id: str):
        """Get the URL of the extraction endpoint."""
        return f'/submission/{source_id}'

    def status_endpoint(self, source_id: str):
        """Get the URL of the extraction status endpoint."""
        return f'/submission/{source_id}/status'

    def request_extraction(self, source_id: str) -> None:
        """
        Make a request for plaintext extraction using the submission upload ID.

        Parameters
        ----------
        source_id : str
            ID of the submission upload workspace.

        """
        expected_code = [status.OK, status.ACCEPTED,
                         status.SEE_OTHER]
        response = self.request('post', self.endpoint(source_id),
                                expected_code=expected_code)
        if response.status_code == status.SEE_OTHER:
            raise ExtractionInProgress('Extraction already exists', response)
        elif response.status_code not in expected_code:
            raise exceptions.RequestFailed('Unexpected status', response)
        return

    def extraction_is_complete(self, source_id: str) -> bool:
        """
        Check the status of an extraction task by submission upload ID.

        Parameters
        ----------
        source_id : str
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
        endpoint = self.status_endpoint(source_id)
        expected_code = [status.OK, status.SEE_OTHER]
        response = self.request('get', endpoint, allow_redirects=False,
                                expected_code=expected_code)
        data = response.json()
        if response.status_code == status.SEE_OTHER:
            return True
        elif self.Status(data['status']) is self.Status.IN_PROGRESS:
            return False
        elif self.Status(data['status']) is self.Status.FAILED:
            raise ExtractionFailed('Extraction failed', response)
        raise ExtractionFailed('Unexpected state', response)

    def retrieve_content(self, source_id: str) -> bytes:
        """
        Retrieve plain text content by submission upload ID.

        Parameters
        ----------
        source_id : str
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
        expected_code = [status.OK, status.SEE_OTHER]
        response = self.request('get', self.endpoint(source_id),
                                expected_code=expected_code)
        if response.status_code == status.SEE_OTHER:
            raise ExtractionInProgress('Extraction is in progress', response)
        return response.content
