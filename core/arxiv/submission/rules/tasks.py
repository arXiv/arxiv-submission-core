from typing import Callable, Optional, Iterable
from functools import wraps, partial

from flask import Flask
from celery import shared_task, Celery

from arxiv.base.globals import get_application_config, get_application_global
from ..domain.submission import Submission
from ..domain.event import Event
from ..domain.agent import Agent
from .. import save
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


def execute_async(callback_name: str, event: Event,
                  before: Submission, after: Submission, agent: Agent):
    worker_app = get_or_create_worker_app()
    worker_app.send_task(callback_name, (event, before, after, agent))


def register_async(func: Callable, name: str) -> None:
    worker_app = get_or_create_worker_app()
    worker_app.task(name=name)(func)


def name_for_callback(event_type: type, func: Callable) -> str:
    return f'{event_type.__name__}::{func.__module__}.{func.__name__}'


def is_async(func: Callable) -> Callable:
    name = f'{func.__module__}.{func.__name__}'

    @wraps(func)
    def do_callback(event: Event, before: Submission,
                    after: Submission, creator: Agent) -> Iterable[Event]:
        for event in func(event, before, after, creator):
            if not event.committed:
                event.commit(save)
    register_async(do_callback, name=name)

    @wraps(func)
    def execute_callback(event: Event, before: Submission,
                         after: Submission, creator: Agent) -> Iterable[Event]:
        execute_async(name, event, before, after, creator)
        return []
    return execute_callback
