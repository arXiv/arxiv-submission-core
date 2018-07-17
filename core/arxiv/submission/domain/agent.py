"""Data structures for agents."""

import hashlib
from typing import Any, Optional, List

from dataclasses import dataclass, field
from dataclasses import asdict

from .meta import Classification

__all__ = ('Agent', 'User', 'System', 'Client', 'agent_factory')


@dataclass
class Agent:
    """
    Base class for agents in the submission system.

    An agent is an actor/system that generates/is responsible for events.
    """

    native_id: str
    """Type-specific identifier for the agent. This might be an URI."""

    @property
    def agent_type(self):
        """The name of the agent instance's class."""
        return self.get_agent_type()

    @classmethod
    def get_agent_type(cls):
        """Get the name of the instance's class."""
        return cls.__name__

    @property
    def agent_identifier(self):
        """
        Unique identifier for the agent instance.

        Based on both the agent type and native ID.
        """
        h = hashlib.new('sha1')
        h.update(b'%s:%s' % (self.agent_type.encode('utf-8'),
                             str(self.native_id).encode('utf-8')))
        return h.hexdigest()

    @classmethod
    def from_dict(cls, data: dict) -> Any:
        """Instantiate an :class:`.Agent` instance from a dict."""
        agent_type = data.pop('agent_type', None)
        native_id = data.pop('native_id', None)
        if agent_type is None and type(cls) is Agent:
            raise ValueError('agent_type not provided')
        return agent_factory(agent_type, native_id, **data)

    def __eq__(self, other: Any) -> bool:
        """Equality comparison for agents based on type and identifier."""
        if not isinstance(other, self.__class__):
            return False
        return self.agent_identifier == other.agent_identifier

    def to_dict(self) -> dict:
        """Generate a dict representation of this :class:`.Agent`."""
        return {
            'native_id': self.native_id,
            'agent_type': self.agent_type
        }


@dataclass
class User(Agent):
    """An (human) end user."""

    email: str
    forename: str = field(default_factory=str)
    surname: str = field(default_factory=str)
    suffix: str = field(default_factory=str)
    identifier: Optional[str] = field(default=None)
    affiliation: str = field(default_factory=str)

    endorsements: List[str] = field(default_factory=list)

    @property
    def name(self):
        """Full name of the user."""
        return f"{self.forename} {self.surname} {self.suffix}"

    def to_dict(self) -> dict:
        """Generate a dict representation of this :class:`.User`."""
        data = super(User, self).to_dict()
        data['name'] = self.name
        data['forename'] = self.forename
        data['surname'] = self.surname
        data['suffix'] = self.suffix
        data['email'] = self.email
        data['identifier'] = self.identifier
        data['affiliation'] = self.affiliation
        data['user_id'] = self.native_id
        data['endorsements'] = self.endorsements
        return data


# TODO: extend this to support arXiv-internal services.
@dataclass
class System(Agent):
    """The submission application (this application)."""


@dataclass
class Client(Agent):
    """A non-human third party, usually an API client."""

    def to_dict(self):
        """Generate a dict representation of this :class:`.Client` instance."""
        return {
            'client_id': self.native_id
        }


_agent_types = {
    User.get_agent_type(): User,
    System.get_agent_type(): System,
    Client.get_agent_type(): Client,
}


def agent_factory(agent_type: str, native_id: Any, **extra) -> Agent:
    """Instantiate a subclass of :class:`.Agent`."""
    if agent_type not in _agent_types:
        raise ValueError(f'No such agent type: {agent_type}')
    klass = _agent_types[agent_type]
    extra = {k: v for k, v in extra.items() if k in klass.__dataclass_fields__}
    return klass(native_id=native_id, **extra)
