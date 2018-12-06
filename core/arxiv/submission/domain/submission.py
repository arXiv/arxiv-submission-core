"""Data structures for submissions."""

import hashlib
from typing import Optional, Dict, TypeVar, List
from datetime import datetime
from dateutil.parser import parse as parse_date

from dataclasses import dataclass, field
from dataclasses import asdict

from .agent import Agent, agent_factory
from .meta import License, Classification
from .util import get_tzaware_utc_now


@dataclass
class Author:
    """Represents an author of a submission."""

    order: int = field(default=0)
    forename: str = field(default_factory=str)
    surname: str = field(default_factory=str)
    initials: str = field(default_factory=str)
    affiliation: str = field(default_factory=str)
    email: str = field(default_factory=str)
    identifier: Optional[str] = field(default=None)
    display: Optional[str] = field(default=None)
    """
    Submitter may include a preferred display name for each author.

    If not provided, will be automatically generated from the other fields.
    """

    def __post_init__(self) -> None:
        """Auto-generate an identifier, if not provided."""
        if not self.identifier:
            self.identifier = self._generate_identifier()
        if not self.display:
            self.display = self.canonical

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
        return asdict(self)


@dataclass
class SubmissionContent:
    """Metadata about the submission source package."""

    identifier: str
    format: str
    checksum: str
    size: int


@dataclass
class SubmissionCompiled:
    """Metadata about a submission compilation product."""

    identifier: str
    format: str
    checksum: str
    size: int


@dataclass
class SubmissionMetadata:
    """Metadata about a :class:`.Submission` instance."""

    title: Optional[str] = None
    abstract: Optional[str] = None

    authors: list = field(default_factory=list)
    authors_display: str = field(default_factory=str)
    """The canonical arXiv author string."""

    doi: Optional[str] = None
    msc_class: Optional[str] = None
    acm_class: Optional[str] = None
    report_num: Optional[str] = None
    journal_ref: Optional[str] = None

    comments: str = field(default_factory=str)

    def to_dict(self) -> dict:
        """Generate dict representation of :class:`.SubmissionMetadata`."""
        return asdict(self)


@dataclass
class Delegation:
    """Delegation of editing privileges to a non-owning :class:`.Agent`."""

    delegate: Agent
    creator: Agent
    created: datetime = field(default_factory=get_tzaware_utc_now)

    @property
    def delegation_id(self):
        """Unique identifier for the delegation instance."""
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
class Hold:
    """Represents a block on announcement, usually for QA/QC purposes."""

    creator: Agent
    created: datetime = field(default_factory=get_tzaware_utc_now)
    hold_type: str = field(default_factory=str)
    hold_reason: Optional[str] = field(default_factory=list)


# TODO: add identification mechanism; consider using mechanism similar to
# comments, below.
@dataclass
class UserRequest:
    """Represents a user request related to a submission."""

    PENDING = 'pending'
    """Request is pending approval."""

    REJECTED = 'rejected'
    """Request has been rejected."""

    APPROVED = 'approved'
    """Request has been approved."""

    APPLIED = 'applied'
    """Submission has been updated on the basis of the approved request."""

    creator: Agent
    created: datetime = field(default_factory=get_tzaware_utc_now)
    updated: datetime = field(default_factory=get_tzaware_utc_now)
    status: str = field(default=PENDING)

    @property
    def request_type(self):
        """Name (str) of the type of user request."""
        return type(self).__name__

    @property
    def request_id(self):
        """The unique identifier for an :class:`.UserRequest` instance."""
        h = hashlib.new('sha1')
        h.update(b'%s:%s:%s' % (self.created.isoformat().encode('utf-8'),
                                self.request_type.encode('utf-8'),
                                self.creator.agent_identifier.encode('utf-8')))
        return h.hexdigest()

    def is_pending(self):
        return self.status == UserRequest.PENDING

    def is_approved(self):
        return self.status == UserRequest.APPROVED

    def is_applied(self):
        return self.status == UserRequest.APPLIED

    def is_rejected(self):
        return self.status == UserRequest.REJECTED

    def is_active(self) -> bool:
        return self.is_pending() or self.is_approved()


@dataclass
class WithdrawalRequest(UserRequest):
    """Represents a request ot withdraw a submission."""

    NAME = "Withdrawal"

    reason_for_withdrawal: Optional[str] = field(default=None)
    """If an e-print is withdrawn, the submitter is asked to explain why."""


@dataclass
class CrossListClassificationRequest(UserRequest):
    """Represents a request to add secondary classifications."""

    NAME = "Cross-list"

    classifications: List[Classification] = field(default_factory=list)

    @property
    def categories(self) -> List[str]:
        return [c.category for c in self.classifications]


