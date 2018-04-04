from typing import List, Optional
from contextlib import contextmanager

from flask import Flask
from sqlalchemy import JSON, Column, String, DateTime, ForeignKey, create_engine
from sqlalchemy.ext.indexable import index_property
from sqlalchemy.orm import relationship
from sqlalchemy.engine import Engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.session import Session

from events.domain.submission import License, Submission
from events.domain.agent import User, Client
from . import models
from .models import Base
from events.context import get_application_config, get_application_global


global Event
Event = None


class NoSuchSubmission(RuntimeError):
    """A request was made for a submission that does not exist."""


@contextmanager
def transaction():
    """Context manager for database transaction."""
    session = current_session()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        raise RuntimeError('Ack! %s' % e) from e


def get_licenses() -> List[License]:
    """Get a list of :class:`.License`s available for new submissions."""
    license_data = current_session().query(models.License) \
        .filter(models.License.active == '1')
    return [License(uri=row.name, name=row.label) for row in license_data]


def get_submission(submission_id: int) -> Submission:

    data = current_session().query(models.Submission).get(submission_id)
    if data is None:
        raise NoSuchSubmission(f'Submission with id {submission_id} not found')
    return Submission(
        creator=User(data.submitter_id),
        owner=User(data.submitter_id),
        created=data.created
    )


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
            db_event = Event(
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
    config = get_application_config(app)
    database_uri = config.get('CLASSIC_DATABASE_URI', 'sqlite://')
    return create_engine(database_uri)


# TODO: consider making this private.
def get_session(app: object = None) -> Session:
    """Get a new :class:`.Session`."""
    global Event
    Event = _declare_event()
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
        g.search = get_session()    # type: ignore
    return g.search     # type: ignore


def create_all() -> None:
    """Create all tables in the database."""
    session = current_session()
    Base.metadata.create_all(current_engine())


def drop_all() -> None:
    """Drop all tables in the database."""
    session = current_session()
    Base.metadata.drop_all(current_engine())


def _declare_event() -> type:
    """
    Define Event model.

    This is deferred until runtime so that we can inject an alternate model
    for testing. This is less than ideal, but (so far) appears to be the only
    way to effectively replace column data types, which we need in order to
    use JSON columns with SQLite.
    """
    class Event(Base):  # type: ignore
        __tablename__ = 'event'

        event_id = Column(String(40), primary_key=True)
        event_type = Column(String(255))
        proxy = Column(JSON)
        proxy_id = index_property('proxy', 'agent_identifier')

        creator = Column(JSON)
        creator_id = index_property('creator', 'agent_identifier')

        created = Column(DateTime)
        data = Column(JSON)
        submission_id = Column(
            ForeignKey('arXiv_submissions.submission_id'),
            index=True
        )

        submission = relationship("Submission")
    return Event
