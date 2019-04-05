"""Tests for reclassification policies."""

from unittest import TestCase, mock
from datetime import datetime
from pytz import UTC
import copy

from arxiv.submission.domain.event import AddClassifierResults, \
    SetPrimaryClassification, AddSecondaryClassification, AddProposal, \
    FinalizeSubmission, AcceptProposal
from arxiv.submission.domain.agent import User, System
from arxiv.submission.domain.submission import Submission, SubmissionContent, \
    Classification, License, SubmissionMetadata
from arxiv.submission.domain.proposal import Proposal
from arxiv.submission.domain.annotation import ClassifierResults

from arxiv.submission.services.classifier.classifier import Classifier

from ..import reclassification, ProposeReclassification, \
    ProposeCrossListFromPrimaryCategory, AcceptSystemCrossListProposals
from ...domain import Trigger
from ...factory import create_app
from ... import config

prob = Classifier.probability
sys = System(__name__)


class TestProposeReclassification(TestCase):
    """We use classifier results to propose reclassification."""

    # These test cases are ported from
    # arxiv-lib/t/arxiv_classifier/check_scores.t.
    CASES = [
        {'primary_category': 'cs.AI',
         'results': [{"category": 'cs.DL', 'probability': prob(1.01)},
                     {"category": 'math.GM', 'probability': prob(1.90)},
                     {"category": 'cs.AI', 'probability': prob(-0.03)}],
         'expected_category': 'cs.DL',
         'expected_reason': 'selected primary cs.AI has probability 0.493'},
        {'primary_category': 'cs.AI',
         'results': [{"category": 'physics.gen-ph', 'probability': prob(1.01)},
                     {"category": 'math.GM', 'probability': prob(1.02)},
                     {"category": 'cs.AI', 'probability': prob(-0.05)}],
         'expected_category': 'math.GM',
         'expected_reason': 'selected primary cs.AI has probability 0.488'},
        {'primary_category': 'cs.AI',
         'results': [{"category": 'cs.AI', 'probability': prob(1.05)},
                     {"category": 'math.GM', 'probability': prob(1.02)},
                     {"category": 'cs.DL', 'probability': prob(0.05)}],
         'expected_category': None,
         'expected_reason': None},
        {'primary_category': 'cs.CE',
         'results': [{"category": 'cs.DL', 'probability': prob(1.01)},
                     {"category": 'math.GM', 'probability': prob(1.90)},
                     {"category": 'cs.CE', 'probability': prob(-0.04)}],
         'expected_category': None,
         'expected_reason': None},
        {'primary_category': 'eess.IV',
         'results': [{"category": 'cs.DL', 'probability': prob(1.01)},
                     {"category": 'math.GM', 'probability': prob(1.90)},
                     {"category": 'eess.IV', 'probability': prob(-0.04)}],
         'expected_category': 'math.GM',
         'expected_reason': 'selected primary eess.IV has probability 0.49'},
        {'primary_category': 'eess.SP',
         'results': [{"category": 'cs.DL', 'probability': prob(1.01)},
                     {"category": 'math.GM', 'probability': prob(1.90)}],
         'expected_category': 'math.GM',
         'expected_reason': 'selected primary eess.SP not found in classifier'
                            ' scores'}
    ]

    def setUp(self):
        """We have a submission."""
        self.creator = User(native_id=1234, email='something@else.com')
        self.submission = Submission(
            submission_id=2347441,
            creator=self.creator,
            owner=self.creator,
            created=datetime.now(UTC),
            source_content=SubmissionContent(
                identifier='5678',
                source_format=SubmissionContent.Format('pdf'),
                checksum='a1b2c3d4',
                uncompressed_size=58493,
                compressed_size=58493
            )
        )
        self.process = ProposeReclassification(self.submission.submission_id)

    def test_suggestions(self):
        """Test suggestions using :const:`.CASES`."""
        before = copy.deepcopy(self.submission)
        for case in self.CASES:
            self.submission.primary_classification \
                = Classification(category=case['primary_category'])
            self.submission.annotations = {
                'asdf1234': ClassifierResults(
                    event_id='asdf1234',
                    creator=self.creator,
                    created=datetime.now(UTC),
                    results=case['results']
                )
            }
            events = []
            params = {
                'NO_RECLASSIFY_ARCHIVES': config.NO_RECLASSIFY_ARCHIVES,
                'NO_RECLASSIFY_CATEGORIES': config.NO_RECLASSIFY_CATEGORIES,
                'RECLASSIFY_PROPOSAL_THRESHOLD':
                    config.RECLASSIFY_PROPOSAL_THRESHOLD
            }
            event = AddClassifierResults(creator=self.creator,
                                         created=datetime.now(UTC),
                                         results=case['results'])
            trigger = Trigger(event=event, actor=self.creator,
                              before=before, after=self.submission,
                              params=params)
            self.process.propose_primary(None, trigger, events.append)

            if case['expected_category'] is None:
                self.assertEqual(len(events), 0, "No proposals are made")
            else:
                self.assertIsInstance(events[0], AddProposal,
                                      "Generates AddProposal")
                self.assertEqual(events[0].proposed_event_type,
                                 SetPrimaryClassification,
                                 "Proposes reclassification")
                self.assertEqual(events[0].proposed_event_data["category"],
                                 case['expected_category'])
                self.assertEqual(events[0].comment, case['expected_reason'])


