"""
Integration with the classic database to persist events and submission state.

As part of the classic renewal strategy, development of new submission
interfaces must maintain data interoperability with classic components. This
service module must therefore do two main things:

1. Store and provide access to event data generated during the submission
   process, and
2. Keep the classic database tables up to date so that "downstream" components
   can continue to operate. Since classic components work directly on
   submission tables, persisting events and resulting submission state must
   occur in the same transaction.

An additional challenge is representing changes to submission state made by
classic components, since those changes will be made directly to submission
tables and not involve event-generation. See :func:`get_submission` for
details.

ORM representations of the classic database tables involved in submission
are located in :mod:`.classic.models`. An additional model, :class:`.DBEvent`,
is defined in the current module.
"""

from typing import List, Optional, Dict, Union, Tuple

from flask import Flask
from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.ext.indexable import index_property
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

# Combining the base DateTime field with a MySQL backend does not support
# fractional seconds. Since we may be creating events only milliseconds apart,
# getting fractional resolution is essential.
from sqlalchemy.dialects.mysql import DATETIME as DateTime

from arxiv.base import logging
from arxiv.base.globals import get_application_config, get_application_global
from ...domain.event import Event, event_factory, RequestWithdrawal, SetDOI, \
    SetJournalReference
from ...domain.submission import License, Submission
from ...domain.agent import User, Client, Agent
from .models import Base
from .exceptions import ClassicBaseException, NoSuchSubmission, CommitFailed
from . import models, util
from .util import transaction, current_session


logger = logging.getLogger(__name__)


class DBEvent(Base):  # type: ignore
    """Database representation of an :class:`.Event`."""

    __tablename__ = 'event'

    event_id = Column(String(40), primary_key=True)
    event_type = Column(String(255))
    proxy = Column(util.FriendlyJSON)
    proxy_id = index_property('proxy', 'agent_identifier')
    client = Column(util.FriendlyJSON)
    client_id = index_property('client', 'agent_identifier')

    creator = Column(util.FriendlyJSON)
    creator_id = index_property('creator', 'agent_identifier')

    created = Column(DateTime(fsp=6))
    data = Column(util.FriendlyJSON)
    submission_id = Column(
        ForeignKey('arXiv_submissions.submission_id'),
        index=True
    )

    submission = relationship("Submission")

    def to_event(self) -> Event:
        """
        Instantiate an :class:`.Event` using event data from this instance.

        Returns
        -------
        :class:`.Event`

        """
        _skip = ['creator', 'proxy', 'client', 'submission_id', 'created',
                 'event_type']
        data = {
            key: value for key, value in self.data.items()
            if key not in _skip
        }
        data['committed'] = True,     # Since we're loading from the DB.
        return event_factory(
            self.event_type,
            creator=Agent.from_dict(self.creator),
            proxy=Agent.from_dict(self.proxy) if self.proxy else None,
            client=Agent.from_dict(self.client) if self.client else None,
            submission_id=self.submission_id,
            created=self.created,
            **data
        )


def get_licenses() -> List[License]:
    """Get a list of :class:`.License`s available for new submissions."""
    license_data = util.current_session().query(models.License) \
        .filter(models.License.active == '1')
    return [License(uri=row.name, name=row.label) for row in license_data]


def get_events(submission_id: int) -> List[Event]:
    """
    Load events from the classic database.

    Parameters
    ----------
    submission_id : int

    Returns
    -------
    list
        Items are :class:`.Event` instances loaded from the class DB.

    Raises
    ------
    :class:`.NoSuchSubmission`
        Raised when there are no events for the provided submission ID.

    """
    with transaction() as session:
        event_data = session.query(DBEvent) \
            .filter(DBEvent.submission_id == submission_id) \
            .order_by(DBEvent.created)
        events = [datum.to_event() for datum in event_data]
        if not events:      # No events, no dice.
            raise NoSuchSubmission(f'Submission {submission_id} not found')
        return events


