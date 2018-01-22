"""Controllers for the external API."""

import json
import jsonschema
from functools import wraps
from datetime import datetime
import copy
from typing import Tuple, List, Callable, Optional

from flask import url_for, current_app

from submit import status
from submit.domain.event import event_factory, Event
from submit.domain.agent import Agent, agent_factory
from submit.domain.submission import Submission, Classification, License, \
    SubmissionMetadata
from submit.services import database
from submit import eventBus

Response = Tuple[dict, int, dict]

NO_SUCH_ARCHIVE = {'reason': 'No such archive'}, status.HTTP_404_NOT_FOUND, {}
NO_USER_OR_CLIENT = (
    {'reason': 'Neither client nor user is set'},
    status.HTTP_400_BAD_REQUEST,
    {}
)
METADATA_FIELDS = [
    ('title', 'title'),
    ('abstract', 'abstract'),
    ('doi', 'identifier'),
    ('msc_class', 'msc_class'),
    ('acm_class', 'acm_class'),
    ('report_num', 'report_num'),
    ('journal_ref', 'journal_ref'),
    ('authors', 'author')
]


def validate_request(schema_path: str) -> Callable:
    """Generate a decorator that validates the request body."""
    with open(schema_path) as f:
        schema = json.load(f)

    def _decorator(func: Callable) -> Callable:
        @wraps(func)
        def _wrapper(body: dict, headers: dict, files: dict=None, **extra):
            try:
                jsonschema.validate(body, schema)
            except jsonschema.exceptions.ValidationError as e:
                # A summary of the exception is on the first line of the repr.
                msg = str(e).split('\n')[0]
                return (
                    {'reason': 'Metadata validation failed: %s' % msg},
                    status.HTTP_400_BAD_REQUEST,
                    {}
                )
            return func(body, headers, files=files, **extra)
        return _wrapper
    return _decorator


def _get_agents(extra: dict) -> Tuple[Optional[Agent], Optional[Agent]]:
    """Get user and/or API client responsible for the request."""
    user = extra.get('user')
    client = extra.get('client')
    user_agent = agent_factory('UserAgent', user) if user else None
    client_agent = agent_factory('Client', client) if client else None
    if user_agent:
        return user_agent, client_agent
    return client_agent, client_agent


def _update_classification(body: dict, creator: Agent,
                           submission_id: Optional[int] = None) -> List[Event]:
    """Generate events for primary and secondary classification."""
    events = []
    if 'primary_classification' in body:
        events.append(
            event_factory(
                'SetPrimaryClassificationEvent',
                creator=creator,
                submission_id=submission_id,
                group=body['primary_classification']['group'],
                archive=body['primary_classification']['archive'],
                category=body['primary_classification']['category'],
            )
        )
    for classification_datum in body.get('secondary_classification', []):
        events.append(event_factory(
            'AddSecondaryClassificationEvent',
            creator=creator,
            submission_id=submission_id,
            group=classification_datum['group'],
            archive=classification_datum['archive'],
            category=classification_datum['category'],
        ))
    return events


def _update_metadata(metadata: dict, creator: Agent, proxy: Optional[Agent],
                     submission_id: Optional[int] = None) -> Event:
    """Generate an :class:`.UpdateMetadataEvent`."""
    return event_factory(
        'UpdateMetadataEvent',
        creator=creator,
        proxy=proxy,
        submission_id=submission_id,
        metadata=[
            (field, metadata[key])
            for field, key in METADATA_FIELDS
            if key in metadata
        ]
    )


def _generate_update_events(body: dict, creator: Agent, proxy: Optional[Agent],
                            submission_id: Optional[int]=None) -> List[Event]:
    """Generate events to update submission."""
    events = []
    if 'submitter_is_author' in body:
        events.append(
            event_factory('AssertAuthorshipEvent', creator=creator,
                          proxy=proxy,
                          submission_id=submission_id,
                          submitter_is_author=body['submitter_is_author'])
        )
    if 'license' in body:
        events.append(
            event_factory('SelectLicenseEvent', creator=creator,
                          proxy=proxy,
                          submission_id=submission_id,
                          license_uri=body['license'])
        )

    if body.get('submitter_accepts_policy'):
        events.append(event_factory('AcceptArXivPolicyEvent',
                                    creator=creator,
                                    proxy=proxy,
                                    submission_id=submission_id))

    # Generate both primary and secondary classifications.
    events += _update_classification(body, creator, submission_id)

    if 'metadata' in body:
        events.append(
            _update_metadata(body['metadata'], creator, proxy, submission_id)
        )
    return events


def _metadata_state(metadata: Optional[SubmissionMetadata]) -> dict:
    """Generate metadata sub-state for a :class:`.Submission`."""
    if not metadata:
        return {}
    return {
        'title': metadata.title,
        'abstract': metadata.abstract,
        'author': metadata.authors,
        'doi': metadata.doi,
        'msc_class': metadata.msc_class,
        'acm_class': metadata.acm_class,
        'report_num': metadata.report_num,
        'journal_ref': metadata.journal_ref,
    }


def _license_state(license: Optional[License]) -> Optional[dict]:
    """Generate license sub-state for a :class:`.Submission`."""
    if not license:
        return
    return {
        'uri': license.uri,
        'name': license.name
    }


