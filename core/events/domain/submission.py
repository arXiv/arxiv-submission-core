"""Data structures for submissions."""

import hashlib
from typing import Optional, Dict, TypeVar, List
from datetime import datetime

from dataclasses import dataclass, field
from dataclasses import asdict

from .agent import Agent


@dataclass
class Classification:
    """An archive/category classification for a :class:`.Submission`."""

    category: str

    def to_dict(self) -> dict:
        """Generate a dict representation of this :class:`.Classification`."""
        return asdict(self)


@dataclass
class License:
    """An license for distribution of the submission."""

    uri: str
    name: Optional[str] = None

    def to_dict(self) -> dict:
        """Generate a dict representation of this :class:`.License`."""
        return asdict(self)


@dataclass
class Author:
    """Represents an author of a submission."""

    order: int
    forename: str = field(default_factory=str)
    surname: str = field(default_factory=str)
    initials: str = field(default_factory=str)
    affiliation: str = field(default_factory=str)
    email: str = field(default_factory=str)
    identifier: Optional[str] = None

    def __post_init__(self) -> None:
        """Auto-generate an identifier, if not provided."""
        if not self.identifier:
            self.identifier = self._generate_identifier()

    def _generate_identifier(self):
        h = hashlib.new('sha1')
        h.update(bytes(':'.join([self.forename, self.surname, self.initials,
                                 self.affiliation, self.email]),
                       encoding='utf-8'))
        return h.hexdigest()

    @property
    def canonical(self):
        """Canonical representation of the author name."""
        name = "%s %s %s" % (self.forename, self.initials, self.surname)
        name = name.replace('  ', ' ')
        if self.affiliation:
            return "%s (%s)" % (name, self.affiliation)
        return name

    def to_dict(self) -> dict:
        """Generate a dict representation of this :class:`.Author`."""
        data = asdict(self)
        data['canonical'] = self.canonical
        return data


@dataclass
class SubmissionContent:
    """Metadata about the submission source package and compiled products."""

    location: str
    format: str
    mime_type: str
    size: str
    checksum: str
    identifier: int


@dataclass
class SubmissionMetadata:
    """Metadata about a :class:`.Submission` instance."""

    title: Optional[str] = None
    abstract: Optional[str] = None

    authors: list = field(default_factory=list)

    doi: Optional[str] = None
    msc_class: Optional[str] = None
    acm_class: Optional[str] = None
    report_num: Optional[str] = None
    journal_ref: Optional[str] = None

    comments: str = field(default_factory=str)

    @property
    def authors_canonical(self):
        """Canonical representation of submission authors."""
        return ", ".join([au.canonical for au in self.authors])

    def to_dict(self) -> dict:
        """Generate dict representation of :class:`.SubmissionMetadata`."""
        data = asdict(self)
        data['authors_canonical'] = self.authors_canonical
        return data


@dataclass
class Delegation:
    """Delegation of editing privileges to a non-owning :class:`.Agent`."""

    delegate: Agent
    creator: Agent
    created: datetime = field(default_factory=datetime.now)

    @property
    def delegation_id(self):
        """Unique identifer for the delegation instance."""
        h = hashlib.new('sha1')
        h.update(b'%s:%s:%s' % (self.delegate.agent_identifier,
                                self.creator.agent_identifier,
                                self.created.isodate()))
        return h.hexdigest()

    def to_dict(self) -> dict:
        """Generate a dict representation of this :class:`.Delegation`."""
        data = asdict(self)
        data['delegation_id'] = self.delegation_id
        return data


@dataclass
class Submission:
    """Represents an arXiv submission object."""

    WORKING = 'working'
    PROCESSING = 'processing'
    SUBMITTED = 'submitted'
    ON_HOLD = 'hold'
    SCHEDULED = 'scheduled'
    PUBLISHED = 'published'
    DELETED = 'deleted'

    creator: Agent
    owner: Agent
    created: datetime
    updated: Optional[datetime] = field(default=None)

    source_content: Optional[SubmissionContent] = field(default=None)
    compiled_content: List[SubmissionContent] = field(default_factory=list)

    primary_classification: Optional[Classification] = field(default=None)
    delegations: Dict[str, Delegation] = field(default_factory=dict)
    proxy: Optional[Agent] = field(default=None)
    client: Optional[Agent] = field(default=None)
    submission_id: Optional[int] = field(default=None)
    metadata: SubmissionMetadata = field(default_factory=SubmissionMetadata)
    active: bool = field(default=True)
    """Actively moving through the submission workflow."""

    finalized: bool = field(default=False)
    """Submitter has indicated submission is ready for publication."""

    published: bool = field(default=False)
    secondary_classification: List[Classification] = \
        field(default_factory=list)
    submitter_contact_verified: bool = field(default=False)
    submitter_is_author: bool = field(default=True)
    submitter_accepts_policy: bool = field(default=False)
    license: Optional[License] = field(default=None)
    status: str = field(default=WORKING)
    arxiv_id: Optional[str] = field(default=None)
    """The published arXiv paper ID."""

    def to_dict(self) -> dict:
        """Generate a dict representation of this :class:`.Submission`."""
        data = asdict(self)
        data.update({
            'creator': self.creator.to_dict(),
            'owner': self.owner.to_dict(),
            'created': self.created.isoformat(),
        })
        if self.client:
            data.update({'client': self.client.to_dict()})
        if self.primary_classification:
            data['primary_classification'] = \
                self.primary_classification.to_dict()
        if self.delegations:
            data['delegations'] = {
                key: delegation.to_dict()
                for key, delegation in self.delegations.items()
            }
        if self.proxy:
            data['proxy'] = self.proxy.to_dict()
        if self.metadata:
            data['metadata'] = self.metadata.to_dict()
        if self.license:
            data['license'] = self.license.to_dict()
        return data


@dataclass
class Annotation:
    """Auxilliary metadata used by the submission and moderation process."""

    creator: Agent
    submission: Submission
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
class Flag(Annotation):
    """Tags used to route submissions based on moderation policies."""

    pass