def get_submission(submission_id: int) -> Tuple[Submission, List[Event]]:
    """
    Get the current state of a :class:`.Submission` from the database.

    In the medium term, services that use this package will need to
    play well with legacy services that integrate with the classic
    database. For example, the moderation system does not use the event
    model implemented here, and will therefore cause direct changes to the
    submission tables that must be reflected in our representation of the
    submission.

    Until those legacy components are replaced, we will need to load both the
    event stack and the current DB state of the submission, and use the DB
    state to patch fields that may have changed outside the purview of the
    event model.

    Parameters
    ----------
    submission_id : int

    Returns
    -------
    :class:`.Submission`
    """
    events = get_events(submission_id)

    # Load submission data from the legacy submission table.
    with transaction() as session:
        # Load the root submission (v=1).
        db_sub = session.query(models.Submission).get(submission_id)
        if db_sub is None:
            raise NoSuchSubmission(f'Submission {submission_id} not found')

        # Load any subsequent submission rows (e.g. v=2, jref, withdrawal).
        if db_sub.doc_paper_id is not None:
            db_subs = list(
                session.query(models.Submission)
                .filter(models.Submission.doc_paper_id == db_sub.doc_paper_id)
                .order_by(models.Submission.submission_id.asc())
            )
        else:
            db_subs = []

    # Play the events forward.
    submission = None
    for event in events:
        # As we go, look for moments where a new row in the legacy submission
        # table was created.
        if db_subs and db_subs[0].created < event.created:
            # If we find one, patch the domain submission from the preceding
            # row, and load the next row. We want to do this before projecting
            # the event, since we are inferring that the event occurred after
            # a change was made via the legacy system.
            submission = db_sub.patch(submission)
            db_sub = db_subs.pop(0)

        # Now project the event.
        submission = event.apply(submission)

    # Finally, patch the submission with any remaining changes that may have
    # occurred via the legacy system.
    for db_sub in [db_sub] + list(db_subs):
        submission = db_sub.patch(submission)
    return submission, events


def _load_submission(submission_id: Optional[int] = None,
                     paper_id: Optional[str] = None,
                     version: Optional[int] = 1) -> models.Submission:
    session = current_session()
    if submission_id is not None:
        submission = session.query(models.Submission) \
            .filter(models.Submission.submission_id == submission_id) \
            .one()
    elif submission_id is None and paper_id is not None:
        submission = session.query(models.Submission) \
            .filter(models.Submission.doc_paper_id == paper_id) \
            .filter(models.Submission.version == version) \
            .order_by(models.Submission.created.desc()) \
            .first()
    else:
        submission = None
    if submission is None:
        raise NoSuchSubmission("No submission row matches those parameters")
    return submission


def _load_document_id(paper_id: str, version: int) -> int:
    logger.debug('get document ID with %s and %s', paper_id, version)
    session = current_session()
    document_id = session.query(models.Submission.document_id) \
        .filter(models.Submission.doc_paper_id == paper_id) \
        .filter(models.Submission.version == version) \
        .first()
    if document_id is None:
        raise NoSuchSubmission("No submission row matches those parameters")
    return document_id[0]


def _create_replacement(document_id: int, paper_id: str, version: int,
                        submission: Submission) -> models.Submission:
    """
    Create a new replacement submission.

    From the perspective of the database, a replacement is mainly an
    incremented version number. This requires a new row in the database.
    """
    db_sb = models.Submission(type=models.Submission.REPLACEMENT,
                              document_id=document_id,
                              version=version)
    db_sb.update_from_submission(submission)
    db_sb.doc_paper_id = paper_id
    db_sb.status = models.Submission.NOT_SUBMITTED
    return db_sb


def _create_withdrawal(document_id: int, paper_id: str, version: int,
                       submission: Submission) -> models.Submission:
    """
    Create a new withdrawal request.

    Withdrawals also require a new row, and they use the most recent version
    number.
    """
    db_sb = models.Submission(type=models.Submission.WITHDRAWAL,
                              document_id=document_id,
                              version=version)
    db_sb.update_from_submission(submission)
    db_sb.doc_paper_id = paper_id
    db_sb.status = models.Submission.SUBMITTED
    return db_sb


def _create_jref(document_id: int, paper_id: str, version: int,
                 submission: Submission) -> models.Submission:
    """
    Create a JREF submission.

    Adding DOIs and citation information (so-called "journal reference") also
    requires a new row. The version number is not incremented.
    """
    db_sb = models.Submission(type=models.Submission.JOURNAL_REFERENCE,
                              document_id=document_id,
                              version=version)
    db_sb.update_from_submission(submission)
    db_sb.doc_paper_id = paper_id
    db_sb.status = models.Submission.SUBMITTED
    return db_sb


def _create_event(event: Event) -> DBEvent:
    """Create an event entry in the database."""
    return DBEvent(event_type=event.event_type,
                   event_id=event.event_id,
                   data=event.to_dict(),
                   created=event.created,
                   creator=event.creator.to_dict(),
                   proxy=event.proxy.to_dict() if event.proxy else None)


