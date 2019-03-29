"""
Entry-point for the submission worker application.

The heart of the worker is a Celery application that listens for tasks on a
Redis queue. Tasks are event callbacks defined in :mod:`.rules`. Tasks are
identified by name, and get registered by the :func:`.tasks.is_async`
decorator. Importantly, this means that registration of tasks is a side-effect
of importing  :mod:`.rules`.
"""

from flask import Flask

from .runner.async import get_or_create_worker_app
from .factory import create_app

import logging

logging.getLogger('arxiv.submission.services.classic.interpolate') \
    .setLevel(logging.ERROR)

app = create_app()
worker_app = get_or_create_worker_app()
