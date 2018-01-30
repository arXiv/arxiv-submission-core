"""
Test the events API.

These events test the routes and controllers against the JSON Schema. Methods
provided by the :mod:`events.services.database` service are mocked.
"""

from unittest import TestCase, mock
import json
import os
from datetime import datetime

import jwt

from arxiv import status
from arxiv.util import schema
from events.factory import create_web_app

from events.domain import Submission, agent_factory, event_factory

JWT_SECRET = os.environ.get('JWT_SECRET', 'foo')

JWT_WRITE = jwt.encode({
        'client': 'fooclient',
        'user': 'foouser',
        'scope': ['submission:write', 'submission:read']
    }, 'foo')

JWT_READ = jwt.encode({
        'client': 'fooclient',
        'user': 'foouser',
        'scope': ['submission:read']
    }, 'foo')


class TestRegisterSubmissionEvent(TestCase):
    """Register a new event at /events/submission/{sub_id}/events/."""

    def setUp(self):
        """Initialize the application and get a test client."""
        self.app = create_web_app()
        self.client = self.app.test_client()

    def test_register_event_requires_write_scope(self):
        """If submission:write not in auth scope a 403 is returned."""
        valid_payload = json.dumps({
            'event_type': 'UpdateMetadataEvent',
            'metadata': [('title', 'foo title')]
        })
        response = self.client.post('/events/submission/1/update_metadata/',
                                    data=valid_payload,
                                    content_type='application/json',
                                    headers={'Authorization': JWT_READ})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @mock.patch('events.controllers.database')
    def test_register_event(self, mock_db):
        """Valid event results in a 201 Created response."""
        def _store_events(*events, submission):
            submission.submission_id = 1
            return submission
        creator = agent_factory('UserAgent', 'foo-user')
        mock_db.store_events = mock.MagicMock(side_effect=_store_events)
        mock_db.get_rules_for_submission = mock.MagicMock(return_value=[])
        mock_db.get_events_for_submission = mock.MagicMock(
            return_value=[event_factory(
                'CreateSubmissionEvent',
                creator=creator,
                created=datetime.now()
            )]
        )

        mock_db.get_submission_agents = mock.MagicMock(
            return_value={
                'creator': agent_factory('UserAgent', 'foouser'),
                'owner': agent_factory('UserAgent', 'foouser'),
                'proxy': agent_factory('Client', 'fooclient'),
                'delegates': []
            }
        )

        valid_payload = json.dumps({
            'event_type': 'UpdateMetadataEvent',
            'metadata': [('title', 'foo title')]

        })
        response = self.client.post('/events/submission/1/update_metadata/',
                                    data=valid_payload,
                                    content_type='application/json',
                                    headers={'Authorization': JWT_WRITE})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        validate = schema.load('schema/resources/submission.json')
        try:
            validate(json.loads(response.data))
        except schema.ValidationError as e:
            self.fail('Invalid response: %s' % str(e).split('\n')[0])

    @mock.patch('events.controllers.database')
    def test_register_event_user_not_owner_nor_delegate(self, mock_db):
        """User must be owner or a delgate of submission to create event."""
        mock_db.get_submission_agents = mock.MagicMock(
            return_value={
                'creator': agent_factory('UserAgent', 'foouser'),
                'owner': agent_factory('UserAgent', 'altuser'),
                'proxy': agent_factory('Client', 'fooclient'),
                'delegates': []
            }
        )
        token = jwt.encode({
                'client': 'fooclient',
                'user': 'otheruser',
                'scope': ['submission:write', 'submission:read']
            }, 'foo')
        valid_payload = json.dumps({
            'event_type': 'UpdateMetadataEvent',
            'metadata': [('title', 'foo title')]

        })
        response = self.client.post('/events/submission/1/update_metadata/',
                                    data=valid_payload,
                                    content_type='application/json',
                                    headers={'Authorization': token})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @mock.patch('events.controllers.database')
    def test_register_event_user_missing_client_not_proxy(self, mock_db):
        """If user not set, client must be the proxy."""
        mock_db.get_submission_agents = mock.MagicMock(
            return_value={
                'creator': agent_factory('UserAgent', 'foouser'),
                'owner': agent_factory('UserAgent', 'altuser'),
                'proxy': agent_factory('Client', 'fooclient'),
                'delegates': []
            }
        )
        token = jwt.encode({
                'client': 'altclient',
                'scope': ['submission:write', 'submission:read']
            }, 'foo')
        valid_payload = json.dumps({
            'event_type': 'UpdateMetadataEvent',
            'metadata': [('title', 'foo title')]
        })
        response = self.client.post('/events/submission/1/update_metadata/',
                                    data=valid_payload,
                                    content_type='application/json',
                                    headers={'Authorization': token})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @mock.patch('events.controllers.database')
    def test_register_event_client_is_system(self, mock_db):
        """System agent with valid scope may register event."""
        # TODO: implement this test.

    @mock.patch('events.controllers.database')
    def test_register_event_user_present(self, mock_db):
        """User must be present if client is not owner."""
        # TODO: implement this test.


