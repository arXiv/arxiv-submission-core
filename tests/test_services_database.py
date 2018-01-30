"""Tests for :mod:`.services.database`."""

from unittest import TestCase, mock
import os
from datetime import datetime
from flask import Flask
from submit.services import database
from api.domain.event import event_factory, Event
from api.domain.submission import Submission, SubmissionMetadata
from api.domain.agent import agent_factory


TEST = os.environ.get(
    'TEST_DATABASE_URI',
    'postgres://arxiv-submit:arxiv-submit@localhost:5432/arxiv-submit-test'
)


# TODO: more tests!
class TestStoreGetEvent(TestCase):
    """The database service stores and retrieves :class:`.Event`s."""

    def setUp(self):
        """Initialize a fresh database."""
        app = Flask(__name__)
        app.app_context().push()
        app.config['SQLALCHEMY_DATABASE_URI'] = TEST
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        database.db.init_app(app)
        database.db.create_all()

    def tearDown(self):
        """Clear our the test database."""
        database.db.session.commit()
        database.db.drop_all()
        database.util._db_agent_cache = {}

    def test_store_event(self):
        """:func:`.database.store_events` persists events and submission."""
        creator = agent_factory('UserAgent', 'foo-user')
        submission = Submission(
            metadata=SubmissionMetadata(
                title='foo title'
            ),
            created=datetime.now(),
            creator=creator,
            owner=creator
        )
        event = event_factory('UpdateMetadataEvent', creator=creator,
                              metadata=[('title', 'foo title')])
        submission = database.store_events(event, submission=submission)

        self.assertIsNotNone(submission.submission_id)
        self.assertTrue(event.committed)

        N_events = database.db.session.query(database.models.Event).count()
        self.assertEqual(N_events, 1)

        db_event = database.db.session.query(database.models.Event).first()
        self.assertEqual(db_event.event_id, event.event_id)
        self.assertEqual(db_event.data.get('created'),
                         event.created.isoformat())
        self.assertEqual(db_event.data['creator']['native_id'],
                         creator.native_id)

    def test_get_events_for_submission(self):
        """:func:`.get_events_for_submission` retrieves :class:`.Event`s."""
        creator = agent_factory('UserAgent', 'foo-user')
        submission = database.models.Submission()
        event = event_factory('UpdateMetadataEvent', creator=creator,
                              metadata=[('title', 'foo title')])
        database.db.session.add(
            database.models.Event(
                submission_id=submission.submission_id,
                event_type='UpdateMetadataEvent',
                event_id=event.event_id,
                data=event.to_dict(),
                created=event.created,
                creator=database.util._get_or_create_dbagent(creator)
            )
        )
        database.db.session.commit()

        r_events = database.get_events_for_submission(submission.submission_id)
        self.assertEqual(len(r_events), 1)
        self.assertIsInstance(r_events[0], Event)
        self.assertEqual(r_events[0].event_id, event.event_id)


# TODO: more tests!
class TestStoreGetSubmission(TestCase):
    """The database service stores and retrieves :class:`.Submission`s."""

    def setUp(self):
        """Initialize a fresh database."""
        app = Flask(__name__)
        app.app_context().push()
        app.config['SQLALCHEMY_DATABASE_URI'] = TEST
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        database.db.init_app(app)
        database.db.create_all()

    def tearDown(self):
        """Clear our the test database."""
        database.db.session.commit()
        database.db.drop_all()
        database.util._db_agent_cache = {}

    def test_store_submission(self):
        """:func:`.database.store_events` persists events and submission."""
        creator = agent_factory('UserAgent', 'foo-user')
        submission = Submission(
            metadata=SubmissionMetadata(
                title='foo title'
            ),
            created=datetime.now(),
            creator=creator,
            owner=creator
        )
        event = event_factory('UpdateMetadataEvent', creator=creator,
                              metadata=[('title', 'foo title')])
        submission = database.store_events(event, submission=submission)

        r_events = database.get_events_for_submission(submission.submission_id)
        self.assertEqual(len(r_events), 1)
        self.assertIsInstance(r_events[0], Event)
        self.assertEqual(r_events[0].event_id, event.event_id)

        r_submission = database.get_submission(submission.submission_id)
        self.assertEqual(r_submission.submission_id, submission.submission_id)
