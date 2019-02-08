"""Monitor the status of the compilation process."""

from typing import Iterable
from itertools import count
import time

from arxiv.base import logging
from ..domain.event import Event, AddProcessStatus
from ..domain.event.event import Condition
from ..domain.submission import Submission
from ..domain.flag import Flag, ContentFlag
from ..domain.annotation import Feature
from ..domain.agent import Agent, User
from ..domain.process import ProcessStatus
from ..services import plaintext, compiler
from ..tasks import is_async

logger = logging.getLogger(__name__)


def when_compilation_starts(event: Event, *args, **kwargs) -> bool:
    """Condition that the compilation process has started."""
    return event.process is ProcessStatus.Process.COMPILATION \
        and event.status is ProcessStatus.Status.REQUESTED


@AddProcessStatus.bind(when_compilation_starts)
@is_async
def poll_compilation(event: AddProcessStatus, before: Submission,
                     after: Submission, creator: Agent) -> Iterable[Event]:
    """Monitor the status of the compilation process until completion."""
    logger.debug('Poll compilation for submission %s', after.submission_id)
    source_id, checksum, fmt = compiler.split_task_id(event.identifier)
    process = ProcessStatus.Process.COMPILATION
    try:
        for tries in count(1):
            if compiler.compilation_is_complete(source_id, checksum, fmt):
                yield AddProcessStatus(creator=creator, process=process,
                                       status=ProcessStatus.Status.SUCCEEDED,
                                       service=compiler.NAME,
                                       version=compiler.VERSION,
                                       identifier=event.identifier)
                break
            time.sleep(tries ** 2)  # Exponential back-off.
    except (compiler.RequestFailed, compiler.CompilationFailed) as e:
        reason = 'request failed (%s): %s' % (type(e).__name__, e)
        yield AddProcessStatus(creator=creator, process=process,
                               status=ProcessStatus.Status.FAILED,
                               service=compiler.NAME,
                               version=plaintext.VERSION,
                               identifier=event.identifier,
                               reason=reason)
