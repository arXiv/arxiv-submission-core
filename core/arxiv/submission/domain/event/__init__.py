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
  :mod:`arxiv.submission.domain.tests.test_events`.

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
import copy
from datetime import datetime
from pytz import UTC
from typing import Optional, TypeVar, List, Tuple, Any, Dict
from urllib.parse import urlparse
from dataclasses import dataclass, field, asdict
import bleach

from arxiv.util import schema
from arxiv import taxonomy, identifier
from arxiv.base import logging

from ..agent import Agent
from ..submission import Submission, SubmissionMetadata, Author, \
    Classification, License, Delegation, Comment, Flag, Proposal, \
    SubmissionContent, WithdrawalRequest, CrossListClassificationRequest

from ...exceptions import InvalidEvent
from ..util import get_tzaware_utc_now
from .event import Event
from .request import RequestCrossList, RequestWithdrawal, ApplyRequest, \
    RejectRequest, ApproveRequest
from . import validators

logger = logging.getLogger(__name__)


# Events related to the creation of a new submission.
#
# These are largely the domain of the metadata API, and the submission UI.


@dataclass
class CreateSubmission(Event):
    """Creation of a new :class:`.Submission`."""

    NAME = "create submission"
    NAMED = "submission created"

    def __hash__(self):
        """Use event ID as object hash."""
        return hash(self.event_id)

    def validate(self, *args, **kwargs) -> None:
        """Validate creation of a submission."""
        return

    def project(self, submission: None = None) -> Submission:
        """Create a new :class:`.Submission`."""
        return Submission(creator=self.creator, created=self.created,
                          owner=self.creator, proxy=self.proxy,
                          client=self.client)

    def to_dict(self):
        """Generate a dict of this :class:`.CreateSubmission`."""
        data = super(CreateSubmission, self).to_dict()
        return data

    @classmethod
    def from_dict(cls, **data) -> 'CreateSubmission':
        """Override the ``from_dict`` constructor to handle submission."""
        return cls(**data)


@dataclass(init=False)
class CreateSubmissionVersion(Event):
    """
    Creates a new version of a submission.

    Takes the submission back to "working" state; the user or client may make
    additional changes before finalizing the submission.
    """

    NAME = "create a new version"
    NAMED = "new version created"

    def __hash__(self):
        """Use event ID as object hash."""
        return hash(self.event_id)

    def validate(self, submission: Submission) -> None:
        """Only applies to published submissions."""
        if not submission.published:
            raise InvalidEvent(self, "Must already be published")
        validators.no_active_requests(self, submission)

    def project(self, submission: Submission) -> Submission:
        """Increment the version number, and reset several fields."""
        submission.version += 1
        submission.status = Submission.WORKING
        # Return these to default.
        submission.status = Submission.status
        submission.source_content = Submission.source_content
        submission.license = Submission.license
        submission.submitter_is_author = Submission.submitter_is_author
        submission.submitter_contact_verified = \
            Submission.submitter_contact_verified
        submission.submitter_accepts_policy = \
            Submission.submitter_accepts_policy
        submission.submitter_confirmed_preview = \
            Submission.submitter_confirmed_preview
        submission.compiled_content.clear()
        return submission


@dataclass(init=False)
class Rollback(Event):
    """Roll back to the most recent published version, or delete."""

    NAME = "roll back or delete"
    NAMED = "rolled back or deleted"

    def __hash__(self):
        """Use event ID as object hash."""
        return hash(self.event_id)

    def validate(self, submission: Submission) -> None:
        """Only applies to submissions in an unpublished state."""
        if submission.published:
            raise InvalidEvent(self, "Cannot already be published")
        elif submission.version > 1 and not submission.versions:
            raise InvalidEvent(self, "No published version to which to revert")

    def project(self, submission: Submission) -> Submission:
        """Decrement the version number, and reset fields."""
        if submission.version == 1:
            submission.status = Submission.DELETED
            return submission
        submission.version -= 1
        target = submission.versions[-1]
        # Return these to last published state.
        submission.status = target.status
        submission.source_content = target.source_content
        submission.compiled_content = target.compiled_content
        submission.submitter_contact_verified = \
            target.submitter_contact_verified
        submission.submitter_accepts_policy = \
            target.submitter_accepts_policy
        submission.submitter_confirmed_preview = \
            target.submitter_confirmed_preview
        submission.license = target.license
        submission.metadata = copy.deepcopy(target.metadata)
        return submission


