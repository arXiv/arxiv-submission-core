"""Application factory for references service components."""

from arxiv.base import logging

from flask import Flask

from api import routes
from arxiv.base.middleware import wrap

from authorization import middleware as auth


def create_web_app() -> Flask:
    """Initialize an instance of the extractor backend service."""
    app = Flask('api')
    app.config.from_pyfile('config.py')

    app.register_blueprint(routes.blueprint)

    wrap(app, [auth.AuthMiddleware])
    return app
