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
  the passed :class:`.domain.submission.Submission` instance.
  The projection *must not* generate side-effects, because it will be called
  any time we are generating the state of a submission. If you need to
  generate a side-effect, see :ref:`callbacks`\.
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

.. _callbacks:

Registering event callbacks
===========================

The base :class:`Event` provides support for callbacks that are executed when
an event instance is committed. To attach a callback to an event type, use the
:func:`Event.bind` decorator. For example:

.. code-block:: python

   @SetTitle.bind()
   def do_this_when_a_title_is_set(event, before, after, agent):
       ...
       return []


Callbacks must have the signature ``(event: Event, before: Submission,
after: Submission, creator: Agent) -> Iterable[Event]``. ``event`` is the
event instance being committed that triggered the callback. ``before`` and
``after`` are the states of the submission before and after the event was
applied, respectively. ``agent`` is the agent responsible for any subsequent
events created by the callback, and should be used for that purpose.

The callback should not concern itself with persistence; that is handled by
:func:`Event.commit`. Any mutations of submission should be made by returning
the appropriate command/event instances.

The circumstances under which the callback is executed can be controlled by
passing a condition callable to the decorator. This should have the signature
``(event: Event, before: Submission, after: Submission, creator: Agent) ->
bool``; if it returns ``True``, the  callback will be executed. For example:

.. code-block:: python

   @SetTitle.bind(condition=lambda e, b, a, c: e.title == 'foo')
   def do_this_when_a_title_is_set_to_foo(event, before, after, agent):
       ...
       return []


When do things actually happen?
-------------------------------
Callbacks are triggered when the :func:`.commit` method is called,
usually by :func:`.core.save`. Normally, any event instances returned
by the callback are applied and committed right away, in order.

Setting :mod:`.config.ENABLE_CALLBACKS=0` will disable callbacks
entirely.

