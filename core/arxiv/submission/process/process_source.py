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
from typing import IO, Dict, Tuple, NamedTuple, Optional, Any, Callable

from mypy_extensions import TypedDict

from arxiv.integration.api.exceptions import NotFound
from arxiv.submission import InvalidEvent, User, Client, Event, Submission, \
    SaveError
from .. import save
from ..domain import Preview, SubmissionContent, Submission
from ..domain.event import ConfirmSourceProcessed
from ..services import PreviewService, Compiler, Filemanager

Status = str
SUCCEEDED: Status = 'succeeded'
FAILED: Status = 'failed'
IN_PROGRESS: Status = 'in_progress'

Summary = Dict[str, Any]
"""Summary information suitable for generating a response to users/clients."""

IStarter = Callable[[Submission, User, Optional[Client], str], 'CheckResult']
"""Interface for processing starter functions."""

IChecker = Callable[[Submission, User, Optional[Client], str], 'CheckResult']
"""Interface for status check functions."""


class SourceProcess(NamedTuple):
    """Container for source processing routines for a specific format."""

    supports: SubmissionContent.Format
    """The source format supported by this process."""

    start: IStarter
    """A function for starting processing."""

    check: IChecker
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


class BaseStarter:
    """
    Base class for starting processing.

    To extend this class, override :func:`BaseStarter.start`. That function
    should perform whatever steps are necessary to start processing, and
    return a :const:`.Status` that indicates the disposition of
    processing for that submission.
    """

    def start(self, submission: Submission, user: User,
              client: Optional[Client],
              token: str) -> Tuple[Status, Dict[str, Any]]:
        """Start processing the source. Must be implemented by child class."""
        raise NotImplementedError('Must be implemented by a child class')

    def __call__(self, submission: Submission, user: User,
                 client: Optional[Client], token: str) -> CheckResult:
        """Start processing a submission source package."""
        try:
            status, extra = self.start(submission, user, client, token)
        except SourceProcessingException:   # Propagate.
            raise
        except Exception as e:
            message = f'Could not start processing {submission.submission_id}'
            raise FailedToStart(message) from e
        return CheckResult(status=status, extra=extra)


class BaseChecker:
    """
    Base class for checking the status of processing.

    To extend this class, override :func:`BaseStarter.check`. That function
    should return a :const:`.Status` that indicates the disposition of
    processing for a given submission.
    """

    def check(self, submission: Submission, user: User,
              client: Optional[Client],
              token: str) -> Tuple[Status, Dict[str, Any]]:
        """Perform the status check."""
        raise NotImplementedError('Must be implemented by a subclass')

    # Some of these args are unused; keeping them for the sake of a consistent
    # API.
    def _pre_check(self, submission: Submission, user: User,
                   client: Optional[Client],
                   token: str) -> Optional[Dict[str, Any]]:
        # If the preview service is already consistent with the submission,
        # then there is nothing left to do.
        if submission.is_source_processed and submission.preview is not None:
            p = PreviewService.current_session()
            is_ok = p.has_preview(submission.source_content.identifier,
                                  submission.source_content.checksum, token,
                                  submission.preview.preview_checksum)
            if is_ok:
                return {'preview': submission.preview}
        return None

    def _deposit(self, submission: Submission, user: User,
                 client: Optional[Client], token: str, stream: IO[bytes],
                 content_checksum: str) -> Preview:
        # It is possible that the content is already there, we just failed to
        # update the submission last time. In the future we might do a more
        # efficient check, but this is fine for now.
        p = PreviewService.current_session()
        preview = p.deposit(submission.source_content.identifier,
                            submission.source_content.checksum,
                            stream, token, overwrite=True,
                            content_checksum=content_checksum)

        save(ConfirmSourceProcessed(creator=user,   # type: ignore
                                    client=client,
                                    source_id=preview.source_id,
                                    source_checksum=preview.source_checksum,
                                    preview_checksum=preview.preview_checksum,
                                    size_bytes=preview.size_bytes,
                                    added=preview.added),
             submission_id=submission.submission_id)
        return preview

    def __call__(self, submission: Submission, user: User,
                 client: Optional[Client], token: str) -> CheckResult:
        """Check the status of source processing for a submission."""
        result = self._pre_check(submission, user, client, token)
        if result is not None:  # Don't repeat any uncessary work.
            return CheckResult(status=SUCCEEDED, extra=result)

        try:
            status, extra = self.check(submission, user, client, token)
        except SourceProcessingException:   # Propagate.
            raise
        except Exception as e:
            raise FailedToCheckStatus(f'Status check failed: {e}') from e
        return CheckResult(status=status, extra=extra)


class _PDFStarter(BaseStarter):
    """Start processing a PDF source package."""

    def start(self, submission: Submission, user: User,
              client: Optional[Client],
              token: str) -> Tuple[Status, Dict[str, Any]]:
        """Ship the PDF to the preview service."""
        m = Filemanager.current_session()
        if m.has_single_file(submission.source_content.identifier, token,
                             file_type='PDF'):
            return IN_PROGRESS, {}
        return FAILED, {'reason': 'Not a single-file PDF submission.'}


