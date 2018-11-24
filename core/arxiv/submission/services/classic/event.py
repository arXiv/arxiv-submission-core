"""Persistence for NG events in the classic database."""

from datetime import datetime
from pytz import UTC

from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.ext.indexable import index_property
from sqlalchemy.orm import relationship

# Combining the base DateTime field with a MySQL backend does not support
# fractional seconds. Since we may be creating events only milliseconds apart,
# getting fractional resolution is essential.
from sqlalchemy.dialects.mysql import DATETIME as DateTime

from ...domain.event import Event, event_factory
from ...domain.agent import User, Client, Agent, System
from .models import Base
from .util import transaction, current_session, FriendlyJSON


class DBEvent(Base):  # type: ignore
    """Database representation of an :class:`.Event`."""

    __tablename__ = 'event'

    event_id = Column(String(40), primary_key=True)
    event_type = Column(String(255))
    proxy = Column(FriendlyJSON)
    proxy_id = index_property('proxy', 'agent_identifier')
    client = Column(FriendlyJSON)
    client_id = index_property('client', 'agent_identifier')

    creator = Column(FriendlyJSON)
    creator_id = index_property('creator', 'agent_identifier')

    created = Column(DateTime(fsp=6))
    data = Column(FriendlyJSON)
    submission_id = Column(
        ForeignKey('arXiv_submissions.submission_id'),
        index=True
    )

    submission = relationship("Submission")

    def to_event(self) -> Event:
        """
        Instantiate an :class:`.Event` using event data from this instance.

        Returns
        -------
        :class:`.Event`

        """
        _skip = ['creator', 'proxy', 'client', 'submission_id', 'created',
                 'event_type']
        data = {
            key: value for key, value in self.data.items()
            if key not in _skip
        }
        data['committed'] = True     # Since we're loading from the DB.
        return event_factory(
            self.event_type,
            creator=Agent.from_dict(self.creator),
            proxy=Agent.from_dict(self.proxy) if self.proxy else None,
            client=Agent.from_dict(self.client) if self.client else None,
            submission_id=self.submission_id,
            created=self.get_created(),
            **data
        )

    def get_created(self) -> datetime:
        """Get the UTC-localized creation time for this event."""
        return self.created.replace(tzinfo=UTC)