@dataclass(init=False)
class ConfirmContactInformation(Event):
    """Submitter has verified their contact information."""

    NAME = "confirm contact information"
    NAMED = "contact information confirmed"

    def __hash__(self):
        """Use event ID as object hash."""
        return hash(self.event_id)

    def validate(self, submission: Submission) -> None:
        """Cannot apply to a finalized submission."""
        validators.submission_is_not_finalized(self, submission)

    def project(self, submission: Submission) -> Submission:
        """Update :prop:`.Submission.submitter_contact_verified`."""
        submission.submitter_contact_verified = True
        return submission


@dataclass
class ConfirmAuthorship(Event):
    """The submitting user asserts whether they are an author of the paper."""

    NAME = "confirm that submitter is an author"
    NAMED = "submitter authorship status confirmed"

    def __hash__(self):
        """Use event ID as object hash."""
        return hash(self.event_id)

    submitter_is_author: bool = True

    def validate(self, submission: Submission) -> None:
        """Cannot apply to a finalized submission."""
        validators.submission_is_not_finalized(self, submission)

    def project(self, submission: Submission) -> Submission:
        """Update the authorship flag on the submission."""
        submission.submitter_is_author = self.submitter_is_author
        return submission


@dataclass(init=False)
class ConfirmPolicy(Event):
    """The submitting user accepts the arXiv submission policy."""

    NAME = "confirm policy acceptance"
    NAMED = "policy acceptance confirmed"

    def __hash__(self):
        """Use event ID as object hash."""
        return hash(self.event_id)

    def validate(self, submission: Submission) -> None:
        """Cannot apply to a finalized submission."""
        validators.submission_is_not_finalized(self, submission)

    def project(self, submission: Submission) -> Submission:
        """Set the policy flag on the submission."""
        submission.submitter_accepts_policy = True
        return submission


@dataclass
class SetPrimaryClassification(Event):
    """Update the primary classification of a submission."""

    NAME = "set primary classification"
    NAMED = "primary classification set"

    def __hash__(self):
        """Use event ID as object hash."""
        return hash(self.event_id)

    category: Optional[str] = None

    def validate(self, submission: Submission) -> None:
        """Validate the primary classification category."""
        validators.must_be_a_valid_category(self, self.category, submission)
        self._creator_must_be_endorsed(submission)
        self._must_be_unpublished(submission)
        validators.submission_is_not_finalized(self, submission)
        validators.cannot_be_secondary(self, self.category, submission)

    def _must_be_unpublished(self, submission: Submission) -> None:
        """Can only be set on the first version before publication."""
        if submission.arxiv_id is not None or submission.version > 1:
            raise InvalidEvent(self, "Can only be set on the first version,"
                                     " before publication.")

    def _creator_must_be_endorsed(self, submission: Submission) -> None:
        """The creator of this event must be endorsed for the category."""
        try:
            archive,  = self.category.split('.', 1)
        except ValueError:
            archive = self.category
        if self.category not in self.creator.endorsements \
                and f'{archive}.*' not in self.creator.endorsements \
                and '*.*' not in self.creator.endorsements:
            raise InvalidEvent(self, f"Creator is not endorsed for"
                                     f" {self.category}.")

    def project(self, submission: Submission) -> Submission:
        """Set :prop:`.Submission.primary_classification`."""
        clsn = Classification(category=self.category)
        submission.primary_classification = clsn
        return submission


@dataclass
class AddSecondaryClassification(Event):
    """Add a secondary :class:`.Classification` to a submission."""

    NAME = "add cross-list classification"
    NAMED = "cross-list classification added"

    def __hash__(self):
        """Use event ID as object hash."""
        return hash(self.event_id)

    category: Optional[str] = field(default=None)

    def validate(self, submission: Submission) -> None:
        """Validate the secondary classification category to add."""
        validators.must_be_a_valid_category(self, self.category, submission)
        validators.cannot_be_primary(self, self.category, submission)
        validators.cannot_be_secondary(self, self.category, submission)
        validators.submission_is_not_finalized(self, submission)

    def project(self, submission: Submission) -> Submission:
        """Add a :class:`.Classification` as a secondary classification."""
        classification = Classification(category=self.category)
        submission.secondary_classification.append(classification)
        return submission


