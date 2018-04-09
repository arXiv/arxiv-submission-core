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
from typing import Optional, TypeVar, List, Tuple, Any, Dict
from urllib.parse import urlparse
from dataclasses import dataclass, field
from dataclasses import asdict

from arxiv.util import schema

from .agent import Agent
from .submission import Submission, SubmissionMetadata, Author, \
    Classification, License, Delegation, Comment, Flag, Proposal

from events.exceptions import InvalidEvent


@dataclass
class Event:
    """Base class for submission-related events."""

    creator: Agent
    """
    The agent responsible for the operation represented by this event.

    This is **not** necessarily the creator of the submission.
    """

    created: datetime = field(default_factory=datetime.now)
    """
    The timestamp when the event was originally committed.

    This should generally not be set from outside this package.
    """

    proxy: Optional[Agent] = field(default=None)
    """
    The agent who facilitated the operation on behalf of the :prop:`.creator`.

    This may be an API client, or another user who has been designated as a
    proxy. Note that proxy implies that the creator was not directly involved.
    """

    client: Optional[Agent] = field(default=None)
    """
    The client through which the :prop:`.creator` performed the operation.

    If the creator was directly involved in the operation, this property should
    be the client that facilitated the operation.
    """

    submission_id: Optional[int] = field(default=None)
    """
    The primary identifier of the submission being operated upon.

    This is defined as optional to support creation events, and to facilitate
    chaining of events with creation events in the same transaction.
    """

    committed: bool = field(default=False)
    """
    Indicates whether the event has been committed to the database.

    This should generally not be set from outside this package.
    """

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

    def valid(self, submission: Submission) -> bool:
        """Determine whether this event is valid for the submission."""
        if submission and submission.published:
            raise InvalidEvent(self, "Cannot alter a published submission")

        if not hasattr(self, 'validate'):
            return True
        try:
            self.validate(submission)
        except InvalidEvent:
            return False
        return True

    def apply(self, submission: Optional[Submission] = None) -> Submission:
        if submission:
            submission = self.project(submission)
        else:
            submission = self.project()
        submission.updated = self.created
        return submission

    def to_dict(self):
        data = asdict(self)
        data.update({
            'creator': self.creator.to_dict(),
            'created': self.created.isoformat(),
        })
        return data


# Events related to the creation of a new submission.
#
# These are largely the domain of the metadata API, and the submission UI.


@dataclass(init=False)
class CreateSubmission(Event):
    """Creation of a new :class:`events.domain.submission.Submission`."""

    def project(self) -> Submission:
        """Create a new :class:`.Submission`."""
        return Submission(creator=self.creator, created=self.created,
                          owner=self.creator, proxy=self.proxy,
                          client=self.client)


@dataclass(init=False)
class RemoveSubmission(Event):
    """Removal of a :class:`events.domain.submission.Submission`."""

    def project(self, submission: Submission) -> Submission:
        """Remove the :class:`.Submission` from the system (set inactive)."""
        submission.active = False
        return submission


@dataclass(init=False)
class VerifyContactInformation(Event):
    """Submitter has verified their contact information."""

    def project(self, submission: Submission) -> Submission:
        """Update :prop:`.Submission.submitter_contact_verified`."""
        submission.submitter_contact_verified = True
        return submission


@dataclass
class AssertAuthorship(Event):
    """The submitting user asserts whether they are an author of the paper."""

    submitter_is_author: bool = True

    def project(self, submission: Submission) -> Submission:
        """Update the authorship flag on the submission."""
        submission.submitter_is_author = self.submitter_is_author
        return submission


@dataclass
class AcceptPolicy(Event):
    """The submitting user accepts the arXiv submission policy."""

    def project(self, submission: Submission) -> Submission:
        """Set the policy flag on the submission."""
        submission.submitter_accepts_policy = True
        return submission


@dataclass
class SetPrimaryClassification(Event):
    """Update the primary classification of a submission."""

    category: Optional[str] = None

    def validate(self, submission: Submission) -> None:
        try:
            assert self.category
        except AssertionError as e:
            raise InvalidEvent(e) from e

    def project(self, submission: Submission) -> Submission:
        """Set :prop:`.Submission.primary_classification`."""
        submission.primary_classification = Classification(
            category=self.category
        )
        return submission


