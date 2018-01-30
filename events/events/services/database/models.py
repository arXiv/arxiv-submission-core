"""ORM classes for the datastore."""

from sqlalchemy import Column, DateTime, ForeignKey, Boolean, Integer, String,\
    Text, JSON
from sqlalchemy.exc import OperationalError
from flask_sqlalchemy import SQLAlchemy, Model
from sqlalchemy.orm import relationship
from sqlalchemy.ext.indexable import index_property

db = SQLAlchemy()


class Event(db.Model):  # type: ignore
    __tablename__ = 'event'

    event_id = Column(String(40), primary_key=True)
    event_type = Column(String(255))
    proxy = Column(JSON)
    proxy_id = index_property('proxy', 'agent_identifier')

    creator = Column(JSON)
    creator_id = index_property('creator', 'agent_identifier')

    created = Column(DateTime)
    data = Column(JSON)
    submission_id = Column(ForeignKey('submission.submission_id'), index=True)

    submission = relationship("Submission", back_populates="events")


class Comment(db.Model):  # type: ignore
    __tablename__ = 'comment'

    comment_id = Column(String(40), primary_key=True)

    proxy = Column(JSON)
    proxy_id = index_property('proxy', 'agent_identifier')

    creator = Column(JSON)
    creator_id = index_property('creator', 'agent_identifier')

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
    authors = Column(JSON)

    submitter_contact_verified = Column(Boolean, default=False)
    submitter_is_author = Column(Boolean, default=True)
    submitter_accepts_policy = Column(Boolean, default=False)

    primary_classification_category = Column(String(20))
    secondary_classification = Column(JSON)

    license_name = Column(String(255))
    license_uri = Column(String(255))

    active = Column(Boolean, default=True)
    finalized = Column(Boolean, default=False)
    published = Column(Boolean, default=False)

    events = relationship("Event", order_by=Event.created,
                          back_populates="submission")
    comments = relationship("Comment", order_by=Comment.created,
                            back_populates="submission")

    owner = Column(JSON)
    owner_id = index_property('owner', 'agent_identifier')

    proxy = Column(JSON)
    proxy_id = index_property('proxy', 'agent_identifier')

    creator = Column(JSON)
    creator_id = index_property('creator', 'agent_identifier')

    delegations = Column(JSON)


class Rule(db.Model):  # type: ignore
    __tablename__ = 'rule'

    rule_id = Column(Integer, primary_key=True)
    created = Column(DateTime)
    proxy = Column(JSON)
    proxy_id = index_property('proxy', 'agent_identifier')

    creator = Column(JSON)
    creator_id = index_property('creator', 'agent_identifier')

    active = Column(Boolean, default=True)

    submission_id = Column(ForeignKey('submission.submission_id'), index=True)
    condition_event_type = Column(String(255))
    condition_extra = Column(JSON)

    consequence_event_type = Column(String(255))
    consequence_event_data = Column(JSON)
