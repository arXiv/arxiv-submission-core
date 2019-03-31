import logging

from flask import Flask

from arxiv import mail
from arxiv.base import Base
from arxiv.base.middleware import wrap, request_logs
from arxiv.submission import init_app
from arxiv.submission.services import Classifier, PlainTextService, Compiler, \
    classic
from . import config
from .services import database


def create_app() -> Flask:
    """Create a new agent application."""
    app = Flask(__name__)

    Base(app)
    classic.init_app(app)
    database.init_app(app)
    Compiler.init_app(app)
    PlainTextService.init_app(app)
    Classifier.init_app(app)
    mail.init_app(app)

    app.config.from_object(config)
    app.app_context().push()
    init_app(app)

    wrap(app, [request_logs.ClassicLogsMiddleware])

    return app

# if not database.tables_exist():
#     database.create_all()
