"""Exceptions raised by :mod:`events.services.classic`."""


class ClassicBaseException(RuntimeError):
    """Base for classic service exceptions."""


class NoSuchSubmission(ClassicBaseException):
    """A request was made for a submission that does not exist."""


class CommitFailed(ClassicBaseException):
    """Raised when there was a problem committing changes to the database."""
