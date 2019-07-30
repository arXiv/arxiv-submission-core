"""Provides :class:`.Preview`."""
from typing import Optional, IO
from datetime import datetime
from dataclasses import dataclass, field, asdict


@dataclass
class Preview:
    source_id: int
    source_checksum: str
    preview_checksum: str
    size_bytes: int
    added: datetime
