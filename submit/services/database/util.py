"""Private functions in support of the database service."""

from typing import Tuple, Optional, List, Type, Dict
from contextlib import contextmanager
from itertools import groupby
from datetime import datetime
import copy

from submit.domain.submission import Submission
from submit.domain.agent import UserAgent, System, Client, Agent, agent_factory
from submit.domain.event import Event, CreateSubmissionEvent, event_factory
from submit.domain.rule import EventRule, RuleCondition, RuleConsequence

from . import models
from .models import db

_db_agent_cache: Dict[str, models.Agent] = {}


@contextmanager
def transaction():
    """Context manager for database transaction."""
    try:
        yield
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise RuntimeError('Ack! %s' % e) from e


def _agent_data_to_domain(agent_data: models.Agent) -> Agent:
    """Instantiate an :class:`.Agent` using agent data from the db."""
    return agent_factory(agent_data.agent_type, agent_data.agent_id)


def _event_data_to_domain(event_data: models.Event) -> Event:
    """Instantiate an :class:`.Event` using event data from the db."""
    data = {key: value for key, value in event_data.data.items()
            if key not in ['creator', 'submission_id', 'created']}
    data.update(dict(committed=True))  # So that we don't store an event twice.
    return event_factory(
        event_data.event_type,
        creator=_agent_data_to_domain(event_data.creator),
        submission_id=event_data.submission_id,
        created=event_data.created,
        **data
    )


def _submission_domain_to_data(submission: Submission,
                               db_submission: models.Submission) \
                               -> models.Submission:
    db_agent = _get_or_create_dbagent(submission.creator)
    db_submission.title = submission.metadata.title
    db_submission.abstract = submission.metadata.abstract
    db_submission.finalized = submission.finalized
    db_submission.active = submission.active
    db_submission.creator = db_agent
    db_submission.archive = submission.archive
    return db_submission


def _update_submission_comments(submission: Submission,
                                db_submission: models.Submission) -> None:
    """Bring comments on a submission up to date in the database."""
    for db_comment in db_submission.comments:
        if db_comment.comment_id not in submission.comments.keys():
            db.session.delete(db_comment)
    db_comments = {dbc.comment_id: dbc for dbc in db_submission.comments}
    for comment_id, comment in submission.comments.items():
        db_comment = db_comments.get(comment_id)
        if not db_comment:
            creator = _get_or_create_dbagent(comment.creator)
            db_comment = models.Comment(
                comment_id=comment.comment_id,
                creator=creator,
                created=comment.created,
                submission=db_submission,
                body=comment.body
            )
            db.session.add(db_comment)
        elif db_comment.body != comment.body:
            db_comment.body = comment.body
            db.session.add(db_comment)


def _get_or_create_dbagent(agent: Agent) -> models.Agent:
    """Get or create the database entry for an :class:`.Agent` instance."""
    # We may make several calls for the same agent, so check the cache first
    #  to avoid unnecessary database calls.
    if agent.agent_identifier in _db_agent_cache:
        return _db_agent_cache[agent.agent_identifier]

    # Check the DB for an existing entry for this agent.
    db_agent = db.session.query(models.Agent).get(agent.agent_identifier)
    if db_agent is not None:
        _db_agent_cache[agent.agent_identifier] = db_agent
        return db_agent

    # Create a new entry in the database for this agent.
    db_agent = models.Agent(
        agent_identifier=agent.agent_identifier,
        agent_type=agent.agent_type,
        agent_id=agent.native_id
    )
    db.session.add(db_agent)
    _db_agent_cache[agent.agent_identifier] = db_agent
    return db_agent


def _store_submission(submission: Submission,
                      db_submission: Optional[models.Submission] = None) \
                      -> models.Submission:
    """Update or create a :class:`.models.Submission` in the database."""
    # if db_submission is None:
    if submission.submission_id is None:
        db_submission = models.Submission()
    else:
        db_submission = db.session.query(models.Submission)\
            .get(submission.submission_id)
        if db_submission is None:
            raise RuntimeError("Submission ID is set, but can't find data")
    db_submission = _submission_domain_to_data(submission, db_submission)
    _update_submission_comments(submission, db_submission)
    db.session.add(db_submission)
    return db_submission


def _store_event(event: Event) -> models.Event:
    """Create an :class:`.models.Event` in the database."""
    if event.committed:
        raise RuntimeError('Event is already committed')
    db_event = models.Event(
        event_type=event.event_type,
        event_id=event.event_id,
        data=event.to_dict(),
        created=event.created,
        creator=_get_or_create_dbagent(event.creator),
        submission_id=event.submission_id
    )
    db.session.add(db_event)
    return db_event


def _rule_condition_data_to_domain(db_rule: models.Rule) -> RuleCondition:
    return RuleCondition(
        submission_id=db_rule.submission_id,
        event_type=db_rule.condition_event_type,
        extra_condition=db_rule.condition_extra
    )


def _rule_consequence_data_to_domain(db_rule: models.Rule) -> RuleConsequence:
    return RuleConsequence(
        event_type=db_rule.consequence_event_type,
        event_data=db_rule.consequence_event_data
    )


def _rule_data_to_domain(db_rule: models.Rule) -> EventRule:
    return EventRule(
        rule_id=db_rule.rule_id,
        creator=_agent_data_to_domain(db_rule.creator),
        condition=_rule_condition_data_to_domain(db_rule),
        consequence=_rule_consequence_data_to_domain(db_rule),
    )
