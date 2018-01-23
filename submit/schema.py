"""Provides JSON Schema validation tools."""

import json
import os
from typing import Callable
import jsonschema


def load(schema_path: str) -> Callable:
    """
    Load a JSON Schema from ``schema_path``.

    Parameters
    ----------
    schema_path : str
        Location of the target schema.

    Returns
    -------
    callable
        A validator function; when called with a ``dict``, validates the data
        against the schema.
    """
    with open(schema_path) as f:
        schema = json.load(f)

    schema_base_path = os.path.dirname(os.path.realpath(schema_path))
    resolver = jsonschema.RefResolver(referrer=schema,
                                      base_uri="file://%s/" % schema_base_path)

    def validate(data: dict) -> None:
        """
        Validate ``data`` against the enclosed schema.

        Parameters
        ----------
        data : dict

        Raises
        ------
        :class:`.ValidationError`
        """
        jsonschema.validate(data, schema, resolver=resolver)
    return validate


ValidationError = jsonschema.exceptions.ValidationError
