"""
Tests for :mod:`api.services.events` service.

.. todo::

   Build this out with each of the methods exposed by the submission event
   controller service.

"""

from unittest import TestCase, mock
import os
from datetime import datetime

import jwt
import requests

from api.services import events
from api.domain import Submission


JWT_SECRET = os.environ.get('JWT_SECRET', 'foo')


def raise_connection_failure(*args, **kwargs):
    raise requests.exceptions.ConnectionError('Whoops!')


def raise_bad_request(*args, **kwargs):
    raise events.BadRequest('Whoops!')


class TestCreateSubmission(TestCase):
    """Create a new submission via the submission event service."""

    def setUp(self):
        """Create a JWT for the request."""
        self.claims = {
            'client': 'fooclient',
            'user': 'foouser',
            'scope': ['submission:write', 'submission:read']
        }
        self.token = jwt.encode(self.claims, 'foo')

    @mock.patch('api.services.events.requests.Session')
    def test_create_with_valid_data(self, mock_session):
        """A :class:`.Submission` instance is returned."""
        mock_response = mock.MagicMock(
            status_code=200,
            json=mock.MagicMock(
                return_value={
                    'submission_id': '1',
                    'created': datetime.now(),
                    'creator': {
                        'agent_type': 'UserAgent',
                        'native_id': 'foouser'
                    },
                    'proxy': {
                        'agent_type': 'Client',
                        'native_id': 'fooclient'
                    }
                }
            )
        )
        mock_post = mock.MagicMock(return_value=mock_response)
        mock_session_instance = mock.MagicMock()
        type(mock_session_instance).post = mock_post
        mock_session.return_value = mock_session_instance

        submission = events.create_submission(self.token)

        args, kwargs = mock_post.call_args

        # Should call the create_submission endpoint.
        self.assertEqual(args[0], '/create_submission/')
        self.assertIn('Authorization', kwargs['headers'])

        self.assertIsInstance(submission, Submission)
        self.assertTrue(submission.submission_id is not None)

    @mock.patch('api.services.events.requests.Session')
    def test_create_connection_fails(self, mock_session):
        """An IOError is raised when the event service connection fails."""
        mock_post = mock.MagicMock(side_effect=raise_connection_failure)
        mock_session_instance = mock.MagicMock()
        type(mock_session_instance).post = mock_post
        mock_session.return_value = mock_session_instance

        with self.assertRaises(IOError):
            events.create_submission(self.token)

    @mock.patch('api.services.events.requests.Session')
    def test_create_with_invalid_data(self, mock_session):
        """An BadRequest is raised when the event service connection fails."""
        mock_post = mock.MagicMock(side_effect=raise_bad_request)
        mock_session_instance = mock.MagicMock()
        type(mock_session_instance).post = mock_post
        mock_session.return_value = mock_session_instance

        with self.assertRaises(events.BadRequest):
            events.create_submission(self.token)


class TestUpdateMetadata(TestCase):
    """Update metadata for an existing submission."""

    def setUp(self):
        """Create a JWT for the request."""
        self.claims = {
            'client': 'fooclient',
            'user': 'foouser',
            'scope': ['submission:write', 'submission:read']
        }
        self.token = jwt.encode(self.claims, 'foo')

    @mock.patch('api.services.events.requests.Session')
    def test_create_with_valid_data(self, mock_session):
        """A :class:`.Submission` instance is returned."""
        mock_response = mock.MagicMock(
            status_code=200,
            json=mock.MagicMock(
                return_value={
                    'submission_id': '1',
                    'created': datetime.now(),
                    'creator': {
                        'agent_type': 'UserAgent',
                        'native_id': 'foouser'
                    },
                    'proxy': {
                        'agent_type': 'Client',
                        'native_id': 'fooclient'
                    },
                    'metadata': {
                        'title': 'foo'
                    }
                }
            )
        )
        mock_post = mock.MagicMock(return_value=mock_response)
        mock_session_instance = mock.MagicMock()
        type(mock_session_instance).post = mock_post
        mock_session.return_value = mock_session_instance

        metadata = [('title', 'foo')]
        submission = events.update_metadata('1', metadata, self.token)

        args, kwargs = mock_post.call_args

        # Should call the update_metadata endpoint on the submission instance.
        self.assertEqual(args[0], '/submission/1/update_metadata/')
        self.assertIn('Authorization', kwargs['headers'])

        self.assertIsInstance(submission, Submission)
        self.assertTrue(submission.submission_id is not None)
        self.assertEqual(submission.metadata.title, 'foo')
