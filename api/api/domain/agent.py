"""Data structures for agents."""

import hashlib
from typing import Any
from api.domain import Data, Property


class Agent(Data):
    """
    Base class for agents in the submission system.

    An agent is an actor/system that generates/is responsible for events.
    """

    native_id = Property('native_id', object)
    """Type-specific identifier for the agent. This might be an URI."""

    @property
    def agent_type(self):
        return self.get_agent_type()

    @classmethod
    def get_agent_type(cls):
        return cls.__name__

    @property
    def agent_identifier(self):
        h = hashlib.new('sha1')
        h.update(b'%s:%s' % (self.agent_type.encode('utf-8'),
                             str(self.native_id).encode('utf-8')))
        return h.hexdigest()

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Agent):
            return False
        return self.agent_identifier == other.agent_identifier


class User(Agent):
    """An (human) end user, whom generally acts via form-based interfaces."""

    pass


class System(Agent):
    """The submission application (this application)."""

    pass


class Client(Agent):
    """A non-human third party, usually an API client."""

    pass


_agent_types = {
    User.get_agent_type(): User,
    System.get_agent_type(): System,
    Client.get_agent_type(): Client,
}


def agent_factory(agent_type: str, native_id: Any) -> Agent:
    """Instantiate a subclass of :class:`.Agent`."""
    if agent_type not in _agent_types:
        raise ValueError('No such agent type.')
    return _agent_types[agent_type](native_id=native_id)
