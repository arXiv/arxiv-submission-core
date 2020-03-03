"""
Core procedures for processing source content.

In order for a submission to be finalized, it must have a valid source package,
and the source must be processed. Source processing involves the transformation
(and possibly validation) of sanitized source content (generally housed in the
file manager service) into a usable preview (generally a PDF) that is housed in
the submission preview service.

The specific steps involved in source processing vary among supported source
formats. The primary objective of this module is to encapsulate in one location
the orchestration involved in processing submission source packages.

The end result of source processing is the generation of a
:class:`.ConfirmSourceProcessed` event. This event signifies that the source
has been processed succesfully, and that a corresponding preview may be found
in the preview service.

Implementing support for a new format
=====================================
Processing support for a new format can be implemented by registering a new
:class:`SourceProcess`, using :func:`._make_process`. Each source process
supports a specific :class:`SubmissionContent.Format`, and should provide a
starter, a checker, and a summarizer. The preferred approach is to extend the
base classes, :class:`.BaseStarter` and :class:`.BaseChecker`.

Using a process
===============
The primary API of this module is comprised of the functions :func:`start` and
:func:`check`. These functions dispatch to the processes defined/registered in
this module.

"""
import io
from typing import IO, Dict, Tuple, NamedTuple, Optional, Any, Callable, Type

from mypy_extensions import TypedDict
from typing_extensions import Protocol

# Mypy has a hard time with namespace packages. See
# https://github.com/python/mypy/issues/5759
from arxiv.base import logging                         # type: ignore
from arxiv.integration.api.exceptions import NotFound  # type: ignore
from arxiv.submission import InvalidEvent, User, Client, Event, Submission, \
    SaveError
from .. import save
from ..domain import Preview, SubmissionContent, Submission, Compilation
from ..domain.event import ConfirmSourceProcessed, UnConfirmSourceProcessed
from ..services import PreviewService, Compiler, Filemanager

from .checks.tex_produced import check_tex_produced_pdf_from_stream

logger = logging.getLogger(__name__)

Status = str
SUCCEEDED: Status = 'succeeded'
FAILED: Status = 'failed'
IN_PROGRESS: Status = 'in_progress'
NOT_STARTED: Status = 'not_started'

Summary = Dict[str, Any]
"""Summary information suitable for generating a response to users/clients."""

class IProcess(Protocol):
    """Interface for processing classes."""

    def __init__(self, submission: Submission, user: User,
                 client: Optional[Client], token: str) -> None:
        """Initialize the process with a submission and agent context."""
        ...

    def __call__(self) -> 'CheckResult':
        """Perform the process step."""
        ...


class SourceProcess(NamedTuple):
    """Container for source processing routines for a specific format."""

    supports: SubmissionContent.Format
    """The source format supported by this process."""

    start: Type[IProcess]
    """A function for starting processing."""

    check: Type[IProcess]
    """A function for checking the status of processing."""


class CheckResult(NamedTuple):
    """Information about the result of a check."""

    status: Status
    """The status of source processing."""

    extra: Dict[str, Any]
    """
    Additional data, which may vary by source type and status.

    Summary information suitable for generating feedback to an end user or API
    consumer. E.g. to be injected in a template rendering context.
    """


_PROCESSES: Dict[SubmissionContent.Format, SourceProcess] = {}


# These exceptions refer to errors encountered during checking, and not to the
# status of source processing itself.
class SourceProcessingException(RuntimeError):
    """Base exception for this module."""


class FailedToCheckStatus(SourceProcessingException):
    """Could not check the status of processing."""


class NoProcessToCheck(SourceProcessingException):
    """Attempted to check a process that does not exist."""


class FailedToStart(SourceProcessingException):
    """Could not start processing."""


class FailedToGetResult(SourceProcessingException):
    """Could not get the result of processing."""


