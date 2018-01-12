from submit.domain.event import Event


class InvalidEvent(ValueError):
    """Raised when an invalid event is encountered."""

    def __init__(self, event: Event) -> None:
        self.event = event
        msg = "Encountered invalid event: %s (%s)" % \
            (event.event_type, event.event_id)
        super(InvalidEvent, self).__init__(msg)