class TestRegisterEvent(TestCase):
    """Register a new event at /events/event/ (``registerEvent``)."""

    def setUp(self):
        """Initialize the application and get a test client."""
        self.app = create_web_app()
        self.client = self.app.test_client()

    def test_register_event_requires_write_scope(self):
        """If submission:write not in auth scope a 403 is returned."""
        valid_payload = json.dumps({
            'event_type': 'CreateSubmissionEvent'
        })
        response = self.client.post('/events/create_submission/',
                                    data=valid_payload,
                                    content_type='application/json',
                                    headers={'Authorization': JWT_READ})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @mock.patch('events.controllers.database')
    def test_register_event(self, mock_db):
        """Valid event results in a 201 Created response."""
        def _store_events(*events, submission):
            submission.submission_id = 1
            return submission
        mock_db.store_events = mock.MagicMock(side_effect=_store_events)
        mock_db.get_rules_for_submission = mock.MagicMock(return_value=[])

        mock_db.get_submission_agents = mock.MagicMock(
            return_value={
                'creator': agent_factory('UserAgent', 'foouser'),
                'owner': agent_factory('UserAgent', 'foouser'),
                'proxy': agent_factory('Client', 'fooclient'),
                'delegates': []
            }
        )

        valid_payload = json.dumps({
            'event_type': 'CreateSubmissionEvent'
        })
        response = self.client.post('/events/create_submission/',
                                    data=valid_payload,
                                    content_type='application/json',
                                    headers={'Authorization': JWT_WRITE})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        validate = schema.load('schema/resources/submission.json')
        try:
            validate(json.loads(response.data))
        except schema.ValidationError as e:
            self.fail('Invalid response: %s' % str(e).split('\n')[0])


