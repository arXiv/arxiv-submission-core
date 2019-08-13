"""Tests for :mod:`.serializer`."""

from datetime import datetime
from unittest import TestCase

from pytz import UTC

from arxiv.submission import Submission, User
from arxiv.submission.domain.event import SetTitle, SubmissionMetadata

from ..domain import ProcessData, Trigger
from ..serializer import dumps, loads


class TestSerialize(TestCase):
    def test_serialize_trigger(self):
        """Serialize and deserialize a :class:`.Trigger`."""
        creator = User(1234, username='foo', email='foo@bar.com')
        event = SetTitle(creator=creator, title='the title',
                         created=datetime.now(UTC))
        trigger = Trigger(
            actor=creator,
            event=event,
            before=Submission(creator=creator, created=event.created,
                              owner=creator),
            after=Submission(creator=creator, created=event.created,
                             owner=creator,
                             metadata=SubmissionMetadata(title='the title')),
        )
        deserialized = loads(dumps(trigger))
        self.assertIsInstance(deserialized, Trigger)
        self.assertEqual(deserialized, trigger)

    def test_serialize_processdata(self):
        """Serialize and deserialize a :class:`.ProcessData`."""
        creator = User(1234, username='foo', email='foo@bar.com')
        event = SetTitle(creator=creator, title='the title',
                         created=datetime.now(UTC))
        trigger = Trigger(
            actor=creator,
            event=event,
            before=Submission(creator=creator, created=event.created,
                              owner=creator),
            after=Submission(creator=creator, created=event.created,
                             owner=creator,
                             metadata=SubmissionMetadata(title='the title')),
        )
        data = ProcessData(submission_id=2, process_id='fooid',
                           trigger=trigger, results=[1, 'a'])
        deserialized = loads(dumps(data))
        self.assertIsInstance(deserialized, ProcessData)
        self.assertEqual(deserialized, data)
