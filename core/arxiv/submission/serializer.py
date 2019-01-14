from typing import Any
import json
from datetime import datetime

from .domain import Event, event_factory, Submission, Agent, agent_factory


class EventJSONEncoder(json.JSONEncoder):
    """Encodes domain objects in this package for serialization."""

    def default(self, obj):
        """Look for domain objects, and use their dict-coercion methods."""
        if isinstance(obj, Event):
            data = obj.to_dict()
            data['__type__'] = 'event'
        elif isinstance(obj, Submission):
            data = obj.to_dict()
            data['__type__'] = 'submission'
        elif isinstance(obj, Agent):
            data = obj.to_dict()
            data['__type__'] = 'agent'
        else:
            return json.JSONEncoder.default(self, obj)


def event_decoder(obj: dict) -> Any:
    """Decode domain objects in this package."""
    if '__type__' in obj:
        if obj['__type__'] == 'event':
            return event_factory(obj['event_type'], **obj)
        elif obj['__type__'] == 'submission':
            return Submission.from_dict(**obj)
        elif obj['__type__'] == 'agent':
            return agent_factory(obj['agent_type'], **obj)
    return obj


def dumps(obj: Any) -> str:
    """Generate JSON from a Python object."""
    return json.dumps(obj, cls=EventJSONEncoder)


def loads(data: str) -> Any:
    """Load a Python object from JSON."""
    return json.loads(data, object_hook=event_decoder)
