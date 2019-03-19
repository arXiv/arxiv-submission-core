"""Extract text, and get suggestions, features, and flags from Classifier."""

from typing import Iterable, Optional
from itertools import count
import time

from arxiv.taxonomy import CATEGORIES, Category
from arxiv.integration.api import exceptions

from ..domain.event import Event, AddProcessStatus, ConfirmPreview, \
    AddClassifierResults, AddContentFlag, AddFeature
from ..domain.event.event import Condition
from ..domain.submission import Submission
from ..domain.flag import Flag, ContentFlag
from ..domain.annotation import Feature
from ..domain.agent import Agent, User
from ..domain.process import ProcessStatus
from ..services import Classifier, PlainTextService
from ..services.plaintext import ExtractionFailed
from ..tasks import is_async

# TODO: make this configurable
PROPOSAL_THRESHOLD = 0.57   # Equiv. to logodds of 0.3.
"""This is the threshold for generating a proposal from a classifier result."""

# TODO: make this configurable.
LOW_STOP_PERCENT = 0.10
"""This is the threshold for abornmally low stopword content by percentage."""

LOW_STOP = 400
"""This is the threshold for abornmally low stopword content by count."""

HIGH_STOP_PERCENT = 0.30
"""This is the threshold for abnormally high stopword content by percentage."""

MULTIPLE_LIMIT = 1.01
LINENOS_LIMIT = 0

Process = ProcessStatus.Process
Status = ProcessStatus.Status


@ConfirmPreview.bind()  # As soon as the user has confirmed their PDF preview.
@is_async
def extract_plain_text(event: ConfirmPreview, before: Submission,
                       after: Submission, creator: Agent,
                       task_id: Optional[str] = None,
                       **kwargs) -> Iterable[Event]:
    """Use the plain text extraction service to extract text from the PDF."""
    identifier = after.source_content.identifier
    process = ProcessStatus.Process.PLAIN_TEXT_EXTRACTION
    try:
        PlainTextService.request_extraction(after.source_content.identifier)
        yield AddProcessStatus(creator=creator, process=process,
                               status=ProcessStatus.Status.REQUESTED,
                               service='plaintext',
                               version=PlainTextService.VERSION,
                               identifier=identifier, monitoring_task=task_id)
        for tries in count(1):
            if PlainTextService.extraction_is_complete(identifier):
                yield AddProcessStatus(creator=creator, process=process,
                                       status=ProcessStatus.Status.SUCCEEDED,
                                       service='plaintext',
                                       version=PlainTextService.VERSION,
                                       identifier=identifier,
                                       monitoring_task=task_id)
                break
            time.sleep(tries ** 2)  # Exponential back-off.
    except (exceptions.RequestFailed, ExtractionFailed) as e:
        reason = 'request failed (%s): %s' % (type(e).__name__, e)
        yield AddProcessStatus(creator=creator, process=process,
                               status=ProcessStatus.Status.FAILED,
                               service='plaintext',
                               version=PlainTextService.VERSION,
                               identifier=identifier, reason=reason,
                               monitoring_task=task_id)


def when(process: Process, status: Status) -> Condition:
    """Generate a condition for a :class:`Process` and :class:`Status`."""
    def inner(event: AddProcessStatus, before: Submission,
              after: Submission) -> bool:
        return event.process is process and event.status is status
    return inner


CLASSIFIER_FLAGS = {
    '%stop': None,  # We will handle this ourselves.
    'stops': None,  # We will handle this ourselves.
    'language': ContentFlag.FlagTypes.LANGUAGE,
    'charset': ContentFlag.FlagTypes.CHARACTER_SET,
    'linenos': ContentFlag.FlagTypes.LINE_NUMBERS
}
FEATURE_TYPES = {

}


