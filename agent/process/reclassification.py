"""Reclassification policies."""

from typing import List, Iterable, Optional, Callable

from arxiv.submission.domain.event import Event, AddContentFlag, AddProposal, \
    SetPrimaryClassification, AddProcessStatus, AddClassifierResults, \
    AddFeature, AddSecondaryClassification, AcceptProposal, FinalizeSubmission
from arxiv.submission.domain.event.event import Condition
from arxiv.submission.domain.annotation import ClassifierResult, Feature, \
    ClassifierResults
from arxiv.submission.domain.proposal import Proposal
from arxiv.submission.domain.flag import ContentFlag
from arxiv.submission.domain.submission import Submission
from arxiv.submission.domain.agent import Agent, User, System
from arxiv.submission.domain.process import ProcessStatus
from arxiv.submission.services import classifier, plaintext

from arxiv.taxonomy import CATEGORIES, Category

from ..process import Process, step
from ..domain import Trigger


class ProposeReclassification(Process):
    """Generate system classification proposals based on classifier results."""

    def _get_archive(self, category: Category) -> Optional[str]:
        return CATEGORIES[category]['in_archive']

    def _in_the_same_archive(self, cat_a: Category, cat_b: Category) -> bool:
        """Evaluate whether two categories are in the same archive."""
        return self._get_archive(cat_a) == self._get_archive(cat_b)

    def _get_results(self, trigger: Trigger):
        try:
            return [anno for anno in trigger.after.annotations.values()
                    if type(anno) is ClassifierResults][0].results
        except AttributeError as exc:
            self.fail(exc, 'Missing post-event state')

    def _skip(self, trigger: Trigger) -> bool:
        """Determine whether to skip proposal-making altogether."""
        user_primary = trigger.after.primary_classification.category
        skipped_categories = trigger.params['NO_RECLASSIFY_CATEGORIES']
        skipped_archives = trigger.params['NO_RECLASSIFY_ARCHIVES']
        return user_primary in skipped_categories \
            or self._get_archive(user_primary) in skipped_archives

    def _user_category_ranks_highly(self, trigger: Trigger) -> bool:
        results = self._get_results(trigger)
        user_primary = trigger.after.primary_classification.category
        probs = {r['category']: r['probability'] for r in results}
        return user_primary in probs and probs[user_primary] >= 0.5

    def _find_candidate(self, trigger: Trigger) -> Optional[Category]:
        proposal_threshold = trigger.params['RECLASSIFY_PROPOSAL_THRESHOLD']
        within: Optional[ClassifierResult] = None
        without: Optional[ClassifierResult] = None

        user_primary = trigger.after.primary_classification.category
        for result in self._get_results(trigger):
            probability = result['probability']
            if self._in_the_same_archive(result['category'], user_primary):
                if within is None or probability > within['probability']:
                    within = result
            elif without is None or probability > without['probability']:
                without = result

        if within and within['probability'] >= proposal_threshold:
            return within['category']
        elif without and without['probability'] >= proposal_threshold:
            return without['category']
        return None

    @step()
    def propose_primary(self, previous: Optional, trigger: Trigger,
                        emit: Callable) -> None:
        """Propose a new primary classification, if appropriate."""
        results = self._get_results(trigger)
        if len(results) == 0:    # Nothing to do.
            return

        if self._skip(trigger):
            return

        user_primary = trigger.after.primary_classification.category

        # if the primary is not in the suggestions, or the primary has
        # probability < 0.5 (logodds < 0) and there is an alternative, propose
        # the alternatve (preference for within-archive). otherwise make no
        # proposal
        if self._user_category_ranks_highly(trigger):
            return

        # the best alternative is the suggestion with the highest probability
        # above 0.57 (logodds = 0.3); there may be a best alternative inside or
        # outside of the selected primary archive, or both.
        suggested_category = self._find_candidate(trigger)
        if suggested_category is None:
            return

        probs = probs = {r['category']: r['probability'] for r in results}
        comment = f"selected primary {user_primary}"
        if user_primary not in probs:
            comment += " not found in classifier scores"
        else:
            comment += f" has probability {round(probs[user_primary], 3)}"
        emit(AddProposal(creator=self.agent,
                         proposed_event_type=SetPrimaryClassification,
                         proposed_event_data={'category': suggested_category},
                         comment=comment))


class ProposeCrossListFromPrimaryCategory(Process):
    """Propose a cross-list classification based on primary classification."""

    @step()
    def propose(self, previous: Optional, trigger: Trigger,
                emit: Callable) -> None:
        """Make the proposal."""
        try:
            user_primary = trigger.after.primary_classification.category
            secondary_categories = trigger.after.secondary_categories
        except AttributeError:
            self.fail(message='Missing primary, secondary, or postevent state')
        category_map = trigger.params['AUTO_CROSS_FOR_PRIMARY']
        suggested = category_map.get(user_primary, None)
        if suggested and suggested not in secondary_categories:
            emit(AddProposal(creator=self.agent,
                             proposed_event_type=AddSecondaryClassification,
                             proposed_event_data={'category': suggested},
                             comment=f"{user_primary} is primary"))


class AcceptSystemCrossListProposals(Process):
    """
    Accept any cross-list proposals generated by the system.

    This is a bit odd, since we likely generated the proposal in this very
    thread...but this seems to be an explicit feature of the classic system.
    """

    @step()
    def accept(self, previous: Optional, trigger: Trigger,
               emit: Callable) -> None:
        """Accept pending system proposals for cross-list classification."""
        try:
            proposals = trigger.after.proposals.items()
        except AttributeError as exc:
            self.fail(exc, 'Missing proposals or post-event state')

        for event_id, proposal in proposals:
            if proposal.proposed_event_type is not AddSecondaryClassification:
                continue
            if proposal.status != Proposal.Status.PENDING:
                continue
            if type(proposal.creator) is System:
                comment = "accept cross-list proposal from system"
                emit(AcceptProposal(creator=self.agent,
                                    proposal_id=event_id,
                                    comment=comment))
