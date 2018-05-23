"""Provides routes for the submission user interface."""

from flask import Blueprint, render_template, url_for, abort, make_response
from arxiv import status
# from submission.controllers import verify

blueprint = Blueprint('ui', __name__, url_prefix='/')


@blueprint.route('/verify-user', methods=['GET'])
def verify_user() -> Response:
    """Render the submission start page. Foreshortened valication for template testing."""
    rendered = render_template("submission/verify_user.html", pagetitle='Verify User Information')
    response = make_response(rendered, status.HTTP_200_OK)
    return response
