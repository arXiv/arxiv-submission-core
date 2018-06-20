"""
Data structures for submissions events.

- Events have unique identifiers generated from their data (creation, agent,
  submission).
- Events provide methods to update a submission based on the event data.
- Events provide validation methods for event data.

Writing new events/commands
===========================

Events/commands are implemented as classes that inherit from :class:`.Event`.
It should:

- Be a dataclass (i.e. be decorated with :func:`dataclasses.dataclass`).
- Define (using :func:`dataclasses.field`) associated data.
- Implement a validation method with the signature
  ``validate(self, submission: Submission) -> None`` (see below).
- Implement a projection method with the signature
  ``project(self, submission: Submission) -> Submission:`` that mutates
  the passed :class:`.Submission` instance.
- Be fully documented. Be sure that the class docstring fully describes the
  meaning of the event/command, and that both public and private methods have
  at least a summary docstring.
- Have a corresponding :class:`unittest.TestCase` in
  :mod:`events.domain.tests.test_events`.

Adding validation to events
===========================

Each command/event class should implement an instance method
``validate(self, submission: Submission) -> None`` that raises
:class:`.InvalidEvent` exceptions if the data on the event instance is not
valid.

For clarity, it's a good practice to individuate validation steps as separate
private instance methods, and call them from the public ``validate`` method.
This makes it easier to identify which validation criteria are being applied,
in what order, and what those criteria mean.

See :class:`.SetPrimaryClassification` for an example.

We could consider standalone validation functions for validation checks that
are performed on several event types (instead of just private instance
methods).

"""

import hashlib
import re
from datetime import datetime
from typing import Optional, TypeVar, List, Tuple, Any, Dict
from urllib.parse import urlparse
from dataclasses import dataclass, field
from dataclasses import asdict

from arxiv.util import schema
from arxiv import taxonomy

from .agent import Agent
from .submission import Submission, SubmissionMetadata, Author, \
    Classification, License, Delegation, Comment, Flag, Proposal, \
    SubmissionContent

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

    def apply(self, submission: Optional[Submission] = None) -> Submission:
        """Apply the projection for this :class:`.Event` instance."""
        if submission:
            submission = self.project(submission)
        else:
            submission = self.project()
        submission.updated = self.created
        return submission

    def to_dict(self):
        """Generate a dict representation of this :class:`.Event`."""
        data = asdict(self)
        data.update({
            'creator': self.creator.to_dict(),
            'proxy': self.proxy.to_dict() if self.proxy else None,
            'client': self.client.to_dict() if self.client else None,
            'created': self.created.isoformat(),
        })
        return data


# Events related to the creation of a new submission.
#
# These are largely the domain of the metadata API, and the submission UI.


@dataclass(init=False)
class CreateSubmission(Event):
    """Creation of a new :class:`events.domain.submission.Submission`."""

    def validate(self, *args, **kwargs) -> None:
        """Validate creation of a submission."""
        return

    def project(self) -> Submission:
        """Create a new :class:`.Submission`."""
        return Submission(creator=self.creator, created=self.created,
                          owner=self.creator, proxy=self.proxy,
                          client=self.client)


@dataclass(init=False)
class RemoveSubmission(Event):
    """Removal of a :class:`events.domain.submission.Submission`."""

    def validate(self, submission: Submission) -> None:
        """Validate removal of a submission."""
        return

    def project(self, submission: Submission) -> Submission:
        """Remove the :class:`.Submission` from the system (set inactive)."""
        submission.active = False
        return submission


@dataclass(init=False)
class VerifyContactInformation(Event):
    """Submitter has verified their contact information."""

    def validate(self, submission: Submission) -> None:
        """Cannot apply to a finalized submission."""
        submission_is_not_finalized(self, submission)

    def project(self, submission: Submission) -> Submission:
        """Update :prop:`.Submission.submitter_contact_verified`."""
        submission.submitter_contact_verified = True
        return submission