@AddProcessStatus.bind(when(Process.PLAIN_TEXT_EXTRACTION, Status.SUCCEEDED))
@is_async
def call_classifier(event: AddProcessStatus, before: Submission,
                    after: Submission, creator: Agent,
                    task_id: Optional[str] = None,
                    **kwargs) -> Iterable[Event]:
    """Request the opinion of the auto-Classifier."""
    identifier = after.source_content.identifier
    yield AddProcessStatus(creator=creator, process=Process.CLASSIFICATION,
                           status=ProcessStatus.Status.REQUESTED,
                           service=Classifier.SERVICE,
                           version=Classifier.VERSION,
                           identifier=identifier, monitoring_task=task_id)
    try:
        suggestions, flags, counts = \
            Classifier.classify(
                PlainTextService.retrieve_content(identifier))
    except (exceptions.RequestFailed, exceptions.RequestFailed) as e:
        reason = 'request failed (%s): %s' % (type(e), e)
        yield AddProcessStatus(creator=creator,
                               process=Process.CLASSIFICATION,
                               status=ProcessStatus.Status.FAILED,
                               service=Classifier.SERVICE,
                               version=Classifier.VERSION,
                               identifier=identifier, reason=reason,
                               monitoring_task=task_id)
        return

    success = AddProcessStatus(creator=creator,
                               process=Process.CLASSIFICATION,
                               status=ProcessStatus.Status.SUCCEEDED,
                               service=Classifier.SERVICE,
                               version=Classifier.VERSION,
                               identifier=identifier, monitoring_task=task_id)
    yield success
    yield AddClassifierResults(creator=creator,
                               results=[{'category': suggestion.category,
                                         'probability': suggestion.probability}
                                        for suggestion in suggestions])

    for flag in flags:
        comment = "flag from classification succeeded at %s" \
            % success.created.isoformat()
        flag_type = CLASSIFIER_FLAGS.get(flag.key)
        if flag_type is None:
            continue
        yield AddContentFlag(creator=creator, flag_type=flag_type,
                             flag_data=flag.value, comment=comment)

    yield AddFeature(creator=creator,
                     feature_type=Feature.FeatureTypes.CHARACTER_COUNT,
                     feature_value=counts.chars)
    yield AddFeature(creator=creator,
                     feature_type=Feature.FeatureTypes.PAGE_COUNT,
                     feature_value=counts.pages)
    yield AddFeature(creator=creator,
                     feature_type=Feature.FeatureTypes.STOPWORD_COUNT,
                     feature_value=counts.stops)
    yield AddFeature(creator=creator,
                     feature_type=Feature.FeatureTypes.WORD_COUNT,
                     feature_value=counts.words)
    yield AddFeature(creator=creator,
                     feature_type=Feature.FeatureTypes.STOPWORD_PERCENT,
                     feature_value=counts.stops/counts.words)


def feature_type_is(feature_type: Feature.FeatureTypes) -> Condition:
    """Generate a condition based on feature type."""
    def condition(event: AddFeature, before: Submission,
                  after: Submission) -> bool:
        return event.feature_type is feature_type
    return condition


@AddFeature.bind(feature_type_is(Feature.FeatureTypes.STOPWORD_PERCENT))
def check_stop_percent(event: AddFeature, before: Submission,
                       after: Submission, creator: Agent,
                       task_id: Optional[str] = None,
                       **kwargs) -> Iterable[Event]:
    """Flag the submission if the percentage of stopwords is too low."""
    if event.feature_value < LOW_STOP_PERCENT:
        yield AddContentFlag(
            creator=creator,
            flag_type=ContentFlag.FlagTypes.LOW_STOP_PERCENT,
            flag_data=event.feature_value,
            comment="Classifier reports low stops or %stops"
        )


@AddFeature.bind(feature_type_is(Feature.FeatureTypes.STOPWORD_COUNT))
def check_stop_count(event: AddFeature, before: Submission,
                     after: Submission, creator: Agent,
                     task_id: Optional[str] = None,
                     **kwargs) -> Iterable[Event]:
    """Flag the submission if the number of stopwords is too low."""
    if event.feature_value < LOW_STOP:
        yield AddContentFlag(
            creator=creator,
            flag_type=ContentFlag.FlagTypes.LOW_STOP,
            flag_data=event.feature_value,
            comment="Classifier reports low stops or %stops"
        )
