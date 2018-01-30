"""Application factory for references service components."""

import logging

from flask import Flask

from events import routes
from events.converter import EventTypeConverter
from events.services import database


def create_web_app() -> Flask:
    """Initialize an instance of the submission events controller service."""
    app = Flask('events')
    app.config.from_pyfile('config.py')
    app.url_map.converters['event_type'] = EventTypeConverter
    database.init_app(app)
    app.register_blueprint(routes.blueprint)
    return app
