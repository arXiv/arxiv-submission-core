"""
Integration with the classic database to persist events and submission state.

As part of the classic renewal strategy, development of new submission
interfaces must maintain data interoperability with classic components. This
service module must therefore do three main things:

1. Store and provide access to event data generated during the submission
   process,
2. Keep the classic database tables up to date so that "downstream" components
   can continue to operate.
3. Patch NG submission data with state changes that occur in the classic
   system. Those changes will be made directly to submission tables and not
   involve event-generation. See :func:`get_submission` for details.

Since classic components work directly on submission tables, persisting events
and resulting submission state must occur in the same transaction. We must also
verify that we are not storing events that are stale with respect to the
current state of the submission. To achieve this, the caller should use the
:func:`.util.transaction` context manager, and (when committing new events)
call :func:`.get_submission` with ``for_update=True``. This will trigger a
shared lock on the submission row(s) involved until the transaction is
committed or rolled back.

ORM representations of the classic database tables involved in submission
are located in :mod:`.classic.models`. An additional model, :class:`.DBEvent`,
is defined in :mod:`.classic.event`.

See also :ref:`legacy-integration`.

"""

from typing import List, Optional, Tuple, Set, Callable, Any
from retry import retry
from datetime import datetime
from pytz import UTC
from itertools import groupby
import copy
from functools import reduce, wraps
from operator import ior
from dataclasses import asdict

from flask import Flask
from sqlalchemy import or_
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.exc import DBAPIError, OperationalError

from arxiv.base import logging
from arxiv.base.globals import get_application_config, get_application_global
from ...domain.event import Event, Announce, RequestWithdrawal, SetDOI, \
    SetJournalReference, SetReportNumber, Rollback, RequestCrossList, \
    ApplyRequest, RejectRequest, ApproveRequest, AddProposal, CancelRequest

from ...domain.submission import License, Submission, WithdrawalRequest, \
    CrossListClassificationRequest
from ...domain.agent import Agent, User
from .models import Base
from .exceptions import ClassicBaseException, NoSuchSubmission, \
    TransactionFailed, Unavailable, ConsistencyError
from .util import transaction, current_session, db
from .event import DBEvent
from . import models, util, interpolate, log, proposal, load


logger = logging.getLogger(__name__)
logger.propagate = False


