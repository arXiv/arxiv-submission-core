"""Things that should happen upon the :class:`.FinalizeSubmission` command."""

from typing import List, Iterable

from ..domain.event import Event, AddProposal, AddSecondaryClassification, \
    FinalizeSubmission
from ..domain.event.event import Condition
from ..domain.annotation import ClassifierResult, Feature, ClassifierResults, \
    Comment
from ..domain.flag import ContentFlag
from ..domain.proposal import Proposal
from ..domain.submission import Submission
from ..domain.agent import Agent, User
from ..services import classifier, plaintext
from ..tasks import is_async

from arxiv import taxonomy

# (ARXIVOPS-500)
# When the following categories are the primary, a corresponding category
# should be suggested as secondary
PRIMARY_TO_SECONDARY = {
    'cs.LG': 'stat.ML',
    'stat.ML': 'cs.LG'
}


@FinalizeSubmission.bind()
def propose_cross_from_primary(event: FinalizeSubmission, before: Submission,
                               after: Submission, creator: Agent) \
        -> Iterable[Event]:
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
