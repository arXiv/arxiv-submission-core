# import unittest
# from unittest import mock
# import sword
#
#
# class TestSWORDBaseMethods(unittest.TestCase):
#     """:class:`sword.SWORDBase` is the base class for SWORD resources."""
#
#     def setUp(self):
#         """Instantiate a :class:`sword.SWORDBase`."""
#         self.FOO = 'http://foo.baz/bat/'
#         self.instance = sword.SWORDBase(mock.MagicMock())
#         self.instance.context = {'foo': self.FOO}
#
#     def test_compact(self):
#         """:meth:`._compact` applies :prop:`.context` to produce JSON-LD."""
#         doc = self.instance._compact({'http://foo.baz/bat/bar': True})
#         ld = {'@context': {'foo': self.FOO}, 'foo:bar': True}
#         self.assertDictEqual(ld, doc, "Produces a compact JSON-LD document.")
#
#     def test_fmt(self):
#         """:meth:`._fmt` unfurls a field using :prop:`.context`."""
#         self.assertEqual(self.instance._fmt('foo', 'bar'), '%sbar' % self.FOO,
#                          "If the namespace is in .context, concatenates the"
#                          " field to produce a full URI.")
#         self.assertEqual(self.instance._fmt('foo', '/bar'), '%sbar' % self.FOO,
#                          "Preceding forward slash in the field is ignored.")
#         self.instance.context = {'foo': self.FOO + '/'}
#         self.assertEqual(self.instance._fmt('foo', '/bar'), '%sbar' % self.FOO,
#                          "Trailing forward slash in the ns is ignored.")
#         self.assertEqual(self.instance._fmt('baz', 'bat'), 'bat',
#                          "If the namespace is not in .context, returns the"
#                          " bare field.")
#
#     def test_render(self):
#         """:meth:`.render` generates JSON-LD for an HTTP response."""
#         self.instance.fields = [('foo', 'bar')]
#         body, status, headers = self.instance.render({'bar': True}, 200, {})
#         ld = {'@context': {'foo': self.FOO}, 'foo:bar': True}
#         self.assertDictEqual(ld, body, "Produces a compact JSON-LD document.")
#
#         body, status, headers = self.instance.render({'ack': True}, 200, {})
#         self.assertDictEqual({'@context': {'foo': self.FOO}}, body,
#                              "A field not in :prop:`.fields` is ignored.")
#
#         body, status, headers = self.instance.render({}, 200, {})
#         self.assertDictEqual({'@context': {'foo': self.FOO}}, body,
#                              "Missing fields in :prop:`.fields` are ignored.")
#
#         self.instance.required = [('foo', 'bar')]
#         body, status, headers = self.instance.render({}, 200, {})
#         ld = {'@context': {'foo': self.FOO}, 'foo:bar': None}
#         self.assertDictEqual({'@context': {'foo': self.FOO}}, body,
#                              "Missing fields in :prop:`.fields` that are also"
#                              " in :prop:`.required` are null.")
#
#         body, status, headers = self.instance.render({'bar': True}, 204, {})
#         self.assertEqual(body, '', "204 (no content) responses are empty.")
