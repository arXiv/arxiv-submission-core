

from typing import Optional, Any, Callable

from retry.api import retry_call

from arxiv.submission.domain.submission import Submission
from arxiv.submission.domain.event import Event
from arxiv.submission.domain.agent import Agent
from arxiv.submission import save
from arxiv.base import logging

from ..process import Process, Failed, Recoverable, Retry
from ..domain import Trigger, ProcessData

logger = logging.getLogger(__name__)
logger.propagate = False


class ProcessRunner:
    def __init__(self, process: Process) -> None:
        self.process = process

    def do(self, step_name: str, previous: Any, trigger: Trigger,
           emit: Callable) -> Any:
        """Perform a step with configured retrying."""
        step = getattr(self.process, step_name)

        # @retry(tries=step.max_retries, delay=step.delay,
        #        backoff=step.backoff, max_delay=step.max_delay,
        #        jitter=step.jitter)
        def _do_step(previous, trigger, emit):
            try:
                return step(previous, trigger, emit)
            except Failed as e:
                raise e
            except Exception as e:
                raise Recoverable() from e

        # return _do_step(previous, trigger, emit)
        return retry_call(_do_step, fargs=(previous, trigger, emit),
                          exceptions=(Recoverable,), tries=step.max_retries,
                          delay=step.delay, backoff=step.backoff,
                          max_delay=step.max_delay, jitter=step.jitter)

    def run(self, trigger: Trigger) -> None:
        """Execute the process synchronously."""
        events = []
        self.process.before_start(trigger, events.append)
        result = None
        logger.debug('%s started', self.process.name)
        for step in self.process.steps:
            try:
                result = self.do(step.name, result, trigger, events.append)
                self.process.on_success(step.name, trigger, events.append)
                logger.debug('%s:%s succeeded', self.process.name, step.name)
            except Exception:
                self.process.on_failure(step.name, trigger, events.append)
                logger.debug('%s:%s failed', self.process.name, step.name)
            finally:
                save(*events, submission_id=self.process.submission_id)
                events.clear()
