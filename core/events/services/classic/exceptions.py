"""Exceptions raised by :mod:`events.services.classic`."""


class NoSuchSubmission(RuntimeError):
    """A request was made for a submission that does not exist."""


class CommitFailed(RuntimeError):
    """Raised when there was a problem committing changes to the database."""
