"""Tests for automated metadata checks."""

from unittest import TestCase, mock
from datetime import datetime, timedelta
from pytz import UTC
import copy
from arxiv.submission.domain.event import SetTitle, SetAbstract, \
    AddMetadataFlag, RemoveFlag
from arxiv.submission.domain.agent import Agent, User
from arxiv.submission.domain.flag import Flag, MetadataFlag
from arxiv.submission.domain.submission import Submission, SubmissionContent, \
    SubmissionMetadata, Classification

from .. import CheckForSimilarTitles, CheckTitleForUnicodeAbuse, \
    CheckAbstractForUnicodeAbuse, Failed
from .. import metadata_checks
from ...domain import Trigger
from ...factory import create_app
from .data import titles


class TestCheckForSimilarTitles(TestCase):
    """Tests for :func:`.metadata_checks.check_similar_titles`."""

    def setUp(self):
        """We have a submission."""
        self.app = create_app()
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
        self.process = CheckForSimilarTitles(self.submission.submission_id)

    @mock.patch(f'{metadata_checks.__name__}.classic.get_titles')
    def test_check_similar_titles(self, mock_get_titles):
        """Check for similar titles."""
        mock_get_titles.return_value = titles.TITLES

        user_id = 54321
        title = 'a lepton qed of colliders or interactions with strong field' \
                ' electron laser'
        event = SetTitle(creator=self.creator, title=title)
        before = copy.deepcopy(self.submission)
        after = copy.deepcopy(self.submission)
        after.metadata = SubmissionMetadata(title=title)
        events = []

        trigger = Trigger(event=event, actor=self.creator,
                          before=before, after=after,
                          params={'TITLE_SIMILARITY_WINDOW': 60})

        some_titles = self.process.get_candidates(None, trigger, events.append)

        self.assertEqual(len(some_titles), len(titles.TITLES))
        self.assertEqual(mock_get_titles.call_count, 1)
        self.assertIsInstance(mock_get_titles.call_args[0][0], datetime)

    def test_check_for_duplicates(self):
        """Look for similar titles."""
        title = 'a lepton qed of colliders or interactions with strong field' \
                ' electron laser'
        event = SetTitle(creator=self.creator, title=title)

        before = copy.deepcopy(self.submission)
        after = copy.deepcopy(self.submission)
        after.metadata = SubmissionMetadata(title=title)

        trigger = Trigger(event=event, actor=self.creator,
                          before=before, after=after,
                          params={'TITLE_SIMILARITY_THRESHOLD': 0.7})
        events = []
        self.process.check_for_duplicates(titles.TITLES, trigger,
                                          events.append)
        self.assertGreater(len(events), 0, "Generates some events")
        for event in events:
            self.assertIsInstance(event, AddMetadataFlag,
                                  "Generates AddMetadataFlag events")
            self.assertEqual(
                event.flag_type,
                MetadataFlag.Type.POSSIBLE_DUPLICATE_TITLE,
                "Flag has type POSSIBLE_DUPLICATE_TITLE"
            )

    def test_check_with_existing_flags(self):
        """The submission already has possible dupe title flags."""
        title = 'a lepton qed of colliders or interactions with strong field' \
                ' electron laser'
        self.submission.flags['asdf1234'] = MetadataFlag(
            event_id='asdf1234',
            creator=self.creator,
            created=datetime.now(UTC),
            flag_type=MetadataFlag.Type.POSSIBLE_DUPLICATE_TITLE,
            flag_data={'id': 5, 'title': title, 'owner': self.creator},
            field='title',
            comment='possible duplicate title'
        )
        event = SetTitle(creator=self.creator, title=title)

        before = copy.deepcopy(self.submission)
        after = copy.deepcopy(self.submission)
        after.metadata = SubmissionMetadata(title=title)

        trigger = Trigger(event=event, actor=self.creator,
                          before=before, after=after,
                          params={'TITLE_SIMILARITY_THRESHOLD': 1.0})
        events = []
        self.process.check_for_duplicates(titles.TITLES, trigger,
                                          events.append)
        self.assertGreater(len(events), 0, "Generates some events")
        self.assertIsInstance(events[0], RemoveFlag)
        self.assertEqual(events[0].flag_id, 'asdf1234')

    def test_check_for_duplicates_with_strict_threshold(self):
        """Look for similar titles with an impossibly strict threshold."""
        title = 'a lepton qed of colliders or interactions with strong field' \
                ' electron laser'
        event = SetTitle(creator=self.creator, title=title)
        before = copy.deepcopy(self.submission)
        after = copy.deepcopy(self.submission)
        after.metadata = SubmissionMetadata(title=title)

        trigger = Trigger(event=event, actor=self.creator,
                          before=before, after=after,
                          params={'TITLE_SIMILARITY_THRESHOLD': 1.0})
        events = []
        self.process.check_for_duplicates(titles.TITLES, trigger,
                                          events.append)
        self.assertEqual(len(events), 0)


