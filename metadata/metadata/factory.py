"""Application factory for references service components."""

from arxiv.base import logging

from flask import Flask, jsonify, make_response
from werkzeug.exceptions import Forbidden, Unauthorized, NotFound, BadRequest

from metadata import routes
from arxiv.base.middleware import wrap

from arxiv.submission.services import classic

from authorization import middleware as auth


def jsonify_exception(error):
    """Render the base 404 error page."""
    exc_resp = error.get_response()
    response = jsonify(reason=error.description)
    response.status_code = exc_resp.status_code
    return response


def create_web_app() -> Flask:
    """Initialize an instance of the extractor backend service."""
    app = Flask('metadata')
    classic.init_app(app)
    app.config.from_pyfile('config.py')

    app.register_blueprint(routes.blueprint)
    app.errorhandler(Forbidden)(jsonify_exception)
    app.errorhandler(NotFound)(jsonify_exception)
    app.errorhandler(BadRequest)(jsonify_exception)
    app.errorhandler(Unauthorized)(jsonify_exception)

    wrap(app, [auth.AuthMiddleware])
    return app
