"""SQLAlchemy ORM classes for the classic database."""

import json
from typing import Optional
from datetime import datetime
from sqlalchemy import Column, Date, DateTime, Enum, ForeignKey, Text, text, \
    ForeignKeyConstraint, Index, Integer, SmallInteger, String, Table
from sqlalchemy.orm import relationship, joinedload, backref

from sqlalchemy.ext.declarative import declarative_base

from ... import domain

Base = declarative_base()


class Submission(Base):    # type: ignore
    """Represents an arXiv submission."""

    __tablename__ = 'arXiv_submissions'

    # Pre-moderation stages; these are tied to the classic submission UI.
    NEW = 0
    STARTED = 1
    FILES_ADDED = 2
    PROCESSED = 3
    METADATA_ADDED = 4
    SUBMITTED = 5
    STAGES = [NEW, STARTED, FILES_ADDED, PROCESSED, METADATA_ADDED, SUBMITTED]

    # Submission status; this describes where the submission is in the
    # publication workflow.
    NOT_SUBMITTED = 0   # Working.
    SUBMITTED = 1       # Enqueued for moderation, to be scheduled.
    ON_HOLD = 2
    UNUSED = 3
    NEXT_PUBLISH_DAY = 4
    """Scheduled for the next publication cycle."""
    PROCESSING = 5
    """Scheduled for today."""
    NEEDS_EMAIL = 6
    """Published, not yet announced."""

    PUBLISHED = 7
    DELETED_PUBLISHED = 27
    """Published and files expired."""

    PROCESSING_SUBMISSION = 8
    REMOVED = 9

    USER_DELETED = 10
    ERROR_STATE = 19
    """There was a problem validating the submission during publication."""

    DELETED_EXPIRED = 20
    """Was working but expired."""
    DELETED_ON_HOLD = 22
    DELETED_PROCESSING = 25

    DELETED_REMOVED = 29
    DELETED_USER = 30
    """User deleted and files expired."""

    DELETED = [
        USER_DELETED, DELETED_ON_HOLD, DELETED_PROCESSING,
        DELETED_REMOVED, DELETED_USER
    ]

    NEW_SUBMSSION = 'new'
    REPLACEMENT = 'rep'
    JOURNAL_REFERENCE = 'jref'
    WITHDRAWAL = 'dr'

    WITHDRAWN_FORMAT = 'withdrawn'

    # Map classic status to Submission domain status.
    STATUS_MAP = {
        NOT_SUBMITTED: domain.Submission.WORKING,
        SUBMITTED: domain.Submission.SUBMITTED,
        ON_HOLD: domain.Submission.ON_HOLD,
        NEXT_PUBLISH_DAY: domain.Submission.SCHEDULED,
        PROCESSING: domain.Submission.SCHEDULED,
        PROCESSING_SUBMISSION: domain.Submission.SCHEDULED,
        NEEDS_EMAIL: domain.Submission.SCHEDULED,
        PUBLISHED: domain.Submission.PUBLISHED,
        DELETED_PUBLISHED: domain.Submission.PUBLISHED,
        USER_DELETED:  domain.Submission.DELETED,
        DELETED_EXPIRED: domain.Submission.DELETED,
        DELETED_ON_HOLD: domain.Submission.DELETED,
        DELETED_PROCESSING: domain.Submission.DELETED,
        DELETED_REMOVED: domain.Submission.DELETED,
        DELETED_USER:  domain.Submission.DELETED,
        ERROR_STATE: domain.Submission.ERROR
    }

    submission_id = Column(Integer, primary_key=True)

    type = Column(String(8), index=True)
    """Submission type (e.g. ``new``, ``jref``, ``cross``)."""

    document_id = Column(
        ForeignKey('arXiv_documents.document_id',
                   ondelete='CASCADE',
                   onupdate='CASCADE'),
        index=True
    )
    doc_paper_id = Column(String(20), index=True)

    sword_id = Column(ForeignKey('arXiv_tracking.sword_id'), index=True)
    userinfo = Column(Integer, server_default=text("'0'"))
    is_author = Column(Integer, nullable=False, server_default=text("'0'"))
    agree_policy = Column(Integer, server_default=text("'0'"))
    viewed = Column(Integer, server_default=text("'0'"))
    stage = Column(Integer, server_default=text("'0'"))
    submitter_id = Column(
        ForeignKey('tapir_users.user_id', ondelete='CASCADE',
                   onupdate='CASCADE'),
        index=True
    )
    submitter_name = Column(String(64))
    submitter_email = Column(String(64))
    created = Column(DateTime)
    updated = Column(DateTime)
    status = Column(Integer, nullable=False, index=True,
                    server_default=text("'0'"))
    sticky_status = Column(Integer)
    """
    If the submission goes out of queue (e.g. submitter makes changes),
    this status should be applied when the submission is re-finalized
    (goes back into queue, comes out of working status).
    """

    must_process = Column(Integer, server_default=text("'1'"))
    submit_time = Column(DateTime)
    release_time = Column(DateTime)

    source_size = Column(Integer, server_default=text("'0'"))
    source_format = Column(String(12))
    """Submission content type (e.g. ``pdf``, ``tex``, ``pdftex``)."""
    source_flags = Column(String(12))

    allow_tex_produced = Column(Integer, server_default=text("'0'"))
    """Whether to allow a TeX-produced PDF."""

    package = Column(String(255), nullable=False, server_default=text("''"))
    """Path (on disk) to the submission package (tarball, PDF)."""

    is_oversize = Column(Integer, server_default=text("'0'"))

    has_pilot_data = Column(Integer)
    is_withdrawn = Column(Integer, nullable=False, server_default=text("'0'"))
    title = Column(Text)
    authors = Column(Text)
    comments = Column(Text)
    proxy = Column(String(255))
    report_num = Column(Text)
    msc_class = Column(String(255))
    acm_class = Column(String(255))
    journal_ref = Column(Text)
    doi = Column(String(255))
    abstract = Column(Text)
    license = Column(ForeignKey('arXiv_licenses.name', onupdate='CASCADE'),
                     index=True)
    version = Column(Integer, nullable=False, server_default=text("'1'"))

    is_ok = Column(Integer, index=True)

    admin_ok = Column(Integer)
    """Used by administrators for reporting/bookkeeping."""

    remote_addr = Column(String(16), nullable=False, server_default=text("''"))
    remote_host = Column(String(255), nullable=False,
                         server_default=text("''"))
    rt_ticket_id = Column(Integer, index=True)
    auto_hold = Column(Integer, server_default=text("'0'"))
    """Should be placed on hold when submission comes out of working status."""

    document = relationship('Document')
    arXiv_license = relationship('License')
    submitter = relationship('User')
    sword = relationship('Tracking')
    categories = relationship('SubmissionCategory',
                              back_populates='submission', lazy='joined',
                              cascade="all, delete-orphan")

    def patch(self, submission: domain.Submission) -> domain.Submission:
        """
        Patch a :class:`.Submission` with data outside the event scope.

        There are several fields that may change after a submission enters the
        classic moderation and publication system, that cannot be inferred
        from the event stack.

        Parameters
        ----------
        submission : :class:`.domain.Submission`
            The submission object to patch.

        Returns
        -------
        :class:`.domain.Submission`
            The same submission that was passed; now patched with data outside
            the scope of the event model.

        """
        # Status changes.
        submission.status = self._get_status()
        submission.active = (submission.status not in
                             [submission.DELETED, submission.PUBLISHED])
        submission.published = (submission.status == submission.PUBLISHED)
        submission.arxiv_id = self._get_arxiv_id()

        # Possible reclassification.
        primary = self.primary_classification
        if primary:
            submission.primary_classification = domain.Classification(
                category=primary.category
            )
        submission.secondary_classification = [
            domain.Classification(category=db_cat.category)
            for db_cat in self.categories
            if db_cat.is_primary == 0
        ]

        # Comments (admins may modify).
        submission.metadata.comments = self.comments

        # Apply sticky status.
        if submission.finalized and self.sticky_status is self.ON_HOLD:
            submission.status = submission.ON_HOLD
        return submission

    def to_submission(self) -> domain.Submission:
        """
        Generate a representation of submission state from a DB instance.

        Returns
        -------
        :class:`.domain.Submission`

        """
        status = self._get_status()
        primary = self.primary_classification
        submitter = domain.User(
            native_id=self.submitter.user_id,
            email=self.submitter.email,
            forename=self.submitter.first_name,
            surname=self.submitter.last_name,
            suffix=self.submitter.suffix_name
        )
        return domain.Submission(
            creator=submitter,
            owner=submitter,
            created=self.created,
            updated=self.updated,
            submitter_is_author=bool(self.is_author),
            submitter_accepts_policy=bool(self.agree_policy),
            submitter_contact_verified=bool(self.userinfo),
            submitter_confirmed_preview=bool(self.viewed),
            status=status,
            finalized=(status != domain.Submission.WORKING),
            active=(status not in [domain.Submission.DELETED,
                                   domain.Submission.PUBLISHED]),
            published=(status == domain.Submission.PUBLISHED),
            metadata=domain.SubmissionMetadata(
                title=self.title,
                abstract=self.abstract,
                comments=self.comments,
                report_num=self.report_num,
                doi=self.doi,
                msc_class=self.msc_class,
                acm_class=self.acm_class,
                journal_ref=self.journal_ref
            ),
            license=domain.License(
                uri=self.arXiv_license.name,
                name=self.arXiv_license.label
            ) if self.arXiv_license else None,
            primary_classification=domain.Classification(
                category=primary.category
            ) if primary else None,
            secondary_classification=[
                domain.Classification(category=db_cat.category)
                for db_cat in self.categories
                if db_cat.is_primary == 0
            ]
        )

    def update_from_submission(self, submission: domain.Submission) -> None:
        """Update this database object from a :class:`.domain.Submission`."""
        self.submitter_id = submission.creator.native_id
        self.submitter_name = submission.creator.name
        self.submitter_email = submission.creator.email
        self.is_author = 1 if submission.submitter_is_author else 0
        self.agree_policy = 1 if submission.submitter_accepts_policy else 0
        self.userinfo = 1 if submission.submitter_contact_verified else 0
        self.viewed = 1 if submission.submitter_confirmed_preview else 0
        self.created = submission.created
        self.updated = datetime.now()
        self.title = submission.metadata.title
        self.abstract = submission.metadata.abstract
        self.authors = submission.metadata.authors_display
        self.comments = submission.metadata.comments
        self.report_num = submission.metadata.report_num
        self.doi = submission.metadata.doi
        self.msc_class = submission.metadata.msc_class
        self.acm_class = submission.metadata.acm_class
        self.journal_ref = submission.metadata.journal_ref
        if submission.license:
            self.license = submission.license.uri
        self.type = Submission.NEW   # We're not handling other types here.

        if submission.source_content is not None:
            self.must_process = 0
            self.source_size = submission.source_content.size
            self.source_format = submission.source_content.format

        # Not submitted -> Submitted.
        if submission.finalized and self.status is Submission.NOT_SUBMITTED:
            self.status = Submission.SUBMITTED
            self.submit_time = submission.updated
        # Unsubmit.
        elif self.status is None or self.status <= Submission.ON_HOLD:
            if not submission.finalized:
                self.status = Submission.NOT_SUBMITTED

        if submission.primary_classification:
            self._update_primary(submission)
        self._update_secondaries(submission)

        self._update_submitter(submission)

    @property
    def primary_classification(self):
        """Get the primary classification for this submission."""
        categories = [
            db_cat for db_cat in self.categories if db_cat.is_primary == 1
        ]
        try:
            return categories[0]
        except IndexError:
            return

    def _get_arxiv_id(self) -> Optional[str]:
        if not self.document:
            return
        return self.document.paper_id

    def _get_status(self) -> str:
        """Map classic status codes to :class:`.domain.Submission` status."""
        if self._get_arxiv_id() is not None:
            return domain.Submission.PUBLISHED
        return self.STATUS_MAP.get(self.status)

    def _update_submitter(self, submission: domain.Submission) -> None:
        """Update submitter information."""
        self.submitter_id = submission.creator.native_id

    def _update_primary(self, submission: domain.Submission) -> None:
        """Update primary classification."""
        primary_category = submission.primary_classification.category
        cur_primary = self.primary_classification

        if cur_primary and cur_primary.category != primary_category:
            self.categories.remove(cur_primary)
            self.categories.append(
                SubmissionCategory(submission_id=self.submission_id,
                                   category=primary_category)
            )
        elif cur_primary is None and primary_category:
            self.categories.append(
                SubmissionCategory(
                    submission_id=self.submission_id,
                    category=primary_category,
                    is_primary=1
                )
            )

    def _update_secondaries(self, submission: domain.Submission) -> None:
        """Update secondary classifications."""
        cur_secondaries = [
            db_cat.category for db_cat
            in self.categories if db_cat.is_primary == 0
        ]
        tgt_secondaries = [
            cat.category for cat in submission.secondary_classification
        ]
        # Remove any categories that have been removed from the Submission.
        for db_cat in self.categories:
            if db_cat.is_primary == 1:
                continue
            if db_cat.category not in tgt_secondaries:
                self.categories.remove(db_cat)

        # Add any new secondaries
        for cat in submission.secondary_classification:
            if cat.category not in cur_secondaries:
                self.categories.append(
                    SubmissionCategory(
                        submission_id=self.submission_id,
                        category=cat.category,
                        is_primary=0
                    )
                )