class TestCheckTitleForUnicodeAbuse(TestCase):
    """Tests for :func:`.CheckTitleForUnicodeAbuse.check_title`."""

    def setUp(self):
        """We have a submission."""
        self.app = create_app()
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
        self.process = CheckTitleForUnicodeAbuse(self.submission.submission_id)

    def test_low_ascii(self):
        """Title has very few ASCII characters."""
        before = copy.deepcopy(self.submission)
        title = 'ⓕöö tïtłę'
        self.submission.metadata = SubmissionMetadata(title=title)
        event = SetTitle(creator=self.creator, title=title)
        trigger = Trigger(event=event, actor=self.creator,
                          before=before, after=self.submission,
                          params={'METADATA_ASCII_THRESHOLD': 0.5})

        events = []
        self.process.check_title(None, trigger, events.append)
        self.assertIsInstance(events[0], AddMetadataFlag, 'Adds metadata flag')
        self.assertEqual(events[0].flag_type, MetadataFlag.Type.CHARACTER_SET)
        self.assertEqual(events[0].field, 'title')
        self.assertEqual(events[0].flag_data['ascii'], 3/9)

    def test_plenty_of_ascii(self):
        """Title has very planty of ASCII characters."""
        before = copy.deepcopy(self.submission)
        title = 'A boring title with occâsional non-ASCII characters'
        self.submission.metadata = SubmissionMetadata(title=title)
        event = SetTitle(creator=self.creator, title=title)
        trigger = Trigger(event=event, actor=self.creator,
                          before=before, after=self.submission,
                          params={'METADATA_ASCII_THRESHOLD': 0.1})

        events = []
        self.process.check_title(None, trigger, events.append)
        self.assertEqual(len(events), 0, 'No flags generated')

    def test_no_metadata(self):
        """The submission has no metadata."""
        self.submission.metadata = None
        trigger = Trigger(actor=self.creator,
                          before=self.submission, after=self.submission,
                          params={'METADATA_ASCII_THRESHOLD': 0.1})
        events = []
        with self.assertRaises(Failed):
            self.process.check_title(None, trigger, events.append)

    def test_no_abstract(self):
        """The submission has no title."""
        self.submission.metadata = SubmissionMetadata(title=None)
        trigger = Trigger(actor=self.creator,
                          before=self.submission, after=self.submission,
                          params={'METADATA_ASCII_THRESHOLD': 0.1})
        events = []
        with self.assertRaises(Failed):
            self.process.check_title(None, trigger, events.append)

    def test_clear_previous_tags(self):
        """There were some previous flags."""
        self.submission.flags['asdf1234'] = MetadataFlag(
            event_id='asdf1234',
            creator=self.creator,
            created=datetime.now(UTC),
            flag_type=MetadataFlag.Type.CHARACTER_SET,
            flag_data={'ascii': 0},
            field='title',
            comment='something fishy'
        )
        before = copy.deepcopy(self.submission)
        title = 'A boring title with occâsional non-ASCII characters'
        self.submission.metadata = SubmissionMetadata(title=title)
        event = SetTitle(creator=self.creator, title=title)
        trigger = Trigger(event=event, actor=self.creator,
                          before=before, after=self.submission,
                          params={'METADATA_ASCII_THRESHOLD': 0.1})

        events = []
        self.process.check_title(None, trigger, events.append)
        self.assertGreater(len(events), 0, "Generates some events")
        self.assertIsInstance(events[0], RemoveFlag)
        self.assertEqual(events[0].flag_id, 'asdf1234')


