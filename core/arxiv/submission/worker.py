"""
Entry-point for the submission worker application.

The heart of the worker is a Celery application that listens for tasks on a
Redis queue. Tasks are event callbacks defined in :mod:`.rules`. Tasks are
identified by name, and get registered by the :func:`.tasks.is_async`
decorator. Importantly, this means that registration of tasks is a side-effect
of importing  :mod:`.rules`.
"""

from flask import Flask
from arxiv import mail
from arxiv.base import Base
from .tasks import get_or_create_worker_app
from . import init_app
from . import rules, config
from .services import Classifier, PlainTextService, Compiler, classic

import logging

logging.getLogger('arxiv.submission.services.classic.interpolate') \
    .setLevel(logging.ERROR)

app = Flask(__name__)

Base(app)
classic.init_app(app)
Compiler.init_app(app)
PlainTextService.init_app(app)
Classifier.init_app(app)
mail.init_app(app)

app.config.from_object(config)
app.app_context().push()
init_app(app)
worker_app = get_or_create_worker_app()
