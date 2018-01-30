from unittest import TestCase
import os
from yaml import safe_load
from openapi_spec_validator import validate_spec

base_path, _ = os.path.split(os.path.abspath(__file__))
schema_path = os.path.join(base_path, '..', 'schema/openapi.yaml')


class TestOpenAPISchemaValid(TestCase):
    """Validate the OpenAPI description against the OpenAPI spec."""

    def setUp(self):
        """Load the OpenAPI description."""
        with open(schema_path) as f:
            self.spec = safe_load(f)

    def test_validate(self):
        """Validate the OpenAPI description."""
        try:
            validate_spec(self.spec, spec_url='file://%s' % schema_path)
        except Exception as e:
            self.fail('Invalid OpenAPI schema: %s' % e)