class _ProcessBase:
    """Base class for processing steps."""

    submission: Submission
    user: User
    client: Optional[Client]
    token: str
    extra: Dict[str, Any]
    status: Optional[Status]
    preview: Optional[Preview]

    def __init__(self, submission: Submission, user: User,
                 client: Optional[Client], token: str) -> None:
        """Initialize with a submission."""
        self.submission = submission
        self.user = user
        self.client = client
        self.token = token
        self.extra = {}
        self.status = None
        self.preview = None

    def _deposit(self, stream: IO[bytes], content_checksum: str) -> None:
        """Deposit the preview, and set :attr:`.preview`."""
        assert self.submission.source_content is not None
        # It is possible that the content is already there, we just failed to
        # update the submission last time. In the future we might do a more
        # efficient check, but this is fine for now.
        p = PreviewService.current_session()
        self.preview = p.deposit(self.submission.source_content.identifier,
                                 self.submission.source_content.checksum,
                                 stream, self.token, overwrite=True,
                                 content_checksum=content_checksum)

    def _confirm_processed(self) -> None:
        if self.preview is None:
            raise RuntimeError('Cannot confirm processing without a preview')
        event = ConfirmSourceProcessed(  # type: ignore
            creator=self.user,
            client=self.client,
            source_id=self.preview.source_id,
            source_checksum=self.preview.source_checksum,
            preview_checksum=self.preview.preview_checksum,
            size_bytes=self.preview.size_bytes,
            added=self.preview.added
        )
        self.submission, _ = save(event,
                                  submission_id=self.submission.submission_id)

    def _unconfirm_processed(self) -> None:
        assert self.submission.submission_id is not None
        if not self.submission.is_source_processed:
            return
        event = UnConfirmSourceProcessed(creator=self.user, client=self.client)  # type: ignore
        self.submission, _ = save(event,
                                  submission_id=self.submission.submission_id)

    def finish(self, stream: IO[bytes], content_checksum: str) -> None:
        """
        Wraps up by depositing the preview and updating the submission.

        This should be called by a terminal processing implementation, as the
        appropriate moment to do this may vary among workflows.
        """
        self._deposit(stream, content_checksum)
        self._confirm_processed()


class BaseStarter(_ProcessBase):
    """
    Base class for starting processing.

    To extend this class, override :func:`BaseStarter.start`. That function
    should perform whatever steps are necessary to start processing, and
    return a :const:`.Status` that indicates the disposition of
    processing for that submission.
    """

    def start(self) -> Tuple[Status, Dict[str, Any]]:
        """Start processing the source. Must be implemented by child class."""
        raise NotImplementedError('Must be implemented by a child class')

    def __call__(self) -> CheckResult:
        """Start processing a submission source package."""
        try:
            self._unconfirm_processed()
            self.status, extra = self.start()
            self.extra.update(extra)
        except SourceProcessingException:   # Propagate.
            raise
        # except Exception as e:
        #     message = f'Could not start: {self.submission.submission_id}'
        #     logger.error('Caught unexpected exception: %s', e)
        #     raise FailedToStart(message) from e
        return CheckResult(status=self.status, extra=self.extra)


class BaseChecker(_ProcessBase):
    """
    Base class for checking the status of processing.

    To extend this class, override :func:`BaseStarter.check`. That function
    should return a :const:`.Status` that indicates the disposition of
    processing for a given submission.
    """

    def check(self) -> Tuple[Status, Dict[str, Any]]:
        """Perform the status check."""
        raise NotImplementedError('Must be implemented by a subclass')

    def _pre_check(self) -> None:
        assert self.submission.source_content is not None
        if self.submission.is_source_processed \
                and self.submission.preview is not None:
            p = PreviewService.current_session()
            is_ok = p.has_preview(self.submission.source_content.identifier,
                                  self.submission.source_content.checksum,
                                  self.token,
                                  self.submission.preview.preview_checksum)
            if is_ok:
                self.extra.update({'preview': self.submission.preview})
                self.status = SUCCEEDED

    def __call__(self) -> CheckResult:
        """Check the status of source processing for a submission."""
        try:
            self._pre_check()
            self.status, extra = self.check()
            self.extra.update(extra)
        except SourceProcessingException:   # Propagate.
            raise
        except Exception as e:
            raise FailedToCheckStatus(f'Status check failed: {e}') from e
        return CheckResult(status=self.status, extra=self.extra)


