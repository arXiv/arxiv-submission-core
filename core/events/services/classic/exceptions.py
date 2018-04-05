"""Exceptions raised by :mod:`events.services.classic`."""


class NoSuchSubmission(RuntimeError):
    """A request was made for a submission that does not exist."""
