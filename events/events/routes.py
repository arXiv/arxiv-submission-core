"""Provides an internal API for submission events/commands."""

from typing import Tuple, Dict, Any
from functools import wraps
from flask.json import jsonify
from flask import Blueprint, request, g

from arxiv.util import schema
from arxiv import status

from authorization.decorators import scoped

from events import controllers

Response = Tuple[Dict[str, Any], int, Dict[str, str]]

blueprint = Blueprint('events', __name__, url_prefix='/events')


def json_response(func):
    """Generate a wrapper for routes that JSONifies the response body."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        r_body, r_status, r_headers = func(*args, **kwargs)
        return jsonify(r_body), r_status, r_headers
    return wrapper


@blueprint.route('/create_submission/', methods=['POST'])
@json_response
@scoped('submission:write')
@schema.validate_request('schema/resources/event.json')
def register_create_submission_event() -> Response:
    """Register and apply new submission event."""
    request_data = request.get_json()
    return controllers.register_event(
        request_data.get('submission_id', None),
        'CreateSubmissionEvent',
        request_data,
        user=g.user,
        client=g.client,
        scope=g.scope
    )


@blueprint.route('/submission/<string:sub_id>/events/', methods=['GET'])
@json_response
@scoped('submission:read')
def retrieve_submission_events(sub_id: str) -> Response:
    """Retrieve event log for a submission."""
    return controllers.retrieve_events(
        submission_id=sub_id,
        user=g.user,
        client=g.client,
        scope=g.scope
    )


@blueprint.route('/submission/<string:sub_id>/events/<string:event_id>/',
                 methods=['GET'])
@json_response
@scoped('submission:read')
def retrieve_submission_event(sub_id: str, event_id: str) -> Response:
    """Retrieve a specific submission event."""
    return controllers.retrieve_event(
        sub_id,
        event_id=event_id,
        user=g.user,
        client=g.client,
        scope=g.scope
    )


@blueprint.route('/submission/<string:sub_id>/events/<string:event_id>/state/',
                 methods=['GET'])
@json_response
@scoped('submission:read')
def retrieve_submission_at_event(sub_id: str, event_id: str) -> Response:
    """Retrieve the state of a submission at a specific event."""
    return controllers.retrieve_submission_at_event(
        submission_id=sub_id,
        event_id=event_id,
        user=g.user,
        client=g.client,
        scope=g.scope
    )


@blueprint.route('/submission/<string:sub_id>/<event_type:event_type>/',
                 methods=['POST'])
@json_response
@scoped('submission:write')
@schema.validate_request('schema/resources/event.json')
def register_submission_event(sub_id: str, event_type: str) -> Response:
    """Register and apply new submission event."""
    return controllers.register_event(
        sub_id,
        event_type,
        request.get_json(),
        user=g.user,
        client=g.client,
        scope=g.scope
    )