def _classification_state(classification: Optional[Classification]) \
        -> Optional[dict]:
    """Generate classification sub-state for a :class:`.Submission`."""
    if not classification:
        return
    return {
        'group': classification.group,
        'archive': classification.archive,
        'category': classification.category
    }


def _agent_state(agent: Optional[Agent]) -> dict:
    if agent is None:
        return
    return {
        'agent_type': agent.agent_type,
        'identifier': agent.agent_identifier
    }


def _submission_state(submission: Submission) -> dict:
    """Generate an external state document from a :class:`.Submission`."""
    return {
        'submission_id': str(submission.submission_id),
        'metadata': _metadata_state(submission.metadata),
        'submitter_is_author': submission.submitter_is_author,
        'submitter_accepts_policy': submission.submitter_accepts_policy,
        'license': _license_state(submission.license),
        'primary_classification': (
            _classification_state(submission.primary_classification)
        ),
        'secondary_classification': [
            _classification_state(clsxn) for clsxn
            in submission.secondary_classification
        ],
        'active': submission.active,
        'finalized': submission.finalized,
        'published': submission.published,
        'creator': _agent_state(submission.creator),
        'proxy': _agent_state(submission.proxy),
        'owner': _agent_state(submission.owner),
    }


def _event_state(event: Event) -> dict:
    event_data = {'data': event.to_dict()}
    for field in ['created', 'event_type']:
        if field in event_data['data']:
            event_data[field] = copy.deepcopy(event_data['data'][field])
            del event_data['data'][field]
    if event.proxy:
        event_data['proxy'] = _agent_state(event.proxy)
        del event_data['data']['proxy']
    event_data['creator'] = _agent_state(event.creator)
    del event_data['data']['creator']
    return event_data


def _agent_is_owner(submission_id: int, agent: Agent) -> bool:
    return agent == database.get_submission_owner(submission_id)


@validate_request('schema/submission.json')
def create_submission(body: dict, headers: dict, files: dict=None, **extra) \
        -> Response:
    """
    Create a new submission.

    Implements the hook for :meth:`sword.SWORDCollection.add_submission`.

    Parameters
    ----------
    body : dict
        Deserialized compact JSON-LD document.
    headers : dict
        Request headers from the client.
    files : dict
        Any files attached to the submission.
    extra : dict
        Additional parameters, e.g. from the URL path.

    Returns
    -------
    dict
        Response data.
    int
        HTTP status code.
    dict
        Headers to add to the response.
    """
    creator, proxy = _get_agents(extra)
    if not creator:
        return NO_USER_OR_CLIENT

    events = [
        event_factory('CreateSubmissionEvent', creator=creator, proxy=proxy,
                      created=datetime.now())
    ]
    events += _generate_update_events(body, creator, proxy)
    try:
        submission, _ = eventBus.emit(*events)
    except eventBus.exceptions.InvalidEvent as e:
        return (
            {
                'reason': 'Payload validation failed: %s' % e
            },
            status.HTTP_400_BAD_REQUEST,
            {}
        )

    response_headers = {
        'Location': url_for('submit.get_submission',
                            submission_id=submission.submission_id)
    }
    return (
        _submission_state(submission),
        status.HTTP_202_ACCEPTED,
        response_headers
    )


def get_submission(body: dict, headers: dict, files: dict=None, **extra) \
        -> Response:
    """Retrieve the current state of a submission."""
    submission_id = extra.get('submission_id')
    submission, _ = eventBus.get_submission(submission_id)
    return _submission_state(submission), status.HTTP_200_OK, {}


def update_submission(body: dict, headers: dict, files: dict=None, **extra) \
        -> Response:
    """Update the submission."""
    user, client = _get_agents(extra)
    if not user:
        return NO_USER_OR_CLIENT

    submission_id = extra['submission_id']

    # Get the submission state from the eventBus, so that we are working with
    #  the freshest possible state.
    submission, _ = eventBus.get_submission(submission_id)
    # TODO: need to reimplement delegations to support easier lookups.
    if not user == submission.owner:  # and user not in submission.delegates:
        return (
            {'reason': 'Not authorized to update this submission'},
            status.HTTP_403_FORBIDDEN,
            {}
        )

    events = _generate_update_events(body, user, client, submission_id)
    try:
        submission, _ = eventBus.emit(*events, submission_id=submission_id)
    except eventBus.exceptions.InvalidEvent as e:
        return (
            {
                'reason': 'Payload validation failed: %s' % e
            },
            status.HTTP_400_BAD_REQUEST,
            {}
        )

    response_headers = {
        'Location': url_for('submit.get_submission', creator=user,
                            submission_id=submission.submission_id)
    }
    return (
        _submission_state(submission),
        status.HTTP_202_ACCEPTED,
        response_headers
    )


def get_submission_log(body: dict, headers: dict, files: dict=None, **extra) \
        -> Response:
    """Get a log of events on a specific submission."""
    user, client = _get_agents(extra)
    if not user:
        return NO_USER_OR_CLIENT

    submission_id = extra['submission_id']

    events = eventBus.get_events(submission_id)
    response_data = {
        'events': [_event_state(e) for e in events],
        'submission_id': submission_id
    }
    return response_data, status.HTTP_200_OK, {}
