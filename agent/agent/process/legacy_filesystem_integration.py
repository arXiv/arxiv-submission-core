"""Deposit source content and PDF preview in the legacy filesystem."""

from typing import Optional, Callable

from arxiv.users import auth, domain
from arxiv.integration.api import exceptions
from arxiv.submission.auth import get_system_token
from arxiv.submission.services import preview, filemanager
from .base import Process, step, Retry, Recoverable
from ..domain import Trigger
from ..services import filesystem


class _SourceProcess(Process):
    """Provides :func:`.source_id`."""

    def source_id(self, trigger: Trigger) -> int:
        """Get the source ID for the submission content."""

        if trigger.after is None \
                or trigger.after.source_content is None \
                or trigger.after.source_content.identifier is None:
            exc = RuntimeError('Post-event state or source package not set')
            self.fail(exc, 'Post-event state or source package not set')
            return -1
        return trigger.after.source_content.identifier

    def source_checksum(self, trigger: Trigger) -> Optional[str]:
        """Get the checksum for the submission content."""
        if trigger.after is None \
                or trigger.after.source_content is None \
                or trigger.after.source_content.checksum is None:
            exc = RuntimeError('Post-event state or source package not set')
            self.fail(exc, 'Post-event state or source package not set')
            return None
        return trigger.after.source_content.checksum


class CopySourceToLegacy(_SourceProcess):
    """Deposit source content in the legacy filesystem."""

    @step(max_retries=None)
    def copy_source_content(self, previous: Optional, trigger: Trigger,
                            emit: Callable) -> Optional[str]:
        """Copy source content to the legacy system."""
        if trigger.after is None:
            exc = RuntimeError('Post-event state is not set')
            self.fail(exc, 'Post-event state is not set')
            return None
        fm = filemanager.Filemanager.current_session()
        fs = filesystem.Filesystem.current_session()

        upload_id = self.source_id(trigger)
        if upload_id < 0:
            return None

        scopes = [auth.scopes.READ_UPLOAD.for_resource(upload_id)]
        token = get_system_token(__name__, self.agent, scopes)
        try:
            reader, checksum = fm.get_source_package(upload_id, token)
        except (exceptions.RequestForbidden, exceptions.RequestUnauthorized,
                exceptions.BadRequest) as e:
            msg = 'Unrecoverable error while calling file manager service'
            self.fail(e, msg)
            return None
        except exceptions.RequestFailed as e:
            raise Recoverable('An (hopefully temporary) error occurred while'
                              ' calling the file manager service.') from e

        # If the checksum does not match, it likely means that the source
        # content has changed since the event was produced. It is better to
        # fail here, and let the source get updated in legacy in response to
        # a subsequent source-related event, rather than propagate an
        # inconsistent state.
        if checksum != trigger.after.source_content.checksum:
            msg = ('Checksums do not match; submission has'
                   f' {trigger.after.source_content.checksum}, file manager'
                   f' service returns {checksum}')
            self.fail(RuntimeError(msg), msg)
            return None

        try:
            fs.deposit_source(trigger.after.submission_id, reader, checksum)
        except (exceptions.RequestForbidden, exceptions.RequestUnauthorized,
                exceptions.BadRequest) as e:
            msg = 'Unrecoverable error while calling filesystem service'
            self.fail(e, msg)
            return None
        except filesystem.ValidationFailed as e:
            raise Recoverable('Integrity could not be verified') from e
        except exceptions.RequestFailed as e:
            raise Recoverable('An (hopefully temporary) error occurred while'
                              ' calling the filesystem service.') from e
        return None


class CopyPDFPreviewToLegacy(_SourceProcess):
    """Deposit PDF preview in the legacy filesystem."""

    @step(max_retries=None)
    def copy_preview(self, previous: Optional, trigger: Trigger,
                     emit: Callable) -> None:
        """Copy PDF preview to the legacy system."""
        if trigger.after is None:
            exc = RuntimeError('Post-event state is not set')
            self.fail(exc, 'Post-event state is not set')
            return

        checksum = self.source_checksum(trigger)
        if checksum is None:
            return

        pv = preview.PreviewService.current_session()
        fs = filesystem.Filesystem.current_session()

        upload_id = self.source_id(trigger)
        if upload_id < 0:
            return

        scopes = [auth.scopes.READ_UPLOAD.for_resource(upload_id)]
        token = get_system_token(__name__, self.agent, scopes)

        try:
            reader, checksum = pv.get_preview(upload_id, checksum, token)
        except (exceptions.RequestForbidden, exceptions.RequestUnauthorized,
                exceptions.BadRequest) as e:
            msg = 'Unrecoverable error while calling preview service'
            self.fail(e, msg)
            return None
        except exceptions.RequestFailed as e:
            raise Recoverable('An (hopefully temporary) error occurred while'
                              ' calling the preview service.') from e

        try:
            fs.deposit_preview(trigger.after.submission_id, reader, checksum)
        except (exceptions.RequestForbidden, exceptions.RequestUnauthorized,
                exceptions.BadRequest) as e:
            msg = 'Unrecoverable error while calling filesystem service'
            self.fail(e, msg)
            return None
        except filesystem.ValidationFailed as e:
            raise Recoverable('Integrity could not be verified') from e
        except exceptions.RequestFailed as e:
            raise Recoverable('An (hopefully temporary) error occurred while'
                              ' calling the filesystem service.') from e


