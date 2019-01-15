"""
Provides quality-assurance annotations for the submission & moderation system.

Annotations encode more ephemeral moderation-related information, and are
therefore not represented as events/commands in themselves. To work with
annotations on submissions, use
:class:`arxiv.submission.domain.event.AddAnnotation` and
:class:`arxiv.submission.domain.event.RemoveAnnotation`.
"""

from typing import Optional, Union
from datetime import datetime
import hashlib

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
        """The unique identifier for an :class:`.Annotation` instance."""
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
class Proposal(Annotation):
    """Represents a proposal to apply an event to a submission."""

    event_type: Optional[type] = field(default=None)
    event_data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Generate a dict representation of this :class:`.Proposal`."""
        return asdict(self)


@dataclass
class Comment(Annotation):
    """A freeform textual annotation."""

    body: str = field(default_factory=str)

    @property
    def comment_id(self) -> str:
        """The unique identifier for a :class:`.Comment` instance."""
        return self.annotation_id

    def to_dict(self) -> dict:
        """Generate a dict representation of this :class:`.Comment`."""
        data = asdict(self)
        data['comment_id'] = self.comment_id
        return data


@dataclass
class PossibleDuplicate(Annotation):
    """Represents a possible duplicate submission."""

    matching_id: int = field(default=-1)
    matching_title: str = field(default_factory=str)
    matching_owner: Optional[Agent] = field(default=None)

    def to_dict(self) -> dict:
        """Generate a dict from of this :class:`.PossibleDuplicate`."""
        data = super(PossibleDuplicate, self).to_dict()
        data['matching_owner'] = self.matching_owner.to_dict()
        return data


@dataclass
class PossibleMetadataProblem(Annotation):
    """Represents a possible issue with the content of a metadata field."""

    field_name: Optional[str] = field(default=None)
    """If ``None``, applies to metadata generally."""

    description: str = field(default_factory=str)


@dataclass
class ClassifierResult(Annotation):
    """Represents a suggested classification from an auto-classifier."""

    CLASSIC = "classic"

    classifier: str = field(default=CLASSIC)
    category: Optional[Category] = field(default=None)
    probability: float = field(default=0.0)


@dataclass
class FeatureCount(Annotation):
    """Represents feature counts drawn from the content of the submission."""

    CHARACTERS = "chars"
    PAGES = "pages"
    STOPWORDS = "stops"
    WORDS = "words"

    feature_type: str = field(default=WORDS)
    feature_count: int = field(default=0)


@dataclass
class ContentFlag(Annotation):
    """Represents a QA flag based on the content of the submission."""

    flag_type: Optional[str] = field(default=None)
    flag_value: Optional[Union[int, str, float, dict, list]]


@dataclass
class PlainTextExtraction(Annotation):
    """Represents the status/result of plain text extraction."""

    REQUESTED = "requested"
    SUCCEEDED = "succeeded"
    FAILED = "failed"

    status: str = field(default=SUCCEEDED)
    identifier: Optional[str] = field(default=None)
    """Task ID for the extraction."""
    extractor_version: str = field(default="0.0")
