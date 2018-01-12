from unittest import TestCase, mock

from pyld import jsonld
from pyld.jsonld import JsonLdError

from submit.controllers import submission
from submit import status
from submit.domain.submission import Submission
from submit.domain.event import *


class TestCreateSubmission(TestCase):
    """Tests for :func:`.submission.create_submission`."""

    def test_add_submission_invalid_body(self):
        """:func:`.submission.create_submission` expects a valid body."""
        body = {
            'metadata': {
                'author': [
                    {
                        "name": 'Foo author',
                        "email": 'Foo email',
                        "identifier": 'http://arxiv.org/author/foo'
                    }
                ],
                'submitterIsAuthor': True,
                'submitterAcceptsPolicy': True,
                'license': "http://creativecommons.org/licenses/by-sa/4.0/",
                "primary_classification": [
                    {
                        "group": 'physics',
                        "archive": 'physics',
                        "category": "astro-ph"
                    }
                ]
            }
        }
        extra = {'user': 'foo_user123'}
        response = submission.create_submission(body, {}, {}, **extra)
        response_body, code, head = response
        self.assertEqual(code, status.HTTP_400_BAD_REQUEST)

    @mock.patch('submit.controllers.submission.url_for')
    @mock.patch('submit.controllers.submission.eventBus')
    def test_add_submission_valid_body(self, mock_eventBus, mock_url_for):
        """:func:`.submission.create_submission` creates submission events."""
        mock_eventBus.emit.return_value = Submission(submission_id=1), []
        mock_url_for.return_value = 'https://foo'
        body = {
            'metadata': {
                'title': 'Foo title',
                'abstract': 'The abstract abstract',
                'author': [
                    {
                        "name": 'Foo author',
                        "email": 'Foo email',
                        "identifier": 'http://arxiv.org/author/foo'
                    }
                ],
                "doi": "doi:10.00234/foo/bar"
            },
            'submitterIsAuthor': True,
            'submitterAcceptsPolicy': True,
            'license': "http://creativecommons.org/licenses/by-sa/4.0/",
            "primary_classification": {
                "group": 'physics',
                "archive": 'physics',
                "category": "astro-ph"
            }
        }
        extra = {'archive': 'physics', 'user': 'foo_user123'}
        response = submission.create_submission(body, {}, {}, **extra)
        response_body, code, headers = response
        self.assertEqual(code, status.HTTP_202_ACCEPTED)
        self.assertIn('Location', headers)

        event_types = [type(e) for e in mock_eventBus.emit.call_args[0]]
        self.assertIn(CreateSubmissionEvent, event_types)
        self.assertIn(AssertAuthorshipEvent, event_types)
        self.assertIn(SelectLicenseEvent, event_types)
        self.assertIn(AcceptArXivPolicyEvent, event_types)
        self.assertIn(SetPrimaryClassificationEvent, event_types)
        self.assertIn(UpdateMetadataEvent, event_types)

    def test_add_submission_no_creator(self):
        """:func:`.submission.create_submission` expects a valid creator."""
        body = {
            'metadata': {
                'title': 'Foo title',
                'abstract': 'The abstract abstract',
                'author': [
                    {
                        "name": 'Foo author',
                        "email": 'Foo email',
                        "identifier": 'http://arxiv.org/author/foo'
                    }
                ],
                "doi": "doi:10.00234/foo/bar"
            },
            'submitterIsAuthor': True,
            'submitterAcceptsPolicy': True,
            'license': "http://creativecommons.org/licenses/by-sa/4.0/",
            "primary_classification": {
                "group": 'physics',
                "archive": 'physics',
                "category": "astro-ph"
            }
        }
        extra = {'archive': 'physics', 'user': None}
        response = submission.create_submission(body, {}, {}, **extra)
        _, code, head = response
        self.assertEqual(response, submission.NO_USER_OR_CLIENT)
        self.assertEqual(code, status.HTTP_400_BAD_REQUEST)
