"""SQLAlchemy ORM classes."""

import json

from sqlalchemy import Column, Date, DateTime, Enum, ForeignKey, Text, text, \
    ForeignKeyConstraint, Index, Integer, SmallInteger, String, Table
from sqlalchemy.orm import relationship

from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Submission(Base):    # type: ignore
    """Represents an arXiv submission."""

    __tablename__ = 'arXiv_submissions'

    submission_id = Column(Integer, primary_key=True)
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
    must_process = Column(Integer, server_default=text("'1'"))
    submit_time = Column(DateTime)
    release_time = Column(DateTime)
    source_size = Column(Integer, server_default=text("'0'"))
    source_format = Column(String(12))
    source_flags = Column(String(12))
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
    type = Column(String(8), index=True)
    is_ok = Column(Integer, index=True)
    admin_ok = Column(Integer)
    allow_tex_produced = Column(Integer, server_default=text("'0'"))
    is_oversize = Column(Integer, server_default=text("'0'"))
    remote_addr = Column(String(16), nullable=False, server_default=text("''"))
    remote_host = Column(String(255), nullable=False,
                         server_default=text("''"))
    package = Column(String(255), nullable=False, server_default=text("''"))
    rt_ticket_id = Column(Integer, index=True)
    auto_hold = Column(Integer, server_default=text("'0'"))

    document = relationship('Document')
    arXiv_license = relationship('License')
    submitter = relationship('User')
    sword = relationship('Tracking')
    categories = relationship('SubmissionCategory',
                              back_populates="submission")


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


class Category(Base):    # type: ignore
    """Classifications available for submissions."""

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


class CategoryDef(Base):    # type: ignore
    __tablename__ = 'arXiv_category_def'

    category = Column(String(32), primary_key=True)
    name = Column(String(255))
    active = Column(Integer, server_default=text("'1'"))





class ArchiveCategory(Base):    # type: ignore
    __tablename__ = 'arXiv_archive_category'

    archive_id = Column(String(16), primary_key=True, nullable=False, server_default=text("''"))
    category_id = Column(String(32), primary_key=True, nullable=False)


class ArchiveDef(Base):    # type: ignore
    __tablename__ = 'arXiv_archive_def'

    archive = Column(String(16), primary_key=True, server_default=text("''"))
    name = Column(String(255))


class ArchiveGroup(Base):    # type: ignore
    __tablename__ = 'arXiv_archive_group'

    archive_id = Column(String(16), primary_key=True, nullable=False, server_default=text("''"))
    group_id = Column(String(16), primary_key=True, nullable=False, server_default=text("''"))


class Archive(Base):    # type: ignore
    __tablename__ = 'arXiv_archives'

    archive_id = Column(String(16), primary_key=True, server_default=text("''"))
    in_group = Column(ForeignKey('arXiv_groups.group_id'), nullable=False, index=True, server_default=text("''"))
    archive_name = Column(String(255), nullable=False, server_default=text("''"))
    start_date = Column(String(4), nullable=False, server_default=text("''"))
    end_date = Column(String(4), nullable=False, server_default=text("''"))
    subdivided = Column(Integer, nullable=False, server_default=text("'0'"))

    arXiv_group = relationship('Group')

class GroupDef(Base):    # type: ignore
    __tablename__ = 'arXiv_group_def'

    archive_group = Column(String(16), primary_key=True, server_default=text("''"))
    name = Column(String(255))


class Group(Base):    # type: ignore
    __tablename__ = 'arXiv_groups'

    group_id = Column(String(16), primary_key=True, server_default=text("''"))
    group_name = Column(String(255), nullable=False, server_default=text("''"))
    start_year = Column(String(4), nullable=False, server_default=text("''"))


# t_arXiv_in_category = Table(
#     'arXiv_in_category', metadata,
#     Column('document_id', ForeignKey('arXiv_documents.document_id'), nullable=False, index=True, server_default=text("'0'")),
#     Column('archive', String(16), nullable=False, server_default=text("''")),
#     Column('subject_class', String(16), nullable=False, server_default=text("''")),
#     Column('is_primary', Integer, nullable=False, server_default=text("'0'")),
#     ForeignKeyConstraint(['archive', 'subject_class'], ['arXiv_categories.archive', 'arXiv_categories.subject_class']),
#     Index('arXiv_in_category_mp', 'archive', 'subject_class'),
#     Index('archive', 'archive', 'subject_class', 'document_id', unique=True)
# )





class EndorsementDomain(Base):    # type: ignore
    __tablename__ = 'arXiv_endorsement_domains'

    endorsement_domain = Column(String(32), primary_key=True, server_default=text("''"))
    endorse_all = Column(Enum('y', 'n'), nullable=False, server_default=text("'n'"))
    mods_endorse_all = Column(Enum('y', 'n'), nullable=False, server_default=text("'n'"))
    endorse_email = Column(Enum('y', 'n'), nullable=False, server_default=text("'y'"))
    papers_to_endorse = Column(SmallInteger, nullable=False, server_default=text("'4'"))


class UserDemographic(User):
    __tablename__ = 'arXiv_demographics'
    __table_args__ = (
        ForeignKeyConstraint(['archive', 'subject_class'], ['arXiv_categories.archive', 'arXiv_categories.subject_class']),
        Index('archive', 'archive', 'subject_class')
    )

    user_id = Column(ForeignKey('tapir_users.user_id'), primary_key=True, server_default=text("'0'"))
    country = Column(String(2), nullable=False, index=True, server_default=text("''"))
    affiliation = Column(String(255), nullable=False, server_default=text("''"))
    url = Column(String(255), nullable=False, server_default=text("''"))
    type = Column(SmallInteger, index=True)
    archive = Column(String(16))
    subject_class = Column(String(16))
    original_subject_classes = Column(String(255), nullable=False, server_default=text("''"))
    flag_group_physics = Column(Integer, index=True)
    flag_group_math = Column(Integer, nullable=False, index=True, server_default=text("'0'"))
    flag_group_cs = Column(Integer, nullable=False, index=True, server_default=text("'0'"))
    flag_group_nlin = Column(Integer, nullable=False, index=True, server_default=text("'0'"))
    flag_proxy = Column(Integer, nullable=False, index=True, server_default=text("'0'"))
    flag_journal = Column(Integer, nullable=False, index=True, server_default=text("'0'"))
    flag_xml = Column(Integer, nullable=False, index=True, server_default=text("'0'"))
    dirty = Column(Integer, nullable=False, server_default=text("'2'"))
    flag_group_test = Column(Integer, nullable=False, server_default=text("'0'"))
    flag_suspect = Column(Integer, nullable=False, index=True, server_default=text("'0'"))
    flag_group_q_bio = Column(Integer, nullable=False, index=True, server_default=text("'0'"))
    flag_group_q_fin = Column(Integer, nullable=False, index=True, server_default=text("'0'"))
    flag_group_stat = Column(Integer, nullable=False, index=True, server_default=text("'0'"))
    veto_status = Column(Enum('ok', 'no-endorse', 'no-upload', 'no-replace'), nullable=False, server_default=text("'ok'"))

    arXiv_category = relationship('Category')
