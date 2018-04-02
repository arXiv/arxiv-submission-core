"""Tests for :mod:`events` public API."""

from unittest import TestCase, mock
import os
from collections import defaultdict
from datetime import datetime, timedelta
from flask import Flask
from events import CreateSubmissionEvent, save, Submission, User, Event, \
    UpdateMetadataEvent, EventRule, RuleCondition, RuleConsequence, \
    CreateCommentEvent, SubmissionMetadata


def mock_store_events(*events, submission):
    """Mock for :func:`events.services.database.store_events`."""
    if submission.submission_id is None:
        submission.submission_id = 1
    for event in events:
        event.committed = True
        event.submission_id = submission.submission_id
    return submission


class TestSave(TestCase):
    """Test :func:`.save`."""

    @mock.patch('events.database')
    def test_save_creation_event(self, mock_database):
        """A :class:`.CreationEvent` is passed."""
        mock_database.store_events = mock_store_events
        user = User('foouser')
        event = CreateSubmissionEvent(creator=user)
        submission, events = save(event)
        self.assertIsInstance(submission, Submission,
                              "A submission instance should be returned")
        self.assertIsInstance(events[0], Event,
                              "Should return a list of events")
        self.assertEqual(events[0], event,
                         "The first event should be the event that was passed")
        self.assertIsNotNone(submission.submission_id,
                             "Submission ID should be set.")

    @mock.patch('events.database')
    def test_save_events_from_scratch(self, mock_database):
        """Save multiple events for a nonexistant submission."""
        mock_database.store_events = mock_store_events
        e = CreateSubmissionEvent(creator=User('foouser'))
        e2 = UpdateMetadataEvent(creator=User('foouser'),
                                 metadata=[['title', 'foo']])
        submission, events = save(e, e2)

        self.assertEqual(submission.metadata.title, 'foo')
        self.assertIsInstance(submission.submission_id, int)
        self.assertEqual(submission.created, e.created)

    @mock.patch('events.database')
    def test_save_from_scratch_without_creation_event(self, mock_database):
        """An exception is raised when there is no creation event."""
        mock_database.store_events = mock_store_events
        e2 = UpdateMetadataEvent(creator=User('foouser'),
                                 metadata=[['title', 'foo']])
        with self.assertRaises(RuntimeError):
            save(e2)

    @mock.patch('events.database')
    def test_save_events_on_existing_submission(self, mock_db):
        """Save multiple sets of events in separate calls to :func:`.save`."""
        cache = defaultdict(list)

        def mock_store_events_with_cache(*events, submission):
            if submission.submission_id is None:
                submission.submission_id = 1
            for event in events:
                event.committed = True
                event.submission_id = submission.submission_id
                cache[event.submission_id].append(event)
            return submission

        def mock_get_events_for_submission(submission_id):
            return cache[submission_id]

        mock_db.store_events = mock_store_events_with_cache
        mock_db.get_events_for_submission = mock_get_events_for_submission

        # Here is the first set of events.
        e = CreateSubmissionEvent(creator=User('foouser'))
        e2 = UpdateMetadataEvent(creator=User('foouser'),
                                 metadata=[['title', 'foo']])
        submission, _ = save(e, e2)
        submission_id = submission.submission_id

        # Now we apply a second set of events.
        e3 = UpdateMetadataEvent(creator=User('foouser'),
                                 metadata=[['abstract', 'bar']])
        submission2, _ = save(e3, submission_id=submission_id)

        # The submission state reflects all three events.
        self.assertEqual(submission2.metadata.abstract, 'bar',
                         "State of the submission should reflect both sets"
                         " of events.")
        self.assertEqual(submission2.metadata.title, 'foo',
                         "State of the submission should reflect both sets"
                         " of events.")
        self.assertEqual(submission2.created, e.created,
                         "The creation date of the submission should be the"
                         " original creation date.")
        self.assertEqual(submission2.submission_id, submission_id,
                         "The submission ID should remain the same.")

    @mock.patch('events.database')
    def test_apply_events_with_rules(self, mock_db):
        """Save a set of events for which some rules apply."""
        # Given the following rule...
        def mock_get_rules_for_submission(submission_id):
            return [
                # If the metadata of any submission was updated, add a comment.
                EventRule(
                    rule_id=1,
                    creator=User('foo'),
                    condition=RuleCondition(
                        event_type=UpdateMetadataEvent,
                        extra_condition={}
                    ),
                    consequence=RuleConsequence(
                        event_creator=User('foo'),
                        event_type=CreateCommentEvent,
                        event_data={
                            'body': 'The metadata was updated',
                            'scope': 'private'
                        }
                    )
                )
            ]
        mock_db.get_rules_for_submission = mock_get_rules_for_submission
        mock_db.store_events = mock_store_events
        e = CreateSubmissionEvent(creator=User('foo'))
        e2 = UpdateMetadataEvent(creator=User('foo'),
                                 metadata=[['title', 'foo']])
        submission, events = save(e, e2)
        self.assertEqual(len(submission.comments), 1,
                         "A comment should be added to the submission.")
        self.assertEqual(len(events), 3,
                         "A third event is added to the stack.")
