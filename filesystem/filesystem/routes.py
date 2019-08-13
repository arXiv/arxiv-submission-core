"""Request routing."""

import io
from typing import IO

from flask import Blueprint, Response, request, jsonify, make_response, \
    current_app
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge

from . import controllers

api = Blueprint('filesystem', __name__)


@api.route('/status', methods=['GET', 'HEAD'])
def service_status() -> Response:
    """Status check endpoint."""
    data, code, head = controllers.service_status()
    response: Response = make_response(jsonify(data), code, head)
    return response


@api.route('/<int:submission_id>/source', methods=['POST'])
def deposit_source(submission_id: int) -> Response:
    """Deposit a source package for a submission."""
    stream = request.stream
    data, code, head = controllers.deposit_source(submission_id, get_body())
    response: Response = make_response(jsonify(data), code, head)
    return response


@api.route('/<int:submission_id>/source', methods=['HEAD'])
def check_source_exists(submission_id: int) -> Response:
    """Determine whether a source package for a submission is present."""
    data, code, head = controllers.check_source_exists(submission_id)
    response: Response = make_response(jsonify(data), code, head)
    return response


@api.route('/<int:submission_id>/preview', methods=['POST'])
def deposit_preview(submission_id: int) -> Response:
    """Deposit a preview PDF for a submission."""
    stream = request.stream
    data, code, head = controllers.deposit_preview(submission_id, get_body())
    response: Response = make_response(jsonify(data), code, head)
    return response


@api.route('/<int:submission_id>/preview', methods=['HEAD'])
def check_preview_exists(submission_id: int) -> Response:
    """Determine whether a preview PDF for a submission is present."""
    data, code, head = controllers.check_preview_exists(submission_id)
    response: Response = make_response(jsonify(data), code, head)
    return response


def get_body() -> IO[bytes]:
    """Get a ``BytesIO``-like object wrapping the request body."""
    stream: IO[bytes]
    if request.headers.get('Content-type') is not None:
        length = int(request.headers.get('Content-length', 0))
        if length == 0:
            raise BadRequest('Body empty or content-length not set')
        max_length = int(current_app.config['MAX_PAYLOAD_SIZE_BYTES'])
        if length > max_length:
            raise RequestEntityTooLarge(f'Body exceeds size of {max_length}')
        stream = io.BytesIO(request.data)
    else:
        # DANGER! request.stream will ONLY be available if (a) the content-type
        # header is not passed and (b) we have not accessed the body via any
        # other means, e.g. ``.data``, ``.json``, etc.
        stream = request.stream   # type: ignore
    return stream