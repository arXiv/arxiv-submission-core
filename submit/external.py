"""Provides External REST API."""

import logging
from functools import wraps
from flask.json import jsonify
from flask import Blueprint, current_app, redirect, request, url_for, g
from submit import authorization
from submit.controllers import arxiv_sword


logger = logging.getLogger(__name__)

blueprint = Blueprint('submit', __name__, url_prefix='')


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
    """Provide the service document for arXiv SWORDv3 implementation."""
    controller = arxiv_sword.get_controller('service', request.method)
    return controller(request.get_json(), dict(request.headers))


@blueprint.route('/<string:archive>', methods=['POST'])
@authorization.scoped('submission:write')
@json_response
def collection(archive: str) -> tuple:
    """Accept new submissions to a specific archive."""
    controller = arxiv_sword.get_controller('collection', request.method)
    return controller(request.get_json(), dict(request.headers),
                      files=dict(request.files), archive=archive,
                      user=g.user, client=g.client)


@blueprint.route('/<string:archive>/<int:sub_id>', methods=['GET'])
@authorization.scoped('submission:read')
@json_response
def get_submission(archive: str, sub_id: int) -> tuple:
    """Get details about a submission resource."""
    controller = arxiv_sword.get_controller('submission', request.method)
    return controller(request.get_json(), dict(request.headers),
                                    files=dict(request.files),
                                    archive=archive, submission=sub_id)
#
#
# @blueprint.route('/<string:archive>/<int:sub_id>', methods=['POST'])
# @authorization.scoped('submission:write')
# def add_content_to_submission(archive: str, sub_id: int) -> tuple:
#     """Add a new content package to a submission."""
#     body, st, head = sword.submission.post(request.get_json(), request.headers,
#                                            files=request.files,
#                                            archive=archive, submission=sub_id)
#     return jsonify(body), st, head
#
#
# @blueprint.route('/<string:archive>/<int:sub_id>', methods=['DELETE'])
# @authorization.scoped('submission:write')
# def delete_submission(archive: str, sub_id: int) -> tuple:
#     """Delete a submission."""
#     body, st, head = sword.submission.delete(request.get_json(),
#                                              request.headers, archive=archive,
#                                              submission=sub_id)
#     return jsonify(body), st, head
#
#
# @blueprint.route('/<string:archive>/<int:sub_id>/metadata', methods=['GET'])
# @authorization.scoped('submission:read')
# def retrieve_metadata(archive: str, sub_id: int) -> tuple:
#     """Get metadata for a submission."""
#     body, st, head = sword.metadata.get(request.get_json(), request.headers,
#                                         archive=archive, submission=sub_id)
#     return jsonify(body), st, head
#
#
# @blueprint.route('/<string:archive>/<int:sub_id>/metadata',
#                  methods=['POST', 'PUT'])
# @authorization.scoped('submission:write')
# def update_submission_metadata(archive: str, sub_id: int) -> tuple:
#     """Add or update submission metadata."""
#     body, st, head = sword.metadata.put(request.get_json(), request.headers,
#                                         archive=archive, submission=sub_id)
#     return jsonify(body), st, head
#
#
# @blueprint.route('/<string:archive>/<int:sub_id>/content', methods=['GET'])
# @authorization.scoped('submission:read')
# def retrieve_content_package(archive: str, sub_id: int) -> tuple:
#     """Retrieve submission content as a package."""
#     body, st, head = sword.content.get(request.get_json(), request.headers,
#                                        archive=archive, submission=sub_id)
#     return jsonify(body), st, head
#
#
# @blueprint.route('/<string:archive>/<int:sub_id>/content', methods=['POST'])
# @authorization.scoped('submission:write')
# def add_file_to_content(archive: str, sub_id: int) -> tuple:
#     """Add a new file to submission content."""
#     body, st, head = sword.content.post(request.get_json(), request.headers,
#                                         files=request.files, archive=archive,
#                                         submission=sub_id)
#     return jsonify(body), st, head
#
#
# @blueprint.route('/<string:archive>/<int:sub_id>/content', methods=['PUT'])
# @authorization.scoped('submission:write')
# def update_submission_content(archive: str, sub_id: int) -> tuple:
#     """Add or replace the entire submission content package."""
#     body, st, head = sword.content.put(request.get_json(), request.headers,
#                                        files=request.files, archive=archive,
#                                        submission=sub_id)
#     return jsonify(body), st, head
#
#
# @blueprint.route('/<string:archive>/<int:sub_id>/content', methods=['DELETE'])
# @authorization.scoped('submission:write')
# def delete_submission_content(archive: str, sub_id: int) -> tuple:
#     """Delete the entire submission content package."""
#     body, st, head = sword.content.delete(request.get_json(), request.headers,
#                                           archive=archive, submission=sub_id)
#     return jsonify(body), st, head
#
#
# @blueprint.route('/<string:archive>/<int:sub_id>/content/<string:file_id>',
#                  methods=['GET'])
# @authorization.scoped('submission:read')
# def retrieve_file(archive: str, sub_id: int, file_id: int) -> tuple:
#     """Retrieve a specific file from the submission content package."""
#     body, st, head = sword.file.get(request.get_json(), request.headers,
#                                     archive=archive, submission=sub_id,
#                                     file_id=file_id)
#     return jsonify(body), st, head
#
#
# @blueprint.route('/<string:archive>/<int:sub_id>/content/<string:file_id>',
#                  methods=['PUT'])
# @authorization.scoped('submission:write')
# def update_file(archive: str, sub_id: int, file_id: int) -> tuple:
#     """Replace a specific file in the submission content package."""
#     body, st, head = sword.file.put(request.get_json(), request.headers,
#                                     files=request.files, archive=archive,
#                                     submission=sub_id, file_id=file_id)
#     return jsonify(body), st, head
#
#
# @blueprint.route('/<string:archive>/<int:sub_id>/content/<string:file_id>',
#                  methods=['DELETE'])
# @authorization.scoped('submission:write')
# def delete_file(archive: str, sub_id: int, file_id: int) -> tuple:
#     """Delete a specific file in the submission content package."""
#     body, st, head = sword.file.delete(request.get_json(), request.headers,
#                                        archive=archive, submission=sub_id,
#                                        file_id=file_id)
#     return jsonify(body), st, head