def handle_operational_errors(func):
    """Catch SQLAlchemy OperationalErrors and raise :class:`.Unavailable`."""
    @wraps(func)
    def inner(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except OperationalError as e:
            raise Unavailable('Classic database unavailable') from e
    return inner


@retry(ClassicBaseException, tries=3, delay=1)
@handle_operational_errors
def get_licenses() -> List[License]:
    """Get a list of :class:`.domain.License` instances available."""
    license_data = current_session().query(models.License) \
        .filter(models.License.active == '1')
    return [License(uri=row.name, name=row.label) for row in license_data]


@retry(ClassicBaseException, tries=3, delay=1)
@handle_operational_errors
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
    :class:`.classic.exceptions.NoSuchSubmission`
        Raised when there are no events for the provided submission ID.

    """
    session = current_session()
    event_data = session.query(DBEvent) \
        .filter(DBEvent.submission_id == submission_id) \
        .order_by(DBEvent.created)
    events = [datum.to_event() for datum in event_data]
    if not events:      # No events, no dice.
        raise NoSuchSubmission(f'Submission {submission_id} not found')
    return events


@retry(ClassicBaseException, tries=3, delay=1)
@handle_operational_errors
def get_user_submissions_fast(user_id: int) -> List[Submission]:
    """
    Get all active submissions for a user.

    Uses the same approach as :func:`get_submission_fast`.

    Parameters
    ----------
    submission_id : int

    Returns
    -------
    list
        Items are the user's :class:`.domain.submission.Submission` instances.

    """
    session = current_session()
    db_submissions = list(
        session.query(models.Submission)
        .filter(models.Submission.submitter_id == user_id)
        .order_by(models.Submission.doc_paper_id.desc())
    )
    grouped = groupby(db_submissions, key=lambda dbs: dbs.doc_paper_id)
    submissions: List[Submission] = []
    for arxiv_id, dbss in grouped:
        logger.debug('Handle group for arXiv ID %s: %s', arxiv_id, dbss)
        if arxiv_id is None:    # This is an unannounced submission.
            for dbs in dbss:    # Each row represents a separate e-print.
                submissions.append(load.to_submission(dbs))
        else:
            dbss = sorted(dbss, key=lambda dbs: dbs.submission_id)
            submissions.append(load.load(dbss))
    return [s for s in submissions if not s.deleted]


@retry(ClassicBaseException, tries=3, delay=1)
@handle_operational_errors
def get_submission_fast(submission_id: int) -> List[Submission]:
    """
    Get the projection of the submission directly.

    Instead of playing events forward, we grab the most recent snapshot of the
    submission in the database. Since classic represents the submission using
    several rows, we have to grab all of them and transform/patch as
    appropriate.

    Parameters
    ----------
    submission_id : int

    Returns
    -------
    :class:`.domain.submission.Submission`

    Raises
    ------
    :class:`.classic.exceptions.NoSuchSubmission`
        Raised when there are is no submission for the provided submission ID.

    """
    return load.load(_get_db_submission_rows(submission_id))


# @retry(ClassicBaseException, tries=3, delay=1)
@handle_operational_errors
def get_submission(submission_id: int, for_update: bool = False) \
        -> Tuple[Submission, List[Event]]:
    """
    Get the current state of a submission from the database.

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
    :class:`.domain.submission.Submission`
    list
        Items are :class:`Event` instances.

    """
    # Let the caller determine the transaction scope.
    session = current_session()
    original_row = session.query(models.Submission) \
        .filter(models.Submission.submission_id == submission_id)

    if for_update:
        # Gives us SELECT ... FOR READ. In other words, lock this row for
        # writing, but allow other clients to read from it in the meantime.
        original_row = original_row.with_for_update(read=True)

    try:
        original_row = original_row.one()
    except NoResultFound:       # May also raise MultipleResultsFound; if so,
                                # we want to fail loudly.
        raise NoSuchSubmission(f'Submission {submission_id} not found')

    # Load any subsequent submission rows (e.g. v=2, jref, withdrawal).
    # These do not have the same legacy submission ID as the original
    # submission.
    subsequent_rows: List[models.Submission] = []
    arxiv_id = original_row.get_arxiv_id()
    if arxiv_id is not None:
        subsequent_rows = session.query(models.Submission) \
            .filter(models.Submission.doc_paper_id == arxiv_id) \
            .filter(models.Submission.submission_id != submission_id) \
            .order_by(models.Submission.submission_id.asc())

        if for_update:      # Lock these rows as well.
            subsequent_rows = subsequent_rows.with_for_update(read=True)
        subsequent_rows = list(subsequent_rows)   # Execute query.

    interpolator = interpolate.ClassicEventInterpolator(
        original_row,
        subsequent_rows,
        get_events(submission_id)
    )
    return interpolator.get_submission_state()


# @retry(ClassicBaseException, tries=3, delay=1)
@handle_operational_errors
def store_event(event: Event, before: Optional[Submission],
                after: Optional[Submission],
                *call: List[Callable]) -> Tuple[Event, Submission]:
    """
    Store an event, and update submission state.

    This is where we map the NG event domain onto the classic database. The
    main differences are that:

    - In the event domain, a submission is a single stream of events, but
      in the classic system we create new rows in the submission database
      for things like replacements, adding DOIs, and withdrawing papers.
    - In the event domain, the only concept of the announced paper is the
      paper ID. In the classic submission database, we also have to worry about
      the row in the Document database.

    We assume that the submission states passed to this function have the
    correct paper ID and version number, if announced. The submission ID on
    the event and the before/after states refer to the original classic
    submission only.

    Parameters
    ----------
    event : :class:`Event`
    before : :class:`Submission`
        The state of the submission before the event occurred.
    after : :class:`Submission`
        The state of the submission after the event occurred.
    call : list
        Items are callables that accept args ``Event, Submission, Submission``.
        These are called within the transaction context; if an exception is
        raised, the transaction is rolled back.

    """
    # Let the caller determine the transaction scope.
    session = current_session()
    if event.committed:
        raise TransactionFailed('%s already committed', event.event_id)
    logger.debug('store event %s', event.event_type)

    doc_id: Optional[int] = None

    # This is the case that we have a new submission.
    if before is None and isinstance(after, Submission):
        dbs = models.Submission(type=models.Submission.NEW_SUBMISSION)
        dbs.update_from_submission(after)
        this_is_a_new_submission = True

    else:   # Otherwise we're making an update for an existing submission.
        this_is_a_new_submission = False

        # After the original submission is announced, a new Document row is
        # created. This Document is shared by all subsequent Submission rows.
        if before.announced:
            doc_id = _load_document_id(before.arxiv_id, before.version)

        JREFEvents = [SetDOI, SetJournalReference, SetReportNumber]

        # From the perspective of the database, a replacement is mainly an
        # incremented version number. This requires a new row in the
        # database.
        if after.version > before.version:
            dbs = _create_replacement(doc_id, before.arxiv_id,
                                      after.version, after, event.created)
        elif isinstance(event, Rollback) and before.version > 1:
            dbs = _delete_replacement(doc_id, before.arxiv_id,
                                      before.version)

        # Withdrawals also require a new row, and they use the most recent
        # version number.
        elif isinstance(event, RequestWithdrawal):
            dbs = _create_withdrawal(doc_id, event.reason,
                                     before.arxiv_id, after.version, after,
                                     event.created)
        elif isinstance(event, RequestCrossList):
            dbs = _create_crosslist(doc_id, event.categories,
                                    before.arxiv_id, after.version, after,
                                    event.created)

        # Adding DOIs and citation information (so-called "journal reference")
        # also requires a new row. The version number is not incremented.
        elif before.announced and type(event) in JREFEvents:
            dbs = _create_jref(doc_id, before.arxiv_id, after.version, after,
                               event.created)

        elif isinstance(event, CancelRequest):
            dbs = _cancel_request(event, before, after)

        # The submission has been announced.
        elif isinstance(before, Submission) and before.arxiv_id is not None:
            dbs = _load(paper_id=before.arxiv_id, version=before.version)
            _preserve_sticky_hold(dbs, before, after, event)
            dbs.update_from_submission(after)

        # The submission has not yet been announced; we're working with a
        # single row.
        elif isinstance(before, Submission) and before.submission_id:
            dbs = _load(before.submission_id)

            _preserve_sticky_hold(dbs, before, after, event)
            dbs.update_from_submission(after)
        else:
            raise TransactionFailed("Something is fishy")

    db_event = _new_dbevent(event)
    session.add(dbs)
    session.add(db_event)

    # Make sure that we get a submission ID; note that this # does not commit
    # the transaction, just pushes the # SQL that we have generated so far to
    # the database # server.
    session.flush()

    log.handle(event, before, after)   # Create admin log entry.
    for func in call:
        logger.debug('call %s with event %s', func, event.event_id)
        func(event, before, after)
    if isinstance(event, AddProposal):
        proposal.add(event, before, after)

    # Attach the database object for the event to the row for the
    #  submission.
    if this_is_a_new_submission:    # Update in transaction.
        db_event.submission = dbs
    else:                           # Just set the ID directly.
        db_event.submission_id = before.submission_id

    event.committed = True

    # Update the domain event and submission states with the submission ID.
    # This should carry forward the original submission ID, even if the
    # classic database has several rows for the submission (with different
    # IDs).
    if this_is_a_new_submission:
        event.submission_id = dbs.submission_id
        after.submission_id = dbs.submission_id
    else:
        event.submission_id = before.submission_id
        after.submission_id = before.submission_id
    return event, after


@retry(ClassicBaseException, tries=3, delay=1)
@handle_operational_errors
def get_titles(since: datetime) -> List[Tuple[int, str, Agent]]:
    """Get titles from submissions created on or after a particular date."""
    # TODO: consider making this a param, if we need this function for anything
    # else.
    STATUSES_TO_CHECK = [
        models.Submission.SUBMITTED,
        models.Submission.ON_HOLD,
        models.Submission.NEXT_PUBLISH_DAY,
        models.Submission.REMOVED,
        models.Submission.USER_DELETED,
        models.Submission.DELETED_ON_HOLD,
        models.Submission.DELETED_PROCESSING,
        models.Submission.DELETED_REMOVED,
        models.Submission.DELETED_USER_EXPIRED
    ]
    session = current_session()
    q = session.query(
        models.Submission.submission_id,
        models.Submission.title,
        models.Submission.submitter_id,
        models.Submission.submitter_email
    )
    q = q.filter(models.Submission.status.in_(STATUSES_TO_CHECK))
    q = q.filter(models.Submission.created >= since)
    return [
        (submission_id, title, User(native_id=user_id, email=user_email))
        for submission_id, title, user_id, user_email in q.all()
    ]


# Private functions down here.

def _load(submission_id: Optional[int] = None, paper_id: Optional[str] = None,
          version: Optional[int] = 1, row_type: Optional[str] = None) \
        -> models.Submission:
    if row_type is not None:
        limit_to = [row_type]
    else:
        limit_to = [models.Submission.NEW_SUBMISSION,
                    models.Submission.REPLACEMENT]
    session = current_session()
    if submission_id is not None:
        submission = session.query(models.Submission) \
            .filter(models.Submission.submission_id == submission_id) \
            .filter(models.Submission.type.in_(limit_to)) \
            .one()
    elif submission_id is None and paper_id is not None:
        submission = session.query(models.Submission) \
            .filter(models.Submission.doc_paper_id == paper_id) \
            .filter(models.Submission.version == version) \
            .filter(models.Submission.type.in_(limit_to)) \
            .order_by(models.Submission.submission_id.desc()) \
            .first()
    else:
        submission = None
    if submission is None:
        raise NoSuchSubmission("No submission row matches those parameters")
    return submission


def _cancel_request(event, before, after):
    request = before.user_requests[event.request_id]
    if isinstance(request, WithdrawalRequest):
        row_type = models.Submission.WITHDRAWAL
    elif isinstance(request, CrossListClassificationRequest):
        row_type = models.Submission.CROSS_LIST
    dbs = _load(paper_id=before.arxiv_id, version=before.version,
                row_type=row_type)
    dbs.status = models.Submission.USER_DELETED
    return dbs


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


def _delete_replacement(document_id: int, paper_id: str, version: int) \
        -> models.Submission:
    session = current_session()
    dbs = session.query(models.Submission) \
        .filter(models.Submission.doc_paper_id == paper_id) \
        .filter(models.Submission.version == version) \
        .filter(models.Submission.type == models.Submission.REPLACEMENT) \
        .order_by(models.Submission.submission_id.desc()) \
        .first()
    dbs.status = models.Submission.USER_DELETED
    return dbs


def _create_withdrawal(document_id: int, reason: str, paper_id: str,
                       version: int, submission: Submission,
                       created: datetime) -> models.Submission:
    """
    Create a new withdrawal request.

    Withdrawals also require a new row, and they use the most recent version
    number.
    """
    dbs = models.Submission(type=models.Submission.WITHDRAWAL,
                            document_id=document_id,
                            version=version)
    dbs.update_withdrawal(submission, reason, paper_id, version, created)
    return dbs


def _create_crosslist(document_id: int, categories: List[str], paper_id: str,
                      version: int, submission: Submission,
                      created: datetime) -> models.Submission:
    """
    Create a new crosslist request.

    Cross list requests also require a new row, and they use the most recent
    version number.
    """
    dbs = models.Submission(type=models.Submission.CROSS_LIST,
                            document_id=document_id,
                            version=version)
    dbs.update_cross(submission, categories, paper_id, version, created)
    return dbs


def _create_jref(document_id: int, paper_id: str, version: int,
                 submission: Submission,
                 created: datetime) -> models.Submission:
    """
    Create a JREF submission.

    Adding DOIs and citation information (so-called "journal reference") also
    requires a new row. The version number is not incremented.
    """
    # Try to piggy-back on an existing JREF row. In the classic system, all
    # three fields can get updated on the same row.
    try:
        most_recent_sb = _load(paper_id=paper_id, version=version,
                               row_type=models.Submission.JOURNAL_REFERENCE)
        if most_recent_sb and not most_recent_sb.is_announced():
            most_recent_sb.update_from_submission(submission)
            return most_recent_sb
    except NoSuchSubmission:
        pass

    # Otherwise, create a new JREF row.
    dbs = models.Submission(type=models.Submission.JOURNAL_REFERENCE,
                            document_id=document_id, version=version)
    dbs.update_from_submission(submission)
    dbs.created = created
    dbs.updated = created
    dbs.doc_paper_id = paper_id
    dbs.status = models.Submission.PROCESSING_SUBMISSION
    return dbs


def _new_dbevent(event: Event) -> DBEvent:
    """Create an event entry in the database."""
    return DBEvent(event_type=event.event_type,
                   event_id=event.event_id,
                   event_version=_get_app_version(),
                   data=asdict(event),
                   created=event.created,
                   creator=asdict(event.creator),
                   proxy=asdict(event.proxy) if event.proxy else None)


def _preserve_sticky_hold(dbs: models.Submission, before: Submission,
                          after: Submission, event: Event) -> None:
    if dbs.status != models.Submission.ON_HOLD:
        return
    if dbs.is_on_hold() and after.status == Submission.WORKING:
        dbs.sticky_status = models.Submission.ON_HOLD


def _get_db_submission_rows(submission_id: int) -> List[models.Submission]:
    session = current_session()
    head = session.query(models.Submission.submission_id,
                         models.Submission.doc_paper_id) \
        .filter_by(submission_id=submission_id) \
        .subquery()
    dbss = list(
        session.query(models.Submission)
        .filter(or_(models.Submission.submission_id == submission_id,
                    models.Submission.doc_paper_id == head.c.doc_paper_id))
        .order_by(models.Submission.submission_id.desc())
    )
    if not dbss:
        raise NoSuchSubmission('No submission found')
    return dbss


def _get_app_version() -> str:
    return get_application_config().get('CORE_VERSION', '0.0.0')


def init_app(app: Flask) -> None:
    """Register the SQLAlchemy extension to an application."""
    db.init_app(app)

    @app.teardown_request
    def teardown_request(exception):
        if exception:
            db.session.rollback()
        db.session.remove()


def create_all() -> None:
    """Create all tables in the database."""
    Base.metadata.create_all(db.engine)


def drop_all() -> None:
    """Drop all tables in the database."""
    Base.metadata.drop_all(db.engine)


def _get_db_submission_rows(submission_id: int) -> List[models.Submission]:
    session = current_session()
    head = session.query(models.Submission.submission_id,
                         models.Submission.doc_paper_id) \
        .filter_by(submission_id=submission_id) \
        .subquery()
    dbss = list(
        session.query(models.Submission)
        .filter(or_(models.Submission.submission_id == submission_id,
                    models.Submission.doc_paper_id == head.c.doc_paper_id))
        .order_by(models.Submission.submission_id.desc())
    )
    if not dbss:
        raise NoSuchSubmission('No submission found')
    return dbss
