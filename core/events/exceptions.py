"""Exceptions raised during event handling."""

from typing import TypeVar, List

EventType = TypeVar('EventType', bound='core.events.domain.event.Event')


class InvalidEvent(ValueError):
    """Raised when an invalid event is encountered."""

    def __init__(self, event: EventType, message: str='') -> None:
        """Use the :class:`.Event` to build an error message."""
        self.event: EventType = event
        self.message = message
        r = f"Invalid event: {event.event_type} ({event.event_id}): {message}"
        super(InvalidEvent, self).__init__(r)


class InvalidStack(ValueError):
    """Raised when an invalid event is encountered."""

    def __init__(self, event_exceptions: List[InvalidEvent],
                 extra: str='') -> None:
        """Use the :class:`.Event` to build an error message."""
        self.event_exceptions: List[InvalidEvent] = event_exceptions
        self.message = 'Invalid Stack:'
        for ex in self.event_exceptions:
            self.message += f"\n\t{ex.message}"
        super(InvalidStack, self).__init__(self.message)


class NoSuchSubmission(Exception):
    """An operation was performed on/for a submission that does not exist."""


class SaveError(RuntimeError):
    """Failed to persist event state."""
