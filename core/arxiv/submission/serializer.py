"""JSON serialization for submission core."""

from typing import Any, Union, List
import json
from datetime import datetime, date
from enum import Enum
from importlib import import_module
from .domain import Event, event_factory, Submission, Agent, agent_factory

from arxiv.util.serialize import ISO8601JSONDecoder, ISO8601JSONEncoder


class EventJSONEncoder(ISO8601JSONEncoder):
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
        elif isinstance(obj, type):
            data = {}
            data['__module__'] = obj.__module__
            data['__name__'] = obj.__name__
            data['__type__'] = 'type'
        elif isinstance(obj, Enum):
            data = obj.value
        else:
            data = super(EventJSONEncoder, self).default(obj)
        return data


class EventJSONDecoder(ISO8601JSONDecoder):
    """Decode :class:`.Event` and other domain objects from JSON data."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Pass :func:`object_hook` to the base constructor."""
        kwargs['object_hook'] = kwargs.get('object_hook', self.object_hook)
        super(EventJSONDecoder, self).__init__(*args, **kwargs)

    def object_hook(self, obj: dict, **extra: Any) -> Any:
        """Decode domain objects in this package."""
        obj = super(EventJSONDecoder, self).object_hook(obj, **extra)

        if '__type__' in obj:
            type_name = obj.pop('__type__')
            if type_name == 'event':
                return event_factory(**obj)
            elif type_name == 'submission':
                return Submission.from_dict(**obj)
            elif type_name == 'agent':
                return agent_factory(obj.pop('agent_type'), **obj)
            elif type_name == 'type':
                # Supports deserialization of Event classes.
                #
                # This is fairly dangerous, since we are importing and calling
                # an arbitrary object specified in data. We need to be sure to
                # check that the object originates in this package, and that it
                # is actually a child of Event.
                module_name = obj['__module__']
                if not (module_name.startswith('arxiv.submission')
                        or module_name.startswith('submission')):
                    raise json.decoder.JSONDecodeError(module_name, pos=0)
                cls = getattr(import_module(module_name), obj['__name__'])
                if Event not in cls.mro():
                    raise json.decoder.JSONDecodeError(obj['__name__'], pos=0)
                return cls
        return obj


def dumps(obj: Any) -> str:
    """Generate JSON from a Python object."""
    return json.dumps(obj, cls=EventJSONEncoder)


def loads(data: str) -> Any:
    """Load a Python object from JSON."""
    return json.loads(data, cls=EventJSONDecoder)
