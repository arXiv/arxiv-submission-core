"""Controllers for the external API."""

import json
from functools import wraps
from datetime import datetime
import copy
import logging
from typing import Tuple, List, Callable, Optional

from flask import url_for, current_app

from arxiv import status
from api.domain.agent import Agent, agent_factory, System
from api.domain.submission import Submission, Classification, License, \
    SubmissionMetadata
from api.services import database, events

from . import util

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


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
    ('journal_ref', 'journal_ref')
]


def _is_authorized(submission_id: Optional[str], user: Optional[Agent] = None,
                   client: Optional[Agent] = None) -> bool:
    if submission_id is None:
        return True
    agents = database.get_submission_agents(submission_id)
    return any([
        user == agents['owner'] or client == agents['owner'],
        user in agents['delegates'],
        type(client) is System
    ])


def _get_agents(extra: dict) -> Tuple[Optional[Agent], Optional[Agent]]:
    """Get user and/or API client responsible for the request."""
    user = extra.get('user')
    client = extra.get('client')
    user_agent = agent_factory('UserAgent', user) if user else None
    client_agent = agent_factory('Client', client) if client else None
    if user_agent:
        return user_agent, client_agent
    return client_agent, client_agent


def _update_submission(submission_id: str, body: dict, token: str) \
        -> Submission:
    """Update a submission."""

    if 'submitter_is_author' in body:
        submission = events.assert_authorship(submission_id,
                                              body['submitter_is_author'],
                                              token=token)
    if 'license' in body:
        submission = events.select_license(submission_id, body['license'])

    if body.get('submitter_accepts_policy'):
        submission = events.accept_policy(submission_id, token=token)

    # Generate both primary and secondary classifications.
    if 'primary_classification' in body:
        category = body['primary_classification']['category']
        submission = events.set_primary_classification(submission_id, category,
                                                       token=token)

    for classification_datum in body.get('secondary_classification', []):
        category = classification_datum['category']
        submission = events.add_secondary_classification(submission_id,
                                                         category, token=token)

    if 'metadata' in body:
        metadata = [
            (field, body['metadata'][key])
            for field, key in METADATA_FIELDS
            if key in body['metadata']
        ]
        submission = events.update_metadata(submission_id, metadata,
                                            token=token)
    return submission


def _agent_is_owner(submission_id: int, agent: Agent) -> bool:
    return agent == database.get_submission_owner(submission_id)


def create_submission(body: dict, headers: dict, files: Optional[dict] = None,
                      user: Optional[str] = None, client: Optional[str] = None,
                      token: Optional[str] = None) -> Response:
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
    logger.debug('Received request to create submission')
    if not user and not client:
        logger.debug('Neither user nor client set')
        return NO_USER_OR_CLIENT

    if not _is_authorized(None, user, client):
        logger.debug('Not authorized')
        return {}, status.HTTP_403_FORBIDDEN, {}

    try:
        submission = events.create_submission(token=token)
        submission = _update_submission(submission.submission_id, body, token)
    except events.ServiceDown as e:
        raise
        return (
            {'reason': 'There was a problem connecting to another service'},
            status.HTTP_503_SERVICE_UNAVAILABLE, {}
        )
    response_headers = {
        'Location': url_for('submit.get_submission',
                            submission_id=submission.submission_id)
    }
    return (
        util.serialize_submission(submission),
        status.HTTP_202_ACCEPTED,
        response_headers
    )


def get_submission(submission_id: str, user: Optional[str] = None,
                   client: Optional[str] = None,
                   token: Optional[str] = None) -> Response:
    """Retrieve the current state of a submission."""
    submission = database.get_submission(submission_id)
    return util.serialize_submission(submission), status.HTTP_200_OK, {}


def update_submission(submission_id: str, body: dict, headers: dict,
                      files: dict=None, user: Optional[str] = None,
                      client: Optional[str] = None,
                      token: Optional[str] = None) -> Response:
    """Update the submission."""
    if not user and not client:
        return NO_USER_OR_CLIENT

    if not _is_authorized(submission_id, user, client):
        return {}, status.HTTP_403_FORBIDDEN, {}

    submission = _update_submission(submission_id, body, token)

    response_headers = {
        'Location': url_for('submit.get_submission', creator=user,
                            submission_id=submission.submission_id)
    }
    return (
        util.serialize_submission(submission),
        status.HTTP_202_ACCEPTED,
        response_headers
    )


# def get_submission_log(body: dict, headers: dict, files: dict=None, **extra)\
#         -> Response:
#     """Get a log of events on a specific submission."""
#     user, client = _get_agents(extra)
#     if not user:
#         return NO_USER_OR_CLIENT
#
#     submission_id = extra['submission_id']
#
#     events = eventBus.get_events(submission_id)
#     response_data = {
#         'events': [util.serialize_event(e) for e in events],
#         'submission_id': submission_id
#     }
#     return response_data, status.HTTP_200_OK, {}
