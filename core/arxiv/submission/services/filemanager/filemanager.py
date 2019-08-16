"""Provides an integration with the file management service."""

from collections import defaultdict
from http import HTTPStatus as status
from typing import Tuple, List, IO, Mapping, Any

import dateutil.parser
from werkzeug.datastructures import FileStorage

from arxiv.base import logging
from arxiv.base.globals import get_application_config
from arxiv.integration.api import service

from ...domain import SubmissionContent
from ...domain.uploads import Upload, FileStatus, FileError, UploadStatus, \
    UploadLifecycleStates
from ..util import ReadWrapper

logger = logging.getLogger(__name__)


class Filemanager(service.HTTPIntegration):
    """Encapsulates a connection with the file management service."""

    SERVICE = 'filemanager'
    VERSION = '37bf8d3'

    class Meta:
        """Configuration for :class:`FileManager`."""

        service_name = "filemanager"

    def has_single_file(self, upload_id: str, token: str,
                        file_type: str = 'PDF') -> bool:
        """Checj whether an upload workspace one or more file of a type."""
        stat = self.get_upload_status(upload_id, token)
        try:
            next((f.name for f in stat.files if f.file_type == file_type))
        except StopIteration:  # Empty iterator => no such file.
            return False
        return True

    def get_single_file(self, upload_id: str, token: str,
                        file_type: str = 'PDF') -> Tuple[IO[bytes], str, str]:
        """
        Get a single PDF file from the submission package.

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
        str
            The checksum of the source package.
        str
            The checksum of the single file.

        """
        stat = self.get_upload_status(upload_id, token)
        try:
            pdf_name = next((f.name for f in stat.files
                             if f.file_type == file_type))
        except StopIteration as e:
            raise RuntimeError(f'No single `{file_type}` file found.') from e
        content, headers = self.get_file_content(upload_id, pdf_name, token)
        if stat.checksum is None:
            raise RuntimeError(f'Upload workspace checksum not set')
        return content, stat.checksum, headers['ETag']

    def is_available(self, **kwargs: Any) -> bool:
        """Check our connection to the filemanager service."""
        config = get_application_config()
        status_endpoint = config.get('FILEMANAGER_STATUS_ENDPOINT', 'status')
        timeout: float = kwargs.get('timeout', 0.2)
        try:
            response = self.request('get', status_endpoint, timeout=timeout)
            return bool(response.status_code == 200)
        except Exception as e:
            logger.error('Error when calling filemanager: %s', e)
            return False
        return True

    def _parse_upload_status(self, data: dict) -> Upload:
        file_errors: Mapping[str, List[FileError]] = defaultdict(list)
        non_file_errors = []
        filepaths = [fdata['public_filepath'] for fdata in data['files']]
        for etype, filepath, message in data['errors']:
            if filepath and filepath in filepaths:
                file_errors[filepath].append(FileError(etype.upper(), message))
            else:   # This includes messages for files that were removed.
                non_file_errors.append(FileError(etype.upper(), message))


        return Upload(
            started=dateutil.parser.parse(data['start_datetime']),
            completed=dateutil.parser.parse(data['completion_datetime']),
            created=dateutil.parser.parse(data['created_datetime']),
            modified=dateutil.parser.parse(data['modified_datetime']),
            status=UploadStatus(data['readiness']),
            lifecycle=UploadLifecycleStates(data['upload_status']),
            locked=bool(data['lock_state'] == 'LOCKED'),
            identifier=data['upload_id'],
            files=[
                FileStatus(
                    name=fdata['name'],
                    path=fdata['public_filepath'],
                    size=fdata['size'],
                    file_type=fdata['type'],
                    modified=dateutil.parser.parse(fdata['modified_datetime']),
                    errors=file_errors[fdata['public_filepath']]
                ) for fdata in data['files']
            ],
            errors=non_file_errors,
            compressed_size=data['upload_compressed_size'],
            size=data['upload_total_size'],
            checksum=data['checksum'],
            source_format=SubmissionContent.Format(data['source_format'])
        )

    def request_file(self, path: str, token: str) -> Tuple[IO[bytes], dict]:
        """Perform a GET request for a file, and handle any exceptions."""
        response = self.request('get', path, token, stream=True)
        stream = ReadWrapper(response.iter_content,
                             int(response.headers['Content-Length']))
        return stream, response.headers

    def upload_package(self, pointer: FileStorage, token: str) -> Upload:
        """
        Stream an upload to the file management service.

        If the file is an archive (zip, tar-ball, etc), it will be unpacked.
        A variety of processing and sanitization routines are performed, and
        any errors or warnings (including deleted files) will be included in
        the response body.

        Parameters
        ----------
        pointer : :class:`FileStorage`
            File upload stream from the client.
        token : str
            Auth token to include in the request.

        Returns
        -------
        dict
            A description of the upload package.
        dict
            Response headers.

        """
        files = {'file': (pointer.filename, pointer, pointer.mimetype)}
        data, _, _ = self.json('post', '/', token, files=files,
                               expected_code=[status.CREATED,
                                              status.OK],
                               timeout=30, allow_2xx_redirects=False)
        return self._parse_upload_status(data)

    def get_upload_status(self, upload_id: str, token: str) -> Upload:
        """
        Retrieve metadata about an accepted and processed upload package.

        Parameters
        ----------
        upload_id : int
            Unique long-lived identifier for the upload.
        token : str
            Auth token to include in the request.

        Returns
        -------
        dict
            A description of the upload package.
        dict
            Response headers.

        """
        data, _, _ = self.json('get', f'/{upload_id}', token)
        return self._parse_upload_status(data)

    def add_file(self, upload_id: str, pointer: FileStorage, token: str,
                 ancillary: bool = False) -> Upload:
        """
        Upload a file or package to an existing upload workspace.

        If the file is an archive (zip, tar-ball, etc), it will be unpacked. A
        variety of processing and sanitization routines are performed. Existing
        files will be overwritten by files of the  same name. and any errors or
        warnings (including deleted files) will be included in the response
        body.

        Parameters
        ----------
        upload_id : int
            Unique long-lived identifier for the upload.
        pointer : :class:`FileStorage`
            File upload stream from the client.
        token : str
            Auth token to include in the request.
        ancillary : bool
            If ``True``, the file should be added as an ancillary file.

        Returns
        -------
        dict
            A description of the upload package.
        dict
            Response headers.

        """
        files = {'file': (pointer.filename, pointer, pointer.mimetype)}
        data, _, _ = self.json('post', f'/{upload_id}', token,
                               data={'ancillary': ancillary}, files=files,
                               expected_code=[status.CREATED, status.OK],
                               timeout=30, allow_2xx_redirects=False)
        return self._parse_upload_status(data)

    def delete_all(self, upload_id: str, token: str) -> Upload:
        """
        Delete all files in the workspace.

        Does not delete the workspace itself.

        Parameters
        ----------
        upload_id : str
            Unique long-lived identifier for the upload.
        token : str
            Auth token to include in the request.

        """
        data, _, _ = self.json('post', f'/{upload_id}/delete_all', token)
        return self._parse_upload_status(data)

    def get_file_content(self, upload_id: str, file_path: str, token: str) \
            -> Tuple[IO[bytes], dict]:
        """
        Get the content of a single file from the upload workspace.

        Parameters
        ----------
        upload_id : str
            Unique long-lived identifier for the upload.
        file_path : str
            Path-like key for individual file in upload workspace. This is the
            path relative to the root of the workspace.
        token : str
            Auth token to include in the request.

        Returns
        -------
        :class:`ReadWrapper`
            A ``read() -> bytes``-able wrapper around response content.
        dict
            Response headers.

        """
        return self.request_file(f'/{upload_id}/{file_path}/content', token)

    def delete_file(self, upload_id: str, file_path: str, token: str) \
            -> Upload:
        """
        Delete a single file from the upload workspace.

        Parameters
        ----------
        upload_id : str
            Unique long-lived identifier for the upload.
        file_path : str
            Path-like key for individual file in upload workspace. This is the
            path relative to the root of the workspace.
        token : str
            Auth token to include in the request.

        Returns
        -------
        dict
            An empty dict.
        dict
            Response headers.

        """
        data, _, _ = self.json('delete', f'/{upload_id}/{file_path}', token)
        return self._parse_upload_status(data)

    def get_upload_content(self, upload_id: str, token: str) \
            -> Tuple[IO[bytes], dict]:
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
        :class:`ReadWrapper`
            A ``read() -> bytes``-able wrapper around response content.
        dict
            Response headers.

        """
        return self.request_file(f'/{upload_id}/content', token)

    def get_logs(self, upload_id: str, token: str) -> Tuple[dict, dict]:
        """
        Retrieve log files related to upload workspace.

        Indicates history or actions on workspace.

        Parameters
        ----------
        upload_id : str
            Unique long-lived identifier for the upload.
        token : str
            Auth token to include in the request.

        Returns
        -------
        dict
            Log data for the upload workspace.
        dict
            Response headers.

        """
        data, _, headers = self.json('post', f'/{upload_id}/logs', token)
        return data, headers
