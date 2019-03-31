
from enum import Enum
from typing import Iterable, Tuple, Callable, Union, Optional, Any, \
    NamedTuple, List
from unittest import mock
from contextlib import contextmanager
from collections import OrderedDict

from arxiv.submission import Event, AddProcessStatus, Agent, Submission, System
from ..domain import Trigger


class Failed(RuntimeError):
    """
    The process has failed and cannot recover.

    This exception should be raised when all recourse to recover has been
    exhausted, and no further retries are possible or desired.
    """
    def __init__(self, msg: str, step_name: Optional[str] = None) -> None:
        super(Failed, self).__init__(msg)
        self.step_name = step_name


class Recoverable(RuntimeError):
    """
    The process failed, but there is some hope of recovery.
    """


class Retry(RuntimeError):
    """The process should be retried."""


class ProcessType(type):
    @classmethod
    def __prepare__(self, name, bases):
        return OrderedDict()

    def __new__(self, name: str, bases: Tuple[type], attrs: dict):
        """Identify the ordered steps in the process."""
        steps = [step for base in bases for step in getattr(base, 'steps', [])]
        steps += [obj for obj in attrs.values() if is_step(obj)]
        attrs['steps'] = steps
        return type.__new__(self, name, bases, attrs)


def step(max_retries: Optional[int] = 3,
         delay: Optional[int] = 2,
         backoff: Optional[int] = 2,
         max_delay: Optional[int] = None,
         jitter: Union[int, Tuple[int, int]] = 0) -> Callable:
    """Configure a step."""
    def deco(func: Callable) -> Callable:
        setattr(func, '__is_step__', True)
        setattr(func, 'name', func.__name__)
        setattr(func, 'max_retries', max_retries)
        setattr(func, 'delay', delay)
        setattr(func, 'backoff', backoff)
        setattr(func, 'max_delay', max_delay)
        setattr(func, 'jitter', jitter)
        return func
    return deco


def is_step(func: Callable) -> bool:
    return getattr(func, '__is_step__', None) is True


class Process(metaclass=ProcessType):
    class Status(Enum):
        PENDING = 'pending'
        """The process is waiting to start."""
        IN_PROGRESS = 'in_progress'
        """Process has started, and is running remotely."""
        FAILED_TO_START = 'failed_to_start'
        """Could not start the process."""
        FAILED = 'failed'
        """The process failed while running."""
        FAILED_TO_END = 'failed_to_end'
        """The process ran, but failed to end gracefully."""
        SUCCEEDED = 'succeeded'
        """The process ended successfully."""
        TERMINATED = 'terminated'
        """The process was terminated, e.g. cancelled by operator."""

    def __init__(self, submission_id: int) -> None:
        self.submission_id = submission_id

    @property
    def name(self):
        return self.__class__.__name__

    @property
    def agent(self) -> Agent:
        return System(self.name)

    @property
    def step_names(self):
        return [step.name for step in self.steps]

    def fail(self, exception: Optional[Exception] = None,
             message: Optional[str] = None) -> None:
        """Fail and make no further attempt to recover."""
        if message is None:
            message = f'{self.__class__.__name__} failed fantastically'
        if exception is not None:
            raise Failed(message) from exception
        raise Failed(message)

    def _success_status(self, step_name: str) -> Status:
        """Get the appropriate status for successful completion of a step."""
        if self.step_names.index(step_name) == len(self.steps) - 1:
            return Process.Status.SUCCEEDED
        return Process.Status.IN_PROGRESS

    def before_start(self, trigger: Trigger, emit: Callable, *args, **kwargs):
        """Emit a pending status before the process starts."""
        emit(AddProcessStatus(status=Process.Status.PENDING))

    def on_failure(self, step_name: str, trigger: Trigger,
                   emit: Callable) -> None:
        """Emit a failure status when the process fails."""
        emit(AddProcessStatus(status=Process.Status.FAILED, step=step_name))

    def on_success(self, step_name: str, trigger: Trigger,
                   emit: Callable) -> None:
        """Emit a success state when a step is completed."""
        emit(AddProcessStatus(status=self._success_status(step_name),
                              step=step_name))