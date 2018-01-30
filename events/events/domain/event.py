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

from arxiv.util import schema

from .data import Data, Property
from .agent import Agent
from .submission import Submission, SubmissionMetadata, \
    Classification, License, Delegation
from .annotation import Comment, Flag, Proposal

EventType = TypeVar('EventType', bound='Event')


class Event(Data):
    """Base class for submission-related events."""

    base_schema = 'schema/resources/event.json'

    creator = Property('creator', Agent)
    proxy = Property('proxy', Agent, null=True)
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
        h = hashlib.new('sha1')
        h.update(b'%s:%s:%s' % (self.created.isoformat().encode('utf-8'),
                                self.event_type.encode('utf-8'),
                                self.creator.agent_identifier.encode('utf-8')))
        return h.hexdigest()

    @property
    def valid(self) -> bool:
        """Indicate whether the event instance is valid."""
        try:
            self.validate()
        except InvalidEvent:
            return False
        return True

    def validate(self, submission: Optional[Submission] = None) -> None:
        """Placeholder for validation, to be implemented by subclasses."""
        data = self.to_dict()
        if hasattr(self, 'schema') and self.schema:
            try:
                schema.load(self.schema)(data)
            except schema.ValidationError as e:
                raise InvalidEvent(self) from e

    def apply(self, submission: Optional[Submission] = None) -> Submission:
        """Placeholder for projection, to be implemented by subclasses."""
        pass


class CreateSubmissionEvent(Event):
    """Creation of a new :class:`.Submission`."""

    read_scope = 'submission:read'
    write_scope = 'submission:write'

    def apply(self, submission: Optional[Submission] = None) -> Submission:
        """Create a new :class:`.Submission`."""
        return Submission(creator=self.creator, created=self.created,
                          owner=self.creator, proxy=self.proxy,
                          metadata=SubmissionMetadata())


class RemoveSubmissionEvent(Event):
    """Removal of a :class:`.Submission`."""

    read_scope = 'submission:read'
    write_scope = 'submission:write'

    def apply(self, submission: Optional[Submission] = None) -> Submission:
        """Remove the :class:`.Submission` (set inactive)."""
        submission.active = False
        return submission


class VerifyContactInformationEvent(Event):
    """Submitter has verified their contact information."""

    read_scope = 'submission:read'
    write_scope = 'submission:write'

    def apply(self, submission: Optional[Submission] = None) -> Submission:
        """Update :prop:`.Submission.submitter_contact_verified`."""
        submission.submitter_contact_verified = True
        return submission


class AssertAuthorshipEvent(Event):
    """The submitting user asserts whether they are an author of the paper."""

    read_scope = 'submission:read'
    write_scope = 'submission:write'

    submitter_is_author = Property('is_author', bool, True)

    def apply(self, submission: Optional[Submission] = None) -> Submission:
        """Update the authorship flag on the submission."""
        submission.submitter_is_author = self.submitter_is_author
        return submission


class AcceptPolicyEvent(Event):
    """The submitting user accepts the arXiv submission policy."""

    read_scope = 'submission:read'
    write_scope = 'submission:write'

    def apply(self, submission: Optional[Submission] = None) -> Submission:
        """Set the policy flag on the submission."""
        submission.submitter_accepts_policy = True
        return submission


class SetPrimaryClassificationEvent(Event):
    """Update the primary classification of a :class:`.Submission`."""

    read_scope = 'submission:read'
    write_scope = 'submission:write'

    category = Property('category', str)

    def validate(self, submission: Optional[Submission] = None) -> None:
        """All three fields must be set."""
        try:
            assert self.category
        except AssertionError as e:
            raise InvalidEvent(e) from e

    def apply(self, submission: Optional[Submission] = None) -> Submission:
        """Set :prop:`.Submission.primary_classification`."""
        submission.primary_classification = Classification(
            category=self.category
        )
        return submission


class AddSecondaryClassificationEvent(Event):
    """Add a secondary :class:`.Classification` to a :class:`.Submission`."""

    read_scope = 'submission:read'
    write_scope = 'submission:write'

    category = Property('category', str)

    def validate(self, submission: Optional[Submission] = None) -> None:
        """All three fields must be set."""
        try:
            assert self.category
        except AssertionError as e:
            raise InvalidEvent(e) from e

    def apply(self, submission: Optional[Submission] = None) -> Submission:
        """Append to :prop:`.Submission.secondary_classification`."""
        submission.secondary_classification.append(Classification(
            category=self.category
        ))
        return submission


class RemoveSecondaryClassificationEvent(Event):
    """Remove secondary :class:`.Classification` from :class:`.Submission`."""

    read_scope = 'submission:read'
    write_scope = 'submission:write'

    category = Property('category', str)

    def validate(self, submission: Optional[Submission] = None) -> None:
        """All three fields must be set."""
        try:
            assert self.category
        except AssertionError as e:
            raise InvalidEvent(e) from e

    def apply(self, submission: Optional[Submission] = None) -> Submission:
        """Remove from :prop:`.Submission.secondary_classification`."""
        submission.secondary_classification = [
            classn for classn in submission.secondary_classification
            if not classn.category == self.category
        ]
        return submission


class SelectLicenseEvent(Event):
    """The submitter has selected a license for their submission."""

    read_scope = 'submission:read'
    write_scope = 'submission:write'

    license_name = Property('license_name', str)
    license_uri = Property('license_uri', str)

    def apply(self, submission: Optional[Submission] = None) -> Submission:
        """Set :prop:`.Submission.license`."""
        submission.license = License(
            name=self.license_name,
            uri=self.license_uri
        )
        return submission


