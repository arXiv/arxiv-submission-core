from typing import List

from ..domain.event import Event, AddAnnotation, RemoveAnnotation
from ..domain.event.event import Condition
from ..domain.annotation import ClassifierResult, PlainTextExtraction
from ..domain.submission import Submission
from ..domain.agent import Agent, User
from ..services import classic, classifier
from ..tasks import is_async


def annotation_type_is(this_type: type) -> Condition:
    """Build condition for an :class:`AddAnnotation` from annotation type."""
    def condition(event: AddAnnotation, before: Submission,
                  after: Submission, creator: Agent) -> bool:
        return type(event.annotation) is this_type
    return condition


# TODO: here is where we retrieve text from plaintext service and send to
# classifier.
@AddAnnotation.bind(annotation_type_is(PlainTextExtraction))
@is_async
def call_classifier(event: AddAnnotation, before: Submission,
                    after: Submission, creator: Agent) -> List[Event]:
    if event.annotation.status == PlainTextExtraction.FAILED:
        # TODO: log failure
        return []
    return []


# TODO: here is where we hook in business logic for handling classifier result.
@AddAnnotation.bind(annotation_type_is(ClassifierResult))
@is_async
def propose_reclassification(event: AddAnnotation, before: Submission,
                             after: Submission, creator: Agent) -> List[Event]:
    return []
