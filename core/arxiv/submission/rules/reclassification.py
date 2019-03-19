"""Reclassification policies."""

from typing import List, Iterable, Optional

from ..domain.event import Event, AddContentFlag, AddProposal, \
    SetPrimaryClassification, AddProcessStatus, AddClassifierResults, \
    AddFeature, AddSecondaryClassification, AcceptProposal, FinalizeSubmission
from ..domain.event.event import Condition
from ..domain.annotation import ClassifierResult, Feature, ClassifierResults
from ..domain.flag import ContentFlag
from ..domain.submission import Submission
from ..domain.agent import Agent, User, System
from ..domain.process import ProcessStatus
from ..services import classifier, plaintext
from ..tasks import is_async

from arxiv.taxonomy import CATEGORIES, Category

# TODO: make this configurable
PROPOSAL_THRESHOLD = 0.57   # Equiv. to logodds of 0.3.
"""This is the threshold for generating a proposal from a classifier result."""

Process = ProcessStatus.Process
Status = ProcessStatus.Status


def get_condition(process: Process, status: Status) -> Condition:
    """Generate a condition for a process type and status."""
    def condition(event: AddProcessStatus, before: Submission,
                  after: Submission, creator: Agent) -> bool:
        return event.process is process and event.status is status
    return condition


on_text = get_condition(Process.PLAIN_TEXT_EXTRACTION, Status.SUCCEEDED)
on_classification = get_condition(Process.CLASSIFICATION, Status.SUCCEEDED)


def _get_archive(category: Category) -> Optional[str]:
    return CATEGORIES[category]['in_archive']


def _in_the_same_archive(cat_a: Category, cat_b: Category) -> bool:
    """Evaluate whether two categories are in the same archive."""
    return _get_archive(cat_a) == _get_archive(cat_b)


# Don't make auto-proposals for the following user-supplied primaries.
# These categories may not be known to the classifier, or the
# classifier-suggested alternatives may be consistently innaccurate.
SKIPPED_CATEGORIES = (
    'cs.CE',   # Interdisciplinary category (see ARXIVOPS-466).
)
SKIPPED_ARCHIVES = (
    'econ',  # New September 2017.
)


@AddClassifierResults.bind(lambda *a, **k: True)
@is_async
def propose(event: AddClassifierResults, before: Submission, after: Submission,
            creator: Agent, task_id: Optional[str] = None,
            **kwargs) -> Iterable[Event]:
    """Generate system classification proposals based on classifier results."""
    if len(event.results) == 0:    # Nothing to do.
        return
    user_primary = after.primary_classification.category

    if user_primary in SKIPPED_CATEGORIES \
            or _get_archive(user_primary) in SKIPPED_ARCHIVES:
        return

    # the best alternative is the suggestion with the highest probability above
    # 0.57 (logodds = 0.3); there may be a best alternative inside or outside
    # of the selected primary archive, or both.
    suggested_category: Optional[Category] = None
    within: Optional[ClassifierResult] = None
    without: Optional[ClassifierResult] = None
    probabilities = {result['category']: result['probability']
                     for result in event.results}
    # if the primary is not in the suggestions, or the primary has probability
    # < 0.5 (logodds < 0) and there is an alternative,  propose the
    # alternatve (preference for within-archive). otherwise make no proposal
    if user_primary in probabilities and probabilities[user_primary] >= 0.5:
        return

    for result in event.results:
        if _in_the_same_archive(result['category'], user_primary):
            if within is None or result['probability'] > within['probability']:
                within = result
        elif without is None or result['probability'] > without['probability']:
            without = result

    if within and within['probability'] >= PROPOSAL_THRESHOLD:
        suggested_category = within['category']
    elif without and without['probability'] >= PROPOSAL_THRESHOLD:
        suggested_category = without['category']
    else:
        return

    comment = f"selected primary {user_primary}"
    if user_primary not in probabilities:
        comment += " not found in classifier scores"
    else:
        comment += f" has probability {round(probabilities[user_primary], 3)}"
    yield AddProposal(creator=creator,
                      proposed_event_type=SetPrimaryClassification,
                      proposed_event_data={'category': suggested_category},
                      comment=comment)


# (ARXIVOPS-500)
# When the following categories are the primary, a corresponding category
# should be suggested as secondary
PRIMARY_TO_SECONDARY = {
    'cs.LG': 'stat.ML',
    'stat.ML': 'cs.LG'
}


@FinalizeSubmission.bind()
def propose_cross_from_primary(event: FinalizeSubmission, before: Submission,
                               after: Submission, creator: Agent,
                               task_id: Optional[str] = None,
                               **kwargs) -> Iterable[Event]:
    """Propose a cross-list classification based on primary classification."""
    user_primary = after.primary_classification.category
    suggested = PRIMARY_TO_SECONDARY.get(user_primary)
    if suggested and suggested not in after.secondary_categories:
        yield AddProposal(
            creator=creator,
            proposed_event_type=AddSecondaryClassification,
            proposed_event_data={'category': suggested},
            comment=f"{user_primary} is primary"
        )


@AddProposal.bind()
def accept_system_cross_proposal(event: AddProposal, before: Submission,
                                 after: Submission, creator: Agent,
                                 task_id: Optional[str] = None,
                                 **kwargs) -> Iterable[Event]:
    """
    Accept any cross-list proposals generated by the system.

    This is a bit odd, since we likely generated the proposal in this very
    thread...but this seems to be an explicit feature of the classic system.
    """
    if event.proposed_event_type is AddSecondaryClassification \
            and type(event.creator) is System:
        yield AcceptProposal(creator=creator, proposal_id=event.event_id,
                             comment="accept cross-list proposal from system")
