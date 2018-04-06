"""Controllers for the external API."""

import json
from functools import wraps
from datetime import datetime
import copy
import logging    # TODO: use arxiv.base.logging when arxiv-base==0.5.1 is out.
from typing import Tuple, List, Callable, Optional

from flask import url_for, current_app

from arxiv import status
from api.domain.agent import Agent, agent_factory, System
from api.domain.submission import Submission, Classification, License, \
    SubmissionMetadata
from api.services import database
import events as ev

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
    user_agent = ev.User(user) if user else None
    client_agent = ev.Client(client) if client else None
    if user_agent:
        return user_agent, client_agent
    return client_agent, client_agent


def _update_submission(body: dict, agents: dict) -> Submission:
    """
    Generate :class:`.ev.Event`(s) to update a :class:`Submission`.
    """

    new_events = []
    if 'submitter_is_author' in body:
        new_events.append(
            ev.AssertAuthorshipEvent(
                submitter_is_author=body['submitter_is_author'],
                **agents,
            )
        )
    if 'license' in body:
        new_events.append(
            ev.SelectLicenseEvent(
                license_name=body['license'].get('name'),
                license_uri=body['license']['uri'],
                **agents
            )
        )

    if 'submitter_accepts_policy' in body and body['submitter_accepts_policy']:
        new_events.append(ev.AcceptPolicyEvent(**agents))

    # Generate both primary and secondary classifications.
    if 'primary_classification' in body:
        category = body['primary_classification']['category']
        new_events.append(
            ev.SetPrimaryClassificationEvent(category=category, **agents)
        )

    for classification_datum in body.get('secondary_classification', []):
        category = classification_datum['category']
        new_events.append(
            ev.AddSecondaryClassificationEvent(category=category, **agents)
        )

    if 'metadata' in body:
        metadata = [
            (field, body['metadata'][key])
            for field, key in SubmissionMetadata.FIELDS
            if key in body['metadata']
        ]
        new_events.append(ev.UpdateMetadataEvent(metadata=metadata, **agents))
    return new_events


def create_submission(body: dict, headers: dict,
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

    agents = dict(creator=user, proxy=client)
    new_events = []

    new_events.append(ev.CreateSubmissionEvent(**agents))
    new_events += _update_submission(body, agents)
    submission = ev.save(*new_events)
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
                      user: Optional[str] = None,
                      client: Optional[str] = None,
                      token: Optional[str] = None) -> Response:
    """Update the submission."""
    if not user and not client:
        return NO_USER_OR_CLIENT

    if not _is_authorized(submission_id, user, client):
        return {}, status.HTTP_403_FORBIDDEN, {}

    submission = _update_submission(body, dict(creator=user, proxy=agent))

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
