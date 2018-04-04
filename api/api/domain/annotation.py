"""Data structures for submission annotations."""

from typing import Optional
import hashlib
from datetime import datetime
from dataclasses import dataclass, field
from dataclasses import asdict
from api.domain.submission import Submission
from api.domain.agent import Agent


@dataclass
class Annotation:
    """Auxilliary metadata used by the submission and moderation process."""

    submission: Submission
    creator: Agent
    scope: str
    proxy: Optional[Agent] = None
    created: datetime = field(default_factory=datetime.now)

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


@dataclass
class Comment(Annotation):
    """A freeform textual annotation."""

    body: str = field(default_factory=str)

    @property
    def comment_id(self):
        """The unique identifier for a :class:`.Comment` instance."""
        return self.annotation_id


@dataclass
class Flag(Annotation):
    """Tags used to route submissions based on moderation policies."""
