"""
Submission Agent Worker
=======================

The worker is a `Celery <https://celeryproject.org>`_ application that scales
horizontally to run :class:`.Process` instances dispatched by the consumer.
Processes are divided into smaller steps that are run in series. Keeping steps
small makes the overall process more fault-tolerant; if a step fails for some
reason (e.g. worker crashes, meteor strike), it can be retried without
discarding expensive results from previous steps.


"""

from flask import Flask

from .runner.async import get_or_create_worker_app
from .factory import create_app

import logging

logging.getLogger('arxiv.submission.services.classic.interpolate') \
    .setLevel(logging.ERROR)

app = create_app()
app.app_context().push()
worker_app = get_or_create_worker_app()
