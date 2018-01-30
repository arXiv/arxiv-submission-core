"""Data structures for submission annotations."""

import hashlib
from datetime import datetime
from .data import Data, Property
from .submission import Submission
from .agent import Agent

__all__ = ('Annotation', 'Proposal', 'Comment', 'Flag')


class Annotation(Data):
    """Auxilliary metadata used by the submission and moderation process."""

    created = Property('created', datetime, datetime.now())
    creator = Property('creator', Agent)
    proxy = Property('proxy', Agent, null=True)
    submission = Property('submission', Submission)
    scope = Property('scope', str)

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


class Proposal(Annotation):
    """Represents a proposal to apply an event to a submission."""

    event_type = Property('event_type', type)
    event_data = Property('event_data', dict)


class Comment(Annotation):
    """A freeform textual annotation."""

    body = Property('body', str)

    @property
    def comment_id(self):
        """The unique identifier for a :class:`.Comment` instance."""
        return self.annotation_id


class Flag(Annotation):
    """Tags used to route submissions based on moderation policies."""

    pass
