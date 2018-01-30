"""Provides an event type converter; for URLs with event types."""

import re

from werkzeug.routing import BaseConverter, ValidationError
from events.domain.event import EVENT_TYPES


def snake_to_camel(snake: str) -> str:
    """Convert a snake_case string to CamelCase."""
    return ''.join([part.capitalize() for part in snake.split('_')])


def camel_to_snake(camel: str) -> str:
    """Convert a CamelCase string to snake_case."""
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', camel)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


class EventTypeConverter(BaseConverter):
    """Route converter for event types."""

    @staticmethod
    def to_python(value: str) -> str:
        """Parse URL path part to Python rep (str)."""
        camel = snake_to_camel(value + '_event')
        if camel not in EVENT_TYPES:
            raise ValidationError('Not a valid event type')
        return camel

    @staticmethod
    def to_url(value: str) -> str:
        """Cast Python rep (str) to URL path part."""
        return camel_to_snake(value)