@dataclass
class RemoveSecondaryClassification(Event):
    """Remove secondary :class:`.Classification` from submission."""

    NAME = "remove cross-list classification"
    NAMED = "cross-list classification removed"

    def __hash__(self):
        """Use event ID as object hash."""
        return hash(self.event_id)

    category: Optional[str] = field(default=None)

    def validate(self, submission: Submission) -> None:
        """Validate the secondary classification category to remove."""
        validators.must_be_a_valid_category(self, self.category, submission)
        self._must_already_be_present(submission)
        validators.submission_is_not_finalized(self, submission)

    def project(self, submission: Submission) -> Submission:
        """Remove from :prop:`.Submission.secondary_classification`."""
        submission.secondary_classification = [
            classn for classn in submission.secondary_classification
            if not classn.category == self.category
        ]
        return submission

    def _must_already_be_present(self, submission: Submission) -> None:
        """One cannot remove a secondary that is not actually set."""
        if self.category not in submission.secondary_categories:
            raise InvalidEvent(self, 'No such category on submission')


@dataclass
class SetLicense(Event):
    """The submitter has selected a license for their submission."""

    NAME = "select distribution license"
    NAMED = "distribution license selected"

    def __hash__(self):
        """Use event ID as object hash."""
        return hash(self.event_id)

    license_name: Optional[str] = field(default=None)
    license_uri: Optional[str] = field(default=None)

    def validate(self, submission: Submission) -> None:
        """Validate the selected license."""
        validators.submission_is_not_finalized(self, submission)

    def project(self, submission: Submission) -> Submission:
        """Set :prop:`.Submission.license`."""
        submission.license = License(
            name=self.license_name,
            uri=self.license_uri
        )
        return submission


@dataclass
class SetTitle(Event):
    """Update the title of a submission."""

    NAME = "update title"
    NAMED = "title updated"

    def __hash__(self):
        """Use event ID as object hash."""
        return hash(self.event_id)

    title: str = field(default='')

    MIN_LENGTH = 5
    MAX_LENGTH = 240
    ALLOWED_HTML = ["br", "sup", "sub", "hr", "em", "strong", "h"]

    def __post_init__(self):
        """Perform some light cleanup on the provided value."""
        self.title = self.cleanup(self.title)

    def validate(self, submission: Submission) -> None:
        """Validate the title value."""
        validators.submission_is_not_finalized(self, submission)
        self._does_not_contain_html_escapes(submission)
        self._acceptable_length(submission)
        validators.no_trailing_period(self, submission, self.title)
        if self.title.isupper():
            raise InvalidEvent(self, "Title must not be all-caps")
        self._check_for_html(submission)

    def project(self, submission: Submission) -> Submission:
        """Update the title on a :class:`.Submission`."""
        submission.metadata.title = self.title
        return submission

    def _does_not_contain_html_escapes(self, submission: Submission) -> None:
        """The title must not contain HTML escapes."""
        if re.search(r"\&(?:[a-z]{3,4}|#x?[0-9a-f]{1,4})\;", self.title):
            raise InvalidEvent(self, "Title may not contain HTML escapes")

    def _acceptable_length(self, submission: Submission) -> None:
        """Verify that the title is an acceptable length."""
        N = len(self.title)
        if N < self.MIN_LENGTH or N > self.MAX_LENGTH:
            raise InvalidEvent(self, f"Title must be between {self.MIN_LENGTH}"
                                     f" and {self.MAX_LENGTH} characters")

    # In classic, this is only an admin post-hoc check.
    def _check_for_html(self, submission: Submission) -> None:
        """Check for disallowed HTML."""
        N = len(self.title)
        N_after = len(bleach.clean(self.title, tags=self.ALLOWED_HTML,
                                   strip=True))
        if N > N_after:
            raise InvalidEvent(self, "Title contains unacceptable HTML tags")

    @staticmethod
    def cleanup(value: str) -> str:
        """Perform some light tidying on the title."""
        value = re.sub(r"\s+", " ", value).strip()       # Single spaces only.
        return value


