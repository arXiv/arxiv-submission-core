"""Data structures for submissions."""

from typing import Optional, Dict, TypeVar, List, Iterable, Set, Union
from datetime import datetime
from dateutil.parser import parse as parse_date
from enum import Enum
import hashlib

from dataclasses import dataclass, field, asdict

from .agent import Agent, agent_factory
from .meta import License, Classification
from .annotation import Comment, Feature, Annotation, annotation_factory
from .proposal import Proposal
from .process import ProcessStatus
from .flag import Flag, flag_factory
from .util import get_tzaware_utc_now, dict_coerce, list_coerce
from .compilation import Compilation


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


@dataclass
class SubmissionContent:
    """Metadata about the submission source package."""

    class Format(Enum):
        """Supported source formats."""

        UNKNOWN = None
        """We could not determine the source format."""
        INVALID = "invalid"
        """We are able to infer the source format, and it is not supported."""
        TEX = "tex"
        """A flavor of TeX."""
        PDFTEX = "pdftex"
        """A PDF derived from TeX."""
        POSTSCRIPT = "ps"
        """A postscript source."""
        HTML = "html"
        """An HTML source."""
        PDF = "pdf"
        """A PDF-only source."""

    identifier: str
    checksum: str
    uncompressed_size: int
    compressed_size: int
    source_format: Format = Format.UNKNOWN

    def __post_init__(self):
        """Make sure that :attr:`.source_format` is a :class:`.Format`."""
        if self.source_format and type(self.source_format) is str:
            self.source_format = self.Format(self.source_format)


@dataclass
class SubmissionMetadata:
    """Metadata about a :class:`.domain.submission.Submission` instance."""

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


@dataclass
class Delegation:
    """Delegation of editing privileges to a non-owning :class:`.Agent`."""

    delegate: Agent
    creator: Agent
    created: datetime = field(default_factory=get_tzaware_utc_now)
    delegation_id: str = field(default_factory=str)

    def __post_init__(self):
        """Set derivative fields."""
        self.delegation_id = self.get_delegation_id()

    def get_delegation_id(self):
        """Generate unique identifier for the delegation instance."""
        h = hashlib.new('sha1')
        h.update(b'%s:%s:%s' % (self.delegate.agent_identifier,
                                self.creator.agent_identifier,
                                self.created.isodate()))
        return h.hexdigest()


@dataclass
class Hold:
    """Represents a block on announcement, usually for QA/QC purposes."""

    class Type(Enum):
        """Supported holds in the submission system."""

        PATCH = 'patch'
        """A hold generated from the classic submission system."""

        SOURCE_OVERSIZE = "source_oversize"
        """The submission source is oversize."""

        PDF_OVERSIZE = "pdf_oversize"
        """The submission PDF is oversize."""

    event_id: str
    """The event that created the hold."""

    creator: Agent
    created: datetime = field(default_factory=get_tzaware_utc_now)
    hold_type: Type = field(default=Type.PATCH)
    hold_reason: Optional[str] = field(default_factory=str)

    def __post_init__(self):
        """Check enums and agents."""
        if self.creator and type(self.creator) is dict:
            self.creator = agent_factory(**self.creator)
        self.hold_type = self.Type(self.hold_type)
        # if not isinstance(created, datetime):
        #     created = parse_date(created)


@dataclass
class Waiver:
    """Represents an exception or override."""

    event_id: str
    """The identifier of the event that produced this waiver."""
    waiver_type: Hold.Type
    waiver_reason: str
    created: datetime
    creator: Agent

    def __post_init__(self):
        """Check enums and agents."""
        if self.creator and type(self.creator) is dict:
            self.creator = agent_factory(**self.creator)
        self.waiver_type = Hold.Type(self.waiver_type)


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

    CANCELLED = 'cancelled'

    request_id: str
    creator: Agent
    created: datetime = field(default_factory=get_tzaware_utc_now)
    updated: datetime = field(default_factory=get_tzaware_utc_now)
    status: str = field(default=PENDING)
    request_type: str = field(default_factory=str)

    def __post_init__(self):
        """Check agents."""
        if self.creator and type(self.creator) is dict:
            self.creator = agent_factory(**self.creator)
        self.request_type = self.get_request_type()

    def get_request_type(self) -> str:
        """Name (str) of the type of user request."""
        return type(self).__name__

    def is_pending(self) -> bool:
        """Check whether the request is pending."""
        return self.status == UserRequest.PENDING

    def is_approved(self) -> bool:
        """Check whether the request has been approved."""
        return self.status == UserRequest.APPROVED

    def is_applied(self) -> bool:
        """Check whether the request has been applied."""
        return self.status == UserRequest.APPLIED

    def is_rejected(self) -> bool:
        """Check whether the request has been rejected."""
        return self.status == UserRequest.REJECTED

    def is_active(self) -> bool:
        """Check whether the request is active."""
        return self.is_pending() or self.is_approved()

    @classmethod
    def generate_request_id(cls, submission: 'Submission', N: int = -1) -> str:
        """Generate a unique identifier for this request."""
        h = hashlib.new('sha1')
        if N < 0:
            N = len([rq for rq in submission.iter_requests if type(rq) is cls])
        h.update(f'{submission.submission_id}:{cls.NAME}:{N}'.encode('utf-8'))
        return h.hexdigest()


