"""
Provides an asynchronous process runner.

The :class:`.AsyncProcessRunner` registers and dispatches processes via
Celery, to be carried out by the worker.
"""

from typing import Callable, Optional, Iterable, Tuple, Any, Union, Dict, \
    List
from functools import wraps, partial
import math
import random

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
    Runs :class:`.Process` instances asynchronously.

    In order for this to work at runtime, :meth:`.prepare` *MUST* be called
    with the process class at import time in both the process that dispatches
    tasks (e.g. the event consumer) and the worker process.
    """

    processes = {}

    @classmethod
    def prepare(cls, ProcessImpl: ProcessType) -> None:
        """
        Register an :class:`.ProcessType` for asynchronous execution.

        Parameters
        ----------
        ProcessImpl : :class:`.ProcessType`
            The process (class) to register.

        """
        cls.processes[ProcessImpl.__name__] = register_process(ProcessImpl)

    def run(self, trigger: Trigger) -> None:
        """Run a :class:`.Process` asynchronously."""
        _run = self.processes[self.process.name]
        _run(self.process.submission_id, self.process.process_id, trigger)


def create_worker_app() -> Celery:
    """
    Initialize the worker application.

    Returns
    -------
    :class:`celery.Celery`

    """
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


def async_save(self, *events: Event, submission_id: int = -1) -> None:
    """
    Save/emit new events.

    Parameters
    ----------
    events
        Each item is an :class:`.Event`.
    submission_id : int
        Identifier of the submission to which the commands/events apply.

    """
    if submission_id < 0:
        raise RuntimeError('Invalid submission ID')
    try:
        save(*events, submission_id=submission_id)
    except NothingToDo as e:
        logger.debug('No events to save, move along: %s', e)
    except classic.Unavailable as e:
        self.retry(exc=e, max_retries=None,
                   countdown=(2 ** self.request.retries))
    except classic.ConsistencyError as e:
        logger.error('Encountered a ConsistencyError; could not save: %s', e)
    except Exception as e:
        self.retry(exc=e, countdown=5)


def execute_async_save(*events: Event, submission_id: int = -1):
    """
    Save events asynchronously, using :func:`.async_save`.

    Parameters
    ----------
    events
        Each item is an :class:`.Event`.
    submission_id : int
        Identifier of the submission to which the commands/events apply.

    """
    if submission_id < 0:
        raise RuntimeError('Invalid submission ID')
    kwargs = {'submission_id': submission_id}
    get_or_create_worker_app().send_task('save', (*events,), kwargs)


def make_countdown(delay: int, backoff: Optional[int] = 1,
                   max_delay: Optional[int] = None,
                   jitter: Union[int, Tuple[int, int]] = 0) \
        -> Callable[[int], Union[int, float]]:
    """
    Make a countdown callable based on the retry parameters of a step.

    For use in task retry calls, to customize the retry delay.

    Parameters
    ----------
    delay : int
        The base number of seconds to wait before retrying.
    backoff : int
        If provided, the exponent applied to the delay * number of attempts.
    max_delay : int
        If provided, the maximum number of seconds to wait.
    jitter : int or tuple
        If an int, number of seconds (+/-) to alter the delay, after the
        backoff is applied. If a two-tuple of ints,
        a random offset will be used in the range (jitter[0], jitter[1]).

    Returns
    -------
    function
        Countdown function; accepts a single int parameter representing the
        current retry count.

    """
    if max_delay is None:
        max_delay = math.inf

    def countdown(retries: int) -> int:
        this_delay = delay if backoff is None else (delay * retries) ** backoff
        if jitter:
            if type(jitter) is int:
                this_delay += jitter
            elif type(jitter) is tuple and len(jitter) == 2:
                n, x = jitter
                this_delay += random.random() * (x - n) + x
        return min(this_delay, max_delay)
    return countdown


def make_task(app: Celery, Proc: ProcessType, step: Callable) -> Task:
    """
    Generate an asynchronous task to perform a step.

    Parameters
    ----------
    app : :class:`celery.Celery`
        The Celery application on which to register the task.
    Proc : :class:`.ProcessType`
        The process (class) for which to make a task.
    step : function
        The specific step of the process to make into a task.

    Returns
    -------
    :class:`celery.Task`
        An asynchronous task that performs ``step``.

    """
    countdown = make_countdown(step.delay, step.backoff, step.max_delay)

    @app.task(name=f'{Proc.__name__}.{step.name}', bind=True,
              max_retries=step.max_retries, default_retry_delay=step.delay)
    def do_step(self, data: ProcessData) -> Any:
        logger.debug('Do step %s', step.name)
        emit = partial(async_save, self, submission_id=data.submission_id)
        previous = data.get_last_result() if data.results else None
        try:
            inst = Proc(data.submission_id, data.process_id)
            data.add_result(step(inst, previous, data.trigger, emit))
        except Failed as exc:
            raise exc   # This is a deliberately unrecoverable failure.
        except Exception as exc:
            # Any other exception deserves more chances.
            self.retry(exc=exc, countdown=countdown(self.request.retries))
        return data
    return do_step


def make_failure_task(app: Celery, Proc: ProcessType) -> Task:
    """
    Make a :class:`.Task` to handle failure of a process.

    Parameters
    ----------
    app : :class:`celery.Celery`
        The Celery application on which to register the task.
    Proc : :class:`.ProcessType`
        The process (class) for which the failure handler should be
        generated.

    Returns
    -------
    :class:`celery.Task`
        An asynchronous task that can be used as an errback for an async
        process.

    """
    @app.task
    def on_failure(request, exc, traceback):    # type: ignore
        data, = request.args
        name = getattr(exc, 'step_name', 'none')
        events = []
        process = Proc(data.submission_id, data.process_id)
        process.on_failure(name, data.trigger, events.append)
        execute_async_save(*events, submission_id=data.submission_id)
    return on_failure


def register_process(Proc: ProcessType) -> Callable:
    """
    Generate an asynchronous variant of a :class:`.Process`.

    Builds a chain of asynchronous :class:`celery.Task`s from the steps in the
    process.

    Parameters
    ----------
    Proc : :class:`.ProcessType`
        The process (class) to be registered for asynchronous execution.

    Returns
    -------
    function
        A function that, when called, dispatches the process for asynchronous
        execution.

    """
    app = get_or_create_worker_app()

    # make_step_task() will build and register an asynchronous variant of the
    # step (callable).
    process = chain(*[make_task(app, Proc, step).s() for step in Proc.steps])
    on_failure = make_failure_task(app, Proc)

    def execute_chain(submission_id: int, process_id: str, trigger: Trigger):
        logger.debug('Execute chain %s with id %s for submission %s',
                     Proc.__name__, process_id, submission_id)
        data = ProcessData(submission_id, process_id, trigger, [])
        process.apply_async((data,), link_error=on_failure.s())
    return execute_chain
