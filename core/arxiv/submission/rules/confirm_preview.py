"""Things that should happen upon the :class:`.ConfirmPreview` command."""

from typing import Iterable

from ..domain.event import Event, AddAnnotation, RemoveAnnotation, \
    ConfirmPreview
from ..domain.annotation import PlainTextExtraction
from ..domain.submission import Submission
from ..domain.agent import Agent, User
from ..services import plaintext
from ..tasks import is_async


@ConfirmPreview.bind()
@is_async
def extract_plain_text(event: ConfirmPreview, before: Submission,
                       after: Submission, creator: Agent) -> Iterable[Event]:
    """Use the plain text extraction service to extract text from the PDF."""
    identifier = after.source_content.identifier
    try:
        plaintext.request_extraction(after.source_content.identifier)
        yield AddAnnotation(creator=creator,
                            annotation=PlainTextExtraction(
                                status=PlainTextExtraction.REQUESTED,
                                identifier=identifier))
        while True:
            if plaintext.extraction_is_complete(identifier):
                yield AddAnnotation(
                    creator=creator,
                    annotation=PlainTextExtraction(identifier=identifier))
    except plaintext.RequestFailed as e:
        yield AddAnnotation(
            creator=creator,
            annotation=PlainTextExtraction(status=PlainTextExtraction.FAILED,
                                           identifier=identifier))
