from unittest import TestCase
from datetime import datetime
from pytz import UTC
from dataclasses import asdict
import json

from ...serializer import dumps, loads
from ...domain.event import CreateSubmission, SetTitle
from ...domain.agent import User, System, Client
from ...domain.submission import Submission, SubmissionContent, License, \
    Classification, CrossListClassificationRequest, Hold, Waiver
from ...domain.proposal import Proposal
from ...domain.process import ProcessStatus
from ...domain.annotation import Feature, Comment
from ...domain.flag import ContentFlag


class TestDumpLoad(TestCase):
    """Tests for :func:`.dumps` and :func:`.loads`."""

    def test_dump_createsubmission(self):
        """Serialize and deserialize a :class:`.CreateSubmission` event."""
        user = User('123', 'foo@user.com', 'foouser')
        event = CreateSubmission(creator=user, created=datetime.now(UTC))
        data = dumps(event)
        self.assertDictEqual(asdict(user), json.loads(data)["creator"],
                             "User data is fully encoded")
        deserialized = loads(data)
        self.assertEqual(deserialized, event)
        self.assertEqual(deserialized.creator, user)
        self.assertEqual(deserialized.created, event.created)

    def test_dump_load_submission(self):
        """Serialize and deserialize a :class:`.Submission`."""
        user = User('123', 'foo@user.com', 'foouser')

        client = Client('fooclient', 'asdf')
        system = System('testprocess')
        submission = Submission(
            creator=user,
            owner=user,
            client=client,
            created=datetime.now(UTC),
            updated=datetime.now(UTC),
            submitted=datetime.now(UTC),
            source_content=SubmissionContent(
                identifier='12345',
                checksum='asdf1234',
                uncompressed_size=435321,
                compressed_size=23421,
                source_format=SubmissionContent.Format.TEX
            ),
            primary_classification=Classification(category='cs.DL'),
            secondary_classification=[Classification(category='cs.AI')],
            submitter_contact_verified=True,
            submitter_is_author=True,
            submitter_accepts_policy=True,
            submitter_confirmed_preview=True,
            license=License('http://foolicense.org/v1', 'The Foo License'),
            status=Submission.ANNOUNCED,
            arxiv_id='1234.56789',
            version=2,
            user_requests={
                'asdf1234': CrossListClassificationRequest('asdf1234', user)
            },
            proposals={
                'prop1234': Proposal(
                    event_id='prop1234',
                    creator=user,
                    proposed_event_type=SetTitle,
                    proposed_event_data={'title': 'foo title'}
                )
            },
            processes=[
                ProcessStatus(
                    creator=system,
                    created=datetime.now(UTC),
                    status=ProcessStatus.Status.SUCCEEDED,
                    process='FooProcess'
                )
            ],
            annotations={
                'asdf123543': Feature(
                    event_id='asdf123543',
                    created=datetime.now(UTC),
                    creator=system,
                    feature_type=Feature.Type.PAGE_COUNT,
                    feature_value=12345678.32
                )
            },
            flags={
                'fooflag1': ContentFlag(
                    event_id='fooflag1',
                    creator=system,
                    created=datetime.now(UTC),
                    flag_type=ContentFlag.Type.LOW_STOP,
                    flag_data=25,
                    comment='no comment'
                )
            },
            comments={
                'asdf54321': Comment(
                    event_id='asdf54321',
                    creator=system,
                    created=datetime.now(UTC),
                    body='here is comment'
                )
            },
            holds={
                'foohold1234': Hold(
                    event_id='foohold1234',
                    creator=system,
                    hold_type=Hold.Type.SOURCE_OVERSIZE,
                    hold_reason='the best reason'
                )
            },
            waivers={
                'waiver1234': Waiver(
                    event_id='waiver1234',
                    waiver_type=Hold.Type.SOURCE_OVERSIZE,
                    waiver_reason='it is ok',
                    created=datetime.now(UTC),
                    creator=system
                )
            }
        )
        raw = dumps(submission)
        loaded = loads(raw)

        self.assertEqual(submission.creator, loaded.creator)
        self.assertEqual(submission.owner, loaded.owner)
        self.assertEqual(submission.client, loaded.client)
        self.assertEqual(submission.created, loaded.created)
        self.assertEqual(submission.updated, loaded.updated)
        self.assertEqual(submission.submitted, loaded.submitted)
        self.assertEqual(submission.source_content, loaded.source_content)
        self.assertEqual(submission.source_content.source_format,
                         loaded.source_content.source_format)
        self.assertEqual(submission.primary_classification,
                         loaded.primary_classification)
        self.assertEqual(submission.secondary_classification,
                         loaded.secondary_classification)
        self.assertEqual(submission.license, loaded.license)
        self.assertEqual(submission.user_requests, loaded.user_requests)
        self.assertEqual(submission.proposals, loaded.proposals)
        self.assertEqual(submission.processes, loaded.processes)
        self.assertEqual(submission.annotations, loaded.annotations)
        self.assertEqual(submission.flags, loaded.flags)
        self.assertEqual(submission.comments, loaded.comments)
        self.assertEqual(submission.holds, loaded.holds)
        self.assertEqual(submission.waivers, loaded.waivers)
