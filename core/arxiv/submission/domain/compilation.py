"""Data structs related to compilation."""

from enum import Enum
from datetime import datetime
from typing import Optional, NamedTuple
from dataclasses import dataclass, field
import io


@dataclass
class Compilation:
    """The state of a compilation attempt from the :mod:`.compiler` service."""

    class Status(Enum):      # type: ignore
        """Acceptable compilation process statuses."""

        SUCCEEDED = "completed"
        IN_PROGRESS = "in_progress"
        FAILED = "failed"

    class Format(Enum):      # type: ignore
        """Supported compilation output formats."""

        PDF = "pdf"
        DVI = "dvi"
        PS = "ps"

        @property
        def content_type(self):
            """Get the MIME type for the compilation product."""
            _ctypes = {
                self.PDF: 'application/pdf',
                self.DVI: 'application/x-dvi',
                self.PS: 'application/postscript'
            }
            return _ctypes[self]

    class SupportedCompiler(Enum):
        """Compiler known to be supported by the compiler service."""

        PDFLATEX = 'pdflatex'

    class Reason(Enum):
        """Specific reasons for a (usually failure) outcome."""

        AUTHORIZATION = "auth_error"
        MISSING = "missing_source"
        SOURCE_TYPE = "invalid_source_type"
        CORRUPTED = "corrupted_source"
        CANCELLED = "cancelled"
        ERROR = "compilation_errors"
        NETWORK = "network_error"
        STORAGE = "storage"
        DOCKER = 'docker'
        NONE = None

    # Here are the actual slots/fields.
    source_id: str
    """This is the upload workspace identifier."""
    status: Status
    """The status of the compilation."""
    checksum: str
    """Checksum of the source package that we are compiling."""
    output_format: Format = field(default=Format.PDF)
    """The requested output format."""
    reason: Reason = field(default=Reason.NONE)
    """The specific reason for the :attr:`.status`."""
    description: Optional[str] = field(default=None)
    """Additional detail about the :attr:`.status`."""
    size_bytes: int = field(default=0)
    """The size of the compilation product in bytes."""
    start_time: Optional[datetime] = field(default=None)
    end_time: Optional[datetime] = field(default=None)

    def __post_init__(self):
        """Check enums."""
        self.output_format = self.Format(self.output_format)
        self.reason = self.Reason(self.reason)

    @property
    def identifier(self):
        """Get the task identifier."""
        return self.get_identifier(self.source_id, self.checksum,
                                   self.output_format)

    @staticmethod
    def get_identifier(source_id: str, checksum: str,
                       output_format: Format = Format.PDF) -> str:
        return f"{source_id}/{checksum}/{output_format.value}"

    @property
    def content_type(self):
        """Get the MIME type for the compilation product."""
        return self.output_format.content_type


@dataclass
class CompilationProduct:
    """Content of a compilation product itself."""

    stream: io.BytesIO
    """Readable buffer with the product content."""

    content_type: str
    """MIME-type of the stream."""

    status: Optional[Compilation] = field(default=None)
    """Status information about the product."""

    checksum: Optional[str] = field(default=None)
    """The B64-encoded MD5 hash of the compilation product."""

    def __post_init__(self):
        """Check status."""
        if self.status and type(self.status) is dict:
            self.status = Compilation(**self.status)


@dataclass
class CompilationLog:
    """Content of a compilation log."""

    stream: io.BytesIO
    """Readable buffer with the product content."""

    status: Optional[Compilation] = field(default=None)
    """Status information about the log."""

    checksum: Optional[str] = field(default=None)
    """The B64-encoded MD5 hash of the log."""

    content_type: str = field(default='text/plain')
    """MIME-type of the stream."""

    def __post_init__(self):
        """Check status."""
        if self.status and type(self.status) is dict:
            self.status = Compilation(**self.status)
