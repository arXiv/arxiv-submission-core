"""Helpers and utilities."""

from datetime import datetime
from pytz import UTC


def get_tzaware_utc_now():
    """Generate a datetime for the current moment in UTC."""
    return datetime.now(UTC)
