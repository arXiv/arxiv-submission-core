"""
Submission event service controllers.

The functions in this module assume primary responsibility for filling
client requests. The :mod:`events.routes` module dispatches handling of client
requests by calling these functions.

Each function should return a three-tuple of request data (``dict``),
an HTTP status code (``int``), and extra headers (``dict``). It is the
responsibility of the :mod:`events.routes` module to serialize the response
(e.g. to JSON).
"""
from datetime import datetime
from functools import wraps
from typing import Tuple, Dict, Any, Optional, List
from arxiv import status

from events.services import database
from events.domain import event_factory, agent_factory, Agent, Data, Event, \
    System, Submission, EventRule, CreateSubmissionEvent
from events.domain.event import InvalidEvent

from . import util

Response = Tuple[Dict[str, Any], int, Dict[str, str]]


def _authorized(submission_id: Optional[str], user: Optional[Agent] = None,
                client: Optional[Agent] = None) -> bool:
    if submission_id is None:
        return True
    agents = database.get_submission_agents(submission_id)
    return any([
        user == agents['owner'] or client == agents['owner'],
        user in agents['delegates'],
        type(client) is System
    ])


def protect(func):
    """
    Ensure that the requesting user and/or client is authorized.

    Expects ``func`` to accept ``submission_id`` as its first positional
    argument, and ``user`` and ``client`` as keyword arguments.
    """
    @wraps(func)
    def wrapper(submission_id, *args, **kwargs):
        if 'user' in kwargs:
            user_agent = agent_factory('UserAgent', kwargs.pop('user'))
        else:
            user_agent = None
        if 'client'in kwargs:
            client_agent = agent_factory('Client', kwargs.pop('client'))
        else:
            client_agent = None

        if _authorized(submission_id, user=user_agent, client=client_agent):
            return func(submission_id, *args, user=user_agent,
                        client=client_agent, **kwargs)
        return {}, status.HTTP_403_FORBIDDEN, {}
    return wrapper


@protect    # Non-creation events require authorization against the submission.
def register_event(submission_id: Optional[str], event_type: str, data: dict,
                   user: Optional[Agent] = None,
                   client: Optional[Agent] = None,
                   scope: List[str] = []) -> Response:
    """
    Register a new event.

    Parameters
    ----------
    data : dict
    submission_id : str

    Returns
    -------
    :class:`.Response`
    """
    if 'event_type' in data:
        if data.pop('event_type') != event_type:
            return {
                'reason': 'Explicit event type in data does not match endpoint'
            }, status.HTTP_400_BAD_REQUEST, {}

    event = event_factory(event_type, creator=user, proxy=client, **data)
    if event.write_scope not in scope:
        return {}, status.HTTP_403_FORBIDDEN, {}
    submission, events = _emit(event, submission_id=submission_id)
    submission_data = util.serialize_submission(submission)
    submission_data['events'] = [util.serialize_event(ev) for ev in events]
    return submission_data, status.HTTP_201_CREATED, {}


# TODO: implement filtering on user/client scope.
@protect
def retrieve_events(submission_id: str, user: Optional[Agent] = None,
                    client: Optional[Agent] = None,
                    scope: List[str] = []) -> Response:
    """Retrieve all events for a submission."""
    # An existant submission will have at least one (creation) event.
    events = database.get_events_for_submission(submission_id)
    if len(events) == 0:
        return {}, status.HTTP_404_NOT_FOUND, {}

    response_data = {
        'submission_id': submission_id,
        'events': [util.serialize_event(ev) for ev in events]
    }
    return response_data, status.HTTP_200_OK, {}


@protect
def retrieve_event(submission_id: str, event_id: str,
                   user: Optional[Agent] = None,
                   client: Optional[Agent] = None,
                   scope: List[str] = []) -> Response:
    """
    Retrieve an event by ID.

    Parameters
    ----------
    event_id : str

    """
    event = database.get_event(event_id)
    if not event:
        return {}, status.HTTP_404_NOT_FOUND, {}
    return util.serialize_event(event), status.HTTP_200_OK, {}


@protect
def get_submission_at_event(submission_id: int, event_id: str,
                            user: Optional[Agent] = None,
                            client: Optional[Agent] = None,
                            scope: List[str] = []) \
        -> Tuple[Submission, List[Event]]:
    """
    Get a :class:`.Submission` in state after a specific event has occurred.

    Parameters
    ----------
    submission_id : int
        The unique identifier for the submission.

    Returns
    -------

    """
    submission, _ = _play_events(
        database.get_events_thru(submission_id, event_id),
        []
    )
    return util.serialize_submission(submission), status.HTTP_200_OK, {}


def _emit(*events: Event, submission_id: Optional[str] = None) \
        -> Tuple[Submission, List[Event]]:
    """
    Register a set of new :class:`.Event`s for a submission.

    This will persist the events to the database, along with the final
    state of the submission, and generate external notification(s) on the
    appropriate channels.

    Paramters
    ---------
    events : :class:`.Event`
        Events to apply and persist.
    submission_id : int
        The unique ID for the submission, if available. If not provided, it is
        expected that ``events`` includes a :class:`.CreateSubmissionEvent`.

    Returns
    -------
    :class:`.Submission`
        The state of the submission after all events (including rule-derived
        events) have been applied. Updated with the submission ID, if a
        :class:`.CreateSubmissionEvent` was included.
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

    # Update the submission ID to ensure the existing submission is updated.
    if submission.submission_id is None:
        submission.submission_id = submission_id    # May still be None.

    # Persist in database; submission ID is updated after transaction.
    submission = database.store_events(*combined, submission=submission)

    for event in combined:
        event.submission_id = submission.submission_id
    return submission, combined


def _apply_rules(submission: Submission, event: Event,
                 rules: List[EventRule]) -> List[Event]:
    """Generate new event(s) by applying rules to a submission event."""
    def _apply(rule: EventRule) -> bool:
        return rule.condition(submission, event)
    return [rule.consequence(submission, event)
            for rule in filter(_apply, rules)]


def _play_events(events: List[Event], rules: List[EventRule],
                 submission: Optional[Submission] = None) \
         -> Tuple[Submission, List[Event]]:
    """Apply a set of events in order."""
    events = sorted(events, key=lambda e: e.created)

    # Need either a creation event or a submission state from which to start.
    if not isinstance(events[0], CreateSubmissionEvent) and submission is None:
        raise RuntimeError('Creation missing and submission not provided')

    extra_events: List[Event] = []    # Generated by applied rules.
    for event in events:
        if not event.valid:
            event.validate()
            raise InvalidEvent(event)

        submission = event.apply(submission)

        if event.committed:   # Don't create duplicate rule-derived events.
            continue

        # Any rule-derived events should be applied before moving on.
        _extra = _apply_rules(submission, event, rules)
        if len(_extra) > 0:
            submission, _extra = _play_events(_extra, rules, submission)
            extra_events += _extra
    return submission, events + extra_events
