"""Exceptions raised during event handling."""

from typing import TypeVar

EventType = TypeVar('EventType', bound='core.events.domain.event.Event')


class InvalidEvent(ValueError):
    """Raised when an invalid event is encountered."""

    def __init__(self, event: EventType, extra: str='') -> None:
        """Use the :class:`.Event` to build an error message."""
        self.event: EventType = event
        msg = f"Invalid event: {event.event_type} ({event.event_id}): {extra}"
        super(InvalidEvent, self).__init__(msg)


class NoSuchSubmission(Exception):
    """An operation was performed on/for a submission that does not exist."""


class SaveError(RuntimeError):
    """Failed to persist event state."""
