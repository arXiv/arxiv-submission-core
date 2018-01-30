"""Test the behavior of :func:`events.controllers._emit` with live database."""

from unittest import TestCase, mock
import os
from datetime import datetime, timedelta
from flask import Flask
from events.services import database
from events import controllers
from events.domain import CreateSubmissionEvent, UpdateMetadataEvent, \
    CreateCommentEvent, System, EventRule, RuleCondition, RuleConsequence, \
    SubmissionMetadata, Submission, Author

TEST = 'postgres://arxiv-submit:arxiv@localhost:5432/arxiv-submit-test'
os.environ['SQLALCHEMY_DATABASE_URI'] = TEST


class TestApplyEvents(TestCase):
    def setUp(self):
        app = Flask(__name__)
        # app.config.from_pyfile('../events.config')
        app.app_context().push()
        app.config['SQLALCHEMY_DATABASE_URI'] = TEST
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        database.db.init_app(app)
        database.db.create_all()

    def tearDown(self):
        database.db.session.commit()
        database.db.drop_all()
        database.util._db_agent_cache = {}

    def test_store_events_from_scratch(self):
        """Store events for nonexistant submission."""
        created = datetime.now()
        e = CreateSubmissionEvent(creator=System(), created=created)
        e2 = UpdateMetadataEvent(creator=System(), metadata=[['title', 'foo']],
                                 created=created + timedelta(seconds=1))
        submission, _ = controllers._emit(e, e2)

        self.assertEqual(submission.metadata.title, 'foo')
        self.assertIsInstance(submission.submission_id, int)
        self.assertEqual(submission.created, created)

    def test_apply_events_from_scratch_without_creation_event(self):
        """An exception is raised when there is no creation event."""
        e2 = UpdateMetadataEvent(creator=System(), metadata=[['title', 'foo']])
        with self.assertRaises(RuntimeError):
            controllers._emit(e2)

    def test_apply_events_on_existing_submission(self):
        """Apply multiple sets of events in separate db transactions."""
        created = datetime.now()
        e = CreateSubmissionEvent(creator=System(), created=created)
        e2 = UpdateMetadataEvent(creator=System(), metadata=[['title', 'foo']],
                                 created=created + timedelta(seconds=1))
        submission, _ = controllers._emit(e, e2)
        submission_id = submission.submission_id
        e3 = UpdateMetadataEvent(creator=System(),
                                 metadata=[['abstract', 'bar']],
                                 created=created + timedelta(seconds=0.5))
        submission2, _ = controllers._emit(e3, submission_id=submission_id)

        # The submission state reflects all three events.
        self.assertEqual(submission2.metadata.abstract, 'bar')
        self.assertEqual(submission2.metadata.title, 'foo')
        self.assertEqual(submission2.created, created)
        self.assertEqual(submission2.submission_id, submission_id)

        events = database.get_events_for_submission(submission.submission_id)
        self.assertEqual(len(events), 3, "A total of three events are stored")

        e4 = UpdateMetadataEvent(creator=System(),
                                 metadata=[['title', 'something else']],
                                 created=created + timedelta(seconds=1.5))
        submission3, _ = controllers._emit(e4, submission_id=submission_id)

        self.assertEqual(submission3.submission_id, submission_id)
        self.assertEqual(submission3.metadata.title, 'something else')

    @mock.patch('events.controllers.database.get_rules_for_submission')
    def test_apply_events_with_rules(self, mock_get_rules_for_submission):
        """Apply a set of events for which some rules apply."""
        mock_get_rules_for_submission.return_value = [
            EventRule(rule_id=1, creator=System(), created=datetime.now(),
                      condition=RuleCondition(
                        event_type='UpdateMetadataEvent',
                        extra_condition={}),
                      consequence=RuleConsequence(
                        event_creator=System(),
                        event_type='CreateCommentEvent',
                        event_data={'body': 'The metadata was updated'})),
            EventRule(rule_id=2, creator=System(), created=datetime.now(),
                      condition=RuleCondition(
                        submission_id=2,
                        event_type='UpdateMetadataEvent',
                        extra_condition={}),
                      consequence=RuleConsequence(
                        event_creator=System(),
                        event_type='CreateCommentEvent',
                        event_data={'body': 'The metadata was updated'}))
        ]
        created = datetime.now()
        e = CreateSubmissionEvent(creator=System(), created=created)
        e2 = UpdateMetadataEvent(creator=System(), metadata=[['title', 'foo']],
                                 created=created + timedelta(seconds=1))
        submission, _ = controllers._emit(e, e2)

        self.assertEqual(len(submission.comments), 1, "A comment is added")


