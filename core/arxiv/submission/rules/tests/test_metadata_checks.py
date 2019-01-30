"""Tests for automated metadata checks."""

from unittest import TestCase, mock
from datetime import datetime
import copy
from ...domain.event import SetTitle, AddMetadataFlag, RemoveFlag
from ...domain.submission import Submission
from ...domain.agent import Agent, User
from ...domain.flag import Flag, MetadataFlag

from .. import metadata_checks
from ... import tasks
from .data import titles


class TestCheckForSimilarTitles(TestCase):
    """Tests for :func:`.metadata_checks.check_similar_titles`."""

    @mock.patch(f'{tasks.__name__}.get_application_config',
                mock.MagicMock(return_value={'ENABLE_ASYNC': 0}))
    @mock.patch(f'{metadata_checks.__name__}.classic.get_titles',
                mock.MagicMock(return_value=titles.TITLES))
    def test_check_similar_titles(self):
        """Check for similar titles."""
        user_id = 54321
        title = 'a lepton qed of colliders or interactions with strong field' \
                ' electron laser'
        creator = User(native_id=user_id, email='something@else.com')
        before = Submission(
            submission_id=2347441,
            creator=creator,
            owner=creator,
            created=datetime.now()
        )
        event_t = SetTitle(title=title, creator=creator)
        after = copy.deepcopy(before)
        before.metadata.title = title

        events = list(
            metadata_checks.check_similar_titles(event_t, before, after,
                                                 creator)
        )
        self.assertEqual(len(events), 2, "Generates two events")
        for event in events:
            self.assertIsInstance(event, AddMetadataFlag,
                                  "Generates AddMetadataFlag events")
            self.assertEqual(
                event.flag_type,
                MetadataFlag.FlagTypes.POSSIBLE_DUPLICATE_TITLE,
                "Flag has type POSSIBLE_DUPLICATE_TITLE"
            )

        for event in events:      # Apply the generated events.
            after = event.apply(after)

        # Checking a second time removes the previous annotations.
        events = list(
            metadata_checks.check_similar_titles(event_t, before, after,
                                                 creator)
        )
        self.assertEqual(len(events), 4, "Generates four events")
        for event in events[:2]:
            self.assertIsInstance(event, RemoveFlag,
                                  "Generates RemoveFlag events")

        for event in events[2:]:
            self.assertIsInstance(event, AddMetadataFlag,
                                  "Generates AddMetadataFlag events")
            self.assertEqual(
                event.flag_type,
                MetadataFlag.FlagTypes.POSSIBLE_DUPLICATE_TITLE,
                "Flag has type POSSIBLE_DUPLICATE_TITLE"
            )
