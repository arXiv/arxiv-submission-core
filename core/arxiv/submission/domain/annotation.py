"""
Provides quality-assurance annotations for the submission & moderation system.

Annotations encode more ephemeral moderation-related information, and are
therefore not represented as events/commands in themselves. To work with
annotations on submissions, use
:class:`arxiv.submission.domain.event.AddAnnotation` and
:class:`arxiv.submission.domain.event.RemoveAnnotation`.
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
class Annotation:
    """Auxilliary metadata used by the submission and moderation process."""

    creator: Agent
    created: datetime = field(default_factory=get_tzaware_utc_now)
    # scope: str      # TODO: document this.
    proxy: Optional[Agent] = field(default=None)

    @property
    def annotation_type(self) -> str:
        """Name (str) of the type of annotation."""
        return type(self).__name__

    @property
    def annotation_id(self) -> str:
        """Get the unique identifier for an :class:`.Annotation` instance."""
        h = hashlib.new('sha1')
        h.update(b'%s:%s:%s' % (self.created.isoformat().encode('utf-8'),
                                self.annotation_type.encode('utf-8'),
                                self.creator.agent_identifier.encode('utf-8')))
        return h.hexdigest()

    def to_dict(self) -> dict:
        """Generate a dict representation of this :class:`.Annotation`."""
        data = asdict(self)
        data['annotation_type'] = self.annotation_type
        data['annotation_id'] = self.annotation_id
        data['created'] = self.created.isoformat()
        return data


@dataclass
class Comment(Annotation):
    """A freeform textual annotation."""

    body: str = field(default_factory=str)

    @property
    def comment_id(self) -> str:
        """Get the unique identifier for a :class:`.Comment` instance."""
        return self.annotation_id

    def to_dict(self) -> dict:
        """Generate a dict representation of this :class:`.Comment`."""
        data = asdict(self)
        data['comment_id'] = self.comment_id
        return data


ClassifierResult = TypedDict('ClassifierResult',
                             {'category': Category, 'probability': float})


@dataclass
class ClassifierResults(Annotation):
    """Represents suggested classifications from an auto-classifier."""

    class Classifiers(Enum):
        """Supported classifiers."""

        CLASSIC = "classic"

    classifier: Classifiers = field(default=Classifiers.CLASSIC)
    results: List[ClassifierResult] = field(default_factory=list)


@dataclass
class Feature(Annotation):
    """Represents feature counts drawn from the content of the submission."""

    class FeatureTypes(Enum):
        """Supported features."""

        CHARACTER_COUNT = "chars"
        PAGE_COUNT = "pages"
        STOPWORD_COUNT = "stops"
        STOPWORD_PERCENT = "%stop"
        WORD_COUNT = "words"

    feature_type: FeatureTypes = field(default=FeatureTypes.WORDS)
    feature_value: Union[int, float] = field(default=0)
