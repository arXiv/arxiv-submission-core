"""Controllers for the external API."""

import json
import jsonschema
from functools import wraps
from datetime import datetime
from typing import Tuple, List, Callable, Optional

from flask import url_for, current_app

from submit import status
from submit.domain.event import event_factory, Event
from submit.domain.agent import Agent, agent_factory
from submit.domain.submission import Submission
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
    ('msc_class', 'mscClass'),
    ('acm_class', 'acmClass'),
    ('report_num', 'reportNum'),
    ('journal_ref', 'journalRef')
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
    events = [event_factory(
        'SetPrimaryClassificationEvent',
        creator=creator,
        submission_id=submission_id,
        group=body['primary_classification']['group'],
        archive=body['primary_classification']['archive'],
        category=body['primary_classification']['category'],
    )]
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


def _update_metadata(metadata: dict, creator: Agent,
                     submission_id: Optional[int] = None) -> Event:
    """Generate an :class:`.UpdateMetadataEvent`."""
    return event_factory(
        'UpdateMetadataEvent',
        creator=creator,
        submission_id=submission_id,
        metadata=[
            (field, metadata[key])
            for field, key in METADATA_FIELDS
            if key in metadata
        ]
    )


def _update_submission(body: dict, creator: Agent,
                       submission_id: Optional[int]=None) -> List[Event]:
    """Generate events to update submission"""
    events = []
    if 'submitterIsAuthor' in body:
        events.append(
            event_factory('AssertAuthorshipEvent', creator=creator,
                          submission_id=submission_id,
                          submitter_is_author=body['submitterIsAuthor'])
        )
    if 'license' in body:
        events.append(
            event_factory('SelectLicenseEvent', creator=creator,
                          submission_id=submission_id,
                          license_uri=body['license'])
        )

    if body.get('submitterAcceptsPolicy'):
        events.append(event_factory('AcceptArXivPolicyEvent',
                                    creator=creator,
                                    submission_id=submission_id))

    # Generate both primary and secondary classifications.
    events += _update_classification(body, creator, submission_id)

    events.append(_update_metadata(body['metadata'], creator, submission_id))
    return events


def _metadata_state(submission: Submission) -> dict:
    """Generate metadata sub-state for a :class:`.Submission`."""
    if not submission.metadata:
        return {}
    return {
        'title': submission.metadata.title,
        'abstract': submission.metadata.abstract,
        'authors': [
            {
                'name': author.name,
                'email': author.email,
                'identifier': author.identifier
            } for author in submission.metadata.authors
        ],
        'doi': submission.metadata.doi,
        'mscClass': submission.metadata.msc_class,
        'acmClass': submission.metadata.acm_class,
        'reportNum': submission.metadata.report_num,
        'journalRef': submission.metadata.journal_ref,
    }


def _license_state(submission: Submission) -> Optional[dict]:
    """Generate license sub-state for a :class:`.Submission`."""
    if not submission.license:
        return
    return {
        'uri': submission.license.uri,
        'name': submission.license.name
    }


def _primary_classification_state(submission: Submission) -> Optional[dict]:
    """Generate primary classification sub-state for a :class:`.Submission`."""
    if not submission.primary_classification:
        return
    return {
        'group': submission.primary_classification.group,
        'archive': submission.primary_classification.archive,
        'category': submission.primary_classification.category
    }


def _secondry_classification_state(submission: Submission) -> List[dict]:
    """Generate secondary classification sub-state a :class:`.Submission`."""
    if not submission.secondary_classification:
        return []
    return [
        {
            'group': classification.group,
            'archive': classification.archive,
            'category': classification.category
        } for classification in submission.secondary_classification
    ]


def _submission_state_response(submission: Submission) -> dict:
    """Generate am external state document from a :class:`.Submission`."""
    return {
        'submission_id': submission.submission_id,
        'metadata': _metadata_state(submission),
        'submitterIsAuthor': submission.submitter_is_author,
        'submitterAcceptsPolicy': submission.submitter_accepts_policy,
        'license': _license_state(submission),
        'primary_classification': _primary_classification_state(submission),
        'secondary_classification': _secondry_classification_state(submission),
        'active': submission.active,
        'finalized': submission.finalized,
        'published': submission.published
    }


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
    events += _update_submission(body, creator)
    submission, _ = eventBus.emit(*events)

    response_headers = {
        'Location': url_for('submit.get_submission',
                            submission_id=submission.submission_id)
    }
    return (
        _submission_state_response(submission),
        status.HTTP_202_ACCEPTED,
        response_headers
    )


def get_submission(body: dict, headers: dict, files: dict=None, **extra) \
        -> Response:
    """Retrieve the current state of a submission."""
    submission_id = extra.get('submission_id')
    submission, _ = eventBus.get_submission(submission_id)
    return _submission_state_response(submission), status.HTTP_200_OK, {}


def update_submission(body: dict, headers: dict, files: dict=None, **extra) \
        -> Response:
    """Update the submission."""
    creator, proxy = _get_agents(extra)
    if not creator:
        return NO_USER_OR_CLIENT

    metadata = body['metadata']
    submission_id = extra['submission_id']

    events = _update_submission(metadata, creator, proxy, submission_id)
    submission, _ = eventBus.emit(*events)
    response_headers = {
        'Location': url_for('submit.get_submission', creator=creator,
                            submission_id=submission.submission_id)
    }
    return (
        _submission_state_response(submission),
        status.HTTP_202_ACCEPTED,
        response_headers
    )
