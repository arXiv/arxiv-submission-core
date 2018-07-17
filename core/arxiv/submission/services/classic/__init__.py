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

from typing import List, Optional, Generator, Dict, Union, Tuple
from contextlib import contextmanager

from flask import Flask
from sqlalchemy import Column, String, DateTime, ForeignKey, \
    create_engine
from sqlalchemy.ext.indexable import index_property
from sqlalchemy.orm import relationship
from sqlalchemy.engine import Engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.session import Session

from arxiv.base import logging
from arxiv.base.globals import get_application_config, get_application_global
from ...domain.event import Event, event_factory
from ...domain.submission import License, Submission
from ...domain.agent import User, Client, Agent
from .models import Base
from .exceptions import NoSuchSubmission, CommitFailed, ClassicBaseException
from . import models, util


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

    created = Column(DateTime)
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


@contextmanager
def transaction() -> Generator:
    """Context manager for database transaction."""
    session = current_session()
    try:
        yield session
        session.commit()
    except ClassicBaseException as e:
        logger.debug('Commit failed, rolling back: %s', str(e))
        session.rollback()
        raise   # Propagate exceptions raised from this module.
    except Exception as e:
        logger.debug('Commit failed, rolling back: %s', str(e))
        session.rollback()
        raise CommitFailed('Failed to commit transaction') from e


def get_licenses() -> List[License]:
    """Get a list of :class:`.License`s available for new submissions."""
    license_data = current_session().query(models.License) \
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
        if not event_data:      # No events, no dice.
            raise NoSuchSubmission(f'Submission {submission_id} not found')
        return [datum.to_event() for datum in event_data]


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
    # Load and play events. Eventually, this is the only query we will make
    # against the database.
    events = get_events(submission_id)
    submission = None       # We assume that the first event is a creation.
    for ev in events:
        submission = ev.apply(submission) if submission else ev.apply()

    with transaction() as session:
        # Load the current db state of the submission, and patch. Once we have
        # retired legacy components that do not follow the event model, this
        # step should be removed.
        data = session.query(models.Submission).get(submission_id)
        if data is None:
            raise NoSuchSubmission(f'Submission {submission_id} not found')
        return data.patch(submission), events


def store_events(*events: Event, submission: Submission) -> Submission:
    """
    Store events in the database.

    Parameters
    ----------
    events : list
        A list of (presumably new) :class:`.Event` instances to be persisted.
        Events that have already been committed will not be committed again,
        so it's safe to include them here.
    submission : :class:`.Submission`
        Current state of the submission (after events have been applied).

    Returns
    -------
    :class:`.Submission`
        Stored submission, updated with current submission ID.
    """
    # Commit new events for a single submission in a transaction.
    with transaction() as session:
        # We need a reference to this row for the event rows, so we add it
        # first.
        if submission.submission_id is None:
            db_submission = models.Submission()
        else:
            db_submission = session.query(models.Submission)\
                .get(submission.submission_id)
            if db_submission is None:
                raise RuntimeError("Submission ID is set, but can't find data")

        # Update the submission state from the Submission domain object.
        db_submission.update_from_submission(submission)
        session.add(db_submission)

        for event in events:
            if event.committed:   # Don't create duplicate event entries.
                continue

            if event.committed:
                raise RuntimeError('Event is already committed')
            db_event = DBEvent(
                event_type=event.event_type,
                event_id=event.event_id,
                data=event.to_dict(),
                created=event.created,
                creator=event.creator.to_dict(),
                proxy=event.proxy.to_dict() if event.proxy else None,
                submission_id=event.submission_id
            )
            session.add(db_event)
            db_event.submission = db_submission    # Will be updated on commit.
            event.committed = True
    submission.submission_id = db_submission.submission_id
    return submission


def init_app(app: object = None) -> None:
    """Set default configuration parameters for an application instance."""
    config = get_application_config(app)
    config.setdefault('CLASSIC_DATABASE_URI', 'sqlite://')


def get_engine(app: object = None) -> Engine:
    """Get a new :class:`.Engine` for the classic database."""
    config = get_application_config(app)
    database_uri = config.get('CLASSIC_DATABASE_URI', 'sqlite://')
    return create_engine(database_uri)


# TODO: consider making this private.
def get_session(app: object = None) -> Session:
    """Get a new :class:`.Session` for the classic database."""
    engine = current_engine()
    return sessionmaker(bind=engine)()


def current_engine() -> Engine:
    """Get/create :class:`.Engine` for this context."""
    g = get_application_global()
    if not g:
        return get_engine()
    if 'classic_engine' not in g:
        g.classic_engine = get_engine()    # type: ignore
    return g.classic_engine     # type: ignore


def current_session() -> Session:
    """Get/create :class:`.Session` for this context."""
    g = get_application_global()
    if not g:
        return get_session()
    if 'classic' not in g:
        g.classic = get_session()    # type: ignore
    return g.classic     # type: ignore


def create_all() -> None:
    """Create all tables in the database."""
    Base.metadata.create_all(current_engine())


def drop_all() -> None:
    """Drop all tables in the database."""
    Base.metadata.drop_all(current_engine())


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
