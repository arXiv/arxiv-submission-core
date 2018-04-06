"""Provides External REST API."""

from arxiv.base import logging
from typing import Callable, Union
from functools import wraps
from flask.json import jsonify
from flask import Blueprint, current_app, redirect, request, url_for, g, \
    Response

from authorization.decorators import scoped
from arxiv import status
from api.controllers import submission

logger = logging.getLogger(__name__)

blueprint = Blueprint('submit', __name__, url_prefix='/submit')


def json_response(func):
    """Generate a wrapper for routes that JSONifies the response body."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        r_body, r_status, r_headers = func(*args, **kwargs)
        return jsonify(r_body), r_status, r_headers
    return wrapper


@blueprint.route('/', methods=['POST'])
@json_response
@scoped('submission:write')
def create_submission() -> Union[str, Response]:
    """Accept new submissions."""
    return submission.create_submission(
        request.get_json(),
        dict(request.headers),
        user=g.user,
        client=g.client,
        token=g.token
    )


@blueprint.route('/<string:submission_id>/', methods=['GET'])
@json_response
@scoped('submission:read')
def get_submission(submission_id: str) -> tuple:
    """Get the current state of a submission."""
    return submission.get_submission(
        submission_id,
        user=g.user,
        client=g.client,
        token=g.token
    )

#
# @blueprint.route('/<string:submission_id>/history/', methods=['GET'])
# @authorization.scoped(authorization.READ)
# @json_response
# def get_submission_history(submission_id: str) -> tuple:
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


@blueprint.route('/<string:submission_id>/', methods=['POST'])
@json_response
@scoped('submission:write')
def update_submission(submission_id: str) -> tuple:
    """Update the submission."""
    return submission.update_submission(
        submission_id,
        request.get_json(),
        dict(request.headers),
        user=g.user,
        client=g.client,
        token=g.token
    )