class _PDFChecker(BaseChecker):
    """Check the status of a PDF source package."""

    def check(self, submission: Submission, user: User,
              client: Optional[Client],
              token: str) -> Tuple[Status, Dict[str, Any]]:
        """Verify that the preview is present."""
        m = Filemanager.current_session()

        # Ship the single PDF file from the file manager service to the
        # preview service.
        try:
            stream, checksum, content_checksum = \
                m.get_single_file(submission.source_content.identifier, token)
        except NotFound:
            return FAILED, {'reason': 'Does not have a single PDF file.'}
        if submission.source_content.checksum != checksum:
            return FAILED, {'reason': 'Source has changed.'}

        preview = self._deposit(submission, user, client, token, stream,
                                content_checksum)
        return SUCCEEDED, {'preview': preview}


class _CompilationStarter(BaseStarter):
    """Starts compilation via the compiler service."""

    def start(self, submission: Submission, user: User,
              client: Optional[Client],
              token: str) -> Tuple[Status, Dict[str, Any]]:
        """Start compilation."""
        c = Compiler.current_session()
        stamp_label, stamp_link = self._make_stamp(submission)
        stat = c.compile(submission.source_content.identifier,
                         submission.source_content.checksum,
                         token,
                         stamp_label,
                         stamp_link,
                         force=True)
        # There is no good reason for this to come back as failed right off
        # the bat, so we will treat it as a bona fide exception rather than
        # just FAILED state.
        if stat.is_failed:
            raise FailedToStart(f'Failed to start: {stat.Reason.value}')

        # If we got this far, we're off to the races.
        return IN_PROGRESS, {}

    def _make_stamp(self, submission: Submission) -> Tuple[str, str]:
        # Create label and link for PS/PDF stamp/watermark.
        #
        # Stamp format for submission is of form [identifier category date]
        #
        # "arXiv:submit/<submission_id>  [<primary category>] DD MON YYYY
        #
        # Date segment is optional and added automatically by converter.
        #
        stamp_label = f'arXiv:submit/{submission.submission_id}'

        if submission.primary_classification \
                    and submission.primary_classification.category:
            # Create stamp label string - for now we'll let converter
            #                             add date segment to stamp label
            primary_category = submission.primary_classification.category
            stamp_label = f'{stamp_label} [{primary_category}]'

        stamp_link = f'/{submission.submission_id}/preview.pdf'
        return stamp_label, stamp_link


class _CompilationChecker(BaseChecker):
    def check(self, submission: Submission, user: User,
              client: Optional[Client],
              token: str) -> Tuple[Status, Dict[str, Any]]:
        c = Compiler.current_session()
        try:
            compilation = c.get_status(submission.source_content.identifier,
                                       submission.source_content.checksum,
                                       token)
        except NotFound as e:     # Nothing to do.
            raise NoProcessToCheck('No compilation process found') from e

        if compilation.is_succeeded:
            # Ship the compiled PDF off to the preview service.
            prod = c.get_product(submission.source_content.identifier,
                                 submission.source_content.checksum, token)
            preview = self._deposit(submission, user, client, token,
                                    prod.stream, prod.checksum)
            log_output: Optional[str]
            try:
                log = c.get_log(submission.source_content.identifier,
                                submission.source_content.checksum, token)
                log_output = log.read().decode('utf-8')
            except NotFound:
                log_output = None
            return SUCCEEDED, {'preview': preview, 'log_output': log_output}
        elif compilation.is_failed:
            return FAILED, {'compilation': compilation}
        return IN_PROGRESS, {'compilation': compilation}


def _make_process(supports: SubmissionContent.Format, starter: BaseStarter,
                  checker: BaseChecker) -> SourceProcess:

    proc = SourceProcess(supports, starter, checker)
    _PROCESSES[supports] = proc
    return proc


def _get_process(source_format: SubmissionContent.Format) -> SourceProcess:
    proc = _PROCESSES.get(source_format, None)
    if proc is None:
        raise NotImplementedError(f'No process found for {source_format}')
    return proc


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
    proc = _get_process(submission.source_content.source_format)
    return proc.start(submission, user, client, token)


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
    proc = _get_process(submission.source_content.source_format)
    return proc.check(submission, user, client, token)


TeXProcess = _make_process(
    SubmissionContent.Format.TEX,
    _CompilationStarter(),
    _CompilationChecker()
)
"""Support for processing TeX submissions."""


PostscriptProcess = _make_process(
    SubmissionContent.Format.POSTSCRIPT,
    _CompilationStarter(),
    _CompilationChecker()
)
"""Support for processing Postscript submissions."""


PDFProcess = _make_process(
    SubmissionContent.Format.PDF,
    _PDFStarter(),
    _PDFChecker()
)
"""Support for processing PDF submissions."""