class UpdateMetadataEvent(Event):
    """Update of :class:`.Submission` metadata."""

    read_scope = 'submission:read'
    write_scope = 'submission:write'

    schema = 'schema/resources/events/update_metadata.json'

    metadata = Property('metadata', list)

    # def validate(self, submission: Optional[Submission] = None) -> None:
    #     """The :prop:`.metadata` should be a list of tuples."""
    #     try:
    #         assert len(self.metadata) >= 1
    #         assert type(self.metadata[0]) in [tuple, list]
    #         for metadatum in self.metadata:
    #             assert len(metadatum) == 2
    #     except AssertionError as e:
    #         raise InvalidEvent(e) from e

    def apply(self, submission: Optional[Submission] = None) -> Submission:
        """Update metadata on a :class:`.Submission`."""
        for key, value in self.metadata:
            setattr(submission.metadata, key, value)
        return submission


class UpdateAuthorsEvent(Event):
    """Update the authors on a :class:`.Submission`."""

    read_scope = 'submission:read'
    write_scope = 'submission:write'

    authors = Property('authors', list, [])

    schema = 'schema/resources/events/update_authors.json'

    # def validate(self, submission: Optional[Submission] = None) -> None:
    #     """The :prop:`.authors` should be a list of authors."""
    #     allowed = ['forename', 'surname', 'initials', '']
    #     for author in self.authors:
    #         try:
    #             assert 'forename' in author
    #             assert 'surname' in author


class CreateCommentEvent(Event):
    """Creation of a :class:`.Comment` on a :class:`.Submission`."""

    read_scope = 'submission:moderate'
    write_scope = 'submission:moderate'

    body = Property('body', str)

    def validate(self, submission: Optional[Submission] = None) -> None:
        """The :prop:`.body` should be set."""
        if not self.body:
            raise ValueError('Comment body not set')

    def apply(self, submission: Optional[Submission] = None) -> Submission:
        """Create a new :class:`.Comment` and attach it to the submission."""
        comment = Comment(creator=self.creator, created=self.created,
                          proxy=self.proxy, submission=submission,
                          body=self.body)
        submission.comments[comment.comment_id] = comment
        return submission


class DeleteCommentEvent(Event):
    """Deletion of a :class:`.Comment` on a :class:`.Submission`."""

    read_scope = 'submission:moderate'
    write_scope = 'submission:moderate'

    comment_id = Property('comment_id', str)

    def validate(self, submission: Optional[Submission] = None) -> None:
        """The :prop:`.comment_id` must present on the submission."""
        if self.comment_id is None:
            raise InvalidEvent('comment_id is required')
        if not hasattr(submission, 'comments') or not submission.comments:
            raise InvalidEvent('Cannot delete comment that does not exist')
        if self.comment_id not in submission.comments:
            raise InvalidEvent('Cannot delete comment that does not exist')

    def apply(self, submission: Optional[Submission] = None) -> Submission:
        """Remove the comment from the submission."""
        del submission.comments[self.comment_id]
        return submission


class AddDelegateEvent(Event):
    """Owner delegates authority to another agent."""

    read_scope = 'submission:read'
    write_scope = 'submission:write'

    delegate = Property('delegate', Agent)

    def validate(self, submission: Optional[Submission] = None) -> None:
        """The event creator must be the owner of the submission."""
        if not self.creator == submission.owner:
            raise InvalidEvent('Event creator must be submission owner')

    def apply(self, submission: Optional[Submission] = None) -> Submission:
        """Add the delegate to the submission."""
        delegation = Delegation(
            creator=self.creator,
            delegate=self.delegate,
            created=self.created
        )
        submission.delegations[delegation.delegation_id] = delegation
        return submission


class RemoveDelegateEvent(Event):
    """Owner revokes authority from another agent."""

    read_scope = 'submission:read'
    write_scope = 'submission:write'

    delegation_id = Property('delegation_id', str)

    def validate(self, submission: Optional[Submission] = None) -> None:
        """The event creator must be the owner of the submission."""
        if not self.creator == submission.owner:
            raise InvalidEvent('Event creator must be submission owner')

    def apply(self, submission: Optional[Submission] = None) -> Submission:
        """Remove the delegate from the submission."""
        if self.delegation_id in submission.delegations:
            del submission.delegations[self.delegation_id]
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
    """
    Convenience factory for generating :class:`.Event`s.

    Parameters
    ----------
    event_type : str
        Should be the name of a :class:`.Event` subclass.
    data : kwargs
        Keyword parameters passed to the event constructor.

    Return
    ------
    :class:`.Event`
        An instance of an :class:`.Event` subclass.
    """
    if event_type in EVENT_TYPES:
        return EVENT_TYPES[event_type](**data)
    raise RuntimeError('Unknown event type: %s' % event_type)


__all__ = tuple(
    ['Event', 'event_factory'] +
    [obj.__name__ for obj in locals().values()
     if type(obj) is type and issubclass(obj, Event)]
 )


class InvalidEvent(ValueError):
    """Raised when an invalid event is encountered."""

    def __init__(self, event: Event) -> None:
        """Use the :class:`.Event` to build an error message."""
        self.event = event
        msg = "Encountered invalid event: %s (%s)" % \
            (event.event_type, event.event_id)
        super(InvalidEvent, self).__init__(msg)
