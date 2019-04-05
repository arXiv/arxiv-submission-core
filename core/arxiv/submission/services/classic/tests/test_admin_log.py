"""Tests for admin log integration."""

from unittest import TestCase, mock
import os
from datetime import datetime
from contextlib import contextmanager
import json
from pytz import UTC

from flask import Flask

from ....domain.agent import User, System
from ....domain.submission import Submission, Author
from ....domain.event import CreateSubmission, ConfirmPolicy, SetTitle
from .. import models, store_event, log

from .util import in_memory_db


class TestAdminLog(TestCase):
    """Test adding an admin long entry with :func:`.log.admin_log`."""

    def test_add_admin_log_entry(self):
        """Add a log entry."""
        with in_memory_db() as session:
            log.admin_log(
                "fooprogram",
                "test",
                "this is a test of the admin log",
                username="foouser",
                hostname="127.0.0.1",
                submission_id=5
            )

            logs = session.query(models.AdminLogEntry).all()
            self.assertEqual(len(logs), 1)
            self.assertEqual(logs[0].program, "fooprogram")
            self.assertEqual(logs[0].command, "test")
            self.assertEqual(logs[0].logtext,
                             "this is a test of the admin log")
            self.assertEqual(logs[0].username, "foouser")
            self.assertEqual(logs[0].host, "127.0.0.1")
            self.assertEqual(logs[0].submission_id, 5)
            self.assertEqual(logs[0].paper_id, "submit/5")
            self.assertFalse(logs[0].notify)
            self.assertIsNone(logs[0].document_id)


class TestOnEvent(TestCase):
    """Functions in :const:`.log.ON_EVENT` are called."""

    def test_on_event(self):
        """Function in :const:`.log.ON_EVENT` is called."""
        mock_handler = mock.MagicMock()
        log.ON_EVENT[ConfirmPolicy] = [mock_handler]
        user = User(12345, 'joe@joe.joe', username="joeuser",
                    endorsements=['physics.soc-ph', 'cs.DL'])
        event = ConfirmPolicy(creator=user)
        before = Submission(creator=user, owner=user, submission_id=42)
        after = Submission(creator=user, owner=user, submission_id=42)
        log.handle(event, before, after)
        self.assertEqual(mock_handler.call_count, 1,
                         "Handler registered for ConfirmPolicy is called")

    def test_on_event_is_specific(self):
        """Function in :const:`.log.ON_EVENT` are specific."""
        mock_handler = mock.MagicMock()
        log.ON_EVENT[ConfirmPolicy] = [mock_handler]
        user = User(12345, 'joe@joe.joe', username="joeuser",
                    endorsements=['physics.soc-ph', 'cs.DL'])
        event = SetTitle(creator=user, title="foo title")
        before = Submission(creator=user, owner=user, submission_id=42)
        after = Submission(creator=user, owner=user, submission_id=42)
        log.handle(event, before, after)
        self.assertEqual(mock_handler.call_count, 0,
                         "Handler registered for ConfirmPolicy is not called")


class TestStoreEvent(TestCase):
    """Test log integration when storing event."""

    def test_store_event(self):
        """Log handler is called when an event is stored."""
        mock_handler = mock.MagicMock()
        log.ON_EVENT[CreateSubmission] = [mock_handler]
        user = User(12345, 'joe@joe.joe', username="joeuser",
                    endorsements=['physics.soc-ph', 'cs.DL'])
        event = CreateSubmission(creator=user, created=datetime.now(UTC))
        before = None
        after = Submission(creator=user, owner=user, submission_id=42)

        with in_memory_db():
            store_event(event, before, after)

        self.assertEqual(mock_handler.call_count, 1,
                         "Handler registered for CreateSubmission is called")