@dataclass
class SetAbstract(Event):
    """Update the abstract of a submission."""

    NAME = "update abstract"
    NAMED = "abstract updated"

    def __hash__(self):
        """Use event ID as object hash."""
        return hash(self.event_id)

    abstract: str = field(default='')

    MIN_LENGTH = 20
    MAX_LENGTH = 1920

    def __post_init__(self):
        """Perform some light cleanup on the provided value."""
        self.abstract = self.cleanup(self.abstract)

    def validate(self, submission: Submission) -> None:
        """Validate the abstract value."""
        validators.submission_is_not_finalized(self, submission)
        self._acceptable_length(submission)

    def project(self, submission: Submission) -> Submission:
        """Update the abstract on a :class:`.Submission`."""
        submission.metadata.abstract = self.abstract
        return submission

    def _acceptable_length(self, submission: Submission) -> None:
        N = len(self.abstract)
        if N < self.MIN_LENGTH or N > self.MAX_LENGTH:
            raise InvalidEvent(self,
                               f"Abstract must be between {self.MIN_LENGTH}"
                               f" and {self.MAX_LENGTH} characters")

    @staticmethod
    def cleanup(value: str) -> str:
        """Perform some light tidying on the abstract."""
        value = re.sub(r"\s+", " ", value)          # Single spaces only.
        value = value.strip()   # Remove leading or trailing spaces
        # Tidy paragraphs which should be indicated with "\n  ".
        value = re.sub(r"[ ]+\n", "\n", value)
        value = re.sub(r"\n\s+", "\n  ", value)
        # Newline with no following space is removed, so treated as just a
        # space in paragraph.
        value = re.sub(r"(\S)\n(\S)", "\g<1> \g<2>", value)
        # Tab->space, multiple spaces->space.
        value = re.sub(r"\t", " ", value)
        value = re.sub(r"(?<!\n)[ ]{2,}", " ", value)
        # Remove tex return (\\) at end of line or end of abstract.
        value = re.sub(r"\s*\\\\(\n|$)", "\g<1>", value)
        # Remove lone period.
        value = re.sub(r"\n\.\n", "\n", value)
        value = re.sub(r"\n\.$", "", value)
        return value


@dataclass
class SetDOI(Event):
    """Update the external DOI of a submission."""

    NAME = "add a DOI"
    NAMED = "DOI added"

    def __hash__(self):
        """Use event ID as object hash."""
        return hash(self.event_id)

    doi: str = field(default='')

    def __post_init__(self):
        """Perform some light cleanup on the provided value."""
        self.doi = self.cleanup(self.doi)

    def validate(self, submission: Submission) -> None:
        """Validate the DOI value."""
        if submission.status == Submission.SUBMITTED \
                and not submission.published:
            raise InvalidEvent(self, 'Cannot edit a finalized submission')
        if not self.doi:    # Can be blank.
            return
        for value in re.split('[;,]', self.doi):
            if not self._valid_doi(value.strip()):
                raise InvalidEvent(self, f"Invalid DOI: {value}")

    def project(self, submission: Submission) -> Submission:
        """Update the doi on a :class:`.Submission`."""
        submission.metadata.doi = self.doi
        return submission

    def _valid_doi(self, value: str) -> bool:
        if re.match(r"^10\.\d{4,5}\/\S+$", value):
            return True
        return False

    @staticmethod
    def cleanup(value: str) -> str:
        """Perform some light tidying on the title."""
        value = re.sub(r"\s+", " ", value).strip()        # Single spaces only.
        return value


@dataclass
class SetMSCClassification(Event):
    """Update the MSC classification codes of a submission."""

    NAME = "update MSC classification"
    NAMED = "MSC classification updated"

    def __hash__(self):
        """Use event ID as object hash."""
        return hash(self.event_id)

    msc_class: str = field(default='')

    MAX_LENGTH = 160

    def __post_init__(self):
        """Perform some light cleanup on the provided value."""
        self.msc_class = self.cleanup(self.msc_class)

    def validate(self, submission: Submission) -> None:
        """Validate the MSC classification value."""
        validators.submission_is_not_finalized(self, submission)
        if not self.msc_class:    # Blank values are OK.
            return

    def project(self, submission: Submission) -> Submission:
        """Update the MSC classification on a :class:`.Submission`."""
        submission.metadata.msc_class = self.msc_class
        return submission

    @staticmethod
    def cleanup(value: str) -> str:
        """Perform some light fixes on the MSC classification value."""
        value = re.sub(r"\s+", " ", value).strip()
        value = re.sub(r"\s*\.[\s.]*$", "", value)
        value = value.replace(";", ",")     # No semicolons, should be comma.
        value = re.sub(r"\s*,\s*", ", ", value)     # Want: comma, space.
        value = re.sub(r"^MSC([\s:\-]{0,4}(classification|class|number))?"
                       r"([\s:\-]{0,4}\(?2000\)?)?[\s:\-]*",
                       "", value, flags=re.I)
        return value


