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


@dataclass
class License:
    """An license for distribution of the submission."""

    uri: str
    name: Optional[str] = None


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
        if self.affiliation:
            return "%s (%s)" % (self.name, self.affiliation)
        return name


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

    @property
    def authors_canonical(self):
        """Canonical representation of submission authors."""
        return ", ".join(self.authors)


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


@dataclass
class Submission:
    """Represents an arXiv submission object."""

    creator: Agent
    owner: Agent
    created: datetime
    primary_classification: Optional[Classification] = None
    delegations: Dict[str, Delegation] = field(default_factory=dict)
    proxy: Optional[Agent] = None
    submission_id: Optional[int] = None
    metadata: SubmissionMetadata = field(default_factory=SubmissionMetadata)
    active: bool = True
    finalized: bool = False
    published: bool = False
    # TODO: use a generic to further specify type?
    comments: dict = field(default_factory=dict)
    secondary_classification: List[Classification] = field(default_factory=list)
    submitter_contact_verified: bool = False
    submitter_is_author: bool = True
    submitter_accepts_policy: bool = False
    license: Optional[License] = None

    def to_dict(self) -> dict:
        data = asdict(self)
        data.update({
            'creator': self.creator.to_dict(),
            'owner': self.owner.to_dict(),
            'created': self.created.isoformat(),
        })
        if self.primary_classification:
            data['primary_classification'] = self.primary_classification.to_dict()
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


@dataclass
class Proposal(Annotation):
    """Represents a proposal to apply an event to a submission."""

    event_type: type
    event_data: dict


@dataclass
class Comment(Annotation):
    """A freeform textual annotation."""

    body: str

    @property
    def comment_id(self):
        """The unique identifier for a :class:`.Comment` instance."""
        return self.annotation_id


@dataclass
class Flag(Annotation):
    """Tags used to route submissions based on moderation policies."""

    pass