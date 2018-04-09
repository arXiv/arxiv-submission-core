# TODO: rewrite with mocks, due to refactor.

# from unittest import TestCase, mock
# import os
# import json
# import jwt
# from flask import Flask
# from api.factory import create_web_app
# from api.services import database
# from api import schema
#
#
# TEST_DB_URI = os.environ.get(
#     'TEST_DATABASE_URI',
#     'postgres://arxiv-submit:arxiv-submit@localhost:5432/arxiv-submit-test'
# )
# JWT_SECRET = os.environ.get('JWT_SECRET', 'foo')
#
# JWT = jwt.encode({
#         'client': 'fooclient',
#         'user': 'foouser',
#         'scope': ['submission:write', 'submission:read']
#     }, 'foo')
#
#
# class TestAPISubmission(TestCase):
#     def setUp(self) -> None:
#         """Initialize the Flask application, and get a client for testing."""
#         self.app = create_web_app()
#         self.app.config['SQLALCHEMY_DATABASE_URI'] = TEST_DB_URI
#         self.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
#         self.client = self.app.test_client()
#         database.db.init_app(self.app)
#         self.app.app_context().push()
#         database.db.create_all()
#
#     def tearDown(self):
#         """Clear our the test database."""
#         database.db.session.commit()
#         database.db.drop_all()
#         database.util._db_agent_cache = {}
#
#     @mock.patch('api.services.events')
#     def test_submit(self, mock_events):
#         """Create a new submission via the API."""
#         payload = {
#             'primary_classification': {
#                 'category': 'physics.data-an'
#             },
#             'metadata': {
#                 'title': 'Foo title',
#                 'abstract': 'Here we prove that FOO=NP',
#                 'author': [
#                     {
#                         'forename': 'Joe',
#                         'surname': 'Bloggs',
#                         'initials': 'J',
#                         'affiliation': 'Oklahoma State University',
#                         'email': 'joe@blo.ggs',
#                         'identifier': 'orcid:1234-5678-9012-3456'
#                     },
#                     {
#                         'forename': 'Jane',
#                         'surname': 'Doe',
#                         'affiliation': 'Northern Arizona University',
#                         'email': 'jdoe@witnessprotection.gov',
#                         'identifier': 'https://arxiv.org/author/012345'
#                     }
#                 ]
#             },
#             'submitter_is_author': True
#         }
#
#         response = self.client.post('/submit/', data=json.dumps(payload),
#                                     content_type='application/json',
#                                     headers={'Authorization': JWT})
#
#         self.assertEqual(response.status_code, 202,
#                          'Request failed: %s' % response.data)
#         self.assertEqual(response.headers['Content-Type'], 'application/json')
#         try:
#             response_data = json.loads(response.data)
#         except json.decoder.JSONDecodeError:
#             self.fail('Did not return valid JSON: %s' % response.data)
#
#         validate = schema.load('api/submission.json')
#         try:
#             validate(response_data)
#         except schema.ValidationError as e:
#             self.fail('Response data is invalid: %s' % e)
#
#     # def test_get_submission(self):
#     #     """Get the current state of the submission."""
#     #     payload = {
#     #         'primary_classification': {
#     #             'category': 'physics.data-an'
#     #         },
#     #         'metadata': {
#     #             'title': 'Foo title',
#     #             'abstract': 'Here we prove that FOO=NP',
#     #             'author': [
#     #                 {
#     #                     'forename': 'Joe',
#     #                     'surname': 'Bloggs',
#     #                     'initials': 'J',
#     #                     'affiliation': 'Oklahoma State University',
#     #                     'email': 'joe@blo.ggs',
#     #                     'identifier': 'orcid:1234-5678-9012-3456'
#     #                 },
#     #                 {
#     #                     'forename': 'Jane',
#     #                     'surname': 'Doe',
#     #                     'affiliation': 'Northern Arizona University',
#     #                     'email': 'jdoe@witnessprotection.gov',
#     #                     'identifier': 'https://arxiv.org/author/012345'
#     #                 }
#     #             ]
#     #         },
#     #         'submitter_is_author': True
#     #     }
#     #
#     #     response = self.client.post('/submit/', data=json.dumps(payload),
#     #                                 content_type='application/json',
#     #                                 headers={'Authorization': JWT})
#     #     try:
#     #         response_data = json.loads(response.data)
#     #     except json.decoder.JSONDecodeError:
#     #         self.fail('Did not return valid JSON: %s' % response.data)
#     #
#     #     submission_id = response_data['submission_id']
#     #     get_response = self.client.get('/submit/%s/' % submission_id,
#     #                                    headers={'Authorization': JWT})
#     #     self.assertEqual(get_response.status_code, 200,
#     #                      'Request failed: %s' % get_response.data)
#     #     self.assertEqual(get_response.headers['Content-Type'],
#     #                      'application/json')
#     #     try:
#     #         get_response_data = json.loads(get_response.data)
#     #     except json.decoder.JSONDecodeError:
#     #         self.fail('Did not return valid JSON: %s' % get_response.data)
#     #
#     #     validate = schema.load('api/submission.json')
#     #     try:
#     #         validate(get_response_data)
#     #     except schema.ValidationError as e:
#     #         self.fail('Response data is invalid: %s' % e)
#     #
#     # def test_get_submission_history(self):
#     #     """Get the history for a submission."""
#     #     payload = {
#     #         'primary_classification': {
#     #             'category': 'physics.data-an'
#     #         },
#     #         'metadata': {
#     #             'title': 'Foo title',
#     #             'abstract': 'Here we prove that FOO=NP',
#     #             'author': [
#     #                 {
#     #                     'forename': 'Joe',
#     #                     'surname': 'Bloggs',
#     #                     'initials': 'J',
#     #                     'affiliation': 'Oklahoma State University',
#     #                     'email': 'joe@blo.ggs',
#     #                     'identifier': 'orcid:1234-5678-9012-3456'
#     #                 },
#     #                 {
#     #                     'forename': 'Jane',
#     #                     'surname': 'Doe',
#     #                     'affiliation': 'Northern Arizona University',
#     #                     'email': 'jdoe@witnessprotection.gov',
#     #                     'identifier': 'https://arxiv.org/author/012345'
#     #                 }
#     #             ]
#     #         },
#     #         'submitter_is_author': True
#     #     }
#     #
#     #     response = self.client.post('/submit/', data=json.dumps(payload),
#     #                                 content_type='application/json',
#     #                                 headers={'Authorization': JWT})
#     #     response_data = json.loads(response.data)
#     #     submission_id = response_data['submission_id']
#     #     log_response = self.client.get('/submit/%s/history/' % submission_id,
#     #                                    headers={'Authorization': JWT})
#     #     self.assertEqual(log_response.status_code, 200,
#     #                      'Request failed: %s' % log_response.data)
#     #     self.assertEqual(log_response.headers['Content-Type'],
#     #                      'application/json')
#     #     try:
#     #         log_response_data = json.loads(log_response.data)
#     #     except json.decoder.JSONDecodeError:
#     #         self.fail('Did not return valid JSON: %s' % log_response.data)
#     #
#     #     validate = schema.load('api/log.json')
#     #     try:
#     #         validate(log_response_data)
#     #     except schema.ValidationError as e:
#     #         self.fail('Response data is invalid: %s' % e)
#     #
#     #     # Should result in four events:
#     #     # 1. Create
#     #     # 2. Update metadata
#     #     # 3. Set primary_classification
#     #     # 4. Set submitter_is_author
#     #     self.assertEqual(len(log_response_data['events']), 4)
#     #
#     #     update_payload = {
#     #         'secondary_classification': [
#     #             {
#     #                 'category': 'hep-th'
#     #             }
#     #         ]
#     #     }
#     #     response = self.client.post('/submit/%s/' % submission_id,
#     #                                 data=json.dumps(update_payload),
#     #                                 content_type='application/json',
#     #                                 headers={'Authorization': JWT})
#     #     self.assertEqual(response.status_code, 202)
#     #
#     #     log_response = self.client.get('/submit/%s/history/' % submission_id,
#     #                                    headers={'Authorization': JWT})
#     #     try:
#     #         log_response_data = json.loads(log_response.data)
#     #     except json.decoder.JSONDecodeError:
#     #         self.fail('Did not return valid JSON: %s' % log_response.data)
#     #
#     #     # We should now have a fifth event, update of secondary metadata.
#     #     self.assertEqual(len(log_response_data['events']), 5)