@dataclass
class SetACMClassification(Event):
    """Update the ACM classification codes of a submission."""

    NAME = "update ACM classification"
    NAMED = "ACM classification updated"

    def __hash__(self):
        """Use event ID as object hash."""
        return hash(self.event_id)

    acm_class: str = field(default='')
    """E.g. F.2.2; I.2.7"""

    MAX_LENGTH = 160

    def __post_init__(self):
        """Perform some light cleanup on the provided value."""
        self.acm_class = self.cleanup(self.acm_class)

    def validate(self, submission: Submission) -> None:
        """Validate the ACM classification value."""
        validators.submission_is_not_finalized(self, submission)
        if not self.acm_class:    # Blank values are OK.
            return
        self._valid_acm_class(submission)

    def project(self, submission: Submission) -> Submission:
        """Update the ACM classification on a :class:`.Submission`."""
        submission.metadata.acm_class = self.acm_class
        return submission

    def _valid_acm_class(self, submission: Submission) -> None:
        """Check that the value is a valid ACM class."""
        ptn = r"^[A-K]\.[0-9m](\.(\d{1,2}|m)(\.[a-o])?)?$"
        for acm_class in self.acm_class.split(';'):
            if not re.match(ptn, acm_class.strip()):
                raise InvalidEvent(self, f"Not a valid ACM class: {acm_class}")

    @staticmethod
    def cleanup(value: str) -> str:
        """Perform light cleanup."""
        value = re.sub(r"\s+", " ", value).strip()
        value = re.sub(r"\s*\.[\s.]*$", "", value)
        value = re.sub(r"^ACM-class:\s+", "", value, flags=re.I)
        value = value.replace(",", ";")
        _value = []
        for v in value.split(';'):
            v = v.strip().upper().rstrip('.')
            v = re.sub(r"^([A-K])(\d)", "\g<1>.\g<2>", v)
            v = re.sub(r"M$", "m", v)
            _value.append(v)
        value = "; ".join(_value)
        return value


@dataclass
class SetJournalReference(Event):
    """Update the journal reference of a submission."""

    NAME = "add a journal reference"
    NAMED = "journal reference added"

    def __hash__(self):
        """Use event ID as object hash."""
        return hash(self.event_id)

    journal_ref: str = field(default='')

    def __post_init__(self):
        """Perform some light cleanup on the provided value."""
        self.journal_ref = self.cleanup(self.journal_ref)

    def validate(self, submission: Submission) -> None:
        """Validate the journal reference value."""
        if not self.journal_ref:    # Blank values are OK.
            return
        self._no_disallowed_words(submission)
        self._contains_valid_year(submission)

    def project(self, submission: Submission) -> Submission:
        """Update the journal reference on a :class:`.Submission`."""
        submission.metadata.journal_ref = self.journal_ref
        return submission

    def _no_disallowed_words(self, submission: Submission) -> None:
        """Certain words are not permitted."""
        for word in ['submit', 'in press', 'appear', 'accept', 'to be publ']:
            if word in self.journal_ref.lower():
                raise InvalidEvent(self,
                                   f"The word '{word}' should appear in the"
                                   f" comments, not the Journal ref")

    def _contains_valid_year(self, submission: Submission) -> None:
        """Must contain a valid year."""
        if not re.search(r"(\A|\D)(19|20)\d\d(\D|\Z)", self.journal_ref):
            raise InvalidEvent(self, "Journal reference must include a year")

    @staticmethod
    def cleanup(value: str) -> str:
        """Perform light cleanup."""
        value = value.replace('PHYSICAL REVIEW LETTERS',
                              'Physical Review Letters')
        value = value.replace('PHYSICAL REVIEW', 'Physical Review')
        value = value.replace('OPTICS LETTERS', 'Optics Letters')
        return value