class License(Base):    # type: ignore
    """Licenses available for submissions."""

    __tablename__ = 'arXiv_licenses'

    name = Column(String(255), primary_key=True)
    """This is the URI of the license."""

    label = Column(String(255))
    """Display label for the license."""

    active = Column(Integer, server_default=text("'1'"))
    """Only offer licenses with active=1."""

    note = Column(String(255))
    sequence = Column(Integer)


class CategoryDef(Base):    # type: ignore
    """Classification categories available for submissions."""

    __tablename__ = 'arXiv_category_def'

    category = Column(String(32), primary_key=True)
    name = Column(String(255))
    active = Column(Integer, server_default=text("'1'"))


class SubmissionCategory(Base):    # type: ignore
    """Classification relation for submissions."""

    __tablename__ = 'arXiv_submission_category'

    submission_id = Column(
        ForeignKey('arXiv_submissions.submission_id',
                   ondelete='CASCADE', onupdate='CASCADE'),
        primary_key=True,
        nullable=False,
        index=True
    )
    category = Column(
        ForeignKey('arXiv_category_def.category'),
        primary_key=True,
        nullable=False,
        index=True,
        server_default=text("''")
    )
    is_primary = Column(Integer, nullable=False, index=True,
                        server_default=text("'0'"))
    is_published = Column(Integer, index=True, server_default=text("'0'"))

    # category_def = relationship('CategoryDef')
    submission = relationship('Submission', back_populates='categories')