@dataclass
class AddSecondaryClassification(Event):
    """Add a secondary :class:`.Classification` to a submission."""

    category: Optional[str] = field(default=None)

    def validate(self, submission: Submission) -> None:
        """All three fields must be set."""
        try:
            assert self.category
        except AssertionError as e:
            raise InvalidEvent(e) from e

    def project(self, submission: Submission) -> Submission:
        """Append to :prop:`.Submission.secondary_classification`."""
        submission.secondary_classification.append(Classification(
            category=self.category
        ))
        return submission


@dataclass
class RemoveSecondaryClassification(Event):
    """Remove secondary :class:`.Classification` from submission."""

    category: Optional[str] = field(default=None)

    def validate(self, submission: Submission) -> None:
        """All three fields must be set."""
        try:
            assert self.category
        except AssertionError as e:
            raise InvalidEvent(e) from e

    def project(self, submission: Submission) -> Submission:
        """Remove from :prop:`.Submission.secondary_classification`."""
        submission.secondary_classification = [
            classn for classn in submission.secondary_classification
            if not classn.category == self.category
        ]
        return submission


@dataclass
class SelectLicense(Event):
    """The submitter has selected a license for their submission."""

    license_name: Optional[str] = field(default=None)
    license_uri: Optional[str] = field(default=None)

    def project(self, submission: Submission) -> Submission:
        """Set :prop:`.Submission.license`."""
        submission.license = License(
            name=self.license_name,
            uri=self.license_uri
        )
        return submission


@dataclass
class UpdateMetadata(Event):
    """Update the descriptive metadata for a submission."""

    schema = 'schema/resources/events/update_metadata.json'

    metadata: List[Tuple[str, Any]] = field(default_factory=list)

    def validate(self, submission: Submission) -> None:
        """The :prop:`.metadata` should be a list of tuples."""
        try:
            assert len(self.metadata) >= 1
            assert type(self.metadata[0]) in [tuple, list]
            for metadatum in self.metadata:
                assert len(metadatum) == 2
        except AssertionError as e:
            raise InvalidEvent(self) from e

    def project(self, submission: Submission) -> Submission:
        """Update metadata on a :class:`.Submission`."""
        for key, value in self.metadata:
            setattr(submission.metadata, key, value)
        return submission


@dataclass
class UpdateAuthors(Event):
    """Update the authors on a :class:`.Submission`."""

    authors: List[Author] = field(default_factory=list)


@dataclass
class AttachSourceContent(Event):
    """Add metadata about a source package to a submission."""

    location: str = field(default_factory=str)
    format: str = field(default_factory=str)
    checksum: str = field(default_factory=str)
    identifier: Optional[int] = field(default=None)

    ALLOWED_FORMATS = [
        'application/tar+gzip', 'application/tar', 'application/zip'
    ]

    def validate(self, submission: Submission) -> None:
        """Validate data for :class:`.SubmissionContent`."""
        try:
            parsed = urlparse(self.location)
        except ValueError as e:
            raise InvalidEvent('Not a valid URL') from e
        if not parsed.netloc.endswith('arxiv.org'):
            raise InvalidEvent('External URLs not allowed.')

        if self.format not in self.ALLOWED_FORMATS:
            raise InvalidEvent(f'Format {self.package_format} not allowed')
        if not self.checksum:
            raise InvalidEvent('Missing checksum')
        if not self.identifier:
            raise InvalidEvent('Missing upload ID')

    def project(self, submission: Submission) -> Submission:
        """Replace :class:`.SubmissionContent` metadata on the submission."""
        submission.source_content = SubmissionContent(
            location=self.location,
            format=self.format,
            checksum=self.checksum,
            identifier=self.identifier
        )
        return submission


