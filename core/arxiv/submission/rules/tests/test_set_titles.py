from unittest import TestCase, mock
from datetime import datetime
import copy
from ...domain.event import SetTitle, AddAnnotation, RemoveAnnotation
from ...domain.submission import Submission
from ...domain.agent import Agent, User
from ...domain.annotation import PossibleDuplicate

from .. import set_title
from ... import tasks
from .data import titles


class TestCheckForSimilarTitles(TestCase):
    """Tests for :func:`.set_title.check_for_similar_titles`."""

    @mock.patch(f'{tasks.__name__}.get_application_config',
                mock.MagicMock(return_value={'NO_ASYNC': 1}))
    @mock.patch(f'{set_title.__name__}.classic.get_titles',
                mock.MagicMock(return_value=titles.TITLES))
    def test_check_for_similar_titles(self):
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
            set_title.check_for_similar_titles(event_t, before, after, creator)
        )
        self.assertEqual(len(events), 2, "Generates two events")
        for event in events:
            self.assertIsInstance(event, AddAnnotation,
                                  "Generates AddAnnotation events")
            self.assertIsInstance(event.annotation, PossibleDuplicate,
                                  "Annotations are PossibleDuplicates")

        for event in events:      # Apply the generated events.
            after = event.apply(after)

        # Checking a second time removes the previous annotations.
        events = list(
            set_title.check_for_similar_titles(event_t, before, after, creator)
        )
        self.assertEqual(len(events), 4, "Generates four events")
        for event in events[:2]:
            self.assertIsInstance(event, RemoveAnnotation,
                                  "Generates RemoveAnnotation events")

        for event in events[2:]:
            self.assertIsInstance(event, AddAnnotation,
                                  "Generates AddAnnotation events")
            self.assertIsInstance(event.annotation, PossibleDuplicate,
                                  "Annotations are PossibleDuplicates")