@dataclass
class SetReportNumber(Event):
    """Update the report number of a submission."""

    NAME = "update report number"
    NAMED = "report number updated"

    def __hash__(self):
        """Use event ID as object hash."""
        return hash(self.event_id)

    report_num: str = field(default='')

    def __post_init__(self):
        """Perform some light cleanup on the provided value."""
        self.report_num = self.cleanup(self.report_num)

    def validate(self, submission: Submission) -> None:
        """Validate the report number value."""
        if not self.report_num:    # Blank values are OK.
            return
        if not re.search(r"\d\d", self.report_num):
            raise InvalidEvent(self, "Report number must contain two"
                                     " consecutive digits")

    def project(self, submission: Submission) -> Submission:
        """Update the report number on a :class:`.Submission`."""
        submission.metadata.report_num = self.report_num
        return submission

    @staticmethod
    def cleanup(value: str) -> str:
        """Light cleanup on report number value."""
        value = re.sub(r"\s+", " ", value).strip()
        value = re.sub(r"\s*\.[\s.]*$", "", value)
        return value


@dataclass
class SetComments(Event):
    """Update the comments of a submission."""

    NAME = "update comments"
    NAMED = "comments updated"

    def __hash__(self):
        """Use event ID as object hash."""
        return hash(self.event_id)

    comments: str = field(default='')

    MAX_LENGTH = 400

    def __post_init__(self):
        """Perform some light cleanup on the provided value."""
        self.comments = self.cleanup(self.comments)

    def validate(self, submission: Submission) -> None:
        """Validate the comments value."""
        validators.submission_is_not_finalized(self, submission)
        if not self.comments:    # Blank values are OK.
            return
        if len(self.comments) > self.MAX_LENGTH:
            raise InvalidEvent(self, f"Comments must be no more than"
                                     f" {self.MAX_LENGTH} characters long")

    def project(self, submission: Submission) -> Submission:
        """Update the comments on a :class:`.Submission`."""
        submission.metadata.comments = self.comments
        return submission

    @staticmethod
    def cleanup(value: str) -> str:
        """Light cleanup on comment value."""
        value = re.sub(r"\s+", " ", value).strip()
        value = re.sub(r"\s*\.[\s.]*$", "", value)
        return value


@dataclass
class SetAuthors(Event):
    """Update the authors on a :class:`.Submission`."""

    NAME = "update authors"
    NAMED = "authors updated"

    def __hash__(self):
        """Use event ID as object hash."""
        return hash(self.event_id)

    authors: List[Author] = field(default_factory=list)
    authors_display: Optional[str] = field(default=None)
    """The authors string may be provided."""

    def __post_init__(self):
        """Autogenerate and/or clean display names."""
        if not self.authors_display:
            self.authors_display = self._canonical_author_string()
        self.authors_display = self.cleanup(self.authors_display)

    def validate(self, submission: Submission) -> None:
        """May not apply to a finalized submission."""
        validators.submission_is_not_finalized(self, submission)
        self._does_not_contain_et_al()

    def _canonical_author_string(self) -> str:
        """Canonical representation of authors, using display names."""
        return ", ".join([au.display for au in self.authors])

    @staticmethod
    def cleanup(s: str) -> str:
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
    def from_dict(cls, **data) -> 'SetAuthors':
        """Override the default ``from_dict`` constructor to handle authors."""
        if 'authors' not in data:
            raise ValueError('Missing authors')
        data['authors'] = [Author(**au) for au in data['authors']]
        return cls(**data)


@dataclass
class SetUploadPackage(Event):
    """Set the upload workspace for this submission."""

    NAME = "set the upload package"
    NAMED = "upload package set"

    def __hash__(self):
        """Use event ID as object hash."""
        return hash(self.event_id)

    identifier: str = field(default_factory=str)
    format: str = field(default_factory=str)
    checksum: str = field(default_factory=str)
    size: int = field(default=0)

    ALLOWED_FORMATS = [
        'pdftex', 'tex', 'pdf', 'ps', 'html', 'invalid', 'withdrawn'
    ]

    def validate(self, submission: Submission) -> None:
        """Validate data for :class:`.SetUploadPackage`."""
        validators.submission_is_not_finalized(self, submission)

        if not self.identifier:
            raise InvalidEvent(self, 'Missing upload ID')

        if self.format and self.format not in self.ALLOWED_FORMATS:
            raise InvalidEvent(self, f'Format {self.format} not allowed')

    def project(self, submission: Submission) -> Submission:
        """Replace :class:`.SubmissionContent` metadata on the submission."""
        submission.source_content = SubmissionContent(
            format=self.format,
            checksum=self.checksum,
            identifier=self.identifier,
            size=self.size
        )
        submission.submitter_confirmed_preview = False
        return submission


