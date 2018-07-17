"""Utility classes and functions for :mod:`arxiv.submission.services.classic`."""

import json
from typing import Optional
import sqlalchemy.types as types


class SQLiteJSON(types.TypeDecorator):
    """A SQLite-friendly JSON data type."""

    impl = types.TEXT

    def process_bind_param(self, value: Optional[dict], dialect: str) -> str:
        """Serialize a dict to JSON."""
        if value is not None:
            value = json.dumps(value)
        return value

    def process_result_value(self, value: str, dialect: str) -> Optional[dict]:
        """Deserialize JSON content to a dict."""
        if value is not None:
            value = json.loads(value)
        return value


# SQLite does not support JSON, so we extend JSON to use our custom data type
# as a variant for the 'sqlite' dialect.
FriendlyJSON = types.JSON().with_variant(SQLiteJSON, 'sqlite')
