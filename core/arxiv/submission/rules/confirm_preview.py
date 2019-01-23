"""Things that should happen upon the :class:`.ConfirmPreview` command."""

from typing import Iterable

from ..domain.event import Event, AddProcessStatus, ConfirmPreview
from ..domain.submission import Submission
from ..domain.agent import Agent, User
from ..domain.process import ProcessStatus
from ..services import plaintext
from ..tasks import is_async


@ConfirmPreview.bind()
@is_async
def extract_plain_text(event: ConfirmPreview, before: Submission,
                       after: Submission, creator: Agent) -> Iterable[Event]:
    """Use the plain text extraction service to extract text from the PDF."""
    identifier = after.source_content.identifier
    process = ProcessStatus.Processes.PLAIN_TEXT_EXTRACTION
    try:
        plaintext.request_extraction(after.source_content.identifier)
        yield AddProcessStatus(creator=creator, process=process,
                               status=ProcessStatus.Status.REQUESTED,
                               service='plaintext', version=plaintext.VERSION,
                               identifier=identifier)
        while True:
            if plaintext.extraction_is_complete(identifier):
                yield AddProcessStatus(creator=creator, process=process,
                                       status=ProcessStatus.Status.SUCCEEDED,
                                       service='plaintext',
                                       version=plaintext.VERSION,
                                       identifier=identifier)
    except plaintext.RequestFailed as e:
        reason = 'request failed (%s): %s' % (type(e), e)
        yield AddProcessStatus(creator=creator, process=process,
                               status=ProcessStatus.Status.FAILED,
                               service='plaintext', version=plaintext.VERSION,
                               identifier=identifier, reason=reason)
