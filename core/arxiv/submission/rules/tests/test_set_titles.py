from unittest import TestCase, mock
from datetime import datetime
import copy
from ...domain.event import SetTitle
from ...domain.submission import Submission
from ...domain.agent import Agent, User

from .. import set_title
from .data import titles


class TestCheckForSimilarTitles(TestCase):
    """Tests for :func:`.set_title.check_for_similar_titles`."""

    @mock.patch(f'{set_title.__name__}.classic.get_titles',
                mock.MagicMock(return_value=titles.TITLES))
    def test_check_for_similar_titles(self):
        user_id = 54321
        title = 'a lepton of colliders or interactions with strong field'
        creator = User(native_id=user_id, email='something@else.com')
        before = Submission(
            submission_id=2347441,
            creator=creator,
            created=datetime.now()
        )
        event = SetTitle(title=title, creator=creator)
        after = copy.deepcopy(before)
        before.metadata.title = title

        print(set_title.check_for_similar_titles(event, before, after, creator))
