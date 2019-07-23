"""Data structures for agents."""

import hashlib
from typing import Any, Optional, List, Union

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

    def __post_init__(self):
        """Set derivative fields."""
        self.agent_type = self.__class__.get_agent_type()
        self.agent_identifier = self.get_agent_identifier()

    @classmethod
    def get_agent_type(cls) -> str:
        """Get the name of the instance's class."""
        return cls.__name__

    def get_agent_identifier(self) -> str:
        """
        Get the unique identifier for this agent instance.

        Based on both the agent type and native ID.
        """
        h = hashlib.new('sha1')
        h.update(b'%s:%s' % (self.agent_type.encode('utf-8'),
                             str(self.native_id).encode('utf-8')))
        return h.hexdigest()

    def __eq__(self, other: Any) -> bool:
        """Equality comparison for agents based on type and identifier."""
        if not isinstance(other, self.__class__):
            return False
        return self.agent_identifier == other.agent_identifier


@dataclass
class User(Agent):
    """An (human) end user."""

    email: str = field(default_factory=str)
    username: str = field(default_factory=str)
    forename: str = field(default_factory=str)
    surname: str = field(default_factory=str)
    suffix: str = field(default_factory=str)
    name: str = field(default_factory=str)
    identifier: Optional[str] = field(default=None)
    affiliation: str = field(default_factory=str)
    hostname: Optional[str] = field(default=None)
    """Hostname or IP address from which user requests are originating."""

    endorsements: List[str] = field(default_factory=list)
    agent_type: str = field(default_factory=str)
    agent_identifier: str = field(default_factory=str)

    def __post_init__(self):
        """Set derivative fields."""
        self.name = self.get_name()
        self.agent_type = self.get_agent_type()

    def get_name(self):
        """Full name of the user."""
        return f"{self.forename} {self.surname} {self.suffix}"


# TODO: extend this to support arXiv-internal services.
@dataclass
class System(Agent):
    """The submission application (this application)."""

    agent_type: str = field(default_factory=str)
    agent_identifier: str = field(default_factory=str)
    username: str = field(default_factory=str)
    hostname: str = field(default_factory=str)

    def __post_init__(self):
        """Set derivative fields."""
        super(System, self).__post_init__()
        self.username = self.native_id
        self.hostname = self.native_id
        self.agent_type = self.get_agent_type()


@dataclass
class Client(Agent):
    """A non-human third party, usually an API client."""

    hostname: Optional[str] = field(default=None)
    """Hostname or IP address from which client requests are originating."""

    agent_type: str = field(default_factory=str)
    agent_identifier: str = field(default_factory=str)

    def __post_init__(self):
        """Set derivative fields."""
        self.agent_type = self.get_agent_type()


_agent_types = {
    User.get_agent_type(): User,
    System.get_agent_type(): System,
    Client.get_agent_type(): Client,
}


def agent_factory(**data: Union[Agent, dict]) -> Agent:
    """Instantiate a subclass of :class:`.Agent`."""
    if isinstance(data, Agent):
        return data
    agent_type = data.pop('agent_type')
    native_id = data.pop('native_id')
    if not agent_type or not native_id:
        raise ValueError('No such agent: %s, %s' % (agent_type, native_id))
    if agent_type not in _agent_types:
        raise ValueError(f'No such agent type: {agent_type}')
    klass = _agent_types[agent_type]
    data = {k: v for k, v in data.items() if k in klass.__dataclass_fields__}
    return klass(native_id, **data)