"""

import hashlib
import re
import copy
from datetime import datetime
from collections import defaultdict
from functools import wraps
from pytz import UTC
from typing import Optional, TypeVar, List, Tuple, Any, Dict, Union, Iterable,\
    Callable, ClassVar, Mapping
from urllib.parse import urlparse
from dataclasses import field, asdict
from .util import dataclass
import bleach

from arxiv.util import schema
from arxiv import taxonomy
from arxiv import identifier as arxiv_identifier
from arxiv.base import logging
from arxiv.base.globals import get_application_config

from ..agent import Agent, System, agent_factory
from ..submission import Submission, SubmissionMetadata, Author, \
    Classification, License, Delegation,  \
    SubmissionContent, WithdrawalRequest, CrossListClassificationRequest
from ..annotation import Comment, Feature, ClassifierResults, \
    ClassifierResult

from ...exceptions import InvalidEvent
from ..util import get_tzaware_utc_now
from .base import Event, event_factory, EventType
from .request import RequestCrossList, RequestWithdrawal, ApplyRequest, \
    RejectRequest, ApproveRequest, CancelRequest
from . import validators
from .proposal import AddProposal, RejectProposal, AcceptProposal
from .flag import AddMetadataFlag, AddUserFlag, AddContentFlag, RemoveFlag, \
    AddHold, RemoveHold
from .process import AddProcessStatus

logger = logging.getLogger(__name__)


# Events related to the creation of a new submission.
#
# These are largely the domain of the metadata API, and the submission UI.


@dataclass()
class CreateSubmission(Event):
    """Creation of a new :class:`.domain.submission.Submission`."""

    NAME = "create submission"
    NAMED = "submission created"

    def validate(self, *args, **kwargs) -> None:
        """Validate creation of a submission."""
        return

    def project(self, submission: None = None) -> Submission:
        """Create a new :class:`.domain.submission.Submission`."""
        return Submission(creator=self.creator, created=self.created,
                          owner=self.creator, proxy=self.proxy,
                          client=self.client)


@dataclass(init=False)
class CreateSubmissionVersion(Event):
    """
    Creates a new version of a submission.

    Takes the submission back to "working" state; the user or client may make
    additional changes before finalizing the submission.
    """

    NAME = "create a new version"
    NAMED = "new version created"

    def validate(self, submission: Submission) -> None:
        """Only applies to announced submissions."""
        if not submission.is_announced:
            raise InvalidEvent(self, "Must already be announced")
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
        return submission


@dataclass(init=False)
class Rollback(Event):
    """Roll back to the most recent announced version, or delete."""

    NAME = "roll back or delete"
    NAMED = "rolled back or deleted"

    def validate(self, submission: Submission) -> None:
        """Only applies to submissions in an unannounced state."""
        if submission.is_announced:
            raise InvalidEvent(self, "Cannot already be announced")
        elif submission.version > 1 and not submission.versions:
            raise InvalidEvent(self, "No announced version to which to revert")

    def project(self, submission: Submission) -> Submission:
        """Decrement the version number, and reset fields."""
        if submission.version == 1:
            submission.status = Submission.DELETED
            return submission
        submission.version -= 1
        target = submission.versions[-1]
        # Return these to last announced state.
        submission.status = target.status
        submission.source_content = target.source_content
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

    def validate(self, submission: Submission) -> None:
        """Cannot apply to a finalized submission."""
        validators.submission_is_not_finalized(self, submission)

    def project(self, submission: Submission) -> Submission:
        """Update :attr:`.Submission.submitter_contact_verified`."""
        submission.submitter_contact_verified = True
        return submission


@dataclass()
class ConfirmAuthorship(Event):
    """The submitting user asserts whether they are an author of the paper."""

    NAME = "confirm that submitter is an author"
    NAMED = "submitter authorship status confirmed"

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

    def validate(self, submission: Submission) -> None:
        """Cannot apply to a finalized submission."""
        validators.submission_is_not_finalized(self, submission)

    def project(self, submission: Submission) -> Submission:
        """Set the policy flag on the submission."""
        submission.submitter_accepts_policy = True
        return submission


@dataclass()
class SetPrimaryClassification(Event):
    """Update the primary classification of a submission."""

    NAME = "set primary classification"
    NAMED = "primary classification set"

    category: Optional[taxonomy.Category] = None

    def validate(self, submission: Submission) -> None:
        """Validate the primary classification category."""
        validators.must_be_a_valid_category(self, self.category, submission)
        self._creator_must_be_endorsed(submission)
        self._must_be_unannounced(submission)
        validators.submission_is_not_finalized(self, submission)
        validators.cannot_be_secondary(self, self.category, submission)

    def _must_be_unannounced(self, submission: Submission) -> None:
        """Can only be set on the first version before publication."""
        if submission.arxiv_id is not None or submission.version > 1:
            raise InvalidEvent(self, "Can only be set on the first version,"
                                     " before publication.")

    def _creator_must_be_endorsed(self, submission: Submission) -> None:
        """Creator of this event must be endorsed for the category."""
        if isinstance(self.creator, System):
            return
        try:
            archive = taxonomy.CATEGORIES[self.category]['in_archive']
        except KeyError:
            archive = self.category
        if self.category not in self.creator.endorsements \
                and f'{archive}.*' not in self.creator.endorsements \
                and '*.*' not in self.creator.endorsements:
            raise InvalidEvent(self, f"Creator is not endorsed for"
                                     f" {self.category}.")

    def project(self, submission: Submission) -> Submission:
        """Set :attr:`.domain.Submission.primary_classification`."""
        clsn = Classification(category=self.category)
        submission.primary_classification = clsn
        return submission

    def __post_init__(self):
        """Ensure that we have an :class:`arxiv.taxonomy.Category`."""
        super(SetPrimaryClassification, self).__post_init__()
        if self.category and not isinstance(self.category, taxonomy.Category):
            self.category = taxonomy.Category(self.category)


@dataclass()
class AddSecondaryClassification(Event):
    """Add a secondary :class:`.Classification` to a submission."""

    NAME = "add cross-list classification"
    NAMED = "cross-list classification added"

    category: Optional[taxonomy.Category] = field(default=None)

    def validate(self, submission: Submission) -> None:
        """Validate the secondary classification category to add."""
        validators.must_be_a_valid_category(self, self.category, submission)
        validators.cannot_be_primary(self, self.category, submission)
        validators.cannot_be_secondary(self, self.category, submission)

    def project(self, submission: Submission) -> Submission:
        """Add a :class:`.Classification` as a secondary classification."""
        classification = Classification(category=self.category)
        submission.secondary_classification.append(classification)
        return submission

    def __post_init__(self):
        """Ensure that we have an :class:`arxiv.taxonomy.Category`."""
        super(AddSecondaryClassification, self).__post_init__()
        if self.category and not isinstance(self.category, taxonomy.Category):
            self.category = taxonomy.Category(self.category)


@dataclass()
class RemoveSecondaryClassification(Event):
    """Remove secondary :class:`.Classification` from submission."""

    NAME = "remove cross-list classification"
    NAMED = "cross-list classification removed"

    category: Optional[str] = field(default=None)

    def validate(self, submission: Submission) -> None:
        """Validate the secondary classification category to remove."""
        validators.must_be_a_valid_category(self, self.category, submission)
        self._must_already_be_present(submission)
        validators.submission_is_not_finalized(self, submission)

    def project(self, submission: Submission) -> Submission:
        """Remove from :attr:`.Submission.secondary_classification`."""
        submission.secondary_classification = [
            classn for classn in submission.secondary_classification
            if not classn.category == self.category
        ]
        return submission

    def _must_already_be_present(self, submission: Submission) -> None:
        """One cannot remove a secondary that is not actually set."""
        if self.category not in submission.secondary_categories:
            raise InvalidEvent(self, 'No such category on submission')


@dataclass()
class SetLicense(Event):
    """The submitter has selected a license for their submission."""

    NAME = "select distribution license"
    NAMED = "distribution license selected"

    license_name: Optional[str] = field(default=None)
    license_uri: Optional[str] = field(default=None)

    def validate(self, submission: Submission) -> None:
        """Validate the selected license."""
        validators.submission_is_not_finalized(self, submission)

    def project(self, submission: Submission) -> Submission:
        """Set :attr:`.domain.Submission.license`."""
        submission.license = License(
            name=self.license_name,
            uri=self.license_uri
        )
        return submission


@dataclass()
class SetTitle(Event):
    """Update the title of a submission."""

    NAME = "update title"
    NAMED = "title updated"

    title: str = field(default='')

    MIN_LENGTH = 5
    MAX_LENGTH = 240
    ALLOWED_HTML = ["br", "sup", "sub", "hr", "em", "strong", "h"]

    def __post_init__(self):
        """Perform some light cleanup on the provided value."""
        super(SetTitle, self).__post_init__()
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
        """Update the title on a :class:`.domain.submission.Submission`."""
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


@dataclass()
class SetAbstract(Event):
    """Update the abstract of a submission."""

    NAME = "update abstract"
    NAMED = "abstract updated"

    abstract: str = field(default='')

    MIN_LENGTH = 20
    MAX_LENGTH = 1920

    def __post_init__(self):
        """Perform some light cleanup on the provided value."""
        super(SetAbstract, self).__post_init__()
        self.abstract = self.cleanup(self.abstract)

    def validate(self, submission: Submission) -> None:
        """Validate the abstract value."""
        validators.submission_is_not_finalized(self, submission)
        self._acceptable_length(submission)

    def project(self, submission: Submission) -> Submission:
        """Update the abstract on a :class:`.domain.submission.Submission`."""
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


@dataclass()
class SetDOI(Event):
    """Update the external DOI of a submission."""

    NAME = "add a DOI"
    NAMED = "DOI added"

    doi: str = field(default='')

    def __post_init__(self):
        """Perform some light cleanup on the provided value."""
        super(SetDOI, self).__post_init__()
        self.doi = self.cleanup(self.doi)

    def validate(self, submission: Submission) -> None:
        """Validate the DOI value."""
        if submission.status == Submission.SUBMITTED \
                and not submission.is_announced:
            raise InvalidEvent(self, 'Cannot edit a finalized submission')
        if not self.doi:    # Can be blank.
            return
        for value in re.split('[;,]', self.doi):
            if not self._valid_doi(value.strip()):
                raise InvalidEvent(self, f"Invalid DOI: {value}")

    def project(self, submission: Submission) -> Submission:
        """Update the doi on a :class:`.domain.submission.Submission`."""
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


@dataclass()
class SetMSCClassification(Event):
    """Update the MSC classification codes of a submission."""

    NAME = "update MSC classification"
    NAMED = "MSC classification updated"

    msc_class: str = field(default='')

    MAX_LENGTH = 160

    def __post_init__(self):
        """Perform some light cleanup on the provided value."""
        super(SetMSCClassification, self).__post_init__()
        self.msc_class = self.cleanup(self.msc_class)

    def validate(self, submission: Submission) -> None:
        """Validate the MSC classification value."""
        validators.submission_is_not_finalized(self, submission)
        if not self.msc_class:    # Blank values are OK.
            return

    def project(self, submission: Submission) -> Submission:
        """Update the MSC classification on a :class:`.domain.submission.Submission`."""
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


@dataclass()
class SetACMClassification(Event):
    """Update the ACM classification codes of a submission."""

    NAME = "update ACM classification"
    NAMED = "ACM classification updated"

    acm_class: str = field(default='')
    """E.g. F.2.2; I.2.7"""

    MAX_LENGTH = 160

    def __post_init__(self):
        """Perform some light cleanup on the provided value."""
        super(SetACMClassification, self).__post_init__()
        self.acm_class = self.cleanup(self.acm_class)

    def validate(self, submission: Submission) -> None:
        """Validate the ACM classification value."""
        validators.submission_is_not_finalized(self, submission)
        if not self.acm_class:    # Blank values are OK.
            return
        self._valid_acm_class(submission)

    def project(self, submission: Submission) -> Submission:
        """Update the ACM classification on a :class:`.domain.submission.Submission`."""
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


@dataclass()
class SetJournalReference(Event):
    """Update the journal reference of a submission."""

    NAME = "add a journal reference"
    NAMED = "journal reference added"

    journal_ref: str = field(default='')

    def __post_init__(self):
        """Perform some light cleanup on the provided value."""
        super(SetJournalReference, self).__post_init__()
        self.journal_ref = self.cleanup(self.journal_ref)

    def validate(self, submission: Submission) -> None:
        """Validate the journal reference value."""
        if not self.journal_ref:    # Blank values are OK.
            return
        self._no_disallowed_words(submission)
        self._contains_valid_year(submission)

    def project(self, submission: Submission) -> Submission:
        """Update the journal reference on a :class:`.domain.submission.Submission`."""
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


@dataclass()
class SetReportNumber(Event):
    """Update the report number of a submission."""

    NAME = "update report number"
    NAMED = "report number updated"

    report_num: str = field(default='')

    def __post_init__(self):
        """Perform some light cleanup on the provided value."""
        super(SetReportNumber, self).__post_init__()
        self.report_num = self.cleanup(self.report_num)

    def validate(self, submission: Submission) -> None:
        """Validate the report number value."""
        if not self.report_num:    # Blank values are OK.
            return
        if not re.search(r"\d\d", self.report_num):
            raise InvalidEvent(self, "Report number must contain two"
                                     " consecutive digits")

    def project(self, submission: Submission) -> Submission:
        """Set report number on a :class:`.domain.submission.Submission`."""
        submission.metadata.report_num = self.report_num
        return submission

    @staticmethod
    def cleanup(value: str) -> str:
        """Light cleanup on report number value."""
        value = re.sub(r"\s+", " ", value).strip()
        value = re.sub(r"\s*\.[\s.]*$", "", value)
        return value


@dataclass()
class SetComments(Event):
    """Update the comments of a submission."""

    NAME = "update comments"
    NAMED = "comments updated"

    comments: str = field(default='')

    MAX_LENGTH = 400

    def __post_init__(self):
        """Perform some light cleanup on the provided value."""
        super(SetComments, self).__post_init__()
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
        """Update the comments on a :class:`.domain.submission.Submission`."""
        submission.metadata.comments = self.comments
        return submission

    @staticmethod
    def cleanup(value: str) -> str:
        """Light cleanup on comment value."""
        value = re.sub(r"\s+", " ", value).strip()
        value = re.sub(r"\s*\.[\s.]*$", "", value)
        return value


@dataclass()
class SetAuthors(Event):
    """Update the authors on a :class:`.domain.submission.Submission`."""

    NAME = "update authors"
    NAMED = "authors updated"

    authors: List[Author] = field(default_factory=list)
    authors_display: Optional[str] = field(default=None)
    """The authors string may be provided."""

    def __post_init__(self):
        """Autogenerate and/or clean display names."""
        super(SetAuthors, self).__post_init__()
        self.authors = [Author(**a) if type(a) is dict else a
                        for a in self.authors]
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
        s = re.sub(r"(\w)\(", r"\g<1> (", s)
        # Add spaces between closing parenthesis and word.
        s = re.sub(r"\)(\w)", r") \g<1>", s)
        # Change capitalized or uppercase `And` to `and`.
        s = re.sub(r"\bA(?i:ND)\b", "and", s)
        return s.strip()   # Removing leading and trailing whitespace.

    def _does_not_contain_et_al(self) -> None:
        """The authors display value should not contain `et al`."""
        if self.authors_display and \
                re.search(r"et al\.?($|\s*\()", self.authors_display):
            raise InvalidEvent(self, "Authors should not contain et al.")

    def project(self, submission: Submission) -> Submission:
        """Replace :attr:`.Submission.metadata.authors`."""
        submission.metadata.authors = self.authors
        submission.metadata.authors_display = self.authors_display
        return submission


@dataclass()
class SetUploadPackage(Event):
    """Set the upload workspace for this submission."""

    NAME = "set the upload package"
    NAMED = "upload package set"

    identifier: str = field(default_factory=str)
    checksum: str = field(default_factory=str)
    uncompressed_size: int = field(default=0)
    compressed_size: int = field(default=0)
    source_format: SubmissionContent.Format = \
        field(default=SubmissionContent.Format.UNKNOWN)

    def __post_init__(self) -> None:
        """Make sure that `source_format` is an enum instance."""
        super(SetUploadPackage, self).__post_init__()
        if type(self.source_format) is str:
            self.source_format = SubmissionContent.Format(self.source_format)

    def validate(self, submission: Submission) -> None:
        """Validate data for :class:`.SetUploadPackage`."""
        validators.submission_is_not_finalized(self, submission)

        if not self.identifier:
            raise InvalidEvent(self, 'Missing upload ID')

    def project(self, submission: Submission) -> Submission:
        """Replace :class:`.SubmissionContent` metadata on the submission."""
        submission.source_content = SubmissionContent(
            checksum=self.checksum,
            identifier=self.identifier,
            uncompressed_size=self.uncompressed_size,
            compressed_size=self.compressed_size,
            source_format=self.source_format,
        )
        submission.submitter_confirmed_preview = False
        return submission


@dataclass()
class UpdateUploadPackage(Event):
    """Update the upload workspace on this submission."""

    NAME = "update the upload package"
    NAMED = "upload package updated"

    checksum: str = field(default_factory=str)
    uncompressed_size: int = field(default=0)
    compressed_size: int = field(default=0)
    source_format: SubmissionContent.Format = \
        field(default=SubmissionContent.Format.UNKNOWN)

    def __post_init__(self) -> None:
        """Make sure that `source_format` is an enum instance."""
        super(UpdateUploadPackage, self).__post_init__()
        if type(self.source_format) is str:
            self.source_format = SubmissionContent.Format(self.source_format)

    def validate(self, submission: Submission) -> None:
        """Validate data for :class:`.SetUploadPackage`."""
        validators.submission_is_not_finalized(self, submission)

    def project(self, submission: Submission) -> Submission:
        """Replace :class:`.SubmissionContent` metadata on the submission."""
        submission.source_content.source_format = self.source_format
        submission.source_content.checksum = self.checksum
        submission.source_content.uncompressed_size = self.uncompressed_size
        submission.source_content.compressed_size = self.compressed_size
        submission.submitter_confirmed_preview = False
        return submission


@dataclass()
class UnsetUploadPackage(Event):
    """Unset the upload workspace for this submission."""

    NAME = "unset the upload package"
    NAMED = "upload package unset"

    def validate(self, submission: Submission) -> None:
        """Validate data for :class:`.UnsetUploadPackage`."""
        validators.submission_is_not_finalized(self, submission)

    def project(self, submission: Submission) -> Submission:
        """Set :attr:`Submission.source_content` to None."""
        submission.source_content = None
        submission.submitter_confirmed_preview = False
        return submission


@dataclass()
class ConfirmCompiledPreview(Event):
    """Confirm that the submitter successfully compiled a preview."""

    NAME = "confirm submission preview is compiled"
    NAMED = "confirmed that submission preview was compiled"

    def validate(self, submission: Submission) -> None:
        return

    def project(self, submission: Submission) -> Submission:
        """Set :attr:`Submission.submitter_compiled_preview`."""
        submission.submitter_compiled_preview = True
        return submission


@dataclass()
class UnConfirmCompiledPreview(Event):
    """Unconfirm that the submitter successfully compiled a preview."""

    NAME = "unconfirm submission preview is compiled"
    NAMED = "unconfirmed that submission preview was compiled"

    def validate(self, submission: Submission) -> None:
        return

    def project(self, submission: Submission) -> Submission:
        """Set :attr:`Submission.submitter_compiled_preview`."""
        submission.submitter_compiled_preview = False
        return submission


@dataclass()
class ConfirmPreview(Event):
    """Confirm that the paper and abstract previews are acceptable."""

    NAME = "approve submission preview"
    NAMED = "submission preview approved"

    def validate(self, submission: Submission) -> None:
        """Validate data for :class:`.ConfirmPreview`."""
        validators.submission_is_not_finalized(self, submission)

    def project(self, submission: Submission) -> Submission:
        """Set :attr:`Submission.submitter_confirmed_preview`."""
        submission.submitter_confirmed_preview = True
        return submission


@dataclass(init=False)
class FinalizeSubmission(Event):
    """Send the submission to the queue for announcement."""

    NAME = "finalize submission for announcement"
    NAMED = "submission finalized"

    REQUIRED = [
        'creator', 'primary_classification', 'submitter_contact_verified',
        'submitter_accepts_policy', 'license', 'source_content', 'metadata',
    ]
    REQUIRED_METADATA = ['title', 'abstract', 'authors_display']

    def validate(self, submission: Submission) -> None:
        """Ensure that all required data/steps are complete."""
        if submission.is_finalized:
            raise InvalidEvent(self, "Submission already finalized")
        if not submission.is_active:
            raise InvalidEvent(self, "Submission must be active")
        self._required_fields_are_complete(submission)

    def project(self, submission: Submission) -> Submission:
        """Set :attr:`Submission.is_finalized`."""
        submission.status = Submission.SUBMITTED
        submission.submitted = datetime.now(UTC)
        return submission

    def _required_fields_are_complete(self, submission: Submission) -> None:
        """Verify that all required fields are complete."""
        for key in self.REQUIRED:
            if not getattr(submission, key):
                raise InvalidEvent(self, f"Missing {key}")
        for key in self.REQUIRED_METADATA:
            if not getattr(submission.metadata, key):
                raise InvalidEvent(self, f"Missing {key}")


@dataclass()
class UnFinalizeSubmission(Event):
    """Withdraw the submission from the queue for announcement."""

    NAME = "re-open submission for modification"
    NAMED = "submission re-opened for modification"

    def validate(self, submission: Submission) -> None:
        """Validate the unfinalize action."""
        self._must_be_finalized(submission)
        if submission.is_announced:
            raise InvalidEvent(self, "Cannot unfinalize an announced paper")

    def _must_be_finalized(self, submission: Submission) -> None:
        """May only unfinalize a finalized submission."""
        if not submission.is_finalized:
            raise InvalidEvent(self, "Submission is not finalized")

    def project(self, submission: Submission) -> Submission:
        """Set :attr:`Submission.is_finalized`."""
        submission.status = Submission.WORKING
        submission.submitted = None
        return submission


@dataclass()
class Announce(Event):
    """Announce the current version of the submission."""

    NAME = "publish submission"
    NAMED = "submission announced"

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
        #     arxiv_identifier.parse_arxiv_id(self.arxiv_id)
        # except ValueError:
        #     raise InvalidEvent(self, "Not a valid arXiv ID.")

    def project(self, submission: Submission) -> Submission:
        """Set the arXiv ID on the submission."""
        submission.arxiv_id = self.arxiv_id
        submission.status = Submission.ANNOUNCED
        submission.versions.append(copy.deepcopy(submission))
        return submission


# Moderation-related events.


# @dataclass()
# class CreateComment(Event):
#     """Creation of a :class:`.Comment` on a :class:`.domain.submission.Submission`."""
#
#     read_scope = 'submission:moderate'
#     write_scope = 'submission:moderate'
#
#     body: str = field(default_factory=str)
#     scope: str = 'private'
#
#     def validate(self, submission: Submission) -> None:
#         """The :attr:`.body` should be set."""
#         if not self.body:
#             raise ValueError('Comment body not set')
#
#     def project(self, submission: Submission) -> Submission:
#         """Create a new :class:`.Comment` and attach it to the submission."""
#         submission.comments[self.event_id] = Comment(
#             event_id=self.event_id,
#             creator=self.creator,
#             created=self.created,
#             proxy=self.proxy,
#             submission=submission,
#             body=self.body
#         )
#         return submission
#
#
# @dataclass()
# class DeleteComment(Event):
#     """Deletion of a :class:`.Comment` on a :class:`.domain.submission.Submission`."""
#
#     read_scope = 'submission:moderate'
#     write_scope = 'submission:moderate'
#
#     comment_id: str = field(default_factory=str)
#
#     def validate(self, submission: Submission) -> None:
#         """The :attr:`.comment_id` must present on the submission."""
#         if self.comment_id is None:
#             raise InvalidEvent(self, 'comment_id is required')
#         if not hasattr(submission, 'comments') or not submission.comments:
#             raise InvalidEvent(self, 'Cannot delete nonexistant comment')
#         if self.comment_id not in submission.comments:
#             raise InvalidEvent(self, 'Cannot delete nonexistant comment')
#
#     def project(self, submission: Submission) -> Submission:
#         """Remove the comment from the submission."""
#         del submission.comments[self.comment_id]
#         return submission
#
#
# @dataclass()
# class AddDelegate(Event):
#     """Owner delegates authority to another agent."""
#
#     delegate: Optional[Agent] = None
#
#     def validate(self, submission: Submission) -> None:
#         """The event creator must be the owner of the submission."""
#         if not self.creator == submission.owner:
#             raise InvalidEvent(self, 'Event creator must be submission owner')
#
#     def project(self, submission: Submission) -> Submission:
#         """Add the delegate to the submission."""
#         delegation = Delegation(
#             creator=self.creator,
#             delegate=self.delegate,
#             created=self.created
#         )
#         submission.delegations[delegation.delegation_id] = delegation
#         return submission
#
#
# @dataclass()
# class RemoveDelegate(Event):
#     """Owner revokes authority from another agent."""
#
#     delegation_id: str = field(default_factory=str)
#
#     def validate(self, submission: Submission) -> None:
#         """The event creator must be the owner of the submission."""
#         if not self.creator == submission.owner:
#             raise InvalidEvent(self, 'Event creator must be submission owner')
#
#     def project(self, submission: Submission) -> Submission:
#         """Remove the delegate from the submission."""
#         if self.delegation_id in submission.delegations:
#             del submission.delegations[self.delegation_id]
#         return submission


@dataclass()
class AddFeature(Event):
    """Add feature metadata to a submission."""

    NAME = "add feature metadata"
    NAMED = "feature metadata added"

    feature_type: Feature.Type = \
        field(default=Feature.Type.WORD_COUNT)
    feature_value: Union[float, int] = field(default=0)

    def validate(self, submission: Submission) -> None:
        """Verify that the feature type is a known value."""
        if self.feature_type not in Feature.Type:
            valid_types = ", ".join([ft.value for ft in Feature.Type])
            raise InvalidEvent(self, "Must be one of %s" % valid_types)

    def project(self, submission: Submission) -> Submission:
        """Add the annotation to the submission."""
        submission.annotations[self.event_id] = Feature(
            event_id=self.event_id,
            creator=self.creator,
            created=self.created,
            proxy=self.proxy,
            feature_type=self.feature_type,
            feature_value=self.feature_value
        )
        return submission


@dataclass()
class AddClassifierResults(Event):
    """Add the results of a classifier to a submission."""

    NAME = "add classifer results"
    NAMED = "classifier results added"

    classifier: ClassifierResults.Classifiers \
        = field(default=ClassifierResults.Classifiers.CLASSIC)
    results: List[ClassifierResult] = field(default_factory=list)

    def validate(self, submission: Submission) -> None:
        """Verify that the classifier is a known value."""
        if self.classifier not in ClassifierResults.Classifiers:
            valid = ", ".join([c.value for c in ClassifierResults.Classifiers])
            raise InvalidEvent(self, "Must be one of %s" % valid)

    def project(self, submission: Submission) -> Submission:
        """Add the annotation to the submission."""
        submission.annotations[self.event_id] = ClassifierResults(
            event_id=self.event_id,
            creator=self.creator,
            created=self.created,
            proxy=self.proxy,
            classifier=self.classifier,
            results=self.results
        )
        return submission


@dataclass()
class Reclassify(Event):
    """Reclassify a submission."""

    NAME = "reclassify submission"
    NAMED = "submission reclassified"

    category: Optional[taxonomy.Category] = None

    def validate(self, submission: Submission) -> None:
        """Validate the primary classification category."""
        validators.must_be_a_valid_category(self, self.category, submission)
        self._must_be_unannounced(submission)
        validators.cannot_be_secondary(self, self.category, submission)

    def _must_be_unannounced(self, submission: Submission) -> None:
        """Can only be set on the first version before publication."""
        if submission.arxiv_id is not None or submission.version > 1:
            raise InvalidEvent(self, "Can only be set on the first version,"
                                     " before publication.")

    def project(self, submission: Submission) -> Submission:
        """Set :attr:`.domain.Submission.primary_classification`."""
        clsn = Classification(category=self.category)
        submission.primary_classification = clsn
        return submission
