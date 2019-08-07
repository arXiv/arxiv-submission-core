"""Provides External REST API."""

from typing import Callable, Union
from functools import wraps
from werkzeug.exceptions import Unauthorized, Forbidden, BadRequest
from flask.json import jsonify
from flask import Blueprint, current_app, redirect, request, g, Response

from arxiv.users.auth.decorators import scoped
from arxiv.users.auth import scopes
from arxiv.integration.api import status
from arxiv.base import logging

from arxiv.submission.domain import User, Client, Classification
from metadata.controllers import submission

logger = logging.getLogger(__name__)

blueprint = Blueprint('submission', __name__, url_prefix='')


@blueprint.before_request
def get_agents() -> None:
    """Determine submission roles from the active authenticated session."""
    session = request.auth
    logger.debug(f'Got session {session}')
    proxy: Optional[User] = None
    if not session.client:
        raise Unauthorized('No authenticated client found')

    client = Client(session.client.client_id)
    endorsements = session.authorizations.endorsements
    if request.auth.user:
        creator = User(session.user.user_id, session.user.email,
                       endorsements=endorsements)

    else:
        creator = User(session.client.owner_id, '',
                       endorsements=endorsements)
    request.agents = {'proxy': proxy, 'creator': creator, 'client': client}


def json_response(func):
    """Generate a wrapper for routes that JSONifies the response body."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        r_body, r_status, r_headers = func(*args, **kwargs)
        response = jsonify(r_body)
        response.status_code = r_status
        response.headers.extend(r_headers)
        return response
    return wrapper


@blueprint.route('/', methods=['POST'])
@json_response
@scoped(scopes.CREATE_SUBMISSION)
def create_submission() -> Union[str, Response]:
    """Accept new submissions."""
    data = request.get_json()
    if data is None:
        raise BadRequest('No data in request')
    return submission.create_submission(
        data,
        dict(request.headers),
        agents=request.agents,
        token=request.environ.get('token')
    )


@blueprint.route('/<int:submission_id>/', methods=['GET'])
@json_response
@scoped(scopes.VIEW_SUBMISSION)
def get_submission(submission_id: int) -> tuple:
    """Get the current state of a submission."""
    return submission.get_submission(
        submission_id,
        agents=request.agents,
        token=request.environ.get('token')
    )

#
# @blueprint.route('/<int:submission_id>/history/', methods=['GET'])
# @authorization.scoped(authorization.READ)
# @json_response
# def get_submission_history(submission_id: int) -> tuple:
#     """Get the event log for a submission."""
#     return submission.get_submission_log(
#         request.get_json(),
#         dict(request.headers),
#         submission_id=submission_id,
#         user=g.user,
#         client=g.client,
#         scope=g.scope,
#         token=g.token
#     )


@blueprint.route('/<int:submission_id>/', methods=['POST'])
@json_response
@scoped(scopes.EDIT_SUBMISSION)
def update_submission(submission_id: int) -> tuple:
    """Update the submission."""
    data = request.get_json()
    if data is None:
        raise BadRequest('No data in request')
    return submission.update_submission(
        data,
        dict(request.headers),
        agents=request.agents,
        token=request.environ.get('token'),
        submission_id=submission_id
    )
