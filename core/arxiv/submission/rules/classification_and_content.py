"""Extract text, and get suggestions, features, and flags from classifier."""

from typing import Iterable

from ..domain.event import Event, AddProcessStatus, ConfirmPreview, \
    AddClassifierResults, AddContentFlag, AddFeature
from ..domain.event.event import Condition
from ..domain.submission import Submission
from ..domain.flag import Flag, ContentFlag
from ..domain.annotation import Feature
from ..domain.agent import Agent, User
from ..domain.process import ProcessStatus
from ..services import classifier, plaintext
from ..tasks import is_async

from arxiv.taxonomy import CATEGORIES, Category

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
                       after: Submission, creator: Agent) -> Iterable[Event]:
    """Use the plain text extraction service to extract text from the PDF."""
    identifier = after.source_content.identifier
    process = ProcessStatus.Process.PLAIN_TEXT_EXTRACTION
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


def when(process: Process, status: Status) -> Condition:
    """Generate a condition for a :class:`Process` and :class:`Status`."""
    def inner(event: AddProcessStatus, before: Submission,
              after: Submission, creator: Agent) -> bool:
        return event.process is process and event.status is status
    return inner


@AddProcessStatus.bind(when(Process.PLAIN_TEXT_EXTRACTION, Status.SUCCEEDED))
@is_async
def call_classifier(event: AddProcessStatus, before: Submission,
                    after: Submission, creator: Agent) -> Iterable[Event]:
    """Request the opinion of the auto-classifier."""
    identifier = after.source_content.identifier
    yield AddProcessStatus(creator=creator, process=Process.CLASSIFICATION,
                           status=ProcessStatus.Status.REQUESTED,
                           service=classifier.SERVICE,
                           version=classifier.VERSION,
                           identifier=identifier)
    try:
        suggestions, flags, counts = \
            classifier.classify(plaintext.retrieve_content(identifier))
    except plaintext.RequestFailed as e:
        reason = 'request failed (%s): %s' % (type(e), e)
        yield AddProcessStatus(creator=creator,
                               process=Process.CLASSIFICATION,
                               status=ProcessStatus.Status.FAILED,
                               service=classifier.SERVICE,
                               version=classifier.VERSION,
                               identifier=identifier, reason=reason)

    success = AddProcessStatus(creator=creator,
                               process=Process.CLASSIFICATION,
                               status=ProcessStatus.Status.SUCCEEDED,
                               service=classifier.SERVICE,
                               version=classifier.VERSION,
                               identifier=identifier)
    yield success
    yield AddClassifierResults(creator=creator,
                               results=[{'category': suggestion.category,
                                         'probability': suggestion.probability}
                                        for suggestion in suggestions])

    for flag in flags:
        comment = "flag from classification succeeded at %s" \
            % success.created.iso_format()
        yield AddContentFlag(creator=creator,
                             flag_type=ContentFlag.FlagTypes(flag.key),
                             flag_value=flag.value,
                             comment=comment)

    for feature_type in Feature.FeatureTypes:
        yield AddFeature(creator=creator,
                         feature_type=feature_type,
                         feature_value=getattr(counts, feature_type))


def feature_type_is(feature_type: Feature.FeatureTypes) -> Condition:
    """Generate a condition based on feature type."""
    def condition(event: AddFeature, before: Submission,
                  after: Submission, creator: Agent) -> bool:
        return event.feature_type is feature_type
    return condition


@AddFeature.bind(feature_type_is(Feature.FeatureTypes.STOPWORD_PERCENT))
def check_stop_percent(event: AddFeature, before: Submission,
                       after: Submission, creator: Agent) -> Iterable[Event]:
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
                     after: Submission, creator: Agent) -> Iterable[Event]:
    """Flag the submission if the number of stopwords is too low."""
    if event.feature_value < LOW_STOP:
        yield AddContentFlag(
            creator=creator,
            flag_type=ContentFlag.FlagTypes.LOW_STOP,
            flag_data=event.feature_value,
            comment="Classifier reports low stops or %stops"
        )
