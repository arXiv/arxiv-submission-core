"""Exceptions raised during event handling."""

from typing import TypeVar, List

EventType = TypeVar('EventType')


class InvalidEvent(ValueError):
    """Raised when an invalid event is encountered."""

    def __init__(self, event: EventType, message: str = '') -> None:
        """Use the :class:`.Event` to build an error message."""
        self.event = event
        self.message = message
        r = f"Invalid {event.event_type}: {message}"  # type: ignore
        super(InvalidEvent, self).__init__(r)


class NoSuchSubmission(Exception):
    """An operation was performed on/for a submission that does not exist."""


class SaveError(RuntimeError):
    """Failed to persist event state."""


class NothingToDo(RuntimeError):
    """There is nothing to do."""
