"""Test submission examples and workflows at the API, with an in-memory DB."""

from unittest import TestCase, mock
import jwt
import json
import os
import jsonschema
import tempfile

from arxiv import status
from metadata.factory import create_web_app
from metadata.controllers.submission import ev

BASEPATH = os.path.join(os.path.split(os.path.abspath(__file__))[0], '..')
_, DB_PATH = tempfile.mkstemp(suffix='.db')


class TestSubmit(TestCase):
    """Test submission endpoint."""

    # @mock.patch('events.services.classic')
    def setUp(self):
        """Initialize the metadata service application."""
        SECRET = 'foo'
        os.environ['JWT_SECRET'] = SECRET
        os.environ['CLASSIC_DATABASE_URI'] = 'sqlite:///%s' % DB_PATH

        self.authorization = jwt.encode({
            'scope': ['submission:write', 'submission:read'],
            'user': {
                'user_id': 1234,
                'email': 'joe@bloggs.com'
            },
            'client': {
                'client_id': 5678
            }
        }, SECRET)
        self.headers = {'Authorization': self.authorization.decode('utf-8')}
        self.app = create_web_app()
        with self.app.app_context():
            from events.services import classic
            classic.create_all()

        self.client = self.app.test_client()

        self.resolver = jsonschema.RefResolver(
            'file://%s/' % os.path.join(BASEPATH, 'schema/resources'),
            None)

        _path = os.path.join(BASEPATH, 'schema/resources/submission.json')
        with open(_path) as f:
            self.schema = json.load(f)

    def test_submit_one_shot(self):
        """Client submits a complete submission record."""
        example = os.path.join(BASEPATH, 'examples/complete_submission.json')
        with open(example) as f:
            data = json.load(f)
        response = self.client.post('/', data=json.dumps(data),
                                    content_type='application/json',
                                    headers=self.headers)
        try:
            response_data = json.loads(response.data)
        except Exception as e:
            self.fail("Should return valid JSON")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED,
                         "Should return status 201 Created")
        self.assertIn("Location", response.headers,
                      "Should redirect to created submission resource")

        try:
            jsonschema.validate(response_data, self.schema,
                                resolver=self.resolver)
        except jsonschema.ValidationError as e:
            self.fail("Return content should match submission schema")

        # Verify that author metadata was preserved.
        rq_authors = data['metadata']['authors']
        re_authors = response_data['metadata']['authors']
        for rq_author, re_author in zip(rq_authors, re_authors):
            self.assertEqual(rq_author['forename'], re_author['forename'])
            self.assertEqual(rq_author['surname'], re_author['surname'])
            self.assertEqual(rq_author['email'], re_author['email'])
            if 'display' in rq_author:
                self.assertEqual(rq_author['display'], re_author['display'])
            else:
                self.assertGreater(len(re_author['display']), 0,
                                   "Should be set automatically")

    def test_alter_submission_before_finalization(self):
        """Client submits a partial record, and then updates it."""
        example = os.path.join(BASEPATH, 'examples/complete_submission.json')
        with open(example) as f:
            data = json.load(f)

        # Submission is not complete.
        del data['finalized']
        del data['metadata']['title']
        response = self.client.post('/', data=json.dumps(data),
                                    content_type='application/json',
                                    headers=self.headers)
        response_data = json.loads(response.data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED,
                         "Should return status 201 Created")
        sub_id = response_data['submission_id']
        self.assertFalse(response_data['finalized'],
                         "Should be unfinalized by default")

        # Client submits additional metadata.
        more = {"metadata": {"title": "The best title"}}
        response = self.client.post(f"/{sub_id}/", data=json.dumps(more),
                                    content_type='application/json',
                                    headers=self.headers)

        response_data = json.loads(response.data)
        self.assertEqual(response_data["metadata"]["title"],
                         more["metadata"]["title"],
                         "The submission should be updated with the new data")

    def test_alter_submission_after_finalization(self):
        """Client finalizes a submission, and then tries to updated it."""
        example = os.path.join(BASEPATH, 'examples/complete_submission.json')
        with open(example) as f:
            data = json.load(f)

        # Submission is complete and finalized.
        response = self.client.post('/', data=json.dumps(data),
                                    content_type='application/json',
                                    headers=self.headers)
        response_data = json.loads(response.data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED,
                         "Should return status 201 Created")
        sub_id = response_data['submission_id']
        self.assertTrue(response_data['finalized'], "Should be finalized")

        # Client submits additional metadata.
        more = {"metadata": {"title": "The best title"}}
        response = self.client.post(f"/{sub_id}/", data=json.dumps(more),
                                    content_type='application/json',
                                    headers=self.headers)
        response_data = json.loads(response.data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST,
                         "Should return 400 Bad Request")
        self.assertIn("reason", response_data,
                      "A reason for the rejected request should be provided")


