"""Controllers for the metadata API."""

import json
from functools import wraps
from datetime import datetime
import copy
from arxiv.base import logging
from typing import Tuple, List, Callable, Optional, Dict
from dataclasses import asdict

from flask import url_for, current_app
from werkzeug.exceptions import NotFound, BadRequest, InternalServerError

from arxiv.integration.api import status
from arxiv.submission.domain.agent import Agent, agent_factory, System
from arxiv.submission.domain import Event
from arxiv.submission.domain.submission import Submission, Classification, \
    License, SubmissionMetadata
import arxiv.submission as ev

import arxiv.users.domain as auth_domain

from metadata.controllers import util
from . import handlers

logger = logging.getLogger(__name__)


Response = Tuple[dict, int, dict]


@util.validate_request('schema/resources/submission.json')
def create_submission(data: dict, headers: dict, agents: Dict[str, Agent],
                      token: Optional[str]) -> Response:
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
    logger.debug(f'Received request to create submission, {agents}')
    create = ev.CreateSubmission(**agents)
    events = handlers.handle_submission(data, agents)
    try:
        submission, events = ev.save(create, *events)
    except (ev.InvalidEvent, ev.InvalidStack) as e:
        raise BadRequest(str(e)) from e
    except ev.SaveError as e:
        logger.error('Problem interacting with database: (%s) %s',
                     str(type(e)), str(e))
        raise InternalServerError('Problem interacting with database') from e

    response_headers = {
        'Location': url_for('submission.get_submission',
                            submission_id=submission.submission_id)
    }
    return asdict(submission), status.CREATED, response_headers


def get_submission(submission_id: int,
                   agents: Optional[Dict[str, Agent]] = None,
                   token: Optional[str] = None) -> Response:
    """Retrieve the current state of a submission."""
    try:
        submission, events = ev.load(submission_id)
    except ev.NoSuchSubmission as e:
        raise NotFound('Submission not found') from e
    except Exception as e:
        logger.error('Unhandled exception: (%s) %s', str(type(e)), str(e))
        raise InternalServerError('Encountered unhandled exception') from e
    return asdict(submission), status.OK, {}


@util.validate_request('schema/resources/submission.json')
def update_submission(data: dict, headers: dict, agents: Dict[str, Agent],
                      token: str, submission_id: int) -> Response:
    """Update the submission."""
    events = handlers.handle_submission(data, agents)
    if not data:
        raise BadRequest('No data in request body')

    try:
        submission, events = ev.save(*events, submission_id=submission_id)
    except ev.NoSuchSubmission as e:
        raise NotFound(f"No submission found with id {submission_id}")
    except (ev.InvalidEvent, ev.InvalidStack) as e:
        raise BadRequest(str(e)) from e
    except ev.SaveError as e:
        raise InternalServerError('Problem interacting with database') from e

    response_headers = {
        'Location': url_for('submission.get_submission',
                            creator=agents['creator'].native_id,
                            submission_id=submission.submission_id)
    }
    return asdict(submission), status.OK, response_headers
