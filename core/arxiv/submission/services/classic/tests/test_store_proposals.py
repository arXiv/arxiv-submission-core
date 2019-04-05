"""Test persistence of proposals in the classic database."""

from unittest import TestCase, mock
from datetime import datetime
from pytz import UTC
from ....domain.event import CreateSubmission, SetPrimaryClassification, \
    AddSecondaryClassification, SetTitle, AddProposal
from ....domain.agent import User
from ....domain.annotation import Comment
from ....domain.submission import Submission
from ....domain.proposal import Proposal
from .. import store_event, models, get_events

from .util import in_memory_db

from arxiv import taxonomy


class TestSaveProposal(TestCase):
    """An :class:`AddProposal` event is stored."""

    def setUp(self):
        """Instantiate a user."""
        self.user = User(12345, 'joe@joe.joe',
                         endorsements=['physics.soc-ph', 'cs.DL'])

    def test_save_reclassification_proposal(self):
        """A submission has a new reclassification proposal."""
        with in_memory_db() as session:
            create = CreateSubmission(creator=self.user,
                                      created=datetime.now(UTC))
            before, after = None, create.apply(None)
            create, before = store_event(create, before, after)

            event = AddProposal(
                creator=self.user,
                proposed_event_type=SetPrimaryClassification,
                proposed_event_data={
                    'category': taxonomy.Category('cs.DL'),
                },
                comment='foo',
                created=datetime.now(UTC)
            )
            after = event.apply(before)
            event, after = store_event(event, before, after)

            db_sb = session.query(models.Submission).get(event.submission_id)

            # Make sure that we get the right submission ID.
            self.assertIsNotNone(event.submission_id)
            self.assertEqual(event.submission_id, after.submission_id)
            self.assertEqual(event.submission_id, db_sb.submission_id)

            db_props = session.query(models.CategoryProposal).all()
            self.assertEqual(len(db_props), 1)
            self.assertEqual(db_props[0].submission_id, after.submission_id)
            self.assertEqual(db_props[0].category, 'cs.DL')
            self.assertEqual(db_props[0].is_primary, 1)
            self.assertEqual(db_props[0].updated.replace(tzinfo=UTC),
                             event.created)
            self.assertEqual(db_props[0].proposal_status,
                             models.CategoryProposal.UNRESOLVED)

            self.assertEqual(db_props[0].proposal_comment.logtext,
                             event.comment)

    def test_save_secondary_proposal(self):
        """A submission has a new cross-list proposal."""
        with in_memory_db() as session:
            create = CreateSubmission(creator=self.user,
                                      created=datetime.now(UTC))
            before, after = None, create.apply(None)
            create, before = store_event(create, before, after)

            event = AddProposal(
                creator=self.user,
                created=datetime.now(UTC),
                proposed_event_type=AddSecondaryClassification,
                proposed_event_data={
                    'category': taxonomy.Category('cs.DL'),
                },
                comment='foo'
            )
            after = event.apply(before)
            event, after = store_event(event, before, after)

            db_sb = session.query(models.Submission).get(event.submission_id)

            # Make sure that we get the right submission ID.
            self.assertIsNotNone(event.submission_id)
            self.assertEqual(event.submission_id, after.submission_id)
            self.assertEqual(event.submission_id, db_sb.submission_id)

            db_props = session.query(models.CategoryProposal).all()
            self.assertEqual(len(db_props), 1)
            self.assertEqual(db_props[0].submission_id, after.submission_id)
            self.assertEqual(db_props[0].category, 'cs.DL')
            self.assertEqual(db_props[0].is_primary, 0)
            self.assertEqual(db_props[0].updated.replace(tzinfo=UTC),
                             event.created)
            self.assertEqual(db_props[0].proposal_status,
                             models.CategoryProposal.UNRESOLVED)

            self.assertEqual(db_props[0].proposal_comment.logtext,
                             event.comment)

    def test_save_title_proposal(self):
        """A submission has a new SetTitle proposal."""
        with in_memory_db() as session:
            create = CreateSubmission(creator=self.user,
                                      created=datetime.now(UTC))
            before, after = None, create.apply(None)
            create, before = store_event(create, before, after)

            event = AddProposal(
                creator=self.user,
                created=datetime.now(UTC),
                proposed_event_type=SetTitle,
                proposed_event_data={'title': 'the foo title'},
                comment='foo'
            )
            after = event.apply(before)
            event, after = store_event(event, before, after)

            db_sb = session.query(models.Submission).get(event.submission_id)

            # Make sure that we get the right submission ID.
            self.assertIsNotNone(event.submission_id)
            self.assertEqual(event.submission_id, after.submission_id)
            self.assertEqual(event.submission_id, db_sb.submission_id)

            db_props = session.query(models.CategoryProposal).all()
            self.assertEqual(len(db_props), 0)
