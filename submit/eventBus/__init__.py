"""."""

from datetime import datetime
from typing import List, Optional, Callable, Tuple, Iterable
from submit.domain.event import Event, CreateSubmissionEvent
from submit.domain.rule import EventRule
from submit.domain.submission import Submission
from submit.services import database

from .util import MultiKeyLookup, _apply_rules, _play_events


CALLBACKS = MultiKeyLookup()


def _emit(e: Event):
    callbacks = CALLBACKS.lookup(event_type=e.event_type,
                                 submission_id=e.submission_id,
                                 agent_id=e.creator.agent_id)
    for callback in callbacks:
        callback(e)


# def listen_for(event_type: str, submission_id: int = None,
#                agent_id: str = None, callback: Callable = None):
#     if event_type is type:
#         event_type = event_type.get_event_type()
#     CALLBACKS.register(callback,
#                        event_type=event_type,
#                        submission_id=submission_id,
#                        agent_id=agent_id)

def get_submission(submission_id: int) -> Tuple[Submission, List[Event]]:
    return get_submission_at_timestamp(submission_id, datetime.now())



def get_submission_at_timestamp(submission_id: int, timestamp: datetime) \
        -> Tuple[Submission, List[Event]]:
    """
    Get a :class:`.Submission` in state at a specific point in time.

    Parameters
    ----------
    submission_id : int
        The unique identifier for the submission.
    timestamp : datetime
        The target datetime.

    Returns
    -------
    :class:`.Submission`
        The state of the submission at the target datetime.
    list
        The set of :class:`.Event`s applied.
    """
    events = database.get_events_thru_timestamp(submission_id, timestamp)
    return _play_events(events, [])


def get_submission_at_event(submission_id: int, event_id: str) \
        -> Tuple[Submission, List[Event]]:
    """
    Get a :class:`.Submission` in state after a specific event has occurred.

    Parameters
    ----------
    submission_id : int
        The unique identifier for the submission.

    Returns
    -------
    :class:`.Submission`
        The state of the submission after the target event and all preceding
        events have been applied.
    list
        The set of :class:`.Event`s applied.
    """
    return _play_events(database.get_events_thru(submission_id, event_id), [])


def apply_events(*events: Event, submission_id: Optional[int] = None) \
        -> Submission:
    """
    Apply a set of events for a submission.

    This will persist any new events to the database, along with the final
    state of the submission.

    Paramters
    ---------
    events : :class:`.Event`
        Events to apply and persist.
    submission_id : int
        The unique ID for the submission, if available. If not provided, it is
        expected that ``events`` includes a :class:`CreateSubmissionEvent`.

    Returns
    -------
    :class:`.Submission`
        The state of the submission after all events (including rule-derived
        events) have been applied. Updated with the submission ID, if newly
        created.
    """
    if len(events) == 0:
        raise ValueError('Must pass at least one event')

    # Do some sanity checks before proceeding.
    for event in events:
        assert isinstance(event, Event)
        if submission_id is not None:
            if event.submission_id is None:
                event.submission_id = submission_id
            assert event.submission_id == submission_id

    # We want to play events from the beginning.
    if submission_id is not None:
        existing_events = database.get_events_for_submission(submission_id)
    else:
        existing_events = []
    combined = existing_events + list(events)

    # Load any relevant event rules for this submission.
    rules = database.get_rules_for_submission(submission_id)

    # Calculate the state of the submission from old and new events.
    submission, combined = _play_events(combined, rules)

    # Update the submission ID to ensure existing entry is updated.
    if submission.submission_id is None:
        submission.submission_id = submission_id    # May still be None.

    # Persist in database; submission ID is updated after transaction.
    submission = database.store_events(*combined, submission=submission)

    for event in combined:
        event.submission_id = submission.submission_id
    return submission
