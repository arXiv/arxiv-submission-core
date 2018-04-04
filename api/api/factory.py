"""Application factory for references service components."""

import logging

from flask import Flask

from api import routes
from api.services import database, events


def create_web_app() -> Flask:
    """Initialize an instance of the extractor backend service."""
    app = Flask('api')
    app.config.from_pyfile('config.py')
    database.init_app(app)
    events.init_app(app)
    events.get_session()
    app.register_blueprint(routes.blueprint)
    return app