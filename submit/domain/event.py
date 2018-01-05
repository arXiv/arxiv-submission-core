"""
Data structures for submissions events.

- Events have unique identifiers generated from their data (creation, agent,
  submission).
- Events provide methods to update a submission based on the event data.
- Events provide validation methods for event data.
-
"""

import hashlib
from datetime import datetime
from typing import Optional, TypeVar
from submit.domain import Data, Property
from submit.domain.agent import Agent
from submit.domain.submission import Submission, SubmissionMetadata
from submit.domain.annotation import Comment, Flag, Proposal

EventType = TypeVar('EventType', bound='Event')


class Event(Data):
    """Base class for submission-related events."""

    creator = Property('creator', Agent)
    submission_id = Property('submission_id', int, null=True)
    created = Property('created', datetime)
    committed = Property('committed', bool, False)
    """Indicates whether or not the event has been persisted."""

    def __init__(self, **data) -> None:
        """."""
        self.update_from = data.pop('update_from', None)
        super(Event, self).__init__(**data)
        if not self.created:
            self.created = datetime.now()

    @property
    def event_type(self) -> str:
        """The name (str) of the event type."""
        return self.get_event_type()

    @classmethod
    def get_event_type(cls) -> str:
        """Get the name (str) of the event type."""
        return cls.__name__

    @property
    def event_id(self) -> str:
        """The unique ID for this event."""
        h = hashlib.new('md5')
        h.update(b'%s:%s:%s' % (self.created.isoformat().encode('utf-8'),
                                self.event_type.encode('utf-8'),
                                self.creator.agent_identifier.encode('utf-8')))
        return h.hexdigest()

    def validate(self, submission: Optional[Submission] = None) -> None:
        """Placeholder for validation, to be implemented by subclasses."""
        pass

    def apply(self, submission: Optional[Submission] = None) -> Submission:
        """Placeholder for projection, to be implemented by subclasses."""
        pass


class CreateSubmissionEvent(Event):
    """Creation of a new :class:`.Submission`."""

    def apply(self, submission: Optional[Submission] = None) -> Submission:
        """Create a new :class:`.Submission`."""
        return Submission(creator=self.creator, created=self.created,
                          metadata=SubmissionMetadata())


class RemoveSubmissionEvent(Event):
    """Removal of a :class:`.Submission`."""

    def apply(self, submission: Optional[Submission] = None) -> Submission:
        """Remove the :class:`.Submission` (set inactive)."""
        submission.active = False
        return submission


class UpdateMetadataEvent(Event):
    """Update of :class:`.Submission` metadata."""

    metadata = Property('metadata', list)

    def validate(self, submission: Optional[Submission] = None) -> None:
        """The :prop:`.metadata` should be a list of tuples."""
        try:
            assert len(self.metadata) < 1
            assert type(self.metadata[0]) is tuple
            for metadatum in self.metadata:
                assert len(metadatum) == 2
        except AssertionError as e:
            raise ValueError(e) from e

    def apply(self, submission: Optional[Submission] = None) -> Submission:
        """Update metadata on a :class:`.Submission`."""
        for key, value in self.metadata:
            setattr(submission.metadata, key, value)
        return submission


class CreateCommentEvent(Event):
    """Creation of a :class:`.Comment` on a :class:`.Submission`."""

    body = Property('body', str)

    def validate(self, submission: Optional[Submission] = None) -> None:
        """The :prop:`.body` should be set."""
        if not self.body:
            raise ValueError('Comment body not set')

    def apply(self, submission: Optional[Submission] = None) -> Submission:
        """Create a new :class:`.Comment` and attach it to the submission."""
        comment = Comment(creator=self.creator, created=self.created,
                          submission=submission, body=self.body)
        submission.comments[comment.comment_id] = comment
        return submission


class DeleteCommentEvent(Event):
    """Deletion of a :class:`.Comment` on a :class:`.Submission`."""

    comment_id = Property('comment_id', str)

    def validate(self, submission: Optional[Submission] = None) -> None:
        """The :prop:`.comment_id` must present on the submission."""
        if self.comment_id is None:
            raise ValueError('comment_id is required')
        if not hasattr(submission, 'comments') or not submission.comments:
            raise ValueError('Cannot delete comment that does not exist')
        if self.comment_id not in submission.comments:
            raise ValueError('Cannot delete comment that does not exist')

    def apply(self, submission: Optional[Submission] = None) -> Submission:
        """Remove the comment from the submission."""
        del submission.comments[self.comment_id]
        return submission


# class CreateSourcePackageEvent(Event):
#     pass
#
# class UpdateSourcePackageEvent(Event):
#     pass
#
#
# class DeleteSourcePackageEvent(Event):
#     pass
#
#
# class AnnotationEvent(Event):
#     pass
#
#
# class CreateFlagEvent(AnnotationEvent):
#     pass
#
#
# class DeleteFlagEvent(AnnotationEvent):
#     pass
#
#

#
#
# class DeleteCommentEvent(AnnotationEvent):
#     pass
#
#
# class CreateProposalEvent(AnnotationEvent):
#     pass
#
#
# class DeleteProposalEvent(AnnotationEvent):
#     pass

EVENT_TYPES = {
    obj.get_event_type(): obj for obj in locals().values()
    if type(obj) is type and issubclass(obj, Event)
}


def event_factory(event_type: str, **data) -> Event:
    """Instantiate an event."""
    if event_type in EVENT_TYPES:
        return EVENT_TYPES[event_type](**data)
    raise RuntimeError('Unknown event type: %s' % event_type)
