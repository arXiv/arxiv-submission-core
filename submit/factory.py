"""Application factory for references service components."""

import logging

from flask import Flask

from submit import external


def create_web_app() -> Flask:
    """Initialize an instance of the extractor backend service."""
    app = Flask('submit')
    app.config.from_pyfile('config.py')
    app.register_blueprint(external.blueprint)
    return app
