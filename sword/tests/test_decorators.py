# import warnings
# import unittest
# from unittest import mock
# import sword
#
#
# class TestRequestDecorator(unittest.TestCase):
#     """:func:`sword.request` enforces request characteristics."""
#
#     def test_request_generates_a_decorator(self):
#         """:func:`sword.request` yields a decorator."""
#         decorator = sword.request()
#         self.assertTrue(hasattr(decorator, '__call__'),
#                         "A callable object is returned")
#
#         mock_func = mock.MagicMock()
#         wrapped = decorator(mock_func)
#         self.assertTrue(hasattr(wrapped, '__call__'),
#                         "Decorator returns a callable object.")
#         wrapped(None, {}, {})
#         self.assertEqual(mock_func.call_count, 1,
#                          "Decorator decorates the passed function.")
#
#     def test_header_is_enforced(self):
#         """A header tagged as MUST must (ha) be present in the request."""
#         mock_func = mock.MagicMock(return_value=({}, sword.OK, {}))
#         deco = sword.request(must=['Authorization'])
#         wrapped = deco(mock_func)
#         with self.assertRaises(sword.InvalidRequest):
#             wrapped(None, {}, {})
#
#         self.assertEqual(wrapped.request['must'], ['Authorization'])
#
#         mock_func = mock.MagicMock(return_value=({}, sword.OK, {}))
#         deco = sword.request(must=['Authorization'])
#         wrapped = deco(mock_func)
#         try:
#             wrapped(None, {}, {'Authorization': 'foo'})
#         except Exception as e:
#             self.fail(e)
#
#     def test_missing_should_header_raises_warning(self):
#         """Header flagged as SHOULD results in warning if not found."""
#         mock_func = mock.MagicMock(return_value=({}, sword.OK, {}))
#         deco = sword.request(should=['Authorization'])
#         wrapped = deco(mock_func)
#         with self.assertWarns(RuntimeWarning):
#             wrapped(None, {}, {})
#
#
# class TestResponseDecorator(unittest.TestCase):
#     """:func:`sword.response` enforces response characteristics."""
#
#     def test_response_generates_a_decorator(self):
#         """:func:`sword.response` yields a decorator."""
#         decorator = sword.response(success=[200])
#         self.assertTrue(hasattr(decorator, '__call__'),
#                         "A callable object is returned")
#
#         mock_func = mock.MagicMock(return_value=({}, 200, {}))
#         wrapped = decorator(mock_func)
#         self.assertTrue(hasattr(wrapped, '__call__'),
#                         "Decorator returns a callable object.")
#         wrapped(None, {}, {})
#         self.assertEqual(mock_func.call_count, 1,
#                          "Decorator decorates the passed function.")
#         self.assertTrue(hasattr(wrapped, 'response'))
#
#     def test_success_codes_are_enforced(self):
#         """Success response status code is enforced."""
#         mock_func = mock.MagicMock(return_value=({}, sword.ACCEPTED, {}))
#         wrapped = sword.response(success=[sword.OK])(mock_func)
#         with self.assertRaises(sword.InvalidResponse):
#             wrapped(None, {}, {})
#
#         mock_func = mock.MagicMock(return_value=({}, sword.OK, {}))
#         wrapped = sword.response(success=[sword.OK])(mock_func)
#         try:
#             wrapped(None, {}, {})
#         except Exception as e:
#             self.fail(e)
#
#     def test_error_codes_are_enforced(self):
#         """Error response status code is enforced."""
#         mock_func = mock.MagicMock(return_value=({}, sword.NOT_FOUND, {}))
#         wrapped = sword.response(error=[sword.FORBIDDEN])(mock_func)
#         with self.assertRaises(sword.InvalidResponse):
#             wrapped(None, {}, {})
#
#         mock_func = mock.MagicMock(return_value=({}, sword.FORBIDDEN, {}))
#         wrapped = sword.response(error=[sword.FORBIDDEN])(mock_func)
#         try:
#             wrapped(None, {}, {})
#         except Exception as e:
#             self.fail(e)
#
#     def test_global_header_is_enforced(self):
#         """A header tagged as MUST must (ha) be present in the response."""
#         mock_func = mock.MagicMock(return_value=({}, sword.OK, {}))
#         deco = sword.response(success=[sword.SEE_OTHER], must=['Location'])
#         wrapped = deco(mock_func)
#         with self.assertRaises(sword.InvalidResponse):
#             wrapped(None, {}, {})
#         self.assertIn('Location', wrapped.response['must']['__all__'])
#
#         mock_func = mock.MagicMock(return_value=({}, sword.SEE_OTHER,
#                                    {'Location': 'foo'}))
#         deco = sword.response(success=[sword.SEE_OTHER], must=['Location'])
#         wrapped = deco(mock_func)
#         try:
#             wrapped(None, {}, {})
#         except Exception as e:
#             self.fail(e)
#
#     def test_conditional_header_is_enforced(self):
#         """Header passed with status codes is conditionally enforced."""
#         mock_func = mock.MagicMock(return_value=({}, sword.SEE_OTHER, {}))
#         deco = sword.response(success=[sword.SEE_OTHER],
#                               must=[(sword.SEE_OTHER, 'Location')])
#         wrapped = deco(mock_func)
#         with self.assertRaises(sword.InvalidResponse):
#             wrapped(None, {}, {})
#
#         mock_func = mock.MagicMock(return_value=({}, sword.OK, {}))
#         deco = sword.response(success=[sword.SEE_OTHER, sword.OK],
#                               must=[(sword.SEE_OTHER, 'Location')])
#         wrapped = deco(mock_func)
#         try:
#             wrapped(None, {}, {})
#         except Exception as e:
#             self.fail(e)
#
#     def test_missing_should_header_raises_warning(self):
#         """Header flagged as SHOULD results in warning if not found."""
#         mock_func = mock.MagicMock(return_value=({}, sword.SEE_OTHER, {}))
#         deco = sword.response(success=[sword.SEE_OTHER],
#                               should=['Location'])
#         wrapped = deco(mock_func)
#         with self.assertWarns(RuntimeWarning):
#             wrapped(None, {}, {})
#
#
# class TestDecoratorsOnSWORDResource(unittest.TestCase):
#     """Request and response decorators are used jointly on instance methods."""
#
#     def setUp(self):
#         class TestClass(sword.SWORDBase):
#             @sword.request(must=['Authorization'])
#             @sword.response(success=[200, 301], error=[404],
#                             must=[(301, 'Location')])
#             def get(self, data, headers, files=None, **extra):
#                 return self.manifold.get(data, headers, files, **extra)
#         self.klass = TestClass
#
#     def test_get_fails_on_bad_status(self):
#         """An InvalidResponse exception is raised for invalid status codes."""
#         manifold = mock.MagicMock()
#         manifold.get = mock.MagicMock(return_value=({}, 201, {}))
#         submission = self.klass(manifold)
#         with self.assertRaises(sword.InvalidResponse):
#             submission.get({}, {'Authorization': 'foo'})
#         self.assertEqual(manifold.get.call_count, 1)
#
#     def test_get_fails_on_missing_header(self):
#         """An InvalidResponse raised when Location missing in 3xx responses."""
#         manifold = mock.MagicMock()
#         manifold.get = mock.MagicMock(return_value=({}, 301, {}))
#         submission = self.klass(manifold)
#         with self.assertRaises(sword.InvalidResponse):
#             submission.get({}, {'Authorization': 'foo'})
#
#         manifold = mock.MagicMock()
#         manifold.get = mock.MagicMock(
#             return_value=({}, 301, {'Location': 'foo'})
#         )
#         submission = self.klass(manifold)
#         try:
#             submission.get({}, {'Authorization': 'foo'})
#         except sword.InvalidResponse:
#             self.fail("Expects Location")
#
#     def test_get_succeeds(self):
#         """An InvalidResponse exception not raised for valid status codes."""
#         manifold = mock.MagicMock()
#         manifold.get = mock.MagicMock(return_value=({}, 200, {}))
#         submission = self.klass(manifold)
#         try:
#             submission.get({}, {'Authorization': 'foo'})
#         except sword.InvalidResponse as e:
#             self.fail(e)
#
#     def test_get_succeeds_with_error(self):
#         """An InvalidResponse exception not raised for valid error codes."""
#         manifold = mock.MagicMock()
#         manifold.get = mock.MagicMock(return_value=({}, 404, {}))
#         submission = self.klass(manifold)
#         try:
#             submission.get({}, {'Authorization': 'foo'})
#         except sword.InvalidResponse as e:
#             self.fail(e)
