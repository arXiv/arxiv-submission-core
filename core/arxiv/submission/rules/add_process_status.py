"""Things that should happen upon the :class:`.AddProcessStatus` command."""

from typing import List, Iterable, Optional

from ..domain.event import Event, AddContentFlag, RemoveAnnotation, \
    AddProposal, SetPrimaryClassification, AddProcessStatus, \
    AddClassifierResults, AddFeature
from ..domain.event.event import Condition
from ..domain.annotation import ClassifierResult, \
    ContentFlag, Feature, ClassifierResults
from ..domain.submission import Submission
from ..domain.agent import Agent, User
from ..domain.process import ProcessStatus
from ..services import classifier, plaintext
from ..tasks import is_async

from arxiv.taxonomy import CATEGORIES, Category

# TODO: make this configurable
PROPOSAL_THRESHOLD = 0.57   # Equiv. to logodds of 0.3.
"""This is the threshold for generating a proposal from a classifier result."""

Processes = ProcessStatus.Processes
Statuses = ProcessStatus.Statuses


def get_condition(process: Processes, status: Statuses) -> Condition:
    """Generate a condition for a process type and status."""
    def condition(event: AddProcessStatus, before: Submission,
                  after: Submission, creator: Agent) -> bool:
        return event.process is process and event.status is status
    return condition


on_text = get_condition(Processes.PLAIN_TEXT_EXTRACTION, Statuses.SUCCEEDED)
on_classification = get_condition(Processes.CLASSIFICATION, Statuses.SUCCEEDED)


def in_the_same_archive(cat_a: Category, cat_b: Category) -> bool:
    """Evaluate whether two categories are in the same archive."""
    return CATEGORIES[cat_a]['in_archive'] == CATEGORIES[cat_b]['in_archive']


@AddProcessStatus.bind(on_text)
@is_async
def call_classifier(event: AddProcessStatus, before: Submission,
                    after: Submission, creator: Agent) -> Iterable[Event]:
    """Request the opinion of the auto-classifier."""
    identifier = after.source_content.identifier
    yield AddProcessStatus(creator=creator, process=Processes.CLASSIFICATION,
                           status=ProcessStatus.Statuses.REQUESTED,
                           service=classifier.SERVICE,
                           version=classifier.VERSION,
                           identifier=identifier)
    try:
        suggestions, flags, counts = \
            classifier.classify(plaintext.retrieve_content(identifier))
    except plaintext.RequestFailed as e:
        reason = 'request failed (%s): %s' % (type(e), e)
        yield AddProcessStatus(creator=creator,
                               process=Processes.CLASSIFICATION,
                               status=ProcessStatus.Statuses.FAILED,
                               service=classifier.SERVICE,
                               version=classifier.VERSION,
                               identifier=identifier, reason=reason)

    success = AddProcessStatus(creator=creator,
                               process=Processes.CLASSIFICATION,
                               status=ProcessStatus.Statuses.SUCCEEDED,
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


@AddProcessStatus.bind(on_classification)
@is_async
def propose(event: AddProcessStatus, before: Submission, after: Submission,
            creator: Agent) -> Iterable[Event]:
    """Generate system classification proposals based on classifier results."""
    if not event.annotation.results:    # Nothing to do.
        return
    user_primary = after.primary_classification.category

    # the best alternative is the suggestion with the highest probability above
    # 0.57 (logodds = 0.3); there may be a best alternative inside or outside
    # of the selected primary archive, or both.
    suggested_category: Optional[Category] = None
    within: Optional[ClassifierResult] = None
    without: Optional[ClassifierResult] = None
    probabilities = {result['category']: result['probability']
                     for result in event.annotation.results}

    # if the primary is not in the suggestions, or the primary has probability
    # < 0.5 (logodds < 0) and there is an alternative,  propose the
    # alternatve (preference for within-archive). otherwise make no proposal
    if user_primary in probabilities and probabilities[user_primary] >= 0.5:
        return

    for result in event.annotation.results:
        if in_the_same_archive(result['category'], user_primary):
            if result['probability'] > within['probability']:
                within = result
        elif result['probability'] > without['probability']:
            without = result
    if within and within['probability'] >= PROPOSAL_THRESHOLD:
        suggested_category = within['category']
    elif without and without['probability'] >= PROPOSAL_THRESHOLD:
        suggested_category = without
    else:
        return

    comment = f"selected primary {user_primary}"
    if user_primary not in probabilities:
        comment += " not found in classifier scores"
    else:
        comment += f" has probability {probabilities[user_primary]}"
    yield AddProposal(creator=creator,
                      proposed_event_type=SetPrimaryClassification,
                      proposed_event_data={'category': suggested_category},
                      comment=comment)
