"""Data structures for submissions."""

from typing import TypeVar, Optional, List, Dict
import hashlib
from datetime import datetime
from dataclasses import dataclass, field
from dataclasses import asdict
from api.domain.agent import Agent, agent_factory


SubmissionType = TypeVar('SubmissionType', bound='Submission')


@dataclass
class Classification:
    """An classification for a :class:`.Submission`."""

    domain: str
    archive: str
    category: str


@dataclass
class License:
    """An license for distribution of the submission."""

    uri: str
    name: Optional[str] = None


@dataclass
class Author:
    """Represents an author of a submission."""

    identifier: str
    email: str
    forename: str
    surname: str
    initials: str = field(default_factory=str)
    affiliation: str = field(default_factory=str)
    order: int = 0

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

    title: str = field(default_factory=str)
    abstract: str = field(default_factory=str)
    authors: List[Author] = field(default_factory=list)
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
    created: datetime

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
    metadata: SubmissionMetadata = field(default_factory=SubmissionMetadata)

    submission_id: Optional[int] = None
    delegations: Dict[str, Delegation] = field(default_factory=dict)
    proxy: Optional[Agent] = None
    active: bool = True
    finalized: bool = False
    published: bool = False

    comments: dict = field(default_factory=dict)
    primary_classification: Optional[Classification] = None
    secondary_classification: List[Classification] = field(
        default_factory=list
    )
    submitter_contact_verified: bool = False
    submitter_is_author: bool = True
    submitter_accepts_policy: bool = False

    license: Optional[License] = None
