"""Provides External REST API."""

import logging
from typing import Callable
from functools import wraps
from flask.json import jsonify
from flask import Blueprint, current_app, redirect, request, url_for, g

from authorization.decorators import scoped
from arxiv import status
from arxiv.util import schema
from api.controllers import submission


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

blueprint = Blueprint('submit', __name__, url_prefix='/submit')


def json_response(func):
    """Generate a wrapper for routes that JSONifies the response body."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        r_body, r_status, r_headers = func(*args, **kwargs)
        return jsonify(r_body), r_status, r_headers
    return wrapper


def validate_request(schema_path: str) -> Callable:
    """Generate a decorator that validates the request body."""
    validate = schema.load(schema_path)

    def _decorator(func: Callable) -> Callable:
        @wraps(func)
        def _wrapper(*args, **kwargs):
            data = request.get_json()
            logger.debug('Validating payload: %s', str(data))
            try:
                validate(data)
            except schema.ValidationError as e:
                # A summary of the exception is on the first line of the repr.
                msg = str(e).split('\n')[0]
                logger.debug('Invalid request: %s', msg)
                return (
                    {
                        'reason': 'Metadata validation failed: %s' % msg,
                        'detail': str(e).replace('\n', ' ')
                    },
                    status.HTTP_400_BAD_REQUEST,
                    {}
                )
            return func(*args, **kwargs)
        return _wrapper
    return _decorator


@blueprint.route('/', methods=['GET'])
@json_response
def service() -> tuple:
    """Say hello."""
    return {'hi': 'there'}, status.HTTP_200_OK, {}


@blueprint.route('/', methods=['POST'])
@json_response
@scoped('submission:write')
@validate_request('schema/resources/submission.json')
def create_submission() -> tuple:
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
