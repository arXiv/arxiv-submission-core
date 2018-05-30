"""Application factory for references service components."""

import logging

from flask import Flask

from arxiv.base import Base
from arxiv.base.middleware import wrap, request_logs
from submit.routes import ui


def create_ui_web_app() -> Flask:
    """Initialize an instance of the search frontend UI web application."""
#    logging.getLogger('boto').setLevel(logging.ERROR)
#    logging.getLogger('boto3').setLevel(logging.ERROR)
#    logging.getLogger('botocore').setLevel(logging.ERROR)

    app = Flask('submit', static_folder='static', template_folder='templates')
    app.config.from_pyfile('config.py')

#    submit.init_app(app)

    Base(app)
    app.register_blueprint(ui.blueprint)

#    wrap(app, [request_logs.ClassicLogsMiddleware])

    return app
