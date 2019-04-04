"""Metadata objects in support of submissions."""

from typing import Optional, List
from arxiv.taxonomy import Category
from dataclasses import dataclass, asdict, field


@dataclass
class Classification:
    """An archive/category classification for a :class:`.domain.submission.Submission`."""

    category: Category


@dataclass
class License:
    """An license for distribution of the submission."""

    uri: str
    name: Optional[str] = None