class Document(Base):    # type: ignore
    """
    Represents a published arXiv paper.

    This is here so that we can look up the arXiv ID after a submission is
    published.
    """

    __tablename__ = 'arXiv_documents'

    document_id = Column(Integer, primary_key=True)
    paper_id = Column(String(20), nullable=False, unique=True,
                      server_default=text("''"))
    title = Column(String(255), nullable=False, index=True,
                   server_default=text("''"))
    authors = Column(Text)
    """Canonical author string."""

    dated = Column(Integer, nullable=False, index=True,
                   server_default=text("'0'"))

    primary_subject_class = Column(String(16))

    created = Column(DateTime)

    submitter_email = Column(String(64), nullable=False, index=True,
                             server_default=text("''"))
    submitter_id = Column(ForeignKey('tapir_users.user_id'), index=True)
    submitter = relationship('User')


class DocumentCategory(Base):    # type: ignore
    """Relation between published arXiv papers and their classifications."""

    __tablename__ = 'arXiv_document_category'

    document_id = Column(
        ForeignKey('arXiv_documents.document_id', ondelete='CASCADE'),
        primary_key=True,
        nullable=False,
        index=True,
        server_default=text("'0'")
    )
    category = Column(
        ForeignKey('arXiv_category_def.category'),
        primary_key=True,
        nullable=False,
        index=True
    )
    """E.g. cs.CG, cond-mat.dis-nn, etc."""
    is_primary = Column(Integer, nullable=False, server_default=text("'0'"))

    category_def = relationship('CategoryDef')
    document = relationship('Document')


