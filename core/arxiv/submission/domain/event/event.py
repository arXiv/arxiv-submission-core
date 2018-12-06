from datetime import datetime
import hashlib
import copy
from typing import Optional

from dataclasses import dataclass, field, asdict

from arxiv.base import logging
from ..agent import Agent
from ...exceptions import InvalidEvent
from ..util import get_tzaware_utc_now
from ..submission import Submission

logger = logging.getLogger(__name__)
logger.propagate = False


@dataclass
class Event:
    """Base class for submission-related events."""

    creator: Agent
    """
    The agent responsible for the operation represented by this event.

    This is **not** necessarily the creator of the submission.
    """

    created: datetime = field(default_factory=get_tzaware_utc_now)
    """
    The timestamp when the event was originally committed.

    This should generally not be set from outside this package.
    """

    proxy: Optional[Agent] = field(default=None)
    """
    The agent who facilitated the operation on behalf of the :prop:`.creator`.

    This may be an API client, or another user who has been designated as a
    proxy. Note that proxy implies that the creator was not directly involved.
    """

    client: Optional[Agent] = field(default=None)
    """
    The client through which the :prop:`.creator` performed the operation.

    If the creator was directly involved in the operation, this property should
    be the client that facilitated the operation.
    """

    submission_id: Optional[int] = field(default=None)
    """
    The primary identifier of the submission being operated upon.

    This is defined as optional to support creation events, and to facilitate
    chaining of events with creation events in the same transaction.
    """

    committed: bool = field(default=False)
    """
    Indicates whether the event has been committed to the database.

    This should generally not be set from outside this package.
    """

    @property
    def event_type(self) -> str:
        """The name (str) of the event type."""
        return self.get_event_type()

    @classmethod
    def get_event_type(cls) -> str:
        """Get the name (str) of the event type."""
        return cls.__name__

    @property
    def event_id(self) -> str:
        """The unique ID for this event."""
        h = hashlib.new('sha1')
        h.update(b'%s:%s:%s' % (self.created.isoformat().encode('utf-8'),
                                self.event_type.encode('utf-8'),
                                self.creator.agent_identifier.encode('utf-8')))
        return h.hexdigest()

    def __hash__(self):
        """Use event ID as object hash."""
        return hash(self.event_id)

    def apply(self, submission: Optional[Submission] = None) -> Submission:
        """Apply the projection for this :class:`.Event` instance."""
        self.validate(submission)
        if submission is not None:
            submission = self.project(copy.deepcopy(submission))
        else:
            logger.debug('Submission is None; project without submission.')
            submission = self.project()
        submission.updated = self.created

        # Make sure that the submission has its own ID, if we know what it is.
        if submission.submission_id is None and self.submission_id is not None:
            submission.submission_id = self.submission_id
        if self.submission_id is None and submission.submission_id is not None:
            self.submission_id = submission.submission_id
        return submission

    def to_dict(self):
        """Generate a dict representation of this :class:`.Event`."""
        data = asdict(self)
        data.update({
            'creator': self.creator.to_dict(),
            'proxy': self.proxy.to_dict() if self.proxy else None,
            'client': self.client.to_dict() if self.client else None,
            'created': self.created.isoformat(),
        })
        return data
