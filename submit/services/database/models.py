"""ORM classes for the datastore."""

from sqlalchemy import Column, DateTime, ForeignKey, Boolean, Integer, String,\
    Text, JSON
from sqlalchemy.exc import OperationalError
from flask_sqlalchemy import SQLAlchemy, Model
from sqlalchemy.orm import relationship

db = SQLAlchemy()


class Agent(db.Model):  # type: ignore
    __tablename__ = 'agent'

    agent_identifier = Column(String(32), primary_key=True)
    """MD5 hexdigest of [agent_type]:[agent_id] bytestring."""

    agent_type = Column(String(255))
    """One of ``User``, ``System``, ``Client``."""

    agent_id = Column(String(255))
    """Unique identifier for an agent. Might be an URI."""


class Event(db.Model):  # type: ignore
    __tablename__ = 'event'

    event_id = Column(String(32), primary_key=True)
    event_type = Column(String(255))
    creator_id = Column(ForeignKey('agent.agent_identifier'), index=True)
    created = Column(DateTime)
    data = Column(JSON)
    submission_id = Column(ForeignKey('submission.submission_id'), index=True)

    creator = relationship("Agent")
    submission = relationship("Submission", back_populates="events")


class Comment(db.Model):  # type: ignore
    __tablename__ = 'comment'

    comment_id = Column(String(32), primary_key=True)
    creator_id = Column(ForeignKey('agent.agent_identifier'), index=True)
    creator = relationship("Agent")
    created = Column(DateTime)
    body = Column(Text)
    submission_id = Column(ForeignKey('submission.submission_id'), index=True)
    submission = relationship("Submission", back_populates="comments")


class Submission(db.Model):  # type: ignore
    __tablename__ = 'submission'

    submission_id = Column(Integer, primary_key=True)
    created = Column(DateTime)
    title = Column(String(255))
    abstract = Column(String(255))
    active = Column(Boolean, default=True)
    finalized = Column(Boolean, default=False)
    archive = Column(String(255), index=True)
    creator_id = Column(ForeignKey('agent.agent_identifier'), index=True)

    events = relationship("Event", order_by=Event.created,
                          back_populates="submission")
    comments = relationship("Comment", order_by=Comment.created,
                            back_populates="submission")
    creator = relationship("Agent")


class Rule(db.Model):  # type: ignore
    __tablename__ = 'rule'

    rule_id = Column(Integer, primary_key=True)
    created = Column(DateTime)
    creator_id = Column(ForeignKey('agent.agent_identifier'), index=True)
    creator = relationship("Agent")
    active = Column(Boolean, default=True)

    submission_id = Column(ForeignKey('submission.submission_id'), index=True)
    condition_event_type = Column(String(255))
    condition_extra = Column(JSON)

    consequence_event_type = Column(String(255))
    consequence_event_data = Column(JSON)
