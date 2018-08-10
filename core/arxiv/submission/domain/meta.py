"""Metadata objects in support of :class:`.Submission`s."""

from typing import Optional, List
from dataclasses import dataclass, asdict


@dataclass
class Classification:
    """An archive/category classification for a :class:`.Submission`."""

    category: str

    def to_dict(self) -> dict:
        """Generate a dict representation of this :class:`.Classification`."""
        return asdict(self)


@dataclass
class License:
    """An license for distribution of the submission."""

    uri: str
    name: Optional[str] = None

    def to_dict(self) -> dict:
        """Generate a dict representation of this :class:`.License`."""
        return asdict(self)
