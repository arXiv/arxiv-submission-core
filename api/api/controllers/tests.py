"""Tests for :mod:`api.controllers`."""

from unittest import TestCase, mock
from datetime import datetime
from werkzeug.exceptions import BadRequest, InternalServerError, NotFound

from arxiv import status
from events.domain import User, Submission
from events import CreateSubmissionEvent, UpdateMetadataEvent, SaveError, \
    InvalidEvent, NoSuchSubmission, SetPrimaryClassificationEvent
from api.controllers import submission


def preserve_exceptions_and_events(mock_events):
    """Add real exceptions back to the mock."""
    mock_events.SaveError = SaveError
    mock_events.InvalidEvent = InvalidEvent
    mock_events.NoSuchSubmission = NoSuchSubmission
    mock_events.UpdateMetadataEvent = UpdateMetadataEvent
    mock_events.CreateSubmissionEvent = CreateSubmissionEvent
    mock_events.SetPrimaryClassificationEvent = \
        SetPrimaryClassificationEvent


class TestCreateSubmission(TestCase):
    """Tests for :func:`.submission.create_submission`."""

    def setUp(self):
        """Create some fake request data."""
        self.user_data = {'user_id': 1234, 'email': 'foo@bar.baz'}
        self.client_data = {'client_id': 5678}
        self.token = 'asdf1234'
        self.headers = {}

    @mock.patch('api.controllers.submission.url_for')
    @mock.patch('api.controllers.submission.ev')
    def test_create_submission_with_valid_data(self, mock_events, url_for):
        """Create a submission with valid data."""
        preserve_exceptions_and_events(mock_events)
        url_for.return_value = '/foo/'
        user = User(1234, 'foo@bar.baz')
        mock_events.save.return_value = (
            Submission(creator=user, owner=user, created=datetime.now()),
            [CreateSubmissionEvent(creator=user)]
        )
        data = {
            'primary_classification': {
                'category': 'astro-ph'
            }
        }
        resp, stat, head = submission.create_submission(data, self.headers,
                                                        self.user_data,
                                                        self.client_data,
                                                        self.token)
        call_args, call_kwargs = mock_events.save.call_args

        self.assertIsInstance(call_args[0], CreateSubmissionEvent,
                              "Should pass a CreateSubmissionEvent first")
        self.assertIsInstance(call_args[1], SetPrimaryClassificationEvent,
                              "Should pass a SetPrimaryClassificationEvent")
        self.assertEqual(stat, status.HTTP_201_CREATED,
                         "Should return 201 Created when submission is"
                         " successfully created.")
        self.assertIn('Location', head, "Should include a Location header.")

    @mock.patch('api.controllers.submission.url_for')
    @mock.patch('api.controllers.submission.ev')
    def test_create_submission_with_invalid_data(self, mock_events, url_for):
        """Trying to create a submission with invalid data throws exception."""
        preserve_exceptions_and_events(mock_events)
        url_for.return_value = '/foo/'
        data = {
            'badkey': 'bizarre value',
        }
        with self.assertRaises(BadRequest):
            submission.create_submission(data, self.headers, self.user_data,
                                         self.client_data, self.token)

    @mock.patch('api.controllers.submission.url_for')
    @mock.patch('api.controllers.submission.ev')
    def test_create_submission_with_db_down(self, mock_events, url_for):
        """An internal server error is raised when the database is down."""
        url_for.return_value = '/foo/'
        mock_events.save.side_effect = SaveError
        preserve_exceptions_and_events(mock_events)
        data = {
            'primary_classification': {
                'category': 'astro-ph'
            }
        }
        with self.assertRaises(InternalServerError):
            submission.create_submission(data, self.headers, self.user_data,
                                         self.client_data, self.token)

    @mock.patch('api.controllers.submission.url_for')
    @mock.patch('api.controllers.submission.ev')
    def test_create_submission_with_invalid_event(self, mock_events, url_for):
        """An internal server error is raised on an invalid event."""
        url_for.return_value = '/foo/'
        mock_events.save.side_effect = InvalidEvent
        preserve_exceptions_and_events(mock_events)
        data = {
            'primary_classification': {
                'category': 'astro-ph'
            }
        }
        with self.assertRaises(InternalServerError):
            submission.create_submission(data, self.headers, self.user_data,
                                         self.client_data, self.token)


