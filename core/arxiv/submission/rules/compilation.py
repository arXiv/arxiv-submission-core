"""Monitor the status of the compilation process."""

from typing import Iterable, Optional
from itertools import count
import time

from arxiv.base import logging
from arxiv.integration.api import exceptions
from ..domain.event import Event, AddProcessStatus
from ..domain.event.event import Condition
from ..domain.submission import Submission
from ..domain.flag import Flag, ContentFlag
from ..domain.annotation import Feature
from ..domain.agent import Agent, User
from ..domain.process import ProcessStatus
from ..services import plaintext
from ..services.compiler import Compiler, CompilationFailed, split_task_id
from ..tasks import is_async
from ..auth import get_system_token, get_compiler_scopes

logger = logging.getLogger(__name__)


def when_compilation_starts(event: Event, *args, **kwargs) -> bool:
    """Condition that the compilation process has started."""
    return event.process is ProcessStatus.Process.COMPILATION \
        and event.status is ProcessStatus.Status.REQUESTED


@AddProcessStatus.bind(when_compilation_starts)
@is_async
def poll_compilation(event: AddProcessStatus, before: Submission,
                     after: Submission, creator: Agent,
                     task_id: Optional[str] = None,
                     **kwargs) -> Iterable[Event]:
    """Monitor the status of the compilation process until completion."""
    logger.debug('Poll compilation for submission %s', after.submission_id)
    source_id, checksum, fmt = split_task_id(event.identifier)
    process = ProcessStatus.Process.COMPILATION
    tok = get_system_token(__name__, event.creator,
                           get_compiler_scopes(event.identifier))

    for tries in count(1):
        try:
            logger.debug('check compilation status')
            if Compiler.compilation_is_complete(source_id, checksum, tok, fmt):
                logger.debug('compilation is complete; hurray!')
                yield AddProcessStatus(creator=creator, process=process,
                                       status=ProcessStatus.Status.SUCCEEDED,
                                       service=Compiler.NAME,
                                       version=Compiler.VERSION,
                                       identifier=event.identifier,
                                       monitoring_task=task_id)
                break
            logger.debug(f'not complete, try again in {tries ** 2} seconds')
            time.sleep(tries ** 2)  # Exponential back-off.
        except exceptions.NotFound:
            logger.debug('no such resource; wait and try again')
            time.sleep(tries ** 2)  # Exponential back-off.
        except (exceptions.RequestFailed, CompilationFailed) as e:
            reason = 'request failed (%s): %s' % (type(e).__name__, e)
            logger.debug('off the rails because %s', reason)
            yield AddProcessStatus(creator=creator, process=process,
                                   status=ProcessStatus.Status.FAILED,
                                   service=Compiler.NAME,
                                   version=plaintext.PlainTextService.VERSION,
                                   identifier=event.identifier,
                                   reason=reason,
                                   monitoring_task=task_id)
            break
