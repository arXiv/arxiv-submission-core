"""JSON serialization for submission core."""

from typing import Any, Union, List
import json
from datetime import datetime, date
from importlib import import_module
from .domain import Event, event_factory, Submission, Agent, agent_factory


# TODO: get rid of this when base-0.13 is available.
class ISO8601JSONEncoder(json.JSONEncoder):
    """Renders date and datetime objects as ISO8601 datetime strings."""

    def default(self, obj: Any) -> Union[str, List[Any]]:
        """Overriden to render date(time)s in isoformat."""
        try:
            if isinstance(obj, (date, datetime)):
                return obj.isoformat()
            iterable = iter(obj)
        except TypeError:
            pass
        else:
            return list(iterable)
        return json.JSONEncoder.default(self, obj)  # type: ignore


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
        else:
            data = super(EventJSONEncoder, self).default(obj)
        return data


def event_decoder(obj: dict) -> Any:
    """Decode domain objects in this package."""
    if '__type__' in obj:
        type_name = obj.pop('__type__')
        if type_name == 'event':
            return event_factory(obj.pop('event_type'), **obj)
        elif type_name == 'submission':
            return Submission.from_dict(**obj)
        elif type_name == 'agent':
            return agent_factory(obj.pop('agent_type'), **obj)
        elif type_name == 'type':
            # Supports deserialization of Event classes.
            #
            # This is fairly dangerous, since we are importing and calling
            # an arbitrary object specified in data. We need to be sure to
            # check that the object originates in this package, and that it is
            # actually a child of Event.
            if not (obj['__module__'].startswith('arxiv.submission')
                    or obj['__module__'].startswith('submission')):
                raise json.decoder.JSONDecodeError(obj['__module__'], pos=0)
            cls = getattr(import_module(obj['__module__']), obj['__name__'])
            if Event not in cls.mro():
                raise json.decoder.JSONDecodeError(obj['__name__'], pos=0)
            return cls
    return obj


def dumps(obj: Any) -> str:
    """Generate JSON from a Python object."""
    return json.dumps(obj, cls=EventJSONEncoder)


def loads(data: str) -> Any:
    """Load a Python object from JSON."""
    return json.loads(data, object_hook=event_decoder)
