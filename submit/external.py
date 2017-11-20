"""Provides External REST API."""

import logging
from flask.json import jsonify
from flask import Blueprint, current_app, redirect, request, url_for
from submit import authorization, sword

logger = logging.getLogger(__name__)

blueprint = Blueprint('submit', __name__, url_prefix='')


@blueprint.route('/', methods=['GET'])
def service() -> tuple:
    """Provide the service document for arXiv SWORDv3 implementation."""
    body, st, head = sword.ServiceDocument.get(request.get_json(),
                                               request.headers)
    return jsonify(body), st, head


@blueprint.route('/<string:archive>', methods=['POST'])
@authorization.scoped('submission:write')
def collection(archive: str) -> tuple:
    """Accept new submissions to a specific archive."""
    body, st, head = sword.Collection.post(request.get_json(), request.headers,
                                           files=request.files,
                                           archive=archive)
    return jsonify(body), st, head


@blueprint.route('/<string:archive>/<int:sub_id>', methods=['GET'])
@authorization.scoped('submission:read')
def get_submission(archive: str, sub_id: int) -> tuple:
    """Get details about a submission resource."""
    body, st, head = sword.Submission.get(request.get_json(), request.headers)
    return jsonify(body), st, head


@blueprint.route('/<string:archive>/<int:sub_id>', methods=['POST'])
@authorization.scoped('submission:write')
def add_content_to_submission(archive: str, sub_id: int) -> tuple:
    """Add a new content package to a submission."""
    body, st, head = sword.Submission.post(request.get_json(), request.headers,
                                           files=request.files)
    return jsonify(body), st, head


@blueprint.route('/<string:archive>/<int:sub_id>', methods=['DELETE'])
@authorization.scoped('submission:write')
def delete_submission(archive: str, sub_id: int) -> tuple:
    """Delete a submission."""
    body, st, head = sword.Submission.delete(request.get_json(),
                                             request.headers)
    return jsonify(body), st, head


@blueprint.route('/<string:archive>/<int:sub_id>/metadata', methods=['GET'])
@authorization.scoped('submission:read')
def retrieve_metadata(archive: str, sub_id: int) -> tuple:
    """Get metadata for a submission."""
    body, st, head = sword.Metadata.get(request.get_json(), request.headers)
    return jsonify(body), st, head


@blueprint.route('/<string:archive>/<int:sub_id>/metadata',
                 methods=['POST', 'PUT'])
@authorization.scoped('submission:write')
def update_submission_metadata(archive: str, sub_id: int) -> tuple:
    """Add or update submission metadata."""
    return jsonify({
        'archive': archive,
        'submission': sub_id,
        'action': 'update_submission_metadata'
    })


@blueprint.route('/<string:archive>/<int:sub_id>/content', methods=['GET'])
@authorization.scoped('submission:read')
def retrieve_content_package(archive: str, sub_id: int) -> tuple:
    """Retrieve submission content as a package."""
    return jsonify({
        'archive': archive,
        'submission': sub_id,
        'action': 'retrieve_content_package'
    })


@blueprint.route('/<string:archive>/<int:sub_id>/content', methods=['POST'])
@authorization.scoped('submission:write')
def add_file_to_content(archive: str, sub_id: int) -> tuple:
    """Add a new file to submission content."""
    return jsonify({
        'archive': archive,
        'submission': sub_id,
        'action': 'add_file_to_content'
    })


@blueprint.route('/<string:archive>/<int:sub_id>/content', methods=['PUT'])
@authorization.scoped('submission:write')
def update_submission_content(archive: str, sub_id: int) -> tuple:
    """Add or replace the entire submission content package."""
    return jsonify({
        'archive': archive,
        'submission': sub_id,
        'action': 'update_submission_content'
    })


@blueprint.route('/<string:archive>/<int:sub_id>/content', methods=['DELETE'])
@authorization.scoped('submission:write')
def delete_submission_content(archive: str, sub_id: int) -> tuple:
    """Delete the entire submission content package."""
    return jsonify({
        'archive': archive,
        'submission': sub_id,
        'action': 'delete_submission_content'
    })


@blueprint.route('/<string:archive>/<int:sub_id>/content/<string:file_id>',
                 methods=['GET'])
@authorization.scoped('submission:read')
def retrieve_file(archive: str, sub_id: int, file_id: int) -> tuple:
    """Retrieve a specific file from the submission content package."""
    return jsonify({
        'archive': archive,
        'submission': sub_id,
        'file': file_id,
        'action': 'retrieve_file'
    })


@blueprint.route('/<string:archive>/<int:sub_id>/content/<string:file_id>',
                 methods=['PUT'])
@authorization.scoped('submission:write')
def update_file(archive: str, sub_id: int, file_id: int) -> tuple:
    """Replace a specific file in the submission content package."""
    return jsonify({
        'archive': archive,
        'submission': sub_id,
        'file': file_id,
        'action': 'update_file'
    })


@blueprint.route('/<string:archive>/<int:sub_id>/content/<string:file_id>',
                 methods=['DELETE'])
@authorization.scoped('submission:write')
def delete_file(archive: str, sub_id: int, file_id: int) -> tuple:
    """Delete a specific file in the submission content package."""
    return jsonify({
        'archive': archive,
        'submission': sub_id,
        'file': file_id,
        'action': 'delete_file'
    })
