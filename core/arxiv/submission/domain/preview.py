"""Provides :class:`.Preview`."""
from typing import Optional, IO
from datetime import datetime
from dataclasses import dataclass, field, asdict


@dataclass
class Preview:
    """Metadata about a submission preview."""

    source_id: int
    """Identifier of the source from which the preview was generated."""

    source_checksum: str
    """Checksum of the source from which the preview was generated."""

    preview_checksum: str
    """Checksum of the preview content itself."""

    size_bytes: int
    """Size (in bytes) of the preview content."""

    added: datetime
    """The datetime when the preview was deposited."""
