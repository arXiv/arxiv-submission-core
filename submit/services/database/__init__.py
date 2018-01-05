"""Provides persistence for domain objects."""

from typing import Tuple, Optional, List, Type, Dict
from contextlib import contextmanager
from itertools import groupby
from datetime import datetime
import copy

from submit.domain.submission import Submission
from submit.domain.agent import UserAgent, System, Client, Agent, agent_factory
from submit.domain.event import Event, CreateSubmissionEvent, event_factory
from submit.domain.rule import EventRule

from . import models, util
from .models import db


def get_rules_for_submission(submission_id: int) -> List[EventRule]:
    """Load rules that might apply to a specific submission."""
    rule_data = db.session.query(models.Rule) \
        .filter(models.Rule.submission_id is None
                or models.Rule.submission_id == submission_id)
    return [util._rule_data_to_domain(db_rule) for db_rule in rule_data]


def get_events_for_submission(submission_id: int) -> List[Event]:
    """Get all :class:`.Events` for a submission."""
    event_data = db.session.query(models.Event) \
        .filter(models.Event.submission_id == submission_id) \
        .order_by(models.Event.created)
    return [util._event_data_to_domain(datum) for datum in event_data]


def get_events_thru_timestamp(submission_id: int,
                              timestamp: datetime) -> List[Event]:
    """Retrieve events for a submission up through a point in time."""
    event_data = db.session.query(models.Event) \
        .filter(models.Event.submission_id == submission_id) \
        .filter(models.Event.created <= timestamp) \
        .order_by(models.Event.created)
    return [util._event_data_to_domain(datum) for datum in event_data]


def get_events_thru(submission_id: int, event_id: str) -> List[Event]:
    """Retrieve events for a submission up through a specific event."""
    events = get_events_for_submission(submission_id)
    i = [e.event_id for e in events].index(event_id)
    return events[:i+1]


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
    with util.transaction():
        # We need a reference to this row for the event rows, so we add it
        # first.
        db_submission = util._store_submission(submission)
        for event in events:
            if event.committed:   # Don't create duplicate event entries.
                continue
            db_event = util._store_event(event)
            db_event.submission = db_submission    # Will be updated on commit.
            event.committed = True
    submission.submission_id = db_submission.submission_id
    return submission


def init_app(app):
    """Set configuration defaults and attach session to the application."""
    db.init_app(app)