class TestGetSubmissionAt(TestCase):
    def setUp(self):
        app = Flask(__name__)
        # app.config.from_pyfile('../events.config')
        app.app_context().push()
        app.config['SQLALCHEMY_DATABASE_URI'] = TEST
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        database.db.init_app(app)
        database.db.create_all()

    def tearDown(self):
        database.db.session.commit()
        database.db.drop_all()
        database.util._db_agent_cache = {}


class TestApplyRules(TestCase):
    """Tests for :func:`.database._apply_rules`."""

    def test_apply_with_submission_specific_rule(self) -> None:
        """A rule specific to a submission is applied."""
        rule = EventRule(
            rule_id=1,
            creator=System(),
            created=datetime.now(),
            condition=RuleCondition(
                submission_id=1,
                event_type='UpdateMetadataEvent',
                extra_condition={}
            ),
            consequence=RuleConsequence(
                event_type='CreateCommentEvent',
                event_creator=System(),
                event_data={'body': 'The metadata was updated'}
            )
        )
        rule2 = EventRule(
            rule_id=2,
            creator=System(),
            created=datetime.now(),
            condition=RuleCondition(
                submission_id=2,
                event_type='UpdateMetadataEvent',
                extra_condition={}
            ),
            consequence=RuleConsequence(
                event_type='CreateCommentEvent',
                event_creator=System(),
                event_data={'body': 'The metadata was updated'}
            )
        )
        authors = [
            Author(forename='Joe', surname='Bloggs', affiliation='FSU',
                   email='jbloggs@fsu.wtf', order=1)
        ]
        submission = Submission(
            submission_id=1,
            creator=System(),
            created=datetime.now(),
            metadata=SubmissionMetadata(
                title='The Title',
                abstract='Very abstract',
                authors=authors
            )
        )
        event = UpdateMetadataEvent(
            creator=System(),
            metadata=[['title', 'foo']],
            created=datetime.now()
        )
        events = controllers._apply_rules(submission, event, [rule, rule2])
        self.assertEqual(len(events), 1, "Only one rule is satisfied")
        self.assertIsInstance(events[0], CreateCommentEvent)
        self.assertEqual(events[0].body, 'The metadata was updated')

    def test_apply_with_general_rule(self) -> None:
        """A rule specific to a submission is applied."""
        rule = EventRule(
            rule_id=1,
            creator=System(),
            created=datetime.now(),
            condition=RuleCondition(
                event_type='UpdateMetadataEvent',
                extra_condition={}
            ),
            consequence=RuleConsequence(
                event_creator=System(),
                event_type='CreateCommentEvent',
                event_data={'body': 'The metadata was updated'}
            )
        )
        rule2 = EventRule(
            rule_id=2,
            creator=System(),
            created=datetime.now(),
            condition=RuleCondition(
                submission_id=2,
                event_type='UpdateMetadataEvent',
                extra_condition={}
            ),
            consequence=RuleConsequence(
                event_creator=System(),
                event_type='CreateCommentEvent',
                event_data={'body': 'The metadata was updated'}
            )
        )
        authors = [
            Author(forename='Joe', surname='Bloggs', affiliation='FSU',
                   email='jbloggs@fsu.wtf', order=1)
        ]
        submission = Submission(
            submission_id=1,
            creator=System(),
            created=datetime.now(),
            metadata=SubmissionMetadata(
                title='The Title',
                abstract='Very abstract',
                authors=authors
            )
        )
        event = UpdateMetadataEvent(
            creator=System(),
            metadata=[['title', 'foo']],
            created=datetime.now()
        )
        events = controllers._apply_rules(submission, event, [rule, rule2])
        self.assertEqual(len(events), 1, "Only one rule is satisfied")
        self.assertIsInstance(events[0], CreateCommentEvent)
        self.assertEqual(events[0].body, 'The metadata was updated')
