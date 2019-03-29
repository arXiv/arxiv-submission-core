"""Enforces size limit rules."""

from typing import Iterable, Union, Optional, Callable

from arxiv.integration.api import exceptions

from arxiv.submission.domain.event import Event, SetUploadPackage, \
    UpdateUploadPackage, AddHold, RemoveHold, AddProcessStatus
from arxiv.submission.domain.event.event import Condition
from arxiv.submission.domain.submission import Submission, SubmissionContent, \
    Hold
from arxiv.submission.domain.flag import Flag, ContentFlag
from arxiv.submission.domain.annotation import Feature
from arxiv.submission.domain.agent import Agent, User
from arxiv.submission.domain.process import ProcessStatus
from arxiv.submission.services import plaintext, compiler
from arxiv.submission.tasks import is_async
from arxiv.submission.auth import get_system_token, get_compiler_scopes

from arxiv.taxonomy import CATEGORIES, Category
from ..process import Process, step, Recoverable
from ..domain import Trigger

PackageEvent = Union[SetUploadPackage, UpdateUploadPackage]


class CheckSubmissionSourceSize(Process):
    """When a new source package is attached, check for oversize source."""

    @step()
    def check(self, previous: Optional, trigger: Trigger,
              emit: Callable) -> None:
        """Perform the source size check procedure."""
        uncompressed_max = trigger.params['UNCOMPRESSED_PACKAGE_MAX']
        compressed_max = trigger.params['COMPRESSED_PACKAGE_MAX']
        try:
            uncompressed_size = trigger.after.source_content.uncompressed_size
            compressed_size = trigger.after.source_content.compressed_size
        except AttributeError as exc:
            self.fail(exc, 'Missing source content or post-event state')

        msg = f"{uncompressed_size} bytes; {compressed_size} bytes compressed"

        if uncompressed_size > uncompressed_max \
                or compressed_size > compressed_max:
            # If the submission is already on hold for this reason, there is
            # nothing left to do.
            if Hold.Type.SOURCE_OVERSIZE in trigger.after.hold_types:
                return

            emit(AddHold(creator=self.agent,
                         hold_type=Hold.Type.SOURCE_OVERSIZE,
                         hold_reason=msg))

        # If the submission is on hold due to oversize, and the submission is
        # no longer oversize, remove the hold.
        else:
            for event_id, hold in trigger.after.holds.items():
                if hold.hold_type is Hold.Type.SOURCE_OVERSIZE:
                    emit(RemoveHold(creator=self.agent, hold_event_id=event_id,
                                    hold_type=Hold.Type.SOURCE_OVERSIZE,
                                    removal_reason=msg))


class CheckPDFSize(Process):
    """When a PDF is compiled, check for oversize."""

    recoverable = (exceptions.BadResponse, exceptions.ConnectionFailed,
                   exceptions.SecurityException)

    @step(max_retries=None)
    def get_size(self, previous: Optional, trigger: Trigger,
                 emit: Callable) -> int:
        """Get the size of the compilation from the compiler service."""
        try:
            compilation = trigger.after.latest_compilation
            source_state = trigger.after.source_content.checksum
        except AttributeError as exc:
            self.fail(exc, message='Missing compilation or post-event state')
        if compilation is None or compilation.checksum != source_state:
            self.fail(message='No recent compilation to evaluate')

        # upload_id, checksum, fmt = compiler.split_task_id(event.identifier)
        token = get_system_token(__name__, self.agent,
                                 get_compiler_scopes(compilation.identifier))

        try:
            stat = compiler.Compiler.get_status(compilation.source_id,
                                                compilation.checksum, token,
                                                compilation.output_format)
        except self.recoverable as exc:
            raise Recoverable('Encountered %s; try again' % exc) from exc
        except Exception as exc:
            self.fail(exc, message='Encountered unrecoverable request error')
        return stat.size_bytes

    @step()
    def evaluate_size(self, size_bytes: int, trigger: Trigger,
                      emit: Callable) -> int:
        """Add or remove holds as appropriate."""
        msg = "PDF is %i bytes" % size_bytes
        if size_bytes > trigger.params['PDF_LIMIT']:
            if Hold.Type.PDF_OVERSIZE in trigger.after.hold_types:
                return      # Already on hold for this reason; nothing to do.
            emit(AddHold(creator=self.agent, hold_type=Hold.Type.PDF_OVERSIZE,
                         hold_reason=msg))
        else:
            # If the submission is on hold due to oversize, remove the hold.
            for event_id, hold in trigger.after.holds.items():
                if hold.hold_type is Hold.Type.PDF_OVERSIZE:
                    emit(RemoveHold(creator=self.agent, hold_event_id=event_id,
                                    hold_type=Hold.Type.PDF_OVERSIZE,
                                    removal_reason=msg))
