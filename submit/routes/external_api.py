"""Provides External REST API."""

import logging
from functools import wraps
from flask.json import jsonify
from flask import Blueprint, current_app, redirect, request, url_for, g

from submit import authorization, status
from submit.controllers import submission


logger = logging.getLogger(__name__)

blueprint = Blueprint('submit', __name__, url_prefix='/submit')


def json_response(func):
    """Generate a wrapper for routes that JSONifies the response body."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        r_body, r_status, r_headers = func(*args, **kwargs)
        return jsonify(r_body), r_status, r_headers
    return wrapper


@blueprint.route('/', methods=['GET'])
@json_response
def service() -> tuple:
    """Say hello."""
    return {'hi': 'there'}, status.HTTP_200_OK, {}


@blueprint.route('/', methods=['POST'])
@authorization.scoped(authorization.WRITE)
@json_response
def create_submission() -> tuple:
    """Accept new submissions."""
    return submission.create_submission(
        request.get_json(),
        dict(request.headers),
        user=g.user,
        client=g.client
    )


@blueprint.route('/<string:submission_id>/', methods=['GET'])
@authorization.scoped(authorization.READ)
@json_response
def get_submission(submission_id: str) -> tuple:
    """Get the current state of a submission."""
    return submission.get_submission(
        request.get_json(),
        dict(request.headers),
        submission_id=submission_id,
        user=g.user,
        client=g.client
    )


@blueprint.route('/<string:submission_id>/history/', methods=['GET'])
@authorization.scoped(authorization.READ)
@json_response
def get_submission_history(submission_id: str) -> tuple:
    """Get the event log for a submission."""
    return submission.get_submission_log(
        request.get_json(),
        dict(request.headers),
        submission_id=submission_id,
        user=g.user,
        client=g.client,
        scope=g.scope
    )


@blueprint.route('/<string:submission_id>/', methods=['POST'])
@authorization.scoped(authorization.WRITE)
@json_response
def update_submission(submission_id: str) -> tuple:
    """Update the submission."""
    return submission.update_submission(
        request.get_json(),
        dict(request.headers),
        submission_id=submission_id,
        user=g.user,
        client=g.client
    )
