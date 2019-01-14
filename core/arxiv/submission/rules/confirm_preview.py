from typing import List

from ..domain.event import Event, AddAnnotation, RemoveAnnotation, \
    ConfirmPreview
from ..domain.annotation import ClassifierSuggestion
from ..domain.submission import Submission
from ..domain.agent import Agent, User
from ..services import classic
from ..tasks import is_async


# TODO: here is where we hook into plaintext service.
@ConfirmPreview.bind()
@is_async
def extract_plain_text(event: ConfirmPreview, before: Submission,
                       after: Submission, creator: Agent) -> List[Event]:
    """Use the plain text extraction service to extract text from the PDF."""
    return []