@dataclass
class WithdrawalRequest(UserRequest):
    """Represents a request ot withdraw a submission."""

    NAME = "Withdrawal"

    reason_for_withdrawal: Optional[str] = field(default=None)
    """If an e-print is withdrawn, the submitter is asked to explain why."""

    def apply(self, submission: 'Submission') -> 'Submission':
        """Apply the withdrawal."""
        submission.reason_for_withdrawal = self.reason_for_withdrawal
        submission.status = Submission.WITHDRAWN
        return submission


@dataclass
class CrossListClassificationRequest(UserRequest):
    """Represents a request to add secondary classifications."""

    NAME = "Cross-list"

    classifications: List[Classification] = field(default_factory=list)

    def apply(self, submission: 'Submission') -> 'Submission':
        """Apply the cross-list request."""
        submission.secondary_classification.extend(self.classifications)
        return submission

    @property
    def categories(self) -> List[str]:
        """Get the requested cross-list categories."""
        return [c.category for c in self.classifications]


@dataclass
class Submission:
    """
    Represents an arXiv submission object.

    Some notable differences between this view of submissions and the classic
    model:

    - There is no "hold" status. Status reflects where the submission is
      in the pipeline. Holds are annotations that can be applied to the
      submission, and may impact its ability to proceed (e.g. from submitted
      to scheduled). Submissions that are in working status can have holds on
      them!
    - We use `arxiv_id` instead of `paper_id` to refer to the canonical arXiv
      identifier for the e-print (once it is announced).
    - Instead of having a separate "submission" record for every change to an
      e-print (e.g. replacement, jref, etc), we represent the entire history
      as a single submission. Announced versions can be found in
      :attr:`.versions`. Withdrawal and cross-list requests can be found in
      :attr:`.user_requests`. JREFs are treated like they "just happen",
      reflecting the forthcoming move away from storing journal ref information
      in the core metadata record.

    """

    WORKING = 'working'
    SUBMITTED = 'submitted'
    SCHEDULED = 'scheduled'
    ANNOUNCED = 'announced'
    ERROR = 'error'     # TODO: eliminate this status.
    DELETED = 'deleted'
    WITHDRAWN = 'withdrawn'

    creator: Agent
    owner: Agent
    proxy: Optional[Agent] = field(default=None)
    client: Optional[Agent] = field(default=None)
    created: Optional[datetime] = field(default=None)
    updated: Optional[datetime] = field(default=None)
    submitted: Optional[datetime] = field(default=None)
    submission_id: Optional[int] = field(default=None)

    source_content: Optional[SubmissionContent] = field(default=None)
    metadata: SubmissionMetadata = field(default_factory=SubmissionMetadata)
    primary_classification: Optional[Classification] = field(default=None)
    secondary_classification: List[Classification] = \
        field(default_factory=list)
    submitter_contact_verified: bool = field(default=False)
    submitter_is_author: Optional[bool] = field(default=None)
    submitter_accepts_policy: Optional[bool] = field(default=None)
    submitter_compiled_preview: bool = field(default=False)
    submitter_confirmed_preview: bool = field(default=False)
    license: Optional[License] = field(default=None)
    status: str = field(default=WORKING)
    """Disposition within the submission pipeline."""

    arxiv_id: Optional[str] = field(default=None)
    """The announced arXiv paper ID."""

    version: int = field(default=1)

    reason_for_withdrawal: Optional[str] = field(default=None)
    """If an e-print is withdrawn, the submitter is asked to explain why."""

    versions: List['Submission'] = field(default_factory=list)
    """Announced versions of this :class:`.domain.submission.Submission`."""

    # These fields are related to moderation/quality control.
    user_requests: Dict[str, UserRequest] = field(default_factory=dict)
    """Requests from the owner for changes that require approval."""

    proposals: Dict[str, Proposal] = field(default_factory=dict)
    """Proposed changes to the submission, e.g. reclassification."""

    processes: List[ProcessStatus] = field(default_factory=list)
    """Information about automated processes."""

    annotations: Dict[str, Annotation] = field(default_factory=dict)
    """Quality control annotations."""

    flags: Dict[str, Flag] = field(default_factory=dict)
    """Quality control flags."""

    comments: Dict[str, Comment] = field(default_factory=dict)
    """Moderation/administrative comments."""

    holds: Dict[str, Hold] = field(default_factory=dict)
    """Quality control holds."""

    waivers: Dict[str, Waiver] = field(default_factory=dict)
    """Quality control waivers."""

    @property
    def features(self) -> Dict[str, Feature]:
        return {k: v for k, v in self.annotations.items()
                if isinstance(v, Feature)}

    @property
    def active(self) -> bool:
        """Actively moving through the submission workflow."""
        return self.status not in [self.DELETED, self.ANNOUNCED]

    @property
    def announced(self) -> bool:
        """The submission has been announced."""
        return self.status == self.ANNOUNCED

    @property
    def finalized(self) -> bool:
        """Submitter has indicated submission is ready for publication."""
        return self.status not in [self.WORKING, self.DELETED]

    @property
    def deleted(self) -> bool:
        """Submission is removed."""
        return self.status == self.DELETED

    @property
    def primary_category(self) -> str:
        return self.primary_classification.category

    @property
    def secondary_categories(self) -> List[str]:
        """Category names from secondary classifications."""
        return [c.category for c in self.secondary_classification]

    @property
    def is_on_hold(self) -> bool:
        # We need to explicitly check ``status`` here because classic doesn't
        # have a representation for Hold events.
        return (self.status == self.SUBMITTED
                and len(self.hold_types - self.waiver_types) > 0)

    def has_waiver_for(self, hold_type: Hold.Type) -> bool:
        return hold_type in self.waiver_types

    @property
    def hold_types(self) -> Set[Hold.Type]:
        return set([hold.hold_type for hold in self.holds.values()])

    @property
    def waiver_types(self) -> Set[Hold.Type]:
        return set([waiver.hold_type for waiver in self.waivers.values()])

    @property
    def has_active_requests(self) -> bool:
        return len(self.active_user_requests) > 0

    @property
    def iter_requests(self) -> Iterable[UserRequest]:
        return self.user_requests.values()

    @property
    def active_user_requests(self) -> List[UserRequest]:
        return sorted(filter(lambda r: r.is_active(), self.iter_requests),
                      key=lambda r: r.created)

    @property
    def pending_user_requests(self) -> List[UserRequest]:
        return sorted(filter(lambda r: r.is_pending(), self.iter_requests),
                      key=lambda r: r.created)

    @property
    def rejected_user_requests(self) -> List[UserRequest]:
        return sorted(filter(lambda r: r.is_rejected(), self.iter_requests),
                      key=lambda r: r.created)

    @property
    def approved_user_requests(self) -> List[UserRequest]:
        return sorted(filter(lambda r: r.is_approved(), self.iter_requests),
                      key=lambda r: r.created)

    @property
    def applied_user_requests(self) -> List[UserRequest]:
        return sorted(filter(lambda r: r.is_applied(), self.iter_requests),
                      key=lambda r: r.created)

    def __post_init__(self):
        if type(self.creator) is dict:
            self.creator = agent_factory(**self.creator)
        if type(self.owner) is dict:
            self.owner = agent_factory(**self.owner)
        if self.proxy and type(self.proxy) is dict:
            self.proxy = agent_factory(**self.proxy)
        if self.client and type(self.client) is dict:
            self.client = agent_factory(**self.client)
        if type(self.created) is str:
            self.created = parse_date(self.created)
        if type(self.updated) is str:
            self.updated = parse_date(self.updated)
        if type(self.submitted) is str:
            self.submitted = parse_date(self.submitted)
        if type(self.source_content) is dict:
            self.source_content = SubmissionContent(**self.source_content)
        if type(self.primary_classification) is dict:
            self.primary_classification = \
                Classification(**self.primary_classification)
        if type(self.metadata) is dict:
            self.metadata = SubmissionMetadata(**self.metadata)
        # self.delegations = dict_coerce(Delegation, self.delegations)
        self.secondary_classification = \
            list_coerce(Classification, self.secondary_classification)
        if type(self.license) is dict:
            self.license = License(**self.license)
        self.versions = list_coerce(Submission, self.versions)
        self.user_requests = dict_coerce(request_factory, self.user_requests)
        self.proposals = dict_coerce(Proposal, self.proposals)
        self.processes = list_coerce(ProcessStatus, self.processes)
        self.annotations = dict_coerce(annotation_factory, self.annotations)
        self.flags = dict_coerce(flag_factory, self.flags)
        self.comments = dict_coerce(Comment, self.comments)
        self.holds = dict_coerce(Hold, self.holds)
        self.waivers = dict_coerce(Waiver, self.waivers)


def request_factory(**data: dict) -> UserRequest:
    """Generate a :class:`.UserRequest` from raw data."""
    for cls in UserRequest.__subclasses__():
        if data['request_type'] == cls.__name__:
            return cls(**data)
    raise ValueError('Invalid request type')
