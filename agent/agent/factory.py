import logging
import time

from flask import Flask

from arxiv import mail
from arxiv.base import Base, logging
from arxiv.base.middleware import wrap, request_logs
from arxiv.submission import init_app, wait_for
from arxiv.submission.services import Classifier, PlainTextService, Compiler, \
    classic
from . import config
from .services import database

logger = logging.getLogger(__name__)


def create_app() -> Flask:
    """Create a new agent application."""
    app = Flask(__name__)
    app.config.from_object(config)

    Base(app)

    # Initialize services.
    database.init_app(app)
    mail.init_app(app)
    init_app(app)

    wrap(app, [request_logs.ClassicLogsMiddleware])

    if app.config['WAIT_FOR_SERVICES']:
        time.sleep(app.config['WAIT_ON_STARTUP'])
        with app.app_context():
            wait_for(database)
        logger.info('All upstream services are available; ready to start')
    return app
