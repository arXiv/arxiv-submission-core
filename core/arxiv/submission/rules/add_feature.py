"""Things that should happen upon the :class:`.AddFeature` command."""

from typing import List, Iterable

from ..domain.event import Event, AddContentFlag, AddProposal, \
    SetPrimaryClassification, AddFeature
from ..domain.event.event import Condition
from ..domain.annotation import ClassifierResult, Feature, ClassifierResults
from ..domain.submission import Submission
from ..domain.agent import Agent, User
from ..domain.flag import ContentFlag
from ..services import classifier, plaintext
from ..tasks import is_async

from arxiv import taxonomy

# TODO: make this configurable.
LOW_STOP_PERCENT = 0.10
"""This is the threshold for abornmally low stopword content by percentage."""

LOW_STOP = 400
"""This is the threshold for abornmally low stopword content by count."""

HIGH_STOP_PERCENT = 0.30
"""This is the threshold for abnormally high stopword content by percentage."""
# my $;
# my $MULTIPLE_LIMIT = 1.01;
# my $LINENOS_LIMIT = 0;


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
