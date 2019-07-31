"""Core procedures for processing source content."""

import io
from typing import IO, Dict, Tuple, NamedTuple, Optional, Any, Type

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


class SourceProcess(NamedTuple):
    """."""

    supports: SubmissionContent.Format
    start: 'BaseStarter'
    check: 'BaseChecker'
    summarize: 'BaseSummarizer'


_PROCESSES: Dict[SubmissionContent.Format, SourceProcess] = {}


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


class BaseChecker:
    """Checks the status of processing."""

    def check(self, submission: Submission, token: str) -> Status:
        raise NotImplementedError('Must be implemented by a subclass')

    def on_failure(self, submission: Submission, exc: Exception) -> None:
        pass

    def fail(self, submission: Submission, exc: Exception) -> None:
        """Generate a failure exception."""
        self.on_failure(submission, exc)
        raise FailedToCheckStatus(f'Status check failed: {exc}') from exc

    def finish(self, submission: Submission, user: User,
               client: Optional[Client], token: str) -> None:
        try:
            save(ConfirmSourceProcessed(creator=user, client=client),  # type: ignore
                 submission_id=submission.submission_id)
        except SaveError as e:
            self.fail(submission, e)

    def __call__(self, submission: Submission, user: User,
                 client: Optional[Client], token: str) -> Status:
        if submission.is_source_processed:      # Already succeeded.
            return SUCCEEDED
        try:
            status = self.check(submission, token)
            if status == SUCCEEDED:
                self.finish(submission, user, client, token)
        except SourceProcessingException:   # Propagate.
            raise
        except Exception as e:
            self.fail(submission, e)
        return status



class BaseStarter:
    """Starts processing."""

    def start(self, submission: Submission, token: str) -> Status:
        raise NotImplementedError('Must be implemented by a child class')

    def on_success(self, submission: Submission, token: str) -> None:
        pass

    def on_failure(self, submission: Submission, exc: Exception) -> None:
        pass

    def fail(self, submission: Submission, exc: Exception) -> None:
        self.on_failure(submission, exc)
        message = f'Could not start processing {submission.submission_id}'
        raise FailedToStart(message) from exc

    def __call__(self, submission: Submission, user: User,
                 client: Optional[Client], token: str) -> Status:
        try:
            status = self.start(submission, token)
            self.on_success(submission, token)
        except SourceProcessingException:   # Propagate.
            raise
        except Exception as e:
            self.fail(submission, e)
        return status


class BaseSummarizer:
    """Displays the result of processing."""

    def on_failure(self, submission: Submission, exc: Exception) -> None:
        pass

    def fail(self, submission: Submission, exc: Exception) -> None:
        self.on_failure(submission, exc)
        message = f'Could not summarize processing {submission.submission_id}'
        raise FailedToGetResult(message) from exc

    def summarize(self, submission: Submission, token: str) -> Dict[str, Any]:
        raise NotImplementedError('Must be implemented by a child class')
        return {}

    def __call__(self, submission: Submission, user: User,
                 client: Optional[Client], token: str) -> Dict[str, Any]:
        p = PreviewService.current_session()
        try:
            summary = self.summarize(submission, token)
            preview = p.get_metadata(submission.source_content.identifier,
                                     submission.source_content.checksum,
                                     token)
            summary.update({'preview': preview})
        except SourceProcessingException:   # Propagate.
            raise
        except Exception as e:
            self.fail(submission, e)
        return summary


class _PDFStarter(BaseStarter):
    def start(self, submission: Submission, token: str) -> Status:
        m = Filemanager.current_session()
        stream, fmt, source_checksum, stream_checksum = \
            m.get_single_file(submission.source_content.identifier, token)
        if submission.source_content.checksum != source_checksum:
            raise FailedToStart('Source has changed')
        _ship_to_preview(submission, stream, stream_checksum, token)
        return IN_PROGRESS


class _PDFChecker(BaseChecker):
    def check(self, submission: Submission, token: str) -> Status:
        p = PreviewService.current_session()
        if p.has_preview(submission.source_content.identifier,
                         submission.source_content.checksum,
                         token):
            return SUCCEEDED
        return FAILED


