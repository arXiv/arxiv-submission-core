from typing import Callable

from flask import Flask
from celery import shared_task, Celery

from arxiv.base.globals import get_application_config, get_application_global
from ..domain.submission import Submission
from ..domain.event import Event

from . import config


def create_worker_app() -> Celery:
    """Initialize the Celery application."""
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
    g = get_application_global()
    if not g:
        return create_worker_app()
    if 'worker' not in g:
        g.worker = create_worker_app()
    return g.worker


def execute_async(task_name: str, callback_name: str, event: Event,
                  before: Submission, after: Submission):
    print('execute_async', task_name)
    worker_app = get_or_create_worker_app()
    worker_app.send_task(task_name, (callback_name, event, before, after))


def register_async(func: Callable) -> None:
    worker_app = get_or_create_worker_app()
    worker_app.task(name=func.__name__)(func)
