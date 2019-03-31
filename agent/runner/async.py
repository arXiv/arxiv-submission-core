

from typing import Callable, Optional, Iterable, Tuple, Any, Union, Dict, List
from functools import wraps, partial
import math

from flask import Flask
from celery import shared_task, Celery, Task, chain
from celery.result import AsyncResult

from arxiv.base.globals import get_application_config, get_application_global
from arxiv.base import logging
from arxiv.submission.domain.submission import Submission
from arxiv.submission.domain.event import Event
from arxiv.submission.domain.agent import Agent
from arxiv.submission import save
from arxiv.submission.exceptions import NothingToDo
from arxiv.submission.services import classic
from .. import config

from .base import ProcessRunner
from ..process import ProcessType, Process, Failed
from ..domain import ProcessData, Trigger

logger = logging.getLogger(__name__)
logger.propagate = False


class AsyncProcessRunner(ProcessRunner):
    """
    Runs :class:`.Process`es asynchronously.

    In order for this to work at runtime, :meth:`.prepare` *MUST* be called
    with the process class at import time in both the process that dispatches
    tasks (e.g. the event consumer) and the worker process.
    """

    processes = {}

    @classmethod
    def prepare(cls, ProcessImpl: ProcessType) -> None:
        """Register an :class:`.ProcessType` for asynchronous execution."""
        cls.processes[ProcessImpl.__name__] = register_process(ProcessImpl)

    def run(self, trigger: Trigger) -> None:
        """Run a :class:`.Process` asynchronously."""
        _run = self.processes[self.process.name]
        _run(self.process.submission_id, trigger)


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

    register_save = celery_app.task(
        name='save',
        bind=True,
        max_retries=config.MAX_SAVE_RETRIES,
        default_retry_delay=config.DEFAULT_SAVE_RETRY_DELAY
    )
    register_save(async_save)
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


def async_save(self, *events, submission_id) -> None:
    try:
        save(*events, submission_id=submission_id)
    except NothingToDo as e:
        logger.debug('No events to save, move along: %s', e)
    except classic.Unavailable as e:
        self.retry(exc=e, max_retries=None, countdown=(2 ** self.retries))
    except Exception as e:
        self.retry(exc=e, countdown=5)


def execute_async_save(*events, submission_id):
    """Save events asynchronously."""
    kwargs = {'submission_id': submission_id}
    get_or_create_worker_app().send_task('save', (*events,), kwargs)


def make_countdown(delay: int, backoff: Optional[int] = 1,
                   max_delay: Optional[int] = None,
                   jitter: Union[int, Tuple[int, int]] = 0):
    if max_delay is None:
        max_delay = math.inf

    def countdown(retries: int) -> int:
        this_delay = delay if backoff is None else (delay * retries) ** backoff
        return min(this_delay, max_delay)
    return countdown


def make_task(app: Celery, Proc: ProcessType, step: Callable) -> Callable:
    """Generate an asynchronous task to perform a step."""
    countdown = make_countdown(step.delay, step.backoff, step.max_delay)

    @app.task(name=f'{Proc.__name__}.{step.name}', bind=True,
              max_retries=step.max_retries, default_retry_delay=step.delay)
    def do_step(self, data: ProcessData) -> Any:
        logger.debug('Do step %s with data %s', step.name, data)
        events: List[Event] = []
        previous = data.get_last_result() if data.results else None
        try:
            inst = Proc(data.submission_id)
            data.add_result(step(inst, previous, events.append))
        except Failed as exc:
            raise exc   # This is a deliberately unrecoverable failure.
        except Exception as exc:
            # Any other exception deserves more chances.
            self.retry(exc=exc, countdown=countdown(self.retries))
        finally:
            # Save whatever was emitted before the end of the step, or prior to
            # an exception.
            execute_async_save(*events, submission_id=data.submission_id)
        return data
    return do_step


def make_failure_task(app: Celery, Proc: ProcessType) -> Callable:
    @app.task
    def on_failure(request, exc, traceback):
        data, = request.args
        name = getattr(exc, 'step_name', 'none')
        events = []
        Proc(data.submission_id).on_failure(name, data.trigger, events.append)
        execute_async_save(*events, submission_id=data.submission_id)
    return on_failure


def register_process(Proc: ProcessType) -> Callable:
    """Generate an asynchronous variant of a :class:`.Process`."""
    app = get_or_create_worker_app()

    # Build a chain of asynchronous tasks from the steps in the process.
    # make_step_task() will build and register an asynchronous variant of the
    # step (callable).
    process = chain(*[make_task(app, Proc, step).s() for step in Proc.steps])
    on_failure = make_failure_task(app, Proc)

    def execute_chain(submission_id: int, trigger: Trigger):
        logger.debug('Execute chain %s for submission %s with trigger %s',
                     Proc.__name__, submission_id, trigger)
        process.apply_async((ProcessData(submission_id, trigger, []),),
                            link_error=on_failure.s())
    return execute_chain