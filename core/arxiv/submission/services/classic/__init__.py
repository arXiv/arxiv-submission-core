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

from typing import List, Optional, Tuple
from datetime import datetime
from pytz import UTC

from arxiv.base import logging
from arxiv.base.globals import get_application_config, get_application_global
from ...domain.event import Event, Publish, RequestWithdrawal, SetDOI, \
    SetJournalReference, SetReportNumber
from ...domain.submission import License, Submission
from ...domain.agent import System
from .models import Base
from .exceptions import ClassicBaseException, NoSuchSubmission, CommitFailed
from .util import transaction, current_session
from .event import DBEvent
from . import models, util

SYSTEM = System(__name__)


logger = logging.getLogger(__name__)


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

    Until those legacy components are replaced, this function loads both the
    event stack and the current DB state of the submission, and uses the DB
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
    dbss: List[models.Submission] = []
    arxiv_id: Optional[str] = None

    # Load submission data from the legacy submission table.
    with transaction() as session:
        # Load the root submission (v=1).
        dbs = session.query(models.Submission).get(submission_id)
        if dbs is None:
            raise NoSuchSubmission(f'Submission {submission_id} not found')
        arxiv_id = dbs.doc_paper_id

        # Load any subsequent submission rows (e.g. v=2, jref, withdrawal).
        # These do not have the same legacy submission ID as the original
        # submission.
        if arxiv_id is not None:
            dbss = _load_subsequent_submissions(submission_id, arxiv_id)

    # Play the events forward.
    submission = None   # We always start from the beginning (no submission).
    applied_events: List[Event] = []    # This is what we'll return.

    # Using a closure to cut down on redundant code.
    def insert_publish_event(dbs, submission):
        """Create and apply a Publish event, and add it to the stack."""
        publish_event = _new_publish_event(dbs, submission_id)
        submission = publish_event.apply(submission)
        applied_events.append(publish_event)
        return submission

    for event in events:
        # If the classic submission row is published, we want to insert a
        # Publish event in the appropriate spot in the event stack.
        if dbs and dbs.get_updated() < event.created and dbs.is_published():
            submission = insert_publish_event(dbs, submission)

        # As we go, look for moments where a new row in the legacy submission
        # table was created.
        if dbss and dbss[0].get_created() <= event.created:
            # If we find one, patch the domain submission from the preceding
            # row, and load the next row. We want to do this before projecting
            # the event, since we are inferring that the event occurred after
            # a change was made via the legacy system.
            submission = dbs.patch(submission)
            dbs = dbss.pop(0)

        # Now project the event.
        submission = event.apply(submission)
        applied_events.append(event)

    # Finally, patch the submission with any remaining changes that may have
    # occurred via the legacy system.
    for dbs in [dbs] + list(dbss):
        if dbs.is_published() and not submission.published:
            submission = insert_publish_event(dbs, submission)
        submission = dbs.patch(submission)
    return submission, applied_events


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
        dbs = models.Submission(type=models.Submission.NEW_SUBMSSION)
        dbs.update_from_submission(after)
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
            dbs = _create_replacement(document_id, before.arxiv_id,
                                      after.version, after, event.created)

        # Withdrawals also require a new row, and they use the most recent
        # version number.
        elif isinstance(event, RequestWithdrawal):
            dbs = _create_withdrawal(document_id, before.arxiv_id,
                                     after.version, after, event.created)

        # Adding DOIs and citation information (so-called "journal reference")
        # also requires a new row. The version number is not incremented.
        elif before.published and \
                type(event) in [SetDOI, SetJournalReference, SetReportNumber]:
            dbs = _create_jref(document_id, before.arxiv_id, after.version,
                               after, event.created)

        elif isinstance(before, Submission) and before.published:
            dbs = _load_submission(paper_id=before.arxiv_id,
                                   version=before.version)
            dbs.update_from_submission(after)
        elif isinstance(before, Submission) and before.submission_id:
            dbs = _load_submission(before.submission_id)
            dbs.update_from_submission(after)
        else:
            raise CommitFailed("Something is fishy")

    db_event = _new_dbevent(event)

    session.add(dbs)
    session.add(db_event)

    # Attach the database object for the event to the row for the submission.
    if this_is_a_new_submission:    # Update in transaction.
        db_event.submission = dbs
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
        event.submission_id = dbs.submission_id
        after.submission_id = dbs.submission_id
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


def _load_subsequent_submissions(submission_id: int, paper_id: str) \
        -> List[models.Submission]:
    """Load submission rows for a given arXiv paper ID, except the original."""
    with transaction() as session:
        return list(
            session.query(models.Submission)
            .filter(models.Submission.doc_paper_id == paper_id)
            .filter(models.Submission.submission_id != submission_id)
            .order_by(models.Submission.submission_id.asc())
        )


def _new_publish_event(dbs: models.Submission, submission_id: int) -> Publish:
    return Publish(creator=SYSTEM, created=dbs.get_updated(),
                   committed=True, arxiv_id=dbs.get_arxiv_id(),
                   submission_id=submission_id)


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
            .order_by(models.Submission.submission_id.desc()) \
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
                        submission: Submission, created: datetime) \
        -> models.Submission:
    """
    Create a new replacement submission.

    From the perspective of the database, a replacement is mainly an
    incremented version number. This requires a new row in the database.
    """
    dbs = models.Submission(type=models.Submission.REPLACEMENT,
                            document_id=document_id, version=version)
    dbs.update_from_submission(submission)
    dbs.created = created
    dbs.updated = created
    dbs.doc_paper_id = paper_id
    dbs.status = models.Submission.NOT_SUBMITTED
    return dbs


def _create_withdrawal(document_id: int, paper_id: str, version: int,
                       submission: Submission, created: datetime) \
        -> models.Submission:
    """
    Create a new withdrawal request.

    Withdrawals also require a new row, and they use the most recent version
    number.
    """
    dbs = models.Submission(type=models.Submission.WITHDRAWAL,
                            document_id=document_id,
                            version=version)
    dbs.update_from_submission(submission)
    dbs.created = created
    dbs.updated = created
    dbs.doc_paper_id = paper_id
    dbs.status = models.Submission.SUBMITTED
    dbs.comments = dbs.comments.rstrip('. ') + \
        f". Withdrawn: {submission.reason_for_withdrawal}"
    return dbs


def _create_jref(document_id: int, paper_id: str, version: int,
                 submission: Submission, created: datetime) \
        -> models.Submission:
    """
    Create a JREF submission.

    Adding DOIs and citation information (so-called "journal reference") also
    requires a new row. The version number is not incremented.
    """
    # Try to piggy-back on an existing JREF row. In the classic system, all
    # three fields can get updated on the same row.
    most_recent_sb = _load_submission(paper_id=paper_id, version=version)
    if most_recent_sb.is_jref() and not most_recent_sb.is_published():
        most_recent_sb.update_from_submission(submission)
        return most_recent_sb

    # Otherwise, create a new JREF row.
    dbs = models.Submission(type=models.Submission.JOURNAL_REFERENCE,
                            document_id=document_id, version=version)
    dbs.update_from_submission(submission)
    dbs.created = created
    dbs.updated = created
    dbs.doc_paper_id = paper_id
    dbs.status = models.Submission.SUBMITTED
    return dbs


def _new_dbevent(event: Event) -> DBEvent:
    """Create an event entry in the database."""
    return DBEvent(event_type=event.event_type,
                   event_id=event.event_id,
                   data=event.to_dict(),
                   created=event.created,
                   creator=event.creator.to_dict(),
                   proxy=event.proxy.to_dict() if event.proxy else None)