class TestRetrieveEvents(TestCase):
    """
    Retrieve all submission event at /events/submission/1/events/.

    Operation: ``getSubmissionEvents``
    """

    @mock.patch('events.factory.database')
    def setUp(self, mock_db):
        """Initialize the application and get a test client."""
        self.app = create_web_app()
        self.client = self.app.test_client()

    @mock.patch('events.controllers.database')
    def test_retrieve_events(self, mock_db):
        """Requesting events for a submission that exists returns 200."""
        events = [
            event_factory(
                'CreateSubmissionEvent',
                creator=agent_factory('UserAgent', 'foouser'),
                proxy=agent_factory('Client', 'fooclient'),
                created=datetime.now()
            ),
            event_factory(
                'UpdateMetadataEvent',
                submission_id=1,
                creator=agent_factory('UserAgent', 'foouser'),
                proxy=agent_factory('Client', 'fooclient'),
                metadata=[
                    ('title', 'foo title')
                ]
            )
        ]
        mock_db.get_events_for_submission = mock.MagicMock(return_value=events)
        mock_db.get_submission_agents = mock.MagicMock(
            return_value={
                'creator': agent_factory('UserAgent', 'foouser'),
                'owner': agent_factory('UserAgent', 'foouser'),
                'proxy': agent_factory('Client', 'fooclient'),
                'delegates': []
            }
        )

        token = jwt.encode({
                'client': 'fooclient',
                'user': 'foouser',
                'scope': ['submission:read']
            }, 'foo')

        response = self.client.get('/events/submission/1/events/',
                                   content_type='application/json',
                                   headers={'Authorization': token})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        validate = schema.load('schema/resources/event.json')
        for event in json.loads(response.data)['events']:
            try:
                validate(event)
            except schema.ValidationError as e:
                self.fail('Invalid response: %s' % str(e).split('\n')[0])

    @mock.patch('events.controllers.database')
    def test_retrieve_nonexistant_event(self, mock_db):
        """Requesting events for submission that doesn't exist returns 404."""
        mock_db.get_events_for_submission = mock.MagicMock(return_value=[])
        mock_db.get_submission_agents = mock.MagicMock(
            return_value={
                'creator': agent_factory('UserAgent', 'foouser'),
                'owner': agent_factory('UserAgent', 'foouser'),
                'proxy': agent_factory('Client', 'fooclient'),
                'delegates': []
            }
        )

        token = jwt.encode({
                'client': 'fooclient',
                'user': 'foouser',
                'scope': ['submission:read']
            }, 'foo')

        response = self.client.get('/events/submission/1/events/',
                                   content_type='application/json',
                                   headers={'Authorization': token})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @mock.patch('events.controllers.database')
    def test_retrieve_insufficient_scope(self, mock_db):
        """Request without ``submission:read`` scope returns 403."""
        response = self.client.get('/events/submission/1/events/',
                                   content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @mock.patch('events.controllers.database')
    def test_retrieve_user_not_owner_nor_delegate(self, mock_db):
        """If the user is not the owner or a delegate, returns 403."""
        mock_db.get_submission_agents = mock.MagicMock(
            return_value={
                'creator': agent_factory('UserAgent', 'foouser'),
                'owner': agent_factory('UserAgent', 'foouser'),
                'proxy': agent_factory('Client', 'fooclient'),
                'delegates': []
            }
        )
        token = jwt.encode({
                'client': 'fooclient',
                'user': 'altuser',
                'scope': ['submission:read']
            }, 'foo')
        response = self.client.get('/events/submission/1/events/',
                                   content_type='application/json',
                                   headers={'Authorization': token})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @mock.patch('events.controllers.database')
    def test_retrieve_no_user_client_is_owner(self, mock_db):
        """If there is no user, and the client is the owner, returns 200."""
        events = [
            event_factory(
                'CreateSubmissionEvent',
                creator=agent_factory('UserAgent', 'foouser'),
                proxy=agent_factory('Client', 'fooclient'),
                created=datetime.now()
            ),
            event_factory(
                'UpdateMetadataEvent',
                submission_id=1,
                creator=agent_factory('UserAgent', 'foouser'),
                proxy=agent_factory('Client', 'fooclient'),
                metadata=[
                    ('title', 'foo title')
                ]
            )
        ]
        mock_db.get_events_for_submission = mock.MagicMock(return_value=events)
        mock_db.get_submission_agents = mock.MagicMock(
            return_value={
                'creator': agent_factory('UserAgent', 'foouser'),
                'owner': agent_factory('Client', 'fooclient'),
                'proxy': agent_factory('Client', 'fooclient'),
                'delegates': []
            }
        )
        token = jwt.encode({
                'client': 'fooclient',
                'scope': ['submission:read']
            }, 'foo')
        response = self.client.get('/events/submission/1/events/',
                                   content_type='application/json',
                                   headers={'Authorization': token})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