@dataclass
class UnsetUploadPackage(Event):
    """Unset the upload workspace for this submission."""

    def validate(self, submission: Submission) -> None:
        """Validate data for :class:`.UnsetUploadPackage`."""
        validators.submission_is_not_finalized(self, submission)

    def project(self, submission: Submission) -> Submission:
        """Set :prop:`Submission.source_content` to None."""
        submission.source_content = None
        submission.submitter_confirmed_preview = False
        return submission


@dataclass
class ConfirmPreview(Event):
    """Confirm that the paper and abstract previews are acceptable."""

    NAME = "approve submission preview"
    NAMED = "submission preview approved"

    def __hash__(self):
        """Use event ID as object hash."""
        return hash(self.event_id)

    def validate(self, submission: Submission) -> None:
        """Validate data for :class:`.ConfirmPreview`."""
        validators.submission_is_not_finalized(self, submission)

    def project(self, submission: Submission) -> Submission:
        """Set :prop:`Submission.return submission`."""
        submission.submitter_confirmed_preview = True
        return submission


@dataclass(init=False)
class FinalizeSubmission(Event):
    """Send the submission to the queue for announcement."""

    NAME = "finalize submission for announcement"
    NAMED = "submission finalized"

    def __hash__(self):
        """Use event ID as object hash."""
        return hash(self.event_id)

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
            raise InvalidEvent(self, "Submission must be active")
        self._required_fields_are_complete(submission)

    def project(self, submission: Submission) -> Submission:
        """Set :prop:`Submission.finalized`."""
        submission.status = Submission.SUBMITTED
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

    NAME = "re-open submission for modification"
    NAMED = "submission re-opened for modification"

    def __hash__(self):
        """Use event ID as object hash."""
        return hash(self.event_id)

    def validate(self, submission: Submission) -> None:
        """Validate the unfinalize action."""
        self._must_be_finalized(submission)
        if submission.published:
            raise InvalidEvent(self, "Cannot unfinalize an announced paper")

    def _must_be_finalized(self, submission: Submission) -> None:
        """May only unfinalize a finalized submission."""
        if not submission.finalized:
            raise InvalidEvent(self, "Submission is not finalized")

    def project(self, submission: Submission) -> Submission:
        """Set :prop:`Submission.finalized`."""
        submission.status = Submission.WORKING
        return submission


@dataclass
class Publish(Event):
    """Publish the current version of the submission."""

    NAME = "publish submission"
    NAMED = "submission published"

    def __hash__(self):
        """Use event ID as object hash."""
        return hash(self.event_id)

    arxiv_id: Optional[str] = None

    def validate(self, submission: Submission) -> None:
        """Make sure that we have a valid arXiv ID."""
        # TODO: When we're using this to perform publish in NG, we will want to
        # re-enable this step.
        #
        # if not submission.status == Submission.SUBMITTED:
        #     raise InvalidEvent(self,
        #                        "Can't publish in state %s" % submission.status)
        # if self.arxiv_id is None:
        #     raise InvalidEvent(self, "Must provide an arXiv ID.")
        # try:
        #     identifier.parse_arxiv_id(self.arxiv_id)
        # except ValueError:
        #     raise InvalidEvent(self, "Not a valid arXiv ID.")

    def project(self, submission: Submission) -> Submission:
        """Set the arXiv ID on the submission."""
        submission.arxiv_id = self.arxiv_id
        submission.status = Submission.PUBLISHED
        submission.versions.append(copy.deepcopy(submission))
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
        data['created'] = datetime.now(UTC)
    if event_type in EVENT_TYPES:
        klass = EVENT_TYPES[event_type]
        if hasattr(klass, 'from_dict'):
            return klass.from_dict(**data)
        return EVENT_TYPES[event_type](**data)
    raise RuntimeError('Unknown event type: %s' % event_type)
