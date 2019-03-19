"""Provides support for asynchronous tasks."""

from typing import Callable, Optional, Iterable
from functools import wraps, partial

from flask import Flask
from celery import shared_task, Celery, Task

from arxiv.base.globals import get_application_config, get_application_global
from arxiv.base import logging
from .domain.submission import Submission
from .domain.event import Event
from .domain.agent import Agent
from .core import save
from .exceptions import NothingToDo
from . import config

logger = logging.getLogger(__name__)
logger.propagate = False


def create_worker_app() -> Celery:
    """Initialize the worker application."""
    result_backend = config.RESULT_BACKEND
    broker = config.BROKER_URL
    celery_app = Celery('submission',
                        results=result_backend,
                        backend=result_backend,
                        result_backend=result_backend,
                        broker=broker)
    celery_app.config_from_object(config)

    celery_app.conf.task_default_queue = 'submission-worker'
    return celery_app


def get_or_create_worker_app() -> Celery:
    """
    Get the current worker app, or create one.

    Uses the Flask application global to keep track of the worker app.
    """
    g = get_application_global()
    if not g:
        return create_worker_app()
    if 'worker' not in g:
        g.worker = create_worker_app()
    return g.worker


def name_for_callback(func: Callable) -> str:
    """Produce a name for a function suitable for use as a task name."""
    parent = func.__module__.split('.')[-1]
    return f'{parent}.{func.__name__}'


def is_async(func: Callable) -> Callable:
    """
    Turn a function into an asynchronous task.

    Registers the function with the worker application, and decorates the
    function with logic to dispatch the function to the worker when called.
    When the decorated function is called, a task is added to the worker queue
    and an empty iterable is returned. If ``ENABLE_ASYNC=0`` on the app config,
    calls to the decorated function will execute in-thread and return normally.
    """
    worker_app = get_or_create_worker_app()
    name = name_for_callback(func)

    @wraps(func)
    def do_callback(self: Task, event: Event, before: Submission,
                    after: Submission, creator: Agent) -> Iterable[Event]:
        """Run the callback, and save the results."""
        try:
            save(*func(event, before, after, creator, task_id=self.request.id),
                 submission_id=after.submission_id)
        except NothingToDo as e:
            logger.debug('No events to save, move along: %s', e)

    # Register the wrapped callback.
    worker_app.task(name=name, bind=True)(do_callback)

    @wraps(func)
    def execute_callback(event: Event, before: Submission,
                         after: Submission, creator: Agent) -> Iterable[Event]:
        """Execute the callback asynchronously."""
        config = get_application_config()
        if bool(int(config.get('ENABLE_ASYNC', '0'))):
            worker_app = get_or_create_worker_app()
            worker_app.send_task(name, (event, before, after, creator))
            return []
        return func(event, before, after, creator)
    return execute_callback
