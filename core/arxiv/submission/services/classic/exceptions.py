"""Exceptions raised by :mod:`arxiv.submission.services.classic`."""


class ClassicBaseException(RuntimeError):
    """Base for classic service exceptions."""


class NoSuchSubmission(ClassicBaseException):
    """A request was made for a submission that does not exist."""


class TransactionFailed(ClassicBaseException):
    """Raised when there was a problem committing changes to the database."""


class Unavailable(ClassicBaseException):
    """The classic data store is not available."""


class ConsistencyError(ClassicBaseException):
    """Attempted to persist stale or inconsistent state."""