@dataclass
class AssertAuthorship(Event):
    """The submitting user asserts whether they are an author of the paper."""

    submitter_is_author: bool = True

    def validate(self, submission: Submission) -> None:
        """Cannot apply to a finalized submission."""
        submission_is_not_finalized(self, submission)

    def project(self, submission: Submission) -> Submission:
        """Update the authorship flag on the submission."""
        submission.submitter_is_author = self.submitter_is_author
        return submission


@dataclass
class AcceptPolicy(Event):
    """The submitting user accepts the arXiv submission policy."""

    def validate(self, submission: Submission) -> None:
        """Cannot apply to a finalized submission."""
        submission_is_not_finalized(self, submission)

    def project(self, submission: Submission) -> Submission:
        """Set the policy flag on the submission."""
        submission.submitter_accepts_policy = True
        return submission


@dataclass
class SetPrimaryClassification(Event):
    """Update the primary classification of a submission."""

    category: Optional[str] = None

    def validate(self, submission: Submission) -> None:
        """Validate the primary classification category."""
        self._must_be_a_valid_category(submission)
        self._primary_cannot_be_secondary(submission)
        submission_is_not_finalized(self, submission)

    def _must_be_a_valid_category(self, submission: Submission) -> None:
        """Valid arXiv categories are defined in :mod:`arxiv.taxonomy`."""
        if not self.category or self.category not in taxonomy.CATEGORIES:
            raise InvalidEvent(self, f"Not a valid category: {self.category}")

    def _primary_cannot_be_secondary(self, submission: Submission) -> None:
        """The same category can't be used for both primary and secondary."""
        secondaries = [c.category for c in submission.secondary_classification]
        if self.category in secondaries:
            raise InvalidEvent(self,
                               "The same category cannot be used as both the"
                               " primary and a secondary category.")

    def project(self, submission: Submission) -> Submission:
        """Set :prop:`.Submission.primary_classification`."""
        clsn = Classification(category=self.category)
        submission.primary_classification = clsn
        return submission


@dataclass
class AddSecondaryClassification(Event):
    """Add a secondary :class:`.Classification` to a submission."""

    category: Optional[str] = field(default=None)

    def validate(self, submission: Submission) -> None:
        """Validate the secondary classification category to add."""
        self._must_be_a_valid_category(submission)
        self._primary_cannot_be_secondary(submission)
        self._must_not_already_be_present(submission)
        submission_is_not_finalized(self, submission)

    def project(self, submission: Submission) -> Submission:
        """Add a :class:`.Classification` as a secondary classification."""
        classification = Classification(category=self.category)
        submission.secondary_classification.append(classification)
        return submission

    def _must_be_a_valid_category(self, submission: Submission) -> None:
        """Valid arXiv categories are defined in :mod:`arxiv.taxonomy`."""
        if not self.category or self.category not in taxonomy.CATEGORIES:
            raise InvalidEvent(self, "Not a valid category")

    def _primary_cannot_be_secondary(self, submission: Submission) -> None:
        """The same category can't be used for both primary and secondary."""
        if submission.primary_classification is None:
            return
        if self.category == submission.primary_classification.category:
            raise InvalidEvent(self,
                               "The same category cannot be used as both the"
                               " primary and a secondary category.")

    def _must_not_already_be_present(self, submission: Submission) -> None:
        """The same category cannot be added as a secondary twice."""
        secondaries = [c.category for c in submission.secondary_classification]
        if self.category in secondaries:
            raise InvalidEvent(self,
                               f"Secondary {self.category} already set"
                               f" on this submission.")


@dataclass
class RemoveSecondaryClassification(Event):
    """Remove secondary :class:`.Classification` from submission."""

    category: Optional[str] = field(default=None)

    def validate(self, submission: Submission) -> None:
        """Validate the secondary classification category to remove."""
        self._must_be_a_valid_category(submission)
        self._must_already_be_present(submission)
        submission_is_not_finalized(self, submission)

    def project(self, submission: Submission) -> Submission:
        """Remove from :prop:`.Submission.secondary_classification`."""
        submission.secondary_classification = [
            classn for classn in submission.secondary_classification
            if not classn.category == self.category
        ]
        return submission

    def _must_be_a_valid_category(self, submission: Submission) -> None:
        """Valid arXiv categories are defined in :mod:`arxiv.taxonomy`."""
        if not self.category or self.category not in taxonomy.CATEGORIES:
            raise InvalidEvent(self, "Not a valid category")

    def _must_already_be_present(self, submission: Submission) -> None:
        """One cannot remove a secondary that is not actually set."""
        current = [c.category for c in submission.secondary_classification]
        if self.category not in current:
            raise InvalidEvent(self, 'No such category on submission')


