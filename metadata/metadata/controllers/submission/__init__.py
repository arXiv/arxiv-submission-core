"""Controllers for the metadata API."""

import json
from functools import wraps
from datetime import datetime
import copy
from arxiv.base import logging
from typing import Tuple, List, Callable, Optional

from flask import url_for, current_app
from werkzeug.exceptions import NotFound, BadRequest, InternalServerError

from arxiv import status
from events.domain.agent import Agent, agent_factory, System
from events.domain import Event
from events.domain.submission import Submission, Classification, License, \
    SubmissionMetadata
import events as ev

from metadata.controllers import util
from . import handlers

logger = logging.getLogger(__name__)


Response = Tuple[dict, int, dict]


def _get_agents(headers: dict, user_data: dict, client_data: dict) \
        -> Tuple[Agent, Agent, Optional[Agent]]:
    user = ev.User(
        native_id=user_data['user_id'],
        email=user_data['email']
    )
    client = ev.Client(native_id=client_data['client_id'])
    on_behalf_of = headers.get('X-On-Behalf-Of')
    if on_behalf_of is not None:
        proxy = user
        user = ev.User(on_behalf_of, '', '')
    else:
        proxy = None
    return user, client, proxy


@util.validate_request('schema/resources/submission.json')
def create_submission(data: dict, headers: dict, user_data: dict,
                      client_data: dict, token: str) -> Response:
    """
    Create a new submission.

    Implements the hook for :meth:`sword.SWORDCollection.add_submission`.

    Parameters
    ----------
    data : dict
        Deserialized compact JSON-LD document.
    headers : dict
        Request headers from the client.

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
    user, client, proxy = _get_agents(headers, user_data, client_data)
    logger.debug(f'User: {user}; client: {client}, proxy: {proxy}')
    agents = dict(creator=user, client=client, proxy=proxy)
    create = ev.CreateSubmission(creator=user, client=client, proxy=proxy)
    events = handlers.handle_submission(data, agents)
    try:
        submission, events = ev.save(create, *events)
    except ev.InvalidEvent as e:
        raise BadRequest(str(e)) from e
    except ev.SaveError as e:
        logger.error('Problem interacting with database: (%s) %s',
                     str(type(e)), str(e))
        raise InternalServerError('Problem interacting with database') from e

    response_headers = {
        'Location': url_for('submission.get_submission',
                            submission_id=submission.submission_id)
    }
    return submission.to_dict(), status.HTTP_201_CREATED, response_headers


def get_submission(submission_id: str, user: Optional[str] = None,
                   client: Optional[str] = None,
                   token: Optional[str] = None) -> Response:
    """Retrieve the current state of a submission."""
    try:
        submission, events = ev.load(submission_id)
    except ev.NoSuchSubmission as e:
        raise NotFound('Submission not found') from e
    except Exception as e:
        logger.error('Unhandled exception: (%s) %s', str(type(e)), str(e))
        raise InternalServerError('Encountered unhandled exception') from e
    return submission.to_dict(), status.HTTP_200_OK, {}


@util.validate_request('schema/resources/submission.json')
def update_submission(data: dict, headers: dict, user_data: dict,
                      client_data: dict, token: str, submission_id: str) \
        -> Response:
    """Update the submission."""
    user, client, proxy = _get_agents(headers, user_data, client_data)
    agents = dict(creator=user, client=client, proxy=proxy)
    events = handlers.handle_submission(data, agents)
    try:
        submission, events = ev.save(*events, submission_id=submission_id)
    except ev.NoSuchSubmission as e:
        raise NotFound(f"No submission found with id {submission_id}")
    except ev.InvalidEvent as e:
        raise BadRequest(str(e)) from e
    except ev.SaveError as e:
        raise InternalServerError('Problem interacting with database') from e

    response_headers = {
        'Location': url_for('submission.get_submission', creator=user,
                            submission_id=submission.submission_id)
    }
    return submission.to_dict(), status.HTTP_200_OK, response_headers
