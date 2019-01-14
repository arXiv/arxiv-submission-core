"""Test callback hook functionality on :class:`Event`."""

from unittest import TestCase, mock
from dataclasses import dataclass, field
from ..event import Event
from ...agent import System


class TestCommitEvent(TestCase):
    def test_commit_event(self):

        @dataclass
        class ChildEvent(Event):
            _should_apply_callbacks = lambda *a, **k: True

        @dataclass
        class OtherChildEvent(Event):
            _should_apply_callbacks = lambda *a, **k: True

        callback = mock.MagicMock(return_value=[], __name__='test')
        ChildEvent.bind()(callback)

        save = mock.MagicMock(
            return_value=(mock.MagicMock(), mock.MagicMock())
        )
        event = ChildEvent(creator=System('system'))
        other_event = OtherChildEvent(creator=System('system'))
        event.commit(save)
        self.assertEqual(callback.call_count, 1)