@dataclass
class SelectLicense(Event):
    """The submitter has selected a license for their submission."""

    license_name: Optional[str] = field(default=None)
    license_uri: Optional[str] = field(default=None)

    def validate(self, submission: Submission) -> None:
        """Validate the selected license."""
        submission_is_not_finalized(self, submission)

    def project(self, submission: Submission) -> Submission:
        """Set :prop:`.Submission.license`."""
        submission.license = License(
            name=self.license_name,
            uri=self.license_uri
        )
        return submission


# TODO: consider representing some of these as distinct events/commands?
@dataclass
class UpdateMetadata(Event):
    """Update the descriptive metadata for a submission."""

    metadata: List[Tuple[str, Any]] = field(default_factory=list)

    FIELDS = [
        'title', 'abstract', 'doi', 'msc_class', 'acm_class',
        'report_num', 'journal_ref', 'comments'
    ]

    # TODO: implement more specific validation here.
    def validate(self, submission: Submission) -> None:
        """The :prop:`.metadata` should be a list of tuples."""
        submission_is_not_finalized(self, submission)
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
    authors_display: Optional[str] = field(default=None)
    """The authors string may be provided."""

    def __post_init__(self):
        """Autogenerate and/or clean display names."""
        if not self.authors_display:
            self.authors_display = self._canonical_author_string()
        self.authors_display = self._cleanup(self.authors_display)

    def validate(self, submission: Submission) -> None:
        """May not apply to a finalized submission."""
        submission_is_not_finalized(self, submission)
        self._does_not_contain_et_al()

    def _canonical_author_string(self) -> str:
        """Canonical representation of authors, using display names."""
        return ", ".join([au.display for au in self.authors])

    def _cleanup(self, s: str) -> str:
        """Perform some light tidying on the provided author string(s)."""
        s = re.sub(r"\s+", " ", s)          # Single spaces only.
        s = re.sub(r",(\s*,)+", ",", s)     # Remove double commas.
        # Add spaces between word and opening parenthesis.
        s = re.sub(r"(\w)\(", "\g<1> (", s)
        # Add spaces between closing parenthesis and word.
        s = re.sub(r"\)(\w)", ") \g<1>", s)
        # Change capitalized or uppercase `And` to `and`.
        s = re.sub(r"\bA(?i:ND)\b", "and", s)
        return s.strip()   # Removing leading and trailing whitespace.

    def _does_not_contain_et_al(self) -> None:
        """The authors display value should not contain `et al`."""
        if self.authors_display and \
                re.search(r"et al\.?($|\s*\()", self.authors_display):
            raise InvalidEvent(self, "Authors should not contain et al.")

    def project(self, submission: Submission) -> Submission:
        """Replace :prop:`.Submission.metadata.authors`."""
        submission.metadata.authors = self.authors
        submission.metadata.authors_display = self.authors_display
        return submission

    @classmethod
    def from_dict(cls, **data) -> Submission:
        """Override the default ``from_dict`` constructor to handle authors."""
        if 'authors' not in data:
            raise ValueError('Missing authors')
        data['authors'] = [Author(**au) for au in data['authors']]
        return cls(**data)


