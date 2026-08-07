"""Lightweight database integration for checkpointing."""

import time
from datetime import datetime
from typing import Optional, Any

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from pytz import UTC
from retry import retry
from sqlalchemy import BigInteger, Column, DateTime, Enum, ForeignKey, \
    ForeignKeyConstraint, Index, \
    Integer, SmallInteger, String, Table, text, Text
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.exc import OperationalError, NoSuchTableError

from arxiv.base import logging
from arxiv.submission.domain.event import AddProcessStatus
from ..process import Process
from ..rules import Rule

db: SQLAlchemy = SQLAlchemy()
logger = logging.getLogger(__name__)
logger.propagate = False

class Unavailable(IOError):
    """The database is not available."""


class Checkpoint(db.Model):
    """Stores checkpoint information for the Kinesis consumer."""

    __tablename__ = 'checkpoint'
    __bind_key__ = 'agent'

    id = Column(Integer, primary_key=True)
    position = Column(String(255), index=True, nullable=False)
    created = Column(DATETIME(6), default=lambda: datetime.now(UTC))
    shard_id = Column(String(255), index=True, nullable=False)


class ProcessStatusEvent(db.Model):
    """Stores events related to processes."""

    __tablename__ = 'process_status_events'
    __bind_key__ = 'agent'

    id = Column(Integer, primary_key=True)
    created = Column(DATETIME(6), index=True, nullable=False)
    received = Column(DATETIME(6), index=True, nullable=False,
                      default=lambda: datetime.now(UTC))
    event_id = Column(String(255), index=True, nullable=False)
    submission_id = Column(Integer, index=True)
    process_id = Column(String(100), index=True, nullable=False)
    process = Column(String(100), index=True, nullable=False)
    status = Column(String(50), index=True, nullable=True)
    reason = Column(Text, nullable=True)
    agent_type = Column(Enum('System', 'User', 'Client'), index=True,
                        nullable=False)
    agent_id = Column(String(100), index=True, nullable=False)


def init_app(app: Flask) -> None:
    """Set configuration defaults and attach session to the application."""
    db.init_app(app)

    @app.teardown_request
    def teardown_request(exception) -> None:
        if exception:
            db.session.rollback()
        db.session.remove()

    @app.teardown_appcontext
    def teardown_appcontext(*args, **kwargs) -> None:
        db.session.rollback()
        db.session.remove()


@retry(Unavailable, tries=3, backoff=2)
def create_all() -> None:
    """Create all tables in the agent database."""
    try:
        db.create_all(bind='agent')
    except OperationalError as e:
        raise Unavailable('Caught op error') from e


@retry(Unavailable, tries=10, backoff=2)
def tables_exist() -> bool:
    """Determine whether or not these database tables exist."""
    try:
        db.session.query(text("1")).from_statement(text("SELECT 1 FROM checkpoint limit 1")).all()
        db.session.query(text("1")).from_statement(text("SELECT 1 FROM process_status_events limit 1")).all()
    except (NoSuchTableError, OperationalError) as e:
        return False
    except Exception as e:
        raise Unavailable('Caught op error') from e
    return True


@retry(Unavailable, tries=3, backoff=2)
def get_latest_position(shard_id: str) -> str:
    """Get the latest checkpointed position."""
    try:
        result = db.session.query(Checkpoint.position) \
            .filter(Checkpoint.shard_id == shard_id) \
            .order_by(Checkpoint.id.desc()) \
            .first()
        if result is None:
            return
        position, = result
    except OperationalError as e:
        raise Unavailable('Caught op error') from e
    return position


@retry(Unavailable, tries=3, backoff=2)
def store_position(position: str, shard_id: str) -> None:
    """Store a new checkpoint position."""
    try:
        db.session.add(Checkpoint(position=position, shard_id=shard_id))
        db.session.commit()
    except OperationalError as e:
        db.session.rollback()
        raise Unavailable('Caught op error') from e


def store_event(event: AddProcessStatus) -> None:
    """Store an :class:`.AddProcessStatus` event."""
    try:
        db.session.add(ProcessStatusEvent(
            created=event.created,
            event_id=event.event_id,
            submission_id=event.submission_id,
            process_id=event.process_id,
            process=event.process,
            status=event.status,
            reason=event.reason,
            agent_type=event.creator.agent_type,
            agent_id=event.creator.native_id
        ))
        db.session.commit()
    except OperationalError as e:
        db.session.rollback()
        raise Unavailable('Caught op error') from e


def await_connection(max_wait: int = -1) -> None:
    """Wait for the database to be available."""
    logger.info('Waiting for database server to be available')
    wait = 2
    start = time.time()
    while True:
        if max_wait > 0 and time.time() - start >= max_wait:
            raise Unavailable('Failed to connect in %i seconds', max_wait)

        if is_available():
            break
        logger.info(f'...waiting {wait} seconds...')
        time.sleep(wait)
        wait *= 2


def is_available(**kwargs: Any) -> bool:
    """Check our connection to the database."""
    try:
        db.session.query(text("1")).from_statement(text("SELECT 1")).all()
    except Exception as e:
        logger.error('Agent: Encountered an error talking to database: %s', e)
        return False
    return True
