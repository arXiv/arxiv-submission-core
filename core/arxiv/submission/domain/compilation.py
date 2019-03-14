"""Data structs related to compilation."""

from enum import Enum
from typing import Optional, NamedTuple
import io


# This is intended as a fixed class attributes, not a slot.
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
            Format.PDF: 'application/pdf',
            Format.DVI: 'application/x-dvi',
            Format.PS: 'application/postscript'
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
    NONE = None


class CompilationStatus(NamedTuple):
    """The state of a compilation attempt from the :mod:`.compiler` service."""

    # Here are the actual slots/fields.
    upload_id: str
    """This is the upload workspace identifier."""
    status: Status
    """The status of the compilation."""
    checksum: str
    """Checksum of the source package that we are compiling."""
    output_format: Format = Format.PDF
    """The requested output format."""
    reason: Reason = Reason.NONE
    """The specific reason for the :attr:`.status`."""
    description: Optional[str] = None
    """Additional detail about the :attr:`.status`."""
    size_bytes: int = 0
    """The size of the compilation product in bytes."""

    @property
    def identifier(self):
        """Get the task identifier."""
        return f"{self.upload_id}/{self.checksum}/{self.output_format.value}"

    @property
    def content_type(self):
        """Get the MIME type for the compilation product."""
        _ctypes = {
            Format.PDF: 'application/pdf',
            Format.DVI: 'application/x-dvi',
            Format.PS: 'application/postscript'
        }
        return _ctypes[self.output_format]

    def to_dict(self) -> dict:
        """Generate a dict representation of this object."""
        return {
            'upload_id': self.upload_id,
            'format': self.output_format.value,
            'checksum': self.checksum,
            'status': self.status.value,
            'size_bytes': self.size_bytes
        }


class CompilationProduct(NamedTuple):
    """Content of a compilation product itself."""

    stream: io.BytesIO
    """Readable buffer with the product content."""

    content_type: str
    """MIME-type of the stream."""

    status: Optional[CompilationStatus] = None
    """Status information about the product."""

    checksum: Optional[str] = None
    """The B64-encoded MD5 hash of the compilation product."""


class CompilationLog(NamedTuple):
    """Content of a compilation log."""

    stream: io.BytesIO
    """Readable buffer with the product content."""

    status: Optional[CompilationStatus] = None
    """Status information about the log."""

    checksum: Optional[str] = None
    """The B64-encoded MD5 hash of the log."""

    content_type: str = 'text/plain'
    """MIME-type of the stream."""
