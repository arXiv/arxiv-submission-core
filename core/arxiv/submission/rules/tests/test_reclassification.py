"""Tests for reclassification policies."""

from unittest import TestCase, mock
from datetime import datetime
from pytz import UTC

from ...domain.event import AddClassifierResults, SetPrimaryClassification, \
    AddSecondaryClassification, AddProposal, FinalizeSubmission, AcceptProposal
from ...domain.agent import User, System
from ...domain.submission import Submission, SubmissionContent, \
    Classification, License, SubmissionMetadata

from ...services.classifier.classifier import Classifier
from ..import reclassification

prob = Classifier.probability
sys = System(__name__)


class TestProposeFromClassifierResults(TestCase):
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

    def test_suggestions(self):
        """Test suggestions using :const:`.CASES`."""
        for case in self.CASES:
            self.submission.primary_classification \
                = Classification(category=case['primary_category'])
            event = AddClassifierResults(creator=self.creator,
                                         results=case['results'])
            before, after = self.submission, event.apply(self.submission)

            events = [
                e for e in reclassification.propose(event, before, after, sys)
            ]

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

    @mock.patch(f'{reclassification.__name__}.PRIMARY_TO_SECONDARY',
                {'cs.AI': 'math.GM'})
    def test_propose_cross(self):
        """Propose a cross-list category based on primary."""
        self.submission.primary_classification = Classification('cs.AI')
        event = FinalizeSubmission(creator=self.creator)
        before, after = self.submission, event.apply(self.submission)

        events = list(
            reclassification.propose_cross_from_primary(event, before, after,
                                                        sys)
        )
        self.assertIsInstance(events[0], AddProposal,
                              'Adds a proposal')
        self.assertEqual(events[0].proposed_event_type,
                         AddSecondaryClassification,
                         'Proposes to add a secondary')
        self.assertEqual(events[0].proposed_event_data['category'], 'math.GM',
                         'Proposes cross-list category')
        self.assertEqual(events[0].comment, 'cs.AI is primary')

    @mock.patch(f'{reclassification.__name__}.PRIMARY_TO_SECONDARY',
                {'cs.AI': 'math.GM'})
    def test_no_rule_exists(self):
        """Propose a cross-list category based on primary."""
        self.submission.primary_classification = Classification('cs.DL')
        event = FinalizeSubmission(creator=self.creator)
        before, after = self.submission, event.apply(self.submission)

        events = list(
            reclassification.propose_cross_from_primary(event, before, after,
                                                        sys)
        )
        self.assertEqual(len(events), 0, 'No proposals are made')

    @mock.patch(f'{reclassification.__name__}.PRIMARY_TO_SECONDARY',
                {'cs.AI': 'math.GM'})
    def test_cross_already_set(self):
        """The cross-list category is already present."""
        self.submission.primary_classification = Classification('cs.AI')
        self.submission.secondary_classification = [Classification('math.GM')]
        event = FinalizeSubmission(creator=self.creator)
        before, after = self.submission, event.apply(self.submission)

        events = list(
            reclassification.propose_cross_from_primary(event, before, after,
                                                        sys)
        )
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

    def test_system_cross_proposal(self):
        """A cross-list proposal is generated by the system."""
        event = AddProposal(creator=sys,
                            proposed_event_type=AddSecondaryClassification,
                            proposed_event_data={'category': 'cs.DL'})
        before, after = self.submission, event.apply(self.submission)

        events = list(
            reclassification.accept_system_cross_proposal(event, before, after,
                                                          sys)
        )
        self.assertIsInstance(events[0], AcceptProposal,
                              'The proposal is accepted')
        self.assertEqual(events[0].proposal_id, event.event_id,
                         'Proposal is identified by the event that created it')

    def test_user_cross_proposal(self):
        """A cross-list proposal is generated by a user."""
        event = AddProposal(creator=self.creator,
                            proposed_event_type=AddSecondaryClassification,
                            proposed_event_data={'category': 'cs.DL'})
        before, after = self.submission, event.apply(self.submission)

        events = list(
            reclassification.accept_system_cross_proposal(event, before, after,
                                                          sys)
        )
        self.assertEqual(len(events), 0, 'No proposal is generated')
