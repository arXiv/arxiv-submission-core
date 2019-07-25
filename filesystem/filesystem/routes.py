"""Request routing."""

from flask import Blueprint, Response, request, jsonify, make_response
from . import controllers

api = Blueprint('filesystem', __name__)


@api.route('/status', methods=['GET', 'HEAD'])
def service_status() -> Response:
    data, code, head = controllers.service_status()
    response: Response = make_response(jsonify(data), code, head)
    return response


@api.route('/<int:submission_id>/source', methods=['POST'])
def deposit_source(submission_id: int) -> Response:
    # file_payload = request.files.get('file', None)
    stream = request.stream
    data, code, head = controllers.deposit_source(submission_id, stream)
    response: Response = make_response(jsonify(data), code, head)
    return response


@api.route('/<int:submission_id>/source', methods=['HEAD'])
def check_source_exists(submission_id: int) -> Response:
    data, code, head = controllers.check_source_exists(submission_id)
    response: Response = make_response(jsonify(data), code, head)
    return response


@api.route('/<int:submission_id>/preview', methods=['POST'])
def deposit_preview(submission_id: int) -> Response:
    stream = request.stream
    data, code, head = controllers.deposit_preview(submission_id, stream)
    response: Response = make_response(jsonify(data), code, head)
    return response


@api.route('/<int:submission_id>/preview', methods=['HEAD'])
def check_preview_exists(submission_id: int) -> Response:
    data, code, head = controllers.check_preview_exists(submission_id)
    response: Response = make_response(jsonify(data), code, head)
    return response