@dataclass
class Submission:
    """Represents an arXiv submission object."""

    WORKING = 'working'
    SUBMITTED = 'submitted'
    ON_HOLD = 'hold'
    SCHEDULED = 'scheduled'
    PUBLISHED = 'published'
    ERROR = 'error'
    DELETED = 'deleted'
    WITHDRAWN = 'withdrawn'

    creator: Agent
    owner: Agent
    created: Optional[datetime] = field(default=None)
    updated: Optional[datetime] = field(default=None)

    source_content: Optional[SubmissionContent] = field(default=None)
    compiled_content: List[SubmissionCompiled] = field(default_factory=list)

    primary_classification: Optional[Classification] = field(default=None)
    delegations: Dict[str, Delegation] = field(default_factory=dict)
    proxy: Optional[Agent] = field(default=None)
    client: Optional[Agent] = field(default=None)
    submission_id: Optional[int] = field(default=None)
    metadata: SubmissionMetadata = field(default_factory=SubmissionMetadata)

    secondary_classification: List[Classification] = \
        field(default_factory=list)
    submitter_contact_verified: bool = field(default=False)
    submitter_is_author: Optional[bool] = field(default=None)
    submitter_accepts_policy: Optional[bool] = field(default=None)
    submitter_confirmed_preview: bool = field(default=False)
    license: Optional[License] = field(default=None)
    status: str = field(default=WORKING)
    arxiv_id: Optional[str] = field(default=None)
    """The published arXiv paper ID."""
    version: int = field(default=1)

    reason_for_withdrawal: Optional[str] = field(default=None)
    """If an e-print is withdrawn, the submitter is asked to explain why."""

    versions: List['Submission'] = field(default_factory=list)
    """Published versions of this :class:`.Submission`."""

    holds: List[Hold] = field(default_factory=list)
    user_requests: Dict[str, UserRequest] = field(default_factory=dict)

    @property
    def active(self) -> bool:
        """Actively moving through the submission workflow."""
        return self.status not in [self.DELETED, self.PUBLISHED]

    @property
    def published(self) -> bool:
        """The submission has been announced."""
        return self.status == self.PUBLISHED

    @property
    def finalized(self) -> bool:
        """Submitter has indicated submission is ready for publication."""
        return self.status not in [self.WORKING, self.DELETED]

    @property
    def deleted(self) -> bool:
        """Submission is removed."""
        return self.status == self.DELETED

    @property
    def secondary_categories(self) -> List[str]:
        """Category names from secondary classifications."""
        return [c.category for c in self.secondary_classification]

    @property
    def is_on_hold(self) -> bool:
        return len(self.holds) > 0 or self.status == self.ON_HOLD

    @property
    def has_active_requests(self) -> bool:
        return len(self.active_user_requests) > 0

    @property
    def active_user_requests(self) -> List[UserRequest]:
        return [r for r in self.user_requests.values() if r.is_active()]

    @property
    def pending_user_requests(self) -> List[UserRequest]:
        return [r for r in self.user_requests.values() if r.is_pending()]

    @property
    def rejected_user_requests(self) -> List[UserRequest]:
        return [r for r in self.user_requests.values() if r.is_rejected()]

    @property
    def approved_user_requests(self) -> List[UserRequest]:
        return [r for r in self.user_requests.values() if r.is_approved()]

    @property
    def applied_user_requests(self) -> List[UserRequest]:
        return [r for r in self.user_requests.values() if r.is_applied()]

    def add_user_request(self, request: UserRequest) -> None:
        """Add a :class:`.UserRequest`."""
        self.user_requests[request.request_id] = request

    def get_user_request(self, request_id: str) -> UserRequest:
        """Retrieve a :class:`.UserRequest` by ID."""
        return self.user_requests[request_id]

    def remove_user_request(self, request_id: str) -> None:
        """Remove a :class:`.UserRequest` by ID."""
        del self.user_requests[request_id]

    def to_dict(self) -> dict:
        """Generate a dict representation of this :class:`.Submission`."""
        data = asdict(self)
        data.update({
            'created': self.created.isoformat(),
            'updated': self.updated.isoformat() if self.updated else None,
            'metadata': self.metadata.to_dict(),
            'creator': self.creator.to_dict(),
            'owner': self.owner.to_dict(),
            'proxy': self.proxy.to_dict() if self.proxy else None,
            'client': self.client.to_dict() if self.client else None,
            'finalized': self.finalized,
            'deleted': self.deleted,
            'published': self.published,
            'active': self.active
        })
        return data

    @classmethod
    def from_dict(cls, **data) -> 'Submission':
        """Construct from a ``dict``."""
        data['created'] = parse_date(data['created'])
        if 'updated' in data and data['updated'] is not None:
            data['updated'] = parse_date(data['updated'])
        if 'metadata' in data and data['metadata'] is not None:
            data['metadata'] = SubmissionMetadata(**data['metadata'])
        data['creator'] = agent_factory(**data['creator'])
        data['owner'] = agent_factory(**data['owner'])
        if 'proxy' in data and data['proxy'] is not None:
            data['proxy'] = agent_factory(**data['proxy'])
        if 'client' in data and data['client'] is not None:
            data['client'] = agent_factory(**data['client'])
        return cls(**{k: v for k, v in data.items()
                      if k in cls.__dataclass_fields__})


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
