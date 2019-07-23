"""Test that all event classes are well-formed."""

from unittest import TestCase
import inspect
from ..base import Event


class TestNamed(TestCase):
    """Verify that all event classes are named."""

    def test_has_name(self):
        """All event classes must have a ``NAME`` attribute."""
        for klass in Event.__subclasses__():
            self.assertTrue(hasattr(klass, 'NAME'),
                            f'{klass.__name__} is missing attribute NAME')

    def test_has_named(self):
        """All event classes must have a ``NAMED`` attribute."""
        for klass in Event.__subclasses__():
            self.assertTrue(hasattr(klass, 'NAMED'),
                            f'{klass.__name__} is missing attribute NAMED')


class TestHasProjection(TestCase):
    """Verify that all event classes have a projection method."""

    def test_has_projection(self):
        """Each event class must have an instance method ``project()``."""
        for klass in Event.__subclasses__():
            self.assertTrue(hasattr(klass, 'project'),
                            f'{klass.__name__} is missing project() method')
            self.assertTrue(inspect.isfunction(klass.project),
                            f'{klass.__name__} is missing project() method')


class TestHasValidation(TestCase):
    """Verify that all event classes have a projection method."""

    def test_has_validate(self):
        """Each event class must have an instance method ``validate()``."""
        for klass in Event.__subclasses__():
            self.assertTrue(hasattr(klass, 'validate'),
                            f'{klass.__name__} is missing validate() method')
            self.assertTrue(inspect.isfunction(klass.validate),
                            f'{klass.__name__} is missing validate() method')
