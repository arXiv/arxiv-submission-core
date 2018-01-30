"""Data structures for agents."""

import hashlib
from typing import Any
from .data import Data, Property

__all__ = ('Agent', 'UserAgent', 'System', 'Client', 'agent_factory')


class Agent(Data):
    """
    Base class for agents in the submission system.

    An agent is an actor/system that generates/is responsible for events.
    """

    native_id = Property('native_id', object)
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
        return agent_factory(agent_type, native_id)

    def __eq__(self, other: Any) -> bool:
        """Equality comparison for agents based on type and identifier."""
        if not isinstance(other, self.__class__):
            return False
        return self.agent_identifier == other.agent_identifier


class UserAgent(Agent):
    """An (human) end user."""

    pass


# TODO: extend this to support arXiv-internal services.
class System(Agent):
    """The submission application (this application)."""

    pass


class Client(Agent):
    """A non-human third party, usually an API client."""

    pass


_agent_types = {
    UserAgent.get_agent_type(): UserAgent,
    System.get_agent_type(): System,
    Client.get_agent_type(): Client,
}


def agent_factory(agent_type: str, native_id: Any) -> Agent:
    """Instantiate a subclass of :class:`.Agent`."""
    if agent_type not in _agent_types:
        raise ValueError('No such agent type.')
    return _agent_types[agent_type](native_id=native_id)
