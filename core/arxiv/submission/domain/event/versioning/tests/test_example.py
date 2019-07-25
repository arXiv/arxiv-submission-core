"""Test the example version mapping module."""

from unittest import TestCase

from .. import map_to_version
from .._base import BaseVersionMapping
from .. import version_0_0_0_example


class TestSetTitleExample(TestCase):
    """Test the :class:`.version_0_0_0_example.SetTitleExample` mapping."""

    def test_set_title(self):
        """Execute the built-in version mapping tests."""
        version_0_0_0_example.SetTitleExample.test()