class _PDFStarter(BaseStarter):
    """Start processing a PDF source package."""

    def start(self) -> Tuple[Status, Dict[str, Any]]:
        """Retrieve the PDF from the file manager service and finish."""
        if self.submission.source_content is None:
            return FAILED, {'reason': 'Submission has no source package'}
        m = Filemanager.current_session()
        try:
            stream, checksum, content_checksum = \
                m.get_single_file(self.submission.source_content.identifier,
                                  self.token)
        except NotFound:
            return FAILED, {'reason': 'Does not have a single PDF file.'}
        if self.submission.source_content.checksum != checksum:
            logger.error('source checksum and retrieved checksum do not match;'
                         f' expected {self.submission.source_content.checksum}'
                         f' but got {checksum}')
            return FAILED, {'reason': 'Source has changed.'}

        # This is a PDF-Only submission so we run TeX-produced check as soon as we have
        # the single-file PDF
        try:

            # We need a file-like object that is seekable. The ReadWrapper only
            # encapsulats a live stream from the File Manager service so
            # we read it into an in-memory object.
            filestream = io.BytesIO()

            try:
                line = stream.read()
                while len(line) > 0:
                    filestream.write(line)
                    line = stream.read()
            except StopIteration as ex:
                # This is OK
                pass
            except Exception as ex:
                logger.error(f'There was a problem reading the content stream: {ex}\n')
                return FAILED, {'reason': 'There was a problem reading the '
                                          'content stream: {ex}.'}
            filestream.seek(0,0)

            # Finally run the TeX Produced check
            if check_tex_produced_pdf_from_stream(filestream):
                logger.error('Detected a TeX-produced PDF')
                return FAILED, {'reason': 'PDF appears to have been produced from TeX source.'}
            else:
                return SUCCEEDED, {}
        except Exception as ex:
            logger.error(f'TeX-produced check failed:{ex}')
            return FAILED, {'reason': 'TeX-produced check failed.'}

        self.finish(stream, content_checksum)
        return SUCCEEDED, {}


class _PDFChecker(BaseChecker):
    """Check the status of a PDF source package."""

    def check(self) -> Tuple[Status, Dict[str, Any]]:
        """Verify that the preview is present."""
        if self.submission.source_content is None:
            return FAILED, {'reason': 'Submission has no source package'}
        if self.status is not None:
            return self.status, {}
        p = PreviewService.current_session()
        try:
            preview = p.get_metadata(
                self.submission.source_content.identifier,
                self.submission.source_content.checksum,
                self.token
            )
        except NotFound:
            return NOT_STARTED, {}
        if self.submission.source_content.checksum != preview.source_checksum:
            return NOT_STARTED, {'reason': 'Source has changed.'}
        self.preview = preview
        return SUCCEEDED, {}


class _CompilationStarter(BaseStarter):
    """Starts compilation via the compiler service."""

    def start(self) -> Tuple[Status, Dict[str, Any]]:
        """Start compilation."""
        if self.submission.source_content is None:
            return FAILED, {'reason': 'Submission has no source package'}
        c = Compiler.current_session()
        stat = c.compile(self.submission.source_content.identifier,
                         self.submission.source_content.checksum, self.token,
                         *self._make_stamp(), force=True)

        # There is no good reason for this to come back as failed right off
        # the bat, so we will treat it as a bona fide exception rather than
        # just FAILED state.
        if stat.is_failed:
            raise FailedToStart(f'Failed to start: {stat.Reason.value}')

        # If we got this far, we're off to the races.
        return IN_PROGRESS, {}

    def _make_stamp(self) -> Tuple[str, str]:
        """
        Create label and link for PS/PDF stamp/watermark.

        Stamp format for submission is of form ``[identifier category date]``

        ``arXiv:submit/<submission_id>  [<primary category>] DD MON YYYY``

        Date segment is optional and added automatically by converter.
        """
        stamp_label = f'arXiv:submit/{self.submission.submission_id}'

        if self.submission.primary_classification \
                    and self.submission.primary_classification.category:
            # Create stamp label string - for now we'll let converter
            #                             add date segment to stamp label
            primary_category = self.submission.primary_classification.category
            stamp_label = f'{stamp_label} [{primary_category}]'

        stamp_link = f'/{self.submission.submission_id}/preview.pdf'
        return stamp_label, stamp_link


