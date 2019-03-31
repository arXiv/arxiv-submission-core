"""Lightweight database integration for checkpointing."""

from typing import Optional
from datetime import datetime
from pytz import UTC

from werkzeug.local import LocalProxy
from flask_sqlalchemy import SQLAlchemy

from sqlalchemy import BigInteger, Column, DateTime, Enum, ForeignKey, \
    ForeignKeyConstraint, Index, \
    Integer, SmallInteger, String, Table, text, Text
from sqlalchemy.dialects.mysql import DATETIME

from arxiv.submission.domain.event import AddProcessStatus
from ..rules import Rule
from ..process import Process

db: SQLAlchemy = SQLAlchemy()


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
    process_type = Column(String(100), index=True, nullable=False)
    process_id = Column(String(100), index=True, nullable=False)
    process_status = Column(String(50), index=True, nullable=True)
    reason = Column(Text, nullable=True)
    agent_type = Column(Enum('System', 'User', 'Client'), index=True,
                        nullable=False)
    agent_id = Column(String(100), index=True, nullable=False)


def init_app(app: Optional[LocalProxy]) -> None:
    """Set configuration defaults and attach session to the application."""
    db.init_app(app)


def create_all() -> None:
    """Create all tables in the agent database."""
    db.create_all(bind='agent')


def tables_exist() -> bool:
    """Determine whether or not these database tables exist."""
    return db.engine.dialect.has_table(db.engine, 'checkpoint')


def get_latest_position(shard_id: str) -> str:
    """Get the latest checkpointed position."""
    position, = db.session.query(Checkpoint.position) \
        .filter(Checkpoint.shard_id == shard_id) \
        .order_by(Checkpoint.id.desc()) \
        .first()
    return position


def store_position(position: str, shard_id: str) -> None:
    """Store a new checkpoint position."""
    db.session.add(Checkpoint(position=position, shard_id=shard_id))
    db.session.commit()


def store_event(event: AddProcessStatus) -> None:
    """Store an :class:`.AddProcessStatus` event."""
    db.session.add(ProcessStatusEvent(
        created=event.created,
        event_id=event.event_id,
        submission_id=event.submission_id,
        process_type=event.process_type,
        process_id=event.process_id,
        process_status=event.process_status,
        reason=event.reason,
        agent_type=event.creator.agent_type,
        agent_id=event.creator.native_id
    ))
    db.session.commit()