class User(Base):    # type: ignore
    """Represents an arXiv user."""

    __tablename__ = 'tapir_users'

    user_id = Column(Integer, primary_key=True)
    first_name = Column(String(50), index=True)
    last_name = Column(String(50), index=True)
    suffix_name = Column(String(50))
    share_first_name = Column(Integer, nullable=False,
                              server_default=text("'1'"))
    share_last_name = Column(Integer, nullable=False,
                             server_default=text("'1'"))
    email = Column(String(255), nullable=False, unique=True,
                   server_default=text("''"))
    share_email = Column(Integer, nullable=False, server_default=text("'8'"))
    email_bouncing = Column(Integer, nullable=False,
                            server_default=text("'0'"))
    policy_class = Column(ForeignKey('tapir_policy_classes.class_id'),
                          nullable=False, index=True,
                          server_default=text("'0'"))
    """
    +----------+---------------+
    | class_id | name          |
    +----------+---------------+
    |        1 | Administrator |
    |        2 | Public user   |
    |        3 | Legacy user   |
    +----------+---------------+
    """

    joined_date = Column(Integer, nullable=False, index=True,
                         server_default=text("'0'"))
    joined_ip_num = Column(String(16), index=True)
    joined_remote_host = Column(String(255), nullable=False,
                                server_default=text("''"))
    flag_internal = Column(Integer, nullable=False, index=True,
                           server_default=text("'0'"))
    flag_edit_users = Column(Integer, nullable=False, index=True,
                             server_default=text("'0'"))
    flag_edit_system = Column(Integer, nullable=False,
                              server_default=text("'0'"))
    flag_email_verified = Column(Integer, nullable=False,
                                 server_default=text("'0'"))
    flag_approved = Column(Integer, nullable=False, index=True,
                           server_default=text("'1'"))
    flag_deleted = Column(Integer, nullable=False, index=True,
                          server_default=text("'0'"))
    flag_banned = Column(Integer, nullable=False, index=True,
                         server_default=text("'0'"))
    flag_wants_email = Column(Integer, nullable=False,
                              server_default=text("'0'"))
    flag_html_email = Column(Integer, nullable=False,
                             server_default=text("'0'"))
    tracking_cookie = Column(String(255), nullable=False, index=True,
                             server_default=text("''"))
    flag_allow_tex_produced = Column(Integer, nullable=False,
                                     server_default=text("'0'"))

    tapir_policy_class = relationship('PolicyClass')


