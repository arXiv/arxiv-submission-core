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

    def test_submit_one_shot(self):
        """Client submits a complete submission record."""
        with open(os.path.join(BASEPATH, 'examples/complete_submission.json')) as f:
            data = json.load(f)
        response = self.client.post(
            '/submission',
            data=json.dumps(data),
            content_type='application/json',
            headers={
                'Authorization': self.authorization.decode('utf-8')
            }
        )
        try:
            response_data = json.loads(response.data)
        except Exception as e:
            self.fail("Should return valid JSON")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED,
                         "Should return status 201 Created")
        self.assertIn("Location", response.headers,
                      "Should redirect to created submission resource")


        with open(os.path.join(BASEPATH, 'schema/resources/submission.json')) as f:
            schema = json.load(f)
        try:
            resolver = jsonschema.RefResolver(
                'file://%s/' % os.path.join(BASEPATH, 'schema/resources'),
                None)
            jsonschema.validate(response_data, schema, resolver=resolver)
        except jsonschema.ValidationError as e:
            self.fail("Return content should match submission schema")