class _PDFSummarizer(BaseSummarizer):
    def summarize(self, submission: Submission, token: str) -> Dict[str, Any]:
        return {}


class _CompilationStarter(BaseStarter):
    """Starts compilation via the compiler service."""

    def start(self, submission: Submission, token: str) -> Status:
        """Start compilation."""
        c = Compiler.current_session()
        stamp_label, stamp_link = self._make_stamp(submission)
        stat = c.compile(submission.source_content.identifier,
                         submission.source_content.checksum,
                         token,
                         stamp_label,
                         stamp_link,
                         force=True)
        if stat.is_failed:
            raise FailedToStart(f'Failed to start: {stat.Reason.value}')
        return IN_PROGRESS

    def _make_stamp(self, submission: Submission) -> Tuple[str, str]:   # label, URL
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
    def _get_preview(self, submission: Submission, token: str) \
            -> Tuple[IO[bytes], str]:
        c = Compiler.current_session()
        product = c.get_product(submission.source_content.identifier,
                                submission.source_content.checksum,
                                token)
        return product.stream, product.checksum

    def check(self, submission: Submission, token: str) -> Status:
        c = Compiler.current_session()
        try:
            compilation = c.get_status(submission.source_content.identifier,
                                       submission.source_content.checksum,
                                       token)
        except NotFound as e:     # Nothing to do.
            raise NoProcessToCheck('No compilation process found') from e
        if compilation.is_succeeded:
            stream, stream_checksum = self._get_preview(submission, token)
            _ship_to_preview(submission, stream, stream_checksum, token)
            return SUCCEEDED
        elif compilation.is_failed:
            return FAILED
        return IN_PROGRESS


class _CompilationSummarizer(BaseSummarizer):
    def summarize(self, submission: Submission, token: str) -> Dict[str, Any]:
        c = Compiler.current_session()
        log = c.get_log(submission.source_content.identifier,
                        submission.source_content.checksum,
                        token)
        return {'log_output': log.stream.read().decode('utf-8')}


def _ship_to_preview(submission: Submission, stream: IO[bytes],
                     preview_checksum: str, token: str) -> None:
    p = PreviewService.current_session()
    p.deposit(submission.source_content.identifier,
              submission.source_content.checksum,
              stream, token, overwrite=True)


def _make_process(supports: SubmissionContent.Format,
                  starter: BaseStarter,
                  checker: BaseChecker,
                  summarizer: BaseSummarizer) -> SourceProcess:

    proc = SourceProcess(supports, starter, checker, summarizer)
    _PROCESSES[supports] = proc
    return proc


def _get_process(source_format: SubmissionContent.Format) -> SourceProcess:
    proc = _PROCESSES.get(source_format, None)
    if proc is None:
        raise NotImplementedError(f'No process found for {source_format}')
    return proc


def start(submission: Submission, user: User, client: Optional[Client],
          token: str) -> Status:
    proc = _get_process(submission.source_content.source_format)
    return proc.start(submission, user, client, token)


def check(submission: Submission, user: User, client: Optional[Client],
          token: str) -> Status:
    proc = _get_process(submission.source_content.source_format)
    return proc.check(submission, user, client, token)


def summarize(submission: Submission, user: User, client: Optional[Client],
              token: str) -> Dict[str, Any]:
    proc = _get_process(submission.source_content.source_format)
    return proc.summarize(submission, user, client, token)


TeXProcess = _make_process(
    SubmissionContent.Format.TEX,
    _CompilationStarter(),
    _CompilationChecker(),
    _CompilationSummarizer()
)


PostscriptProcess = _make_process(
    SubmissionContent.Format.POSTSCRIPT,
    _CompilationStarter(),
    _CompilationChecker(),
    _CompilationSummarizer()
)


PDFProcess = _make_process(
    SubmissionContent.Format.PDF,
    _PDFStarter(),
    _PDFChecker(),
    _PDFSummarizer()
)

