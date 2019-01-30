"""Tests for retrieving license information."""

from unittest import TestCase, mock

from flask import Flask

from ....domain.submission import License
from .. import models, get_licenses
from .util import in_memory_db


class TestGetLicenses(TestCase):
    """Test :func:`.get_licenses`."""

    def test_get_all_active_licenses(self):
        """Return a :class:`.domain.License` for each active license."""
        # mock_util.json_factory.return_value = SQLiteJSON

        with in_memory_db() as session:
            session.add(models.License(
                name="http://arxiv.org/licenses/assumed-1991-2003",
                sequence=9,
                label="Assumed arXiv.org perpetual, non-exclusive license to",
                active=0
            ))
            session.add(models.License(
                name="http://creativecommons.org/licenses/publicdomain/",
                sequence=4,
                label="Creative Commons Public Domain Declaration",
                active=1
            ))
            session.commit()
            licenses = get_licenses()

        self.assertEqual(len(licenses), 1,
                         "Only the active license should be returned.")
        self.assertIsInstance(licenses[0], License,
                              "Should return License instances.")
        self.assertEqual(licenses[0].uri,
                         "http://creativecommons.org/licenses/publicdomain/",
                         "Should use name column to populate License.uri")
        self.assertEqual(licenses[0].name,
                         "Creative Commons Public Domain Declaration",
                         "Should use label column to populate License.name")
