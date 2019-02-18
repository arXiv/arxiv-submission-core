"""
Provides quality-assurance annotations for the submission & moderation system.
"""

from typing import Optional, Union, List
from datetime import datetime
import hashlib
from enum import Enum
from mypy_extensions import TypedDict

from dataclasses import dataclass, asdict, field

from arxiv.taxonomy import Category

from .util import get_tzaware_utc_now
from .agent import Agent


@dataclass
class Comment:
    """A freeform textual annotation."""

    event_id: str
    creator: Agent
    created: datetime
    proxy: Optional[Agent] = field(default=None)
    body: str = field(default_factory=str)


ClassifierResult = TypedDict('ClassifierResult',
                             {'category': Category, 'probability': float})


@dataclass
class ClassifierResults:
    """Represents suggested classifications from an auto-classifier."""

    class Classifiers(Enum):
        """Supported classifiers."""

        CLASSIC = "classic"

    event_id: str
    creator: Agent
    created: datetime
    proxy: Optional[Agent] = field(default=None)
    classifier: Classifiers = field(default=Classifiers.CLASSIC)
    results: List[ClassifierResult] = field(default_factory=list)


@dataclass
class Feature:
    """Represents features drawn from the content of the submission."""

    class FeatureTypes(Enum):
        """Supported features."""

        CHARACTER_COUNT = "chars"
        PAGE_COUNT = "pages"
        STOPWORD_COUNT = "stops"
        STOPWORD_PERCENT = "%stop"
        WORD_COUNT = "words"

    event_id: str
    created: datetime
    creator: Agent
    feature_type: FeatureTypes
    proxy: Optional[Agent] = field(default=None)
    feature_value: Union[int, float] = field(default=0)


Annotation = Union[ClassifierResults, Feature]
