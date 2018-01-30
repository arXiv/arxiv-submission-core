# from unittest import TestCase, mock
# from api.domain.event import Event
# from submit.exceptions import ValidationError
# from api import events


# class TestApplyEvent(TestCase):
#     @mock.patch('submit.events.database')
#     def test_invalid_event(self, mock_database):
#         """A ValidationError is allowed to propagate."""
#         fooEvent = mock.MagicMock(
#             validate=mock.MagicMock(side_effect=ValidationError)
#         )
#
#         with self.assertRaises(ValidationError):
#             events.apply_event(fooEvent)
#
#         self.assertEqual(mock_database.create_event.call_count, 0,
#                          "database service should not be called.")
#
#     @mock.patch('submit.events.database')
#     def test_valid_event(self, mock_database):
#         fooEvent = mock.MagicMock()
#         events.apply_event(fooEvent)
#         self.assertEqual(mock_database.create_event.call_count, 1,
#                          "database entry for event is created")
#
#     @mock.patch('submit.events.database')
#     def test_callback_is_called_on_event_type(self, mock_database):
#         """Callbacks registered with :func:`.events.listen_for` are called."""
#         callback = mock.MagicMock()
#         events.listen_for('FooEvent', callback=callback)
#         fooEvent = mock.MagicMock(event_type='FooEvent')
#         events.apply_event(fooEvent)
#         self.assertEqual(callback.call_count, 1)
#
#     @mock.patch('submit.events.database')
#     def test_callback_is_called_on_event_type(self, mock_database):
#         """Callbacks registered with :func:`.events.listen_for` are called."""
#         callback = mock.MagicMock()
#         events.listen_for('FooEvent', callback=callback)
#         fooEvent = mock.MagicMock(event_type='FooEvent')
#         events.apply_event(fooEvent)
#         self.assertEqual(callback.call_count, 1)
