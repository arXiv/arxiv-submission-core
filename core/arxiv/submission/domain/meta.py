"""Metadata objects in support of submissions."""

from typing import Optional, List
from arxiv.taxonomy import Category
from dataclasses import dataclass, asdict, field


@dataclass
class Classification:
    """An archive/category classification for a :class:`.domain.Submission`."""

    category: Category

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
