"""Private functions in support of the database service."""

from typing import Tuple, Optional, List, Type, Dict
from contextlib import contextmanager
from itertools import groupby
from datetime import datetime
import copy

from events.domain.submission import Submission, SubmissionMetadata, \
    Classification, License
from events.domain.annotation import Comment
from events.domain.agent import UserAgent, System, Client, Agent, agent_factory
from events.domain.event import Event, CreateSubmissionEvent, event_factory
from events.domain.rule import EventRule, RuleCondition, RuleConsequence

from . import models
from .models import db


@contextmanager
def transaction():
    """Context manager for database transaction."""
    try:
        yield
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise RuntimeError('Ack! %s' % e) from e


def _event_data_to_domain(event_data: models.Event) -> Event:
    """Instantiate an :class:`.Event` using event data from the db."""
    # There are several fields that we want to set explicitly.
    _skip = ['creator', 'proxy', 'submission_id', 'created', 'event_type']
    data = {key: value for key, value in event_data.data.items()
            if key not in _skip}
    data.update(dict(committed=True))  # So that we don't store an event twice.

    return event_factory(
        event_data.event_type,
        creator=Agent.from_dict(event_data.creator),
        proxy=Agent.from_dict(event_data.proxy) if event_data.proxy else None,
        submission_id=event_data.submission_id,
        created=event_data.created,
        **data
    )


def _comment_data_to_domain(db_comment: models.Comment) -> Comment:
    return Comment(
        created=db_comment.created,
        creator=Agent.from_dict(db_comment.creator),
        proxy=Agent.from_dict(db_comment.proxy) if db_comment.proxy else None,
        body=db_comment.body
    )


def _submission_domain_to_data(submission: Submission,
                               db_submission: models.Submission) \
                               -> models.Submission:
    db_submission.title = submission.metadata.title
    db_submission.abstract = submission.metadata.abstract
    db_submission.authors = submission.metadata.authors
    db_submission.created = submission.created
    db_submission.finalized = submission.finalized
    db_submission.published = submission.published
    db_submission.active = submission.active
    db_submission.primary_classification_category = (
        getattr(submission.primary_classification, 'category', '')
    )
    db_submission.secondary_classification = [
        clsfn.to_dict() for clsfn in submission.secondary_classification
    ]
    db_submission.license_name = getattr(submission.license, 'name', None)
    db_submission.creator = submission.creator.to_dict()
    db_submission.proxy = (
        submission.proxy.to_dict() if submission.proxy else None
    )
    db_submission.owner = submission.owner.to_dict()
    db_submission.delegations = {
        ident: dele.to_dict() for ident, dele in submission.delegations.items()
    }
    return db_submission


def _license_data_to_domain(name: Optional[str], uri: Optional[str]) \
        -> Optional[License]:
    if not uri:
        return
    return License(name=name, uri=uri)


def _submission_data_to_domain(db_submission: models.Submission) -> Submission:
    return Submission(
        submission_id=db_submission.submission_id,
        metadata=SubmissionMetadata(
            title=db_submission.title,
            abstract=db_submission.abstract,
            authors=db_submission.authors
        ),
        created=db_submission.created,
        proxy=Agent.from_dict(db_submission.proxy),
        creator=Agent.from_dict(db_submission.creator),
        owner=Agent.from_dict(db_submission.owner),
        active=db_submission.active,
        finalized=db_submission.finalized,
        published=db_submission.published,
        comments={
            db_comment.comment_id: _comment_data_to_domain(db_comment)
            for db_comment in db_submission.comments
        },
        primary_classification=Classification(
            category=db_submission.primary_classification_category
        ),
        secondary_classification=[
            Classification(**cdata) for cdata
            in db_submission.secondary_classification
        ],
        submitter_contact_verified=db_submission.submitter_contact_verified,
        submitter_accepts_policy=db_submission.submitter_accepts_policy,
        submitter_is_author=db_submission.submitter_is_author,
        license=_license_data_to_domain(
            db_submission.license_name,
            db_submission.license_uri
        )
    )


# def _update_submission_delegations(submission: Submission,
#                                    db_submission: models.Submission) -> None:
#     """Bring delegations on a submission up to date in the database."""
#     for db_delegation in db_submission.delegations:
#         if db_delegation.delegation_id not in submission.delegations.keys():
#             db.session.delete(db_delegation)
#     db_delegations = {
#         dbd.delegation_id: dbd for dbd in db_submission.delegations
#     }
#     for delegation_id, delegation in submission.delegations.items():
#         db_delegation = db_delegations.get(delegation_id)
#         if not db_delegation:
#             db_delegation = models.Delegation(
#                 delegation_id=delegation.delegation_id,
#                 creator=delegation.creator.to_dict(),
#                 delegate=delegation.delegate),
#                 created=delegation.created,
#                 submission=db_submission
#             )
#             db.session.add(db_delegation)


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
            db_comment = models.Comment(
                comment_id=comment.comment_id,
                creator=comment.creator.to_dict(),
                proxy=comment.proxy.to_dict() if comment.proxy else None,
                created=comment.created,
                submission=db_submission,
                body=comment.body
            )
            db.session.add(db_comment)
        elif db_comment.body != comment.body:
            db_comment.body = comment.body
            db.session.add(db_comment)


def _store_submission(submission: Submission,
                      db_submission: Optional[models.Submission] = None) \
                      -> models.Submission:
    """Update or create a :class:`.models.Submission` in the database."""
    if submission.submission_id is None:
        db_submission = models.Submission()
    else:
        db_submission = db.session.query(models.Submission)\
            .get(submission.submission_id)
        if db_submission is None:
            raise RuntimeError("Submission ID is set, but can't find data")
    db_submission = _submission_domain_to_data(submission, db_submission)
    _update_submission_comments(submission, db_submission)
    # _update_submission_delegations(submission, db_submission)
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
        creator=event.creator.to_dict(),
        proxy=event.proxy.to_dict() if event.proxy else None,
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
        creator=Agent.from_dict(db_rule.creator),
        proxy=Agent.from_dict(db_rule.proxy),
        condition=_rule_condition_data_to_domain(db_rule),
        consequence=_rule_consequence_data_to_domain(db_rule),
    )