class _CompilationChecker(BaseChecker):
    def check(self) -> Tuple[Status, Dict[str, Any]]:
        """Check the status of compilation, and finish if succeeded."""
        if self.submission.source_content is None:
            return FAILED, {'reason': 'Submission has no source package'}
        status: Status = self.status or IN_PROGRESS
        extra: Dict[str, Any] = {}
        comp: Optional[Compilation] = None
        c = Compiler.current_session()
        if status not in [SUCCEEDED, FAILED]:
            try:
                comp = c.get_status(self.submission.source_content.identifier,
                                    self.submission.source_content.checksum,
                                    self.token)
                extra.update({'compilation': comp})
            except NotFound:     # Nothing to do.
                return NOT_STARTED, extra

        # Ship the product to preview and confirm processing. We only want to
        # do this once. The pre-check will have set a status if it is known
        # ahead of time.
        if status is IN_PROGRESS and comp is not None and comp.is_succeeded:
            # Ship the compiled PDF off to the preview service.
            prod = c.get_product(self.submission.source_content.identifier,
                                 self.submission.source_content.checksum,
                                 self.token)

            # For Postscript source format ONLY: AutoTeX will convert
            # Postscript files to PDF (instead of compiling it). We run
            # TeX-produced check on final generated PDF since it is easier
            # than getting all of the content files (Postscript + images)
            # and checking each one. TeX-produced charactersistics appears
            # to carry through to generated PDF.
            if self.submission.source_content.source_format == \
                    SubmissionContent.Format.POSTSCRIPT:
                try:
                    # Finally run the TeX-Produced check
                    if check_tex_produced_pdf_from_stream(prod.stream):
                        logger.error('Detected a TeX-produced Postscript submission.')
                        return FAILED, {'reason':
                                            'Postscript submission appears to'
                                            ' have been produced from TeX source.'}
                    else:
                        return SUCCEEDED, {}
                except Exception as ex:
                    logger.error(f'TeX-produced check failed:{ex}')
                    return FAILED, {'reason': 'TeX-produced check failed.'}

            else:
                self.finish(prod.stream, prod.checksum)
                status = SUCCEEDED
        elif comp is not None and comp.is_failed:
            status = FAILED
            extra.update({'reason': comp.reason.value,
                          'description': comp.description})

        # Get the log output for both success and failure.
        log_output: Optional[str] = None
        if status in [SUCCEEDED, FAILED]:
            try:
                log = c.get_log(self.submission.source_content.identifier,
                                self.submission.source_content.checksum,
                                self.token)
                log_output = log.stream.read().decode('utf-8')
            except NotFound:
                log_output = None
            extra.update({'log_output': log_output})
        return status, extra


def _make_process(supports: SubmissionContent.Format, starter: Type[IProcess],
                  checker: Type[IProcess]) -> SourceProcess:

    proc = SourceProcess(supports, starter, checker)
    _PROCESSES[supports] = proc
    return proc


def _get_process(source_format: SubmissionContent.Format) -> SourceProcess:
    proc = _PROCESSES.get(source_format, None)
    if proc is None:
        raise NotImplementedError(f'No process found for {source_format}')
    return proc


def _get_and_call_starter(submission: Submission, user: User,
                          client: Optional[Client], token: str) -> CheckResult:
    assert submission.source_content is not None
    proc = _get_process(submission.source_content.source_format)
    return proc.start(submission, user, client, token)()


def _get_and_call_checker(submission: Submission, user: User,
                          client: Optional[Client], token: str) -> CheckResult:
    assert submission.source_content is not None
    proc = _get_process(submission.source_content.source_format)
    return proc.check(submission, user, client, token)()


def start(submission: Submission, user: User, client: Optional[Client],
          token: str) -> CheckResult:
    """
    Start processing the source package for a submission.

    Parameters
    ----------
    submission : :class:`.Submission`
        The submission to process.
    user : :class:`.User`
        arXiv user who originated the request.
    client : :class:`.Client` or None
        API client that handled the request, if any.
    token : str
        Authn/z token for the request.

    Returns
    -------
    :class:`.CheckResult`
        Status indicates the disposition of the process.

    Raises
    ------
    :class:`NotImplementedError`
        Raised if the submission source format is not supported by this module.

    """
    return _get_and_call_starter(submission, user, client, token)


def check(submission: Submission, user: User, client: Optional[Client],
          token: str) -> CheckResult:
    """
    Check the status of source processing for a submission.

    Parameters
    ----------
    submission : :class:`.Submission`
        The submission to process.
    user : :class:`.User`
        arXiv user who originated the request.
    client : :class:`.Client` or None
        API client that handled the request, if any.
    token : str
        Authn/z token for the request.

    Returns
    -------
    :class:`.CheckResult`
        Status indicates the disposition of the process.

    Raises
    ------
    :class:`NotImplementedError`
        Raised if the submission source format is not supported by this module.

    """
    return _get_and_call_checker(submission, user, client, token)


TeXProcess = _make_process(SubmissionContent.Format.TEX,
                           _CompilationStarter,
                           _CompilationChecker)
"""Support for processing TeX submissions."""


PostscriptProcess = _make_process(SubmissionContent.Format.POSTSCRIPT,
                                  _CompilationStarter,
                                  _CompilationChecker)
"""Support for processing Postscript submissions."""


PDFProcess = _make_process(SubmissionContent.Format.PDF,
                           _PDFStarter,
                           _PDFChecker)
"""Support for processing PDF submissions."""