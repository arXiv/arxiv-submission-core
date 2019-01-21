"""Things that should happen upon the :class:`.AddAnnotation` command."""

from typing import List, Iterable

from ..domain.event import Event, AddAnnotation, RemoveAnnotation, \
    AddProposal, SetPrimaryClassification
from ..domain.event.event import Condition
from ..domain.annotation import ClassifierResult, PlainTextExtraction, \
    ContentFlag, FeatureCount, ClassifierResults, PossibleContentProblem
from ..domain.submission import Submission
from ..domain.agent import Agent, User
from ..services import classifier, plaintext
from ..tasks import is_async

from arxiv import taxonomy

# TODO: make this configurable.
PROPOSAL_THRESHOLD = 0.57   # Equiv. to logodds of 0.3.
"""This is the threshold for generating a proposal from a classifier result."""

LOW_STOP_PERCENT = 0.10
"""This is the threshold for abornmally low stopword content by percentage."""

LOW_STOP = 400
"""This is the threshold for abornmally low stopword content by count."""

HIGH_STOP_PERCENT = 0.30
"""This is the threshold for abnormally high stopword content by percentage."""
# my $;
# my $MULTIPLE_LIMIT = 1.01;
# my $LINENOS_LIMIT = 0;


def annotation_type_is(this_type: type, **attrs) -> Condition:
    """Build condition for an :class:`AddAnnotation` from annotation type."""
    def condition(event: AddAnnotation, before: Submission,
                  after: Submission, creator: Agent) -> bool:
        return type(event.annotation) is this_type \
            and all([getattr(event.annotation, key) == value
                     for key, value in attrs.items()])
    return condition


@AddAnnotation.bind(annotation_type_is(AddAnnotation, flag_type="%stop"))
def check_stop_percent(event: AddAnnotation, before: Submission,
                       after: Submission, creator: Agent) -> Iterable[Event]:
    if event.flag_value < LOW_STOP_PERCENT:
        yield AddAnnotation(
            creator=creator,
            annotation=PossibleContentProblem(
                problem_type=PossibleContentProblem.STOPWORDS,
                description="Classifier reports low stops or %stops"
            )
        )


@AddAnnotation.bind(annotation_type_is(AddAnnotation, flag_type="stops"))
def check_stop_count(event: AddAnnotation, before: Submission,
                     after: Submission, creator: Agent) -> Iterable[Event]:
    if event.flag_value < LOW_STOP:
        yield AddAnnotation(
            creator=creator,
            annotation=PossibleContentProblem(
                problem_type=PossibleContentProblem.STOPWORDS,
                description="Classifier reports low stops or %stops"
            )
        )



@AddAnnotation.bind(annotation_type_is(PlainTextExtraction))
@is_async
def call_classifier(event: AddAnnotation, before: Submission,
                    after: Submission, creator: Agent) -> Iterable[Event]:
    """Request the opinion of the auto-classifier."""
    if event.annotation.status != PlainTextExtraction.SUCCEEDED:
        return
    identifier = after.source_content.identifier
    suggestions, flags, counts = \
        classifier.classify(plaintext.retrieve_content(identifier))

    yield AddAnnotation(
        creator=creator,
        annotation=ClassifierResults(results=[
            ClassifierResult(category=suggestion.category,
                             probability=suggestion.probability)
            for suggestion in suggestions
        ])
    )

    for flag in flags:
        yield AddAnnotation(
            creator=creator,
            annotation=ContentFlag(flag_type=flag.key, flag_value=flag.value))

    for count_type in FeatureCount.TYPES:
        yield AddAnnotation(
            creator=creator,
            annotation=FeatureCount(feature_type=count_type,
                                    feature_count=getattr(counts, count_type)))


def in_the_same_archive(category_a: taxonomy.Category,
                        category_b: taxonomy.Category) -> bool:
    """Evaluate whether two categories are in the same archive."""
    return taxonomy.CATEGORIES[category_a]['in_archive'] \
        == taxonomy.CATEGORIES[category_b]['in_archive']


@AddAnnotation.bind(annotation_type_is(ClassifierResults))
@is_async
def propose(event: AddAnnotation, before: Submission, after: Submission,
            creator: Agent) -> Iterable[Event]:
    """Generate system classification proposals based on classifier results."""
    if not event.annotation.results:    # Nothing to do.
        return
    user_primary = after.primary_classification.category

    # the best alternative is the suggestion with the highest probability above
    # 0.57 (logodds = 0.3); there may be a best alternative inside or outside
    # of the selected primary archive, or both.
    suggested_category: Optional[taxonomy.Category] = None
    within_archive: Optional[ClassifierResult] = None
    outside_archive: Optional[ClassifierResult] = None
    probabilities = {result.category: result.probability
                     for result in event.annotation.results}

    # if the primary is not in the suggestions, or the primary has probability
    # < 0.5 (logodds < 0) and there is an alternative,  propose the
    # alternatve (preference for within-archive). otherwise make no proposal
    if user_primary in probabilities and probabilities[user_primary] >= 0.5:
        return

    for result in event.annotation.results:
        if in_the_same_archive(result.category, user_primary):
            if result.probability > within_archive.probability:
                within_archive = result
        elif result.probability > outside_archive.probability:
            outside_archive = result
    if within_archive and within_archive.probability >= PROPOSAL_THRESHOLD:
        suggested_category = within_archive.category
    elif outside_archive and outside_archive.probability >= PROPOSAL_THRESHOLD:
        suggested_category = outside_archive
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