class TestProposeCrossFromPrimary(TestCase):
    """In some cases, we propose a cross-list category based on primary."""

    def setUp(self):
        """We have a submission."""
        self.creator = User(native_id=1234, email='something@else.com')
        self.submission = Submission(
            submission_id=2347441,
            creator=self.creator,
            owner=self.creator,
            created=datetime.now(UTC),
            source_content=SubmissionContent(
                identifier='5678',
                source_format=SubmissionContent.Format('pdf'),
                checksum='a1b2c3d4',
                uncompressed_size=58493,
                compressed_size=58493
            )
        )
        self.submission.submitter_contact_verified = True
        self.submission.submitter_accepts_policy = True
        self.submission.license = License(name='foo', uri='http://foo.foo')
        self.submission.metadata = SubmissionMetadata(
            title='foo',
            abstract='oof',
            authors_display='Bloggs, J'
        )
        self.process = \
            ProposeCrossListFromPrimaryCategory(self.submission.submission_id)

    def test_propose_cross(self):
        """Propose a cross-list category based on primary."""
        self.submission.primary_classification = Classification('cs.AI')
        event = FinalizeSubmission(creator=self.creator,
                                   created=datetime.now(UTC))
        events = []
        params = {'AUTO_CROSS_FOR_PRIMARY': {'cs.AI': 'math.GM'}}
        trigger = Trigger(event=event, actor=self.creator,
                          before=self.submission,
                          after=self.submission, params=params)
        self.process.propose(None, trigger, events.append)

        self.assertIsInstance(events[0], AddProposal,
                              'Adds a proposal')
        self.assertEqual(events[0].proposed_event_type,
                         AddSecondaryClassification,
                         'Proposes to add a secondary')
        self.assertEqual(events[0].proposed_event_data['category'], 'math.GM',
                         'Proposes cross-list category')
        self.assertEqual(events[0].comment, 'cs.AI is primary')

    def test_no_rule_exists(self):
        """Propose a cross-list category based on primary."""
        self.submission.primary_classification = Classification('cs.DL')
        event = FinalizeSubmission(creator=self.creator,
                                   created=datetime.now(UTC))
        events = []
        params = {'AUTO_CROSS_FOR_PRIMARY': {'cs.AI': 'math.GM'}}
        trigger = Trigger(event=event, actor=self.creator,
                          before=self.submission, after=self.submission,
                          params=params)
        self.process.propose(None, trigger, events.append)
        self.assertEqual(len(events), 0, 'No proposals are made')

    def test_cross_already_set(self):
        """The cross-list category is already present."""
        self.submission.primary_classification = Classification('cs.AI')
        self.submission.secondary_classification = [Classification('math.GM')]
        event = FinalizeSubmission(creator=self.creator,
                                   created=datetime.now(UTC))
        events = []
        params = {'AUTO_CROSS_FOR_PRIMARY': {'cs.AI': 'math.GM'}}
        trigger = Trigger(event=event, actor=self.creator,
                          before=self.submission, after=self.submission,
                          params=params)
        self.process.propose(None, trigger, events.append)
        self.assertEqual(len(events), 0, 'No proposals are made')


class TestAcceptSystemCrossProposal(TestCase):
    """We accept cross-list proposals that we generate ourselves."""

    def setUp(self):
        """We have a submission."""
        self.creator = User(native_id=1234, email='something@else.com')
        self.submission = Submission(
            submission_id=2347441,
            creator=self.creator,
            owner=self.creator,
            created=datetime.now(UTC),
            source_content=SubmissionContent(
                identifier='5678',
                source_format=SubmissionContent.Format('pdf'),
                checksum='a1b2c3d4',
                uncompressed_size=58493,
                compressed_size=58493
            )
        )
        self.process = \
            AcceptSystemCrossListProposals(self.submission.submission_id)

    def test_system_cross_proposal(self):
        """A cross-list proposal is generated by the system."""
        event = AddProposal(creator=sys, created=datetime.now(UTC),
                            proposed_event_type=AddSecondaryClassification,
                            proposed_event_data={'category': 'cs.DL'})
        self.submission.proposals[event.event_id] = Proposal(
            event_id=event.event_id,
            creator=sys,
            proposed_event_type=AddSecondaryClassification,
            proposed_event_data={'category': 'cs.DL'}
        )
        events = []
        trigger = Trigger(event=event, actor=sys, before=self.submission,
                          after=self.submission, params={})
        self.process.accept(None, trigger, events.append)
        self.assertIsInstance(events[0], AcceptProposal,
                              'The proposal is accepted')
        self.assertEqual(events[0].proposal_id, event.event_id,
                         'Proposal is identified by the event that created it')

    def test_user_cross_proposal(self):
        """A cross-list proposal is generated by a user."""
        event = AddProposal(creator=self.creator, created=datetime.now(UTC),
                            proposed_event_type=AddSecondaryClassification,
                            proposed_event_data={'category': 'cs.DL'})
        self.submission.proposals[event.event_id] = Proposal(
            event_id=event.event_id,
            creator=self.creator,
            proposed_event_type=AddSecondaryClassification,
            proposed_event_data={'category': 'cs.DL'}
        )
        events = []
        trigger = Trigger(event=event, actor=self.creator,
                          before=self.submission,
                          after=self.submission, params={})
        self.process.accept(None, trigger, events.append)
        self.assertEqual(len(events), 0, 'No proposal is generated')
