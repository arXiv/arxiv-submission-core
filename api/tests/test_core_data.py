"""Tests for :mod:`submit.domain.data`."""

from unittest import TestCase, mock
from api.domain.data import Data, Property


class TestPropertyDescriptor(TestCase):
    """The :class:`.Property` descriptor describes data properties."""
    def test_property_sets_inner_dict(self):
        """An instance of :class:`.Property` sets items in __dict__."""
        # Like a good descriptor!
        name = 'foo'
        prop = Property(name, str)
        instance = mock.MagicMock()
        value = 'baz'
        prop.__set__(instance, value)
        self.assertEqual(instance.__dict__[name], value)

    def test_property_gets_from_inner_dict(self):
        """An instance of :class:`.Property` gets items from __dict__."""
        # Like a good descriptor!
        name = 'foo'
        prop = Property(name, str)
        instance = mock.MagicMock()
        value = 'baz'
        instance.__dict__[name] = value
        self.assertEqual(prop.__get__(instance, value), value)

    def test_property_raises_typeerror(self):
        """A TypeError raised when set value is instance of wrong type."""
        name = 'foo'
        prop = Property(name, str)
        instance = mock.MagicMock()
        value = -1
        with self.assertRaises(TypeError):
            prop.__set__(instance, value)

    def test_property_does_not_raise_typeerror(self):
        """A TypeError not raised when expected type not set."""
        name = 'foo'
        prop = Property(name)
        instance = mock.MagicMock()
        value = -1
        try:
            prop.__set__(instance, value)
        except TypeError as e:
            self.fail(e)


class TestDataMethods(TestCase):
    """The :class:`.Data` base class provides dict-conversion methods."""

    def test_from_dict(self):
        """Key matching defined :class:`.Property` instance is set."""
        data = {'foo': 'baz', 'qwerty': 'yuiop'}

        class FooData(Data):
            """A foo."""

            foo = Property('foo', str)

        instance = FooData.from_dict(data)
        self.assertIsInstance(instance, FooData)
        self.assertEqual(instance.foo, data['foo'])
        with self.assertRaises(AttributeError):    # Other keys are ignored.
            instance.qwerty

    def test_from_dict_with_nested_data(self):
        """If property expects :class:`.Data`, instantiate it."""
        data = {'foo': 'baz', 'qwerty': {'yes': 'no'}}

        class BazData(Data):
            """A baz."""

            yes = Property('yes')

        class FooData(Data):
            """A foo."""

            foo = Property('foo', str)
            qwerty = Property('qwerty', BazData)

        instance = FooData.from_dict(data)
        self.assertIsInstance(instance, FooData)
        self.assertEqual(instance.foo, data['foo'])
        self.assertIsInstance(instance.qwerty, BazData)
        self.assertEqual(instance.qwerty.yes, 'no')

    def test_from_dict_with_nested_malformed_data(self):
        """Raise ValueError when expects Data and value is not dict."""
        data = {'foo': 'baz', 'qwerty': 'no'}

        class BazData(Data):
            """A baz."""

            yes = Property('yes')

        class FooData(Data):
            """A foo."""

            foo = Property('foo', str)
            qwerty = Property('qwerty', BazData)

        with self.assertRaises(ValueError):
            FooData.from_dict(data)

    def test_from_dict_with_missing_keys(self):
        """If required key is not present, a KeyError is raised."""
        data = {'qwerty': 'yuiop'}

        class FooData(Data):
            """A foo."""

            foo = Property('foo', str)

        with self.assertRaises(KeyError):
            FooData.from_dict(data)

    def test_from_dict_with_missing_keys_and_default_value(self):
        """A KeyError is not raised when :class:`.Property` has a default."""
        data = {'qwerty': 'yuiop'}

        class FooData(Data):
            """A foo."""

            foo = Property('foo', str, 'baz')

        try:
            FooData.from_dict(data)
        except KeyError as e:
            self.fail(e)

    def test_to_dict(self):
        """A dict is created from :class:`.Data` instance property values."""
        class FooData(Data):
            """A foo."""

            foo = Property('foo', str)

        value = 'yes'
        fooInstance = FooData()
        fooInstance.foo = value
        data = fooInstance.to_dict()
        self.assertIsInstance(data, dict)
        self.assertIn('foo', data)
        self.assertEqual(data['foo'], value)
        self.assertEqual(len(data), 1)

    def testto_dict_with_default_value(self):
        """A dict is created from :class:`.Data` instance property values."""
        value = 'yes'

        class FooData(Data):
            """A foo."""

            foo = Property('foo', str, value)

        fooInstance = FooData()
        data = fooInstance.to_dict()
        self.assertIsInstance(data, dict)
        self.assertIn('foo', data)
        self.assertEqual(data['foo'], value)
        self.assertEqual(len(data), 1)

    def testto_dict_with_no_value(self):
        """A dict is created from :class:`.Data` instance property values."""
        #
        class FooData(Data):
            """A foo."""

            foo = Property('foo', str)

        fooInstance = FooData()
        data = fooInstance.to_dict()
        self.assertIsInstance(data, dict)
        self.assertIn('foo', data)
        self.assertIsNone(data['foo'])
        self.assertEqual(len(data), 1)

    def test_copy(self):
        """A copy of the :class:`.Data` instance is created."""
        value = [1, 2, 3]

        class FooData(Data):
            """A foo."""

            foo = Property('foo', list)

        fooInstance = FooData()
        fooInstance.foo = value
        fooCopy = fooInstance.copy()
        self.assertNotEqual(id(fooInstance), id(fooCopy))
        self.assertNotEqual(id(fooInstance.foo), id(fooCopy.foo))
        self.assertEqual(fooInstance.foo, fooCopy.foo)