class TestModerationScenarios(TestCase):
    """Before scheduling for publication, submissions undergo moderation."""

    def setUp(self):
        """Initialize the metadata service application."""
        # mock_classic.store_events.side_effect = lambda *a, **k: print('foo')
        SECRET = 'foo'
        os.environ['JWT_SECRET'] = SECRET
        os.environ['CLASSIC_DATABASE_URI'] = 'sqlite:///%s' % DB_PATH

        self.authorization = jwt.encode({
            'scope': ['submission:write', 'submission:read'],
            'user': {
                'user_id': 1234,
                'email': 'joe@bloggs.com'
            },
            'client': {
                'client_id': 5678
            }
        }, SECRET)
        self.app = create_web_app()
        with self.app.app_context():
            from events.services import classic
            classic.create_all()

        self.client = self.app.test_client()
        self.headers = {'Authorization': self.authorization.decode('utf-8')}

    def test_submission_placed_on_hold(self):
        """Before publication, a submission may be placed on hold."""
        # Client creates the submission.
        example = os.path.join(BASEPATH, 'examples/complete_submission.json')
        with open(example) as f:
            data = json.load(f)
        response = self.client.post('/', data=json.dumps(data),
                                    content_type='application/json',
                                    headers=self.headers)
        submission_id = json.loads(response.data)['submission_id']

        # Moderator, admin, or other agent places the submission on hold.
        with self.app.app_context():
            from events.services import classic
            session = classic.current_session()
            submission = session.query(classic.models.Submission) \
                .get(submission_id)
            submission.status = submission.ON_HOLD
            session.add(submission)
            session.commit()

        # Client gets submission state.
        response = self.client.get(f'/{submission_id}/', headers=self.headers)
        submission_data = json.loads(response.data)
        self.assertEqual(submission_data['status'], 'hold',
                         "Status should be `hold`")

    def test_sticky_status_is_set(self):
        """A sticky status is set during moderation."""
        # Client creates the submission.
        example = os.path.join(BASEPATH, 'examples/complete_submission.json')
        with open(example) as f:
            data = json.load(f)
        response = self.client.post('/', data=json.dumps(data),
                                    content_type='application/json',
                                    headers=self.headers)
        submission_id = json.loads(response.data)['submission_id']

        # Moderator, admin, or other agent places the submission on hold,
        #  and a sticky status is set.
        with self.app.app_context():
            from events.services import classic
            session = classic.current_session()
            submission = session.query(classic.models.Submission)\
                .get(submission_id)
            submission.status = submission.ON_HOLD
            submission.sticky_status = submission.ON_HOLD
            session.add(submission)
            session.commit()

        # Client gets submission state.
        response = self.client.get(f'/{submission_id}/', headers=self.headers)
        submission_data = json.loads(response.data)
        self.assertEqual(submission_data['status'], 'hold',
                         "Status should be `hold`")

        # Client withdraws the submission from the queue.
        response = self.client.post(f'/{submission_id}/',
                                    data=json.dumps({"finalized": False}),
                                    content_type='application/json',
                                    headers=self.headers)
        submission_data = json.loads(response.data)
        self.assertFalse(submission_data['finalized'],
                         "Should no longer be finalized")

        # Client gets submission state.
        response = self.client.get(f'/{submission_id}/', headers=self.headers)
        submission_data = json.loads(response.data)
        self.assertFalse(submission_data['finalized'],
                         "Should no longer be finalized")
        self.assertEqual(submission_data['status'], 'working',
                         "Status should be `working`")

        # Client finalizes the submission for moderation.
        response = self.client.post(f'/{submission_id}/',
                                    data=json.dumps({"finalized": True}),
                                    content_type='application/json',
                                    headers=self.headers)
        submission_data = json.loads(response.data)

        # Client gets submission state.
        response = self.client.get(f'/{submission_id}/', headers=self.headers)
        submission_data = json.loads(response.data)
        self.assertTrue(submission_data['finalized'], "Should be finalized")
        self.assertEqual(submission_data['status'], 'hold',
                         "Status should be `hold`, as sticky_status was set")
