from typing import Optional
from datetime import datetime
import hashlib

from dataclasses import dataclass, asdict, field

from .agent import Agent


@dataclass
class Annotation:
    """Auxilliary metadata used by the submission and moderation process."""

    creator: Agent
    created: datetime
    scope: str      # TODO: document this.
    proxy: Optional[Agent]

    @property
    def annotation_type(self):
        """Name (str) of the type of annotation."""
        return type(self).__name__

    @property
    def annotation_id(self):
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
        return data


@dataclass
class Proposal(Annotation):
    """Represents a proposal to apply an event to a submission."""

    event_type: type
    event_data: dict

    def to_dict(self) -> dict:
        """Generate a dict representation of this :class:`.Proposal`."""
        return asdict(self)


@dataclass
class Comment(Annotation):
    """A freeform textual annotation."""

    body: str

    @property
    def comment_id(self):
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

    matching_id: int
    matching_title: int
    matching_owner: Agent

    def to_dict(self) -> dict:
        """Generate a dict from of this :class:`.PossibleDuplicate`."""
        data = super(PossibleDuplicate, self).to_dict()
        data['matching_owner'] = self.matching_owner.to_dict()
        return data


@dataclass
class Flag(Annotation):
    """Tags used to route submissions based on moderation policies."""

    pass