# TODO: what is this?
class PolicyClass(Base):    # type: ignore
    """Defines user roles in the system."""

    __tablename__ = 'tapir_policy_classes'

    class_id = Column(SmallInteger, primary_key=True)
    name = Column(String(64), nullable=False, server_default=text("''"))
    description = Column(Text, nullable=False)
    password_storage = Column(Integer, nullable=False,
                              server_default=text("'0'"))
    recovery_policy = Column(Integer, nullable=False,
                             server_default=text("'0'"))
    permanent_login = Column(Integer, nullable=False,
                             server_default=text("'0'"))


class Tracking(Base):    # type: ignore
    """Record of SWORD submissions."""

    __tablename__ = 'arXiv_tracking'

    tracking_id = Column(Integer, primary_key=True)
    sword_id = Column(Integer, nullable=False, unique=True,
                      server_default=text("'00000000'"))
    paper_id = Column(String(32), nullable=False)
    submission_errors = Column(Text)
    timestamp = Column(DateTime, nullable=False,
                       server_default=text("CURRENT_TIMESTAMP"))


class ArchiveCategory(Base):    # type: ignore
    """Maps categories to the archives in which they reside."""

    __tablename__ = 'arXiv_archive_category'

    archive_id = Column(String(16), primary_key=True, nullable=False,
                        server_default=text("''"))
    category_id = Column(String(32), primary_key=True, nullable=False)


