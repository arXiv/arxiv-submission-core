"""Upload-related data structures."""

from typing import NamedTuple, List, Optional, Dict, MutableMapping, Iterable
import io
from datetime import datetime
import dateutil.parser
from enum import Enum
import io

from .submission import Submission, SubmissionContent


class FileErrorLevels(Enum):
    """Error severities."""

    ERROR = 'ERROR'
    WARNING = 'WARN'


class FileError(NamedTuple):
    """Represents an error returned by the file management service."""

    error_type: FileErrorLevels
    message: str
    more_info: Optional[str] = None

    def to_dict(self) -> dict:
        """Generate a dict representation of this error."""
        return {
            'error_type': self.error_type,
            'message': self.message,
            'more_info': self.more_info
        }

    @classmethod
    def from_dict(cls: type, data: dict) -> 'FileError':
        """Instantiate a :class:`FileError` from a dict."""
        instance: FileError = cls(**data)
        return instance


class FileStatus(NamedTuple):
    """Represents the state of an uploaded file."""

    path: str
    name: str
    file_type: str
    size: int
    modified: datetime
    ancillary: bool = False
    errors: List[FileError] = []

    def to_dict(self) -> dict:
        """Generate a dict representation of this status object."""
        data = {
            'path': self.path,
            'name': self.name,
            'file_type': self.file_type,
            'size': self.size,
            'modified': self.modified.isoformat(),
            'ancillary': self.ancillary,
            'errors': [e.to_dict() for e in self.errors]
        }
        # if data['modified']:
        #     data['modified'] = data['modified']
        # if data['errors']:
        #     data['errors'] = [e.to_dict() for e in data['errors']]
        return data

    @classmethod
    def from_dict(cls: type, data: dict) -> 'Upload':
        """Instantiate a :class:`FileStatus` from a dict."""
        if 'errors' in data:
            data['errors'] = [FileError.from_dict(e) for e in data['errors']]
        if 'modified' in data and type(data['modified']) is str:
            data['modified'] = dateutil.parser.parse(data['modified'])
        instance: Upload = cls(**data)
        return instance


class UploadStatus(Enum):  # type: ignore
    """The status of the upload workspace with respect to submission."""

    READY = 'READY'
    READY_WITH_WARNINGS = 'READY_WITH_WARNINGS'
    ERRORS = 'ERRORS'

class UploadLifecycleStates(Enum):  # type: ignore
    """The status of the workspace with respect to its lifecycle."""

    ACTIVE = 'ACTIVE'
    RELEASED = 'RELEASED'
    DELETED = 'DELETED'


class Upload(NamedTuple):
    """Represents the state of an upload workspace."""

    started: datetime
    completed: datetime
    created: datetime
    modified: datetime
    status: UploadStatus
    lifecycle: UploadLifecycleStates
    locked: bool
    identifier: int
    source_format: SubmissionContent.Format = SubmissionContent.Format.UNKNOWN
    checksum: Optional[str] = None
    size: Optional[int] = None
    """Size in bytes of the uncompressed upload workspace."""
    compressed_size: Optional[int] = None
    """Size in bytes of the compressed upload package."""
    files: List[FileStatus] = []
    errors: List[FileError] = []

    @property
    def file_count(self) -> int:
        """The number of files in the workspace."""
        return len(self.files)

    def to_dict(self) -> dict:
        """Generate a dict representation of this status object."""
        return {
            'started': self.started.isoformat(),
            'completed': self.completed.isoformat(),
            'created': self.created.isoformat(),
            'modified': self.modified.isoformat(),
            'status': self.status.value,
            'lifecycle': self.lifecycle.value,
            'locked': self.locked,
            'identifier': self.identifier,
            'source_format': self.source_format.value,
            'checksum': self.checksum,
            'size': self.size,
            'files': [d.to_dict() for d in self.files],
            'errors': [d.to_dict() for d in self.errors]
        }

    @classmethod
    def from_dict(cls: type, data: dict) -> 'Upload':
        """Instantiate an :class:`Upload` from a dict."""
        if 'files' in data:
            data['files'] = [FileStatus.from_dict(f) for f in data['files']]
        if 'errors' in data:
            data['errors'] = [FileError.from_dict(e) for e in data['errors']]
        for key in ['started', 'completed', 'created', 'modified']:
            if key in data and type(data[key]) is str:
                data[key] = dateutil.parser.parse(data[key])
        if 'source_format' in data:
            data['source_format'] = \
                SubmissionContent.Format(data['source_format'])
        instance: Upload = cls(**data)
        return instance
