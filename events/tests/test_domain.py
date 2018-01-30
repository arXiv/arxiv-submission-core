"""Tests for :mod:`events.domain`."""

from unittest import TestCase, mock

from events.domain import event_factory, Agent


class TestEventFactory(TestCase):
    """Test for :func:`.event_factory`."""

    def test_event_factory_preserves_agent_type(self):
        """When loading agent data, preserves :prop:`.Agent.agent_type`."""
        event = event_factory('CreateSubmissionEvent',
                              creator={
                                'agent_type': 'UserAgent',
                                'native_id': 'foouser'
                              })
        self.assertEqual(event.creator.agent_type, 'UserAgent')