class TestUpdateSubmission(TestCase):
    """Tests for :func:`.submission.update_submission`."""

    def setUp(self):
        """Create some fake request data."""
        self.user_data = {'user_id': 1234, 'email': 'foo@bar.baz'}
        self.client_data = {'client_id': 5678}
        self.token = 'asdf1234'
        self.headers = {}

    @mock.patch('api.controllers.submission.url_for')
    @mock.patch('api.controllers.submission.ev')
    def test_update_submission_with_valid_data(self, mock_events, url_for):
        """Update a submission with valid data."""
        preserve_exceptions_and_events(mock_events)
        url_for.return_value = '/foo/'
        user = User(1234, 'foo@bar.baz')
        mock_events.save.return_value = (
            Submission(creator=user, owner=user, created=datetime.now()),
            [CreateSubmissionEvent(creator=user),
             UpdateMetadataEvent(creator=user,
                                 metadata=[('title', 'foo title')])]
        )
        data = {
            'metadata': {
                'title': 'foo title'
             }
        }
        resp, stat, head = submission.update_submission(data, self.headers,
                                                        self.user_data,
                                                        self.client_data,
                                                        self.token, 1)
        self.assertEqual(stat, status.HTTP_200_OK,
                         "Should return 200 OK when submission is"
                         " successfully updated.")
        self.assertIn('Location', head, "Should include a Location header.")
        call_args, call_kwargs = mock_events.save.call_args

        self.assertIsInstance(call_args[0], UpdateMetadataEvent,
                              "Should pass an UpdateMetadataEvent")

    @mock.patch('api.controllers.submission.url_for')
    @mock.patch('api.controllers.submission.ev')
    def test_update_nonexistant_submission(self, mock_events, url_for):
        """Trying to update a nonexistant submission throws exception."""
        preserve_exceptions_and_events(mock_events)
        mock_events.save.side_effect = NoSuchSubmission
        url_for.return_value = '/foo/'
        data = {
            'metadata': {
                'title': 'foo title'
             }
        }
        with self.assertRaises(NotFound):
            submission.update_submission(data, self.headers, self.user_data,
                                         self.client_data, self.token, 1)

    @mock.patch('api.controllers.submission.url_for')
    @mock.patch('api.controllers.submission.ev')
    def test_update_submission_with_invalid_data(self, mock_events, url_for):
        """Trying to update a submission with invalid data throws exception."""
        preserve_exceptions_and_events(mock_events)
        url_for.return_value = '/foo/'
        data = {
            'badkey': 'bizarre value',
        }
        with self.assertRaises(BadRequest):
            submission.update_submission(data, self.headers, self.user_data,
                                         self.client_data, self.token, 1)

    @mock.patch('api.controllers.submission.url_for')
    @mock.patch('api.controllers.submission.ev')
    def test_update_submission_with_db_down(self, mock_events, url_for):
        """An internal server error is raised when the database is down."""
        url_for.return_value = '/foo/'
        mock_events.save.side_effect = SaveError
        preserve_exceptions_and_events(mock_events)
        data = {
            'primary_classification': {
                'category': 'astro-ph'
            }
        }
        with self.assertRaises(InternalServerError):
            submission.update_submission(data, self.headers, self.user_data,
                                         self.client_data, self.token, 1)

    @mock.patch('api.controllers.submission.url_for')
    @mock.patch('api.controllers.submission.ev')
    def test_update_submission_with_invalid_event(self, mock_events, url_for):
        """An internal server error is raised on an invalid event."""
        url_for.return_value = '/foo/'
        preserve_exceptions_and_events(mock_events)
        mock_events.save.side_effect = InvalidEvent
        data = {
            'primary_classification': {
                'category': 'astro-ph'
            }
        }
        with self.assertRaises(InternalServerError):
            submission.update_submission(data, self.headers, self.user_data,
                                         self.client_data, self.token, 1)


class TestGetSubmission(TestCase):
    """Tests for :func:`.submission.get_submission`."""