@dataclass
class FinalizeSubmission(Event):
    """Send the submission to the queue for announcement."""

    def validate(self, submission: Submission) -> None:
        """Ensure that all required data/steps are complete."""
        if submission.finalized:
            raise InvalidEvent(self, "Submission already finalized")
        if not submission.active:
            raise InvalidEvent(self, "Submision must be active")

        try:
            assert submission.creator is not None
            assert submission.primary_classification is not None
            assert submission.metadata.title is not None
            assert submission.metadata.abstract is not None
            assert len(submission.metadata.authors) > 0
            assert submission.submitter_contact_verified
            assert submission.submitter_accepts_policy
            assert submission.license is not None
            assert submission.source_content is not None
        except AssertionError as e:
            raise InvalidEvent(self, "Submission missing required data") from e

    def project(self, submission: Submission) -> Submission:
        submission.finalized = True
        return submission


# Moderation-related events.

@dataclass
class CreateComment(Event):
    """Creation of a :class:`.Comment` on a :class:`.Submission`."""

    read_scope = 'submission:moderate'
    write_scope = 'submission:moderate'

    body: str = field(default_factory=str)
    scope: str = 'private'

    def validate(self, submission: Submission) -> None:
        """The :prop:`.body` should be set."""
        if not self.body:
            raise ValueError('Comment body not set')

    def project(self, submission: Submission) -> Submission:
        """Create a new :class:`.Comment` and attach it to the submission."""
        comment = Comment(creator=self.creator, created=self.created,
                          proxy=self.proxy, submission=submission,
                          body=self.body, scope=self.scope)
        submission.comments[comment.comment_id] = comment
        return submission


@dataclass
class DeleteComment(Event):
    """Deletion of a :class:`.Comment` on a :class:`.Submission`."""

    read_scope = 'submission:moderate'
    write_scope = 'submission:moderate'

    comment_id: str = field(default_factory=str)

    def validate(self, submission: Submission) -> None:
        """The :prop:`.comment_id` must present on the submission."""
        if self.comment_id is None:
            raise InvalidEvent('comment_id is required')
        if not hasattr(submission, 'comments') or not submission.comments:
            raise InvalidEvent('Cannot delete comment that does not exist')
        if self.comment_id not in submission.comments:
            raise InvalidEvent('Cannot delete comment that does not exist')

    def project(self, submission: Submission) -> Submission:
        """Remove the comment from the submission."""
        del submission.comments[self.comment_id]
        return submission


@dataclass
class AddDelegate(Event):
    """Owner delegates authority to another agent."""

    delegate: Optional[Agent] = None

    def validate(self, submission: Submission) -> None:
        """The event creator must be the owner of the submission."""
        if not self.creator == submission.owner:
            raise InvalidEvent('Event creator must be submission owner')

    def project(self, submission: Submission) -> Submission:
        """Add the delegate to the submission."""
        delegation = Delegation(
            creator=self.creator,
            delegate=self.delegate,
            created=self.created
        )
        submission.delegations[delegation.delegation_id] = delegation
        return submission


@dataclass
class RemoveDelegate(Event):
    """Owner revokes authority from another agent."""

    delegation_id: str = field(default_factory=str)

    def validate(self, submission: Submission) -> None:
        """The event creator must be the owner of the submission."""
        if not self.creator == submission.owner:
            raise InvalidEvent('Event creator must be submission owner')

    def project(self, submission: Submission) -> Submission:
        """Remove the delegate from the submission."""
        if self.delegation_id in submission.delegations:
            del submission.delegations[self.delegation_id]
        return submission


# class CreateSourcePackage(Event):
#     pass
#
# class UpdateSourcePackage(Event):
#     pass
#
#
# class DeleteSourcePackage(Event):
#     pass
#
#
# class Annotation(Event):
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
    if 'created' not in data:
        data['created'] = datetime.now()
    if event_type in EVENT_TYPES:
        return EVENT_TYPES[event_type](**data)
    raise RuntimeError('Unknown event type: %s' % event_type)


__all__ = tuple(
    ['Event', 'event_factory'] +
    [obj.__name__ for obj in locals().values()
     if type(obj) is type and issubclass(obj, Event)]
 )