@dataclass
class AttachSourceContent(Event):
    """Add metadata about a source package to a submission."""

    location: str = field(default_factory=str)
    format: str = field(default_factory=str)
    checksum: str = field(default_factory=str)
    mime_type: str = field(default_factory=str)
    # TODO: Examine the necessity of an identifier when we are storing URIs.
    identifier: Optional[int] = field(default=None)
    size: int = field(default=0)

    # TODO: This should be configurable somewhere.
    ALLOWED_FORMATS = [
        'pdftex', 'tex', 'pdf', 'ps', 'html', 'invalid'
    ]
    ALLOWED_MIME_TYPES = [
        'application/tar+gzip', 'application/tar', 'application/zip'
    ]

    def validate(self, submission: Submission) -> None:
        """Validate data for :class:`.SubmissionContent`."""
        submission_is_not_finalized(self, submission)
        try:
            parsed = urlparse(self.location)
        except ValueError as e:
            raise InvalidEvent(self, 'Not a valid URL') from e
        if not parsed.netloc.endswith('arxiv.org'):
            raise InvalidEvent(self, 'External URLs not allowed.')

        if self.format not in self.ALLOWED_FORMATS:
            raise InvalidEvent(self, f'Format {self.format} not allowed')
        if not self.checksum:
            raise InvalidEvent(self, 'Missing checksum')
        if not self.identifier:
            raise InvalidEvent(self, 'Missing upload ID')

    def project(self, submission: Submission) -> Submission:
        """Replace :class:`.SubmissionContent` metadata on the submission."""
        submission.source_content = SubmissionContent(
            location=self.location,
            format=self.format,
            checksum=self.checksum,
            identifier=self.identifier,
            mime_type=self.mime_type,
            size=self.size
        )
        return submission


@dataclass
class FinalizeSubmission(Event):
    """Send the submission to the queue for announcement."""

    REQUIRED = [
        'creator', 'primary_classification', 'submitter_contact_verified',
        'submitter_accepts_policy', 'license', 'source_content', 'metadata',
    ]
    REQUIRED_METADATA = ['title', 'abstract', 'authors_display']

    def validate(self, submission: Submission) -> None:
        """Ensure that all required data/steps are complete."""
        if submission.finalized:
            raise InvalidEvent(self, "Submission already finalized")
        if not submission.active:
            raise InvalidEvent(self, "Submision must be active")
        self._required_fields_are_complete(submission)

    def project(self, submission: Submission) -> Submission:
        """Set :prop:`Submission.finalized`."""
        submission.finalized = True
        return submission

    def _required_fields_are_complete(self, submission: Submission) -> None:
        """Verify that all required fields are complete."""
        for key in self.REQUIRED:
            if not getattr(submission, key):
                raise InvalidEvent(self, f"Missing {key}")
        for key in self.REQUIRED_METADATA:
            if not getattr(submission.metadata, key):
                raise InvalidEvent(self, f"Missing {key}")


@dataclass
class UnFinalizeSubmission(Event):
    """Withdraw the submission from the queue for announcement."""

    def validate(self, submission: Submission) -> None:
        """Validate the unfinalize action."""
        self._must_be_finalized(submission)

    def _must_be_finalized(self, submission: Submission) -> None:
        """May only unfinalize a finalized submission."""
        if not submission.finalized:
            raise InvalidEvent(self, "Submission is not finalized")

    def project(self, submission: Submission) -> Submission:
        """Set :prop:`Submission.finalized`."""
        submission.finalized = False
        submission.status = Submission.WORKING
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
            raise InvalidEvent(self, 'comment_id is required')
        if not hasattr(submission, 'comments') or not submission.comments:
            raise InvalidEvent(self, 'Cannot delete comment that does not exist')
        if self.comment_id not in submission.comments:
            raise InvalidEvent(self, 'Cannot delete comment that does not exist')

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
            raise InvalidEvent(self, 'Event creator must be submission owner')

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
            raise InvalidEvent(self, 'Event creator must be submission owner')

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
        klass = EVENT_TYPES[event_type]
        if hasattr(klass, 'from_dict'):
            return klass.from_dict(**data)
        return EVENT_TYPES[event_type](**data)
    raise RuntimeError('Unknown event type: %s' % event_type)


# General-purpose validators go down here.
# TODO: should these be in a sub-module? This file is getting big.

def submission_is_not_finalized(event: Event, submission: Submission) -> None:
    """
    Verify that the submission is not finalized.

    Parameters
    ----------
    event : :class:`.Event`
    submission : :class:`.Submission`

    Raises
    ------
    :class:`.InvalidEvent`
        Raised if the submission is finalized.

    """
    if submission.finalized:
        raise InvalidEvent(event, "Cannot apply to a finalized submission")
