"""Private functions in support of the database service."""

from typing import Tuple, Optional, List, Type, Dict
from contextlib import contextmanager
from itertools import groupby
from datetime import datetime
import copy

from api.domain.submission import Submission, SubmissionMetadata, \
    Classification, License
from api.domain.annotation import Comment
from api.domain.agent import UserAgent, System, Client, Agent, agent_factory
# from api.domain.rule import EventRule, RuleCondition, RuleConsequence

from . import models
from .models import db


def _comment_data_to_domain(db_comment: models.Comment) -> Comment:
    return Comment(
        created=db_comment.created,
        creator=Agent.from_dict(db_comment.creator),
        proxy=Agent.from_dict(db_comment.proxy) if db_comment.proxy else None,
        body=db_comment.body
    )


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