def store_event(event: Event, before: Optional[Submission],
                after: Optional[Submission]) -> Tuple[Event, Submission]:
    """
    Store an event, and update submission state.

    This is where we map the NG event domain onto the classic database. The
    main differences are that:

    - In the event domain, a submission is a single stream of events, but
      in the classic system we create new rows in the submission database
      for things like replacements, adding DOIs, and withdrawing papers.
    - In the event domain, the only concept of the published paper is the
      paper ID. In the classic submission database, we also have to worry about
      the row in the Document database.

    We assume that the submission states passed to this function have the
    correct paper ID and version number, if published. The submission ID on
    the event and the before/after states refer to the original classic
    submission only.

    Parameters
    ----------
    event : :class:`Event`
    before : :class:`Submission`
        The state of the submission before the event occurred.
    after : :class:`Submission`
        The state of the submission after the event occurred.

    """
    if event.committed:
        raise CommitFailed('Event %s already committed', event.event_id)
    session = current_session()
    document_id: Optional[int] = None

    # This is the case that we have a new submission.
    if before is None and isinstance(after, Submission):
        db_sb = models.Submission(type=models.Submission.NEW_SUBMSSION)
        db_sb.update_from_submission(after)
        this_is_a_new_submission = True

    else:   # Otherwise we're making an update for an existing submission.
        this_is_a_new_submission = False

        # After the original submission is published, a new Document row is
        #  created. This Document is shared by all subsequent Submission rows.
        if before.published:
            document_id = _load_document_id(before.arxiv_id, before.version)

        # From the perspective of the database, a replacement is mainly an
        # incremented version number. This requires a new row in the database.
        if after.version > before.version:
            db_sb = _create_replacement(document_id, before.arxiv_id,
                                        after.version, after)

        # Withdrawals also require a new row, and they use the most recent
        # version number.
        elif isinstance(event, RequestWithdrawal):
            db_sb = _create_withdrawal(document_id, before.arxiv_id,
                                       after.version, after)

        # Adding DOIs and citation information (so-called "journal reference")
        # also requires a new row. The version number is not incremented.
        elif before.published and type(event) in [SetDOI, SetJournalReference]:
            db_sb = _create_jref(document_id, before.arxiv_id,
                                 after.version, after)

        elif isinstance(before, Submission) and before.published:
            db_sb = _load_submission(paper_id=before.arxiv_id,
                                     version=before.version)
            db_sb.update_from_submission(after)
        elif isinstance(before, Submission) and before.submission_id:
            db_sb = _load_submission(before.submission_id)
            db_sb.update_from_submission(after)
        else:
            raise CommitFailed("Something is fishy")

    db_event = _create_event(event)

    session.add(db_sb)
    session.add(db_event)

    # Attach the database object for the event to the row for the submission.
    if this_is_a_new_submission:    # Update in transaction.
        db_event.submission = db_sb
    else:                           # Just set the ID directly.
        db_event.submission_id = before.submission_id

    try:
        session.commit()
    except Exception as e:
        session.rollback()
        raise CommitFailed('Something went wrong: %s', e) from e

    event.committed = True

    # Update the domain event and submission states with the submission ID.
    # This should carry forward the original submission ID, even if the classic
    # database has several rows for the submission (with different IDs).
    if this_is_a_new_submission:
        event.submission_id = db_sb.submission_id
        after.submission_id = db_sb.submission_id
    else:
        event.submission_id = before.submission_id
        after.submission_id = before.submission_id
    return event, after


def init_app(app: object = None) -> None:
    """Set default configuration parameters for an application instance."""
    config = get_application_config(app)
    config.setdefault('CLASSIC_DATABASE_URI', 'sqlite://')


def create_all() -> None:
    """Create all tables in the database."""
    Base.metadata.create_all(util.current_engine())


def drop_all() -> None:
    """Drop all tables in the database."""
    Base.metadata.drop_all(util.current_engine())


# # TODO: find a better way!
# def _declare_event() -> type:
#     """
#     Define DBEvent model.
#
#     This is deferred until runtime so that we can inject an alternate model
#     for testing. This is less than ideal, but (so far) appears to be the only
#     way to effectively replace column data types, which we need in order to
#     use JSON columns with SQLite.
#     """
#
#     return DBEvent
