"""Enforces size limit rules."""

from typing import Iterable, Union, Optional, Callable

from arxiv.integration.api import exceptions

from arxiv.submission.domain.event import Event, SetUploadPackage, \
    UpdateUploadPackage, AddHold, RemoveHold, AddProcessStatus
from arxiv.submission.domain.event.event import Condition
from arxiv.submission.domain.submission import Submission, SubmissionContent, \
    Hold, Compilation
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

    def handle_compiler_exception(self, exc: Exception) -> None:
        """Handle exceptions raised when calling the compiler service."""
        exc_type = type(exc)

        if exc_type in (exceptions.BadResponse, exceptions.ConnectionFailed):
            raise Recoverable('Encountered %s; try again' % exc) from exc
        elif exc_type is exceptions.RequestFailed:
            if exc.status_code >= 500:
                msg = 'Compiler service choked: %i' % exc.status_code
                raise Recoverable(msg) from exc
            self.fail(exc, 'Unrecoverable exception: %i' % exc.status_code)
        self.fail(exc, 'Unhandled exception')

    @step(max_retries=None)
    def get_size(self, previous: Optional, trigger: Trigger,
                 emit: Callable) -> int:
        """Get the size of the compilation from the compiler service."""
        try:
            source_id = trigger.after.source_content.identifier
            source_state = trigger.after.source_content.checksum
        except AttributeError as exc:
            self.fail(exc, message='Missing compilation or post-event state')
        compilation_id = Compilation.get_identifier(source_id, source_state)
        scopes = get_compiler_scopes(compilation_id)
        token = get_system_token(__name__, self.agent, scopes)

        try:
            stat = compiler.Compiler.get_status(source_id, source_state, token,
                                                Compilation.Format.PDF)
        except Exception as exc:
            self.handle_compiler_exception(exc)
        if stat.status is Compilation.Status.IN_PROGRESS:
            raise Recoverable('Compilation is stil in progress; try again')
        elif stat.status is Compilation.Status.FAILED:
            self.fail(message='Compilation failed; cannot get size of PDF')
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
