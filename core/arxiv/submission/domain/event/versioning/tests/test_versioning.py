"""Test versioning of event data."""

from unittest import TestCase

from .. import map_to_version
from .._base import BaseVersionMapping


class TitleIsNowCoolTitle(BaseVersionMapping):
    """Changes the ``title`` field to ``cool_title``."""

    class Meta:
        """Metadata for this mapping."""

        event_version = '0.3.5'
        event_type = "SetTitle"
        tests = [({'event_version': '0.1.1', 'title': 'olde'},
                  {'event_version': '0.3.5', 'cool_title': 'olde'})]

    def transform_title(self, original, key, value):
        """Rename the `title` field to `cool_title`."""
        return "cool_title", value


class TestVersionMapping(TestCase):
    """Tests for :func:`.map_to_version`."""

    def test_map_to_version(self):
        """We have data from a previous version and an intermediate mapping."""
        data = {
            'event_version': '0.1.2',
            'event_type': 'SetTitle',
            'title': 'Some olde title'
        }

        expected = {
            'event_version': '0.3.5',
            'event_type': 'SetTitle',
            'cool_title': 'Some olde title'
        }
        self.assertDictEqual(map_to_version(data, '0.4.1'), expected,
                             "The mapping is applied")

    def test_map_to_version_no_intermediate(self):
        """We have data from a previous version and no intermediate mapping."""
        data = {
            'event_version': '0.5.5',
            'event_type': 'SetTitle',
            'cool_title': 'Some olde title'
        }
        self.assertDictEqual(map_to_version(data, '0.6.7'), data,
                             "The mapping is not applied")

    def test_data_is_up_to_date(self):
        """We have data that is 100% current."""
        data = {
            'event_version': '0.5.5',
            'event_type': 'SetTitle',
            'cool_title': 'Some olde title'
        }
        self.assertDictEqual(map_to_version(data, '0.5.5'), data,
                             "The mapping is not applied")


class TestVersionMappingTests(TestCase):
    """Tests defined in metadata can be run, with the expected result."""

    def test_test(self):
        """Run tests in mapping metadata."""
        class BrokenFitleIsNowCoolTitle(BaseVersionMapping):
            """A broken version mapping."""

            class Meta:
                """Metadata for this mapping."""

                event_version = '0.3.5'
                event_type = "SetFitle"
                tests = [({'event_version': '0.1.1', 'title': 'olde'},
                          {'event_version': '0.3.5', 'cool_title': 'olde'})]

            def transform_title(self, original, key, value):
                """Rename the `title` field to `cool_title`."""
                return "fool_title", value

        TitleIsNowCoolTitle.test()
        with self.assertRaises(AssertionError):
            BrokenFitleIsNowCoolTitle.test()

    def test_version_is_present(self):
        """Tests check that version is specified."""
        class MappingWithoutVersion(BaseVersionMapping):
            """Mapping that is missing a version."""

            class Meta:
                """Metadata for this mapping."""

                event_type = "FetBitle"

        with self.assertRaises(AssertionError):
            MappingWithoutVersion.test()

    def test_event_type_is_present(self):
        """Tests check that event_type is specified."""
        class MappingWithoutEventType(BaseVersionMapping):
            """Mapping that is missing an event type."""

            class Meta:
                """Metadata for this mapping."""

                event_version = "5.3.2"

        with self.assertRaises(AssertionError):
            MappingWithoutEventType.test()

    def test_version_is_valid(self):
        """Tests check that version is a valid semver."""
        class MappingWithInvalidVersion(BaseVersionMapping):
            """Mapping that has an invalid semantic version."""

            class Meta:
                """Metadata for this mapping."""

                event_version = "52"
                event_type = "FetBitle"

        with self.assertRaises(AssertionError):
            MappingWithInvalidVersion.test()


class TestVersioningModule(TestCase):
    def test_loads_mappings(self):
        """Loading a version mapping module installs those mappings."""
        from .. import version_0_0_0_example
        self.assertIn(version_0_0_0_example.SetTitleExample,
                      BaseVersionMapping.__subclasses__(),
                      'Mappings in an imported module are available for use')