class TestCheckAbstractForUnicodeAbuse(TestCase):
    """Tests for :func:`.CheckAbstractForUnicodeAbuse.check_abstract`."""

    def setUp(self):
        """We have a submission."""
        self.app = create_app()
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
            CheckAbstractForUnicodeAbuse(self.submission.submission_id)

    def test_low_ascii(self):
        """Abstract has very few ASCII characters."""
        before = copy.deepcopy(self.submission)
        abstract = 'ⓥéⓇÿ âⒷśⓣⓇāčⓣ'
        self.submission.metadata = SubmissionMetadata(abstract=abstract)
        event = SetAbstract(creator=self.creator, abstract=abstract)
        trigger = Trigger(event=event, actor=self.creator,
                          before=before, after=self.submission,
                          params={'METADATA_ASCII_THRESHOLD': 0.5})

        events = []
        self.process.check_abstract(None, trigger, events.append)
        self.assertIsInstance(events[0], AddMetadataFlag, 'Adds metadata flag')
        self.assertEqual(events[0].flag_type, MetadataFlag.Type.CHARACTER_SET)
        self.assertEqual(events[0].field, 'abstract')
        self.assertEqual(events[0].flag_data['ascii'], 1/13)

    def test_plenty_of_ascii(self):
        """Abstract has very planty of ASCII characters."""
        before = copy.deepcopy(self.submission)
        abstract = 'what a boring abstract with no unicode characters'
        self.submission.metadata = SubmissionMetadata(abstract=abstract)
        event = SetAbstract(creator=self.creator, abstract=abstract)
        trigger = Trigger(event=event, actor=self.creator,
                          before=before, after=self.submission,
                          params={'METADATA_ASCII_THRESHOLD': 0.1})

        events = []
        self.process.check_abstract(None, trigger, events.append)
        self.assertEqual(len(events), 0, 'No flags generated')

    def test_no_metadata(self):
        """The submission has no metadata."""
        self.submission.metadata = None
        trigger = Trigger(actor=self.creator,
                          before=self.submission, after=self.submission,
                          params={'METADATA_ASCII_THRESHOLD': 0.1})
        events = []
        with self.assertRaises(Failed):
            self.process.check_abstract(None, trigger, events.append)

    def test_no_abstract(self):
        """The submission has no abstract."""
        self.submission.metadata = SubmissionMetadata(abstract=None)
        trigger = Trigger(actor=self.creator,
                          before=self.submission, after=self.submission,
                          params={'METADATA_ASCII_THRESHOLD': 0.1})
        events = []
        with self.assertRaises(Failed):
            self.process.check_abstract(None, trigger, events.append)

    def test_clear_previous_tags(self):
        """There were some previous flags."""
        self.submission.flags['asdf1234'] = MetadataFlag(
            event_id='asdf1234',
            creator=self.creator,
            created=datetime.now(UTC),
            flag_type=MetadataFlag.Type.CHARACTER_SET,
            flag_data={'ascii': 0},
            field='abstract',
            comment='something fishy'
        )
        before = copy.deepcopy(self.submission)
        abstract = 'what a boring abstract with no unicode characters'
        self.submission.metadata = SubmissionMetadata(abstract=abstract)
        event = SetAbstract(creator=self.creator, abstract=abstract)
        trigger = Trigger(event=event, actor=self.creator,
                          before=before, after=self.submission,
                          params={'METADATA_ASCII_THRESHOLD': 0.1})

        events = []
        self.process.check_abstract(None, trigger, events.append)
        self.assertGreater(len(events), 0, "Generates some events")
        self.assertIsInstance(events[0], RemoveFlag)
        self.assertEqual(events[0].flag_id, 'asdf1234')
