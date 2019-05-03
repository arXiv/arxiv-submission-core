"""Tests for :mod:`events` public API."""

from unittest import TestCase, mock
import os
from collections import defaultdict
from datetime import datetime, timedelta
from flask import Flask
from pytz import UTC
from ... import save, load, core, Submission, User, Event, \
    SubmissionMetadata, CreateSubmission, SetAuthors, Author, \
    SetTitle, SetAbstract
from ...exceptions import NoSuchSubmission, InvalidEvent
from ...services import classic


def mock_store_event(event, before, after, emit):
    event.submission_id = 1
    after.submission_id = 1
    event.committed = True
    emit(event)
    return event, after


class TestLoad(TestCase):
    """Test :func:`.load`."""

    @mock.patch('submission.core.classic')
    def test_load_existant_submission(self, mock_classic):
        """When the submission exists, submission and events are returned."""
        u = User(12345, 'joe@joe.joe')
        mock_classic.get_submission.return_value = (
            Submission(creator=u, submission_id=1, owner=u,
                       created=datetime.now(UTC)),
            [CreateSubmission(creator=u, submission_id=1, committed=True)]
        )
        submission, events = load(1)
        self.assertEqual(mock_classic.get_submission.call_count, 1)
        self.assertIsInstance(submission, Submission,
                              "A submission should be returned")
        self.assertIsInstance(events, list,
                              "A list of events should be returned")
        self.assertIsInstance(events[0], Event,
                              "A list of events should be returned")

    @mock.patch('submission.core.classic')
    def test_load_nonexistant_submission(self, mock_classic):
        """When the submission does not exist, an exception is raised."""
        mock_classic.get_submission.side_effect = classic.NoSuchSubmission
        mock_classic.NoSuchSubmission = classic.NoSuchSubmission
        with self.assertRaises(NoSuchSubmission):
            load(1)


class TestSave(TestCase):
    """Test :func:`.save`."""

    @mock.patch(f'{core.__name__}.StreamPublisher')
    @mock.patch('submission.core.classic')
    def test_save_creation_event(self, mock_database, mock_publisher):
        """A :class:`.CreationEvent` is passed."""
        mock_database.store_event = mock_store_event
        mock_database.exceptions = classic.exceptions
        user = User(12345, 'joe@joe.joe')
        event = CreateSubmission(creator=user)
        submission, events = save(event)
        self.assertIsInstance(submission, Submission,
                              "A submission instance should be returned")
        self.assertIsInstance(events[0], Event,
                              "Should return a list of events")
        self.assertEqual(events[0], event,
                         "The first event should be the event that was passed")
        self.assertIsNotNone(submission.submission_id,
                             "Submission ID should be set.")

        self.assertEqual(mock_publisher.put.call_count, 1)
        args = event, None, submission
        self.assertTrue(mock_publisher.put.called_with(*args))

    @mock.patch(f'{core.__name__}.StreamPublisher')
    @mock.patch('submission.core.classic')
    def test_save_events_from_scratch(self, mock_database, mock_publisher):
        """Save multiple events for a nonexistant submission."""
        mock_database.store_event = mock_store_event
        mock_database.exceptions = classic.exceptions
        user = User(12345, 'joe@joe.joe')
        e = CreateSubmission(creator=user)
        e2 = SetTitle(creator=user, title='footitle')
        submission, events = save(e, e2)

        self.assertEqual(submission.metadata.title, 'footitle')
        self.assertIsInstance(submission.submission_id, int)
        self.assertEqual(submission.created, e.created)

        self.assertEqual(mock_publisher.put.call_count, 2)
        self.assertEqual(mock_publisher.put.mock_calls[0][1][0], e)
        self.assertEqual(mock_publisher.put.mock_calls[1][1][0], e2)

    @mock.patch(f'{core.__name__}.StreamPublisher')
    @mock.patch('submission.core.classic')
    def test_create_and_update_authors(self, mock_database, mock_publisher):
        """Save multiple events for a nonexistant submission."""
        mock_database.store_event = mock_store_event
        mock_database.exceptions = classic.exceptions
        user = User(12345, 'joe@joe.joe')
        e = CreateSubmission(creator=user)
        e2 = SetAuthors(creator=user, authors=[
            Author(0, forename='Joe', surname="Bloggs", email="joe@blog.gs")
        ])
        submission, events = save(e, e2)
        self.assertIsInstance(submission.metadata.authors[0], Author)

        self.assertEqual(mock_publisher.put.call_count, 2)
        self.assertEqual(mock_publisher.put.mock_calls[0][1][0], e)
        self.assertEqual(mock_publisher.put.mock_calls[1][1][0], e2)

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    @mock.patch('submission.core.classic')
    def test_save_from_scratch_without_creation_event(self, mock_database):
        """An exception is raised when there is no creation event."""
        mock_database.store_event = mock_store_event
        user = User(12345, 'joe@joe.joe')
        e2 = SetTitle(creator=user, title='foo')
        with self.assertRaises(NoSuchSubmission):
            save(e2)

    @mock.patch(f'{core.__name__}.StreamPublisher')
    @mock.patch('submission.core.classic')
    def test_save_events_on_existing_submission(self, mock_db, mock_publisher):
        """Save multiple sets of events in separate calls to :func:`.save`."""
        mock_db.exceptions = classic.exceptions
        cache = {}

        def mock_store_event_with_cache(event, before, after, emit):
            if after.submission_id is None:
                if before is not None:
                    before.submission_id = 1
                after.submission_id = 1

            event.committed = True
            event.submission_id = after.submission_id
            if event.submission_id not in cache:
                cache[event.submission_id] = (None, [])
            cache[event.submission_id] = (
                after, cache[event.submission_id][1] + [event]
            )
            emit(event)
            return event, after

        def mock_get_events(submission_id, *args, **kwargs):
            return cache[submission_id]

        mock_db.store_event = mock_store_event_with_cache
        mock_db.get_submission = mock_get_events

        # Here is the first set of events.
        user = User(12345, 'joe@joe.joe')
        e = CreateSubmission(creator=user)
        e2 = SetTitle(creator=user, title='footitle')
        submission, _ = save(e, e2)
        submission_id = submission.submission_id

        # Now we apply a second set of events.
        e3 = SetAbstract(creator=user, abstract='bar'*10)
        submission2, _ = save(e3, submission_id=submission_id)

        # The submission state reflects all three events.
        self.assertEqual(submission2.metadata.abstract, 'bar'*10,
                         "State of the submission should reflect both sets"
                         " of events.")
        self.assertEqual(submission2.metadata.title, 'footitle',
                         "State of the submission should reflect both sets"
                         " of events.")
        self.assertEqual(submission2.created, e.created,
                         "The creation date of the submission should be the"
                         " original creation date.")
        self.assertEqual(submission2.submission_id, submission_id,
                         "The submission ID should remain the same.")

        self.assertEqual(mock_publisher.put.call_count, 3)
        self.assertEqual(mock_publisher.put.mock_calls[0][1][0], e)
        self.assertEqual(mock_publisher.put.mock_calls[1][1][0], e2)
        self.assertEqual(mock_publisher.put.mock_calls[2][1][0], e3)