class ArchiveDef(Base):    # type: ignore
    """Defines the archives in the arXiv classification taxonomy."""

    __tablename__ = 'arXiv_archive_def'

    archive = Column(String(16), primary_key=True, server_default=text("''"))
    name = Column(String(255))


class ArchiveGroup(Base):    # type: ignore
    """Maps archives to the groups in which they reside."""

    __tablename__ = 'arXiv_archive_group'

    archive_id = Column(String(16), primary_key=True, nullable=False,
                        server_default=text("''"))
    group_id = Column(String(16), primary_key=True, nullable=False,
                      server_default=text("''"))


class Archive(Base):    # type: ignore
    """Supplemental data about archives in the classification hierarchy."""

    __tablename__ = 'arXiv_archives'

    archive_id = Column(String(16), primary_key=True,
                        server_default=text("''"))
    in_group = Column(ForeignKey('arXiv_groups.group_id'), nullable=False,
                      index=True, server_default=text("''"))
    archive_name = Column(String(255), nullable=False,
                          server_default=text("''"))
    start_date = Column(String(4), nullable=False, server_default=text("''"))
    end_date = Column(String(4), nullable=False, server_default=text("''"))
    subdivided = Column(Integer, nullable=False, server_default=text("'0'"))

    arXiv_group = relationship('Group')


class GroupDef(Base):    # type: ignore
    """Defines the groups in the arXiv classification taxonomy."""

    __tablename__ = 'arXiv_group_def'

    archive_group = Column(String(16), primary_key=True,
                           server_default=text("''"))
    name = Column(String(255))


class Group(Base):    # type: ignore
    """Supplemental data about groups in the classification hierarchy."""

    __tablename__ = 'arXiv_groups'

    group_id = Column(String(16), primary_key=True, server_default=text("''"))
    group_name = Column(String(255), nullable=False, server_default=text("''"))
    start_year = Column(String(4), nullable=False, server_default=text("''"))


class EndorsementDomain(Base):    # type: ignore
    """Endorsement configurations."""

    __tablename__ = 'arXiv_endorsement_domains'

    endorsement_domain = Column(String(32), primary_key=True,
                                server_default=text("''"))
    endorse_all = Column(Enum('y', 'n'), nullable=False,
                         server_default=text("'n'"))
    mods_endorse_all = Column(Enum('y', 'n'), nullable=False,
                              server_default=text("'n'"))
    endorse_email = Column(Enum('y', 'n'), nullable=False,
                           server_default=text("'y'"))
    papers_to_endorse = Column(SmallInteger, nullable=False,
                               server_default=text("'4'"))


class Category(Base):    # type: ignore
    """Supplemental data about arXiv categories, including endorsement."""

    __tablename__ = 'arXiv_categories'

    arXiv_endorsement_domain = relationship('EndorsementDomain')

    archive = Column(
        ForeignKey('arXiv_archives.archive_id'),
        primary_key=True,
        nullable=False,
        server_default=text("''")
    )
    """E.g. cond-mat, astro-ph, cs."""
    arXiv_archive = relationship('Archive')

    subject_class = Column(String(16), primary_key=True, nullable=False,
                           server_default=text("''"))
    """E.g. AI, spr-con, str-el, CO, EP."""

    definitive = Column(Integer, nullable=False, server_default=text("'0'"))
    active = Column(Integer, nullable=False, server_default=text("'0'"))
    """Only use rows where active == 1."""

    category_name = Column(String(255))
    endorse_all = Column(
        Enum('y', 'n', 'd'),
        nullable=False,
        server_default=text("'d'")
    )
    endorse_email = Column(
        Enum('y', 'n', 'd'),
        nullable=False,
        server_default=text("'d'")
    )
    endorsement_domain = Column(
        ForeignKey('arXiv_endorsement_domains.endorsement_domain'),
        index=True
    )
    """E.g. astro-ph, acc-phys, chem-ph, cs."""

    papers_to_endorse = Column(SmallInteger, nullable=False,
                               server_default=text("'0'"))
