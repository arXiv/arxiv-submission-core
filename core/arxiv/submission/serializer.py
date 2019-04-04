"""JSON serialization for submission core."""

from typing import Any, Union, List
import json
from json.decoder import JSONDecodeError
from datetime import datetime, date
from dataclasses import asdict
from enum import Enum
from importlib import import_module
from .domain import Event, event_factory, Submission, Agent, agent_factory

from arxiv.util.serialize import ISO8601JSONEncoder
from backports.datetime_fromisoformat import MonkeyPatch
MonkeyPatch.patch_fromisoformat()


# The base implementation of this decoder is too generous; we'll use this until
# base gets updated.
class ISO8601JSONDecoder(json.JSONDecoder):
    """Attempts to parse ISO8601 strings as datetime objects."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Pass :func:`object_hook` to the base constructor."""
        kwargs['object_hook'] = kwargs.get('object_hook', self.object_hook)
        super(ISO8601JSONDecoder, self).__init__(*args, **kwargs)

    def _try_isoparse(self, value: Any) -> Any:
        """Attempt to parse a value as an ISO8601 datetime."""
        if type(value) is not str:
            return value
        try:
            return datetime.fromisoformat(value)  # type: ignore
        except ValueError:
            return value

    def object_hook(self, data: dict, **extra: Any) -> Any:
        """Intercept and coerce ISO8601 strings to datetimes."""
        for key, value in data.items():
            if type(value) is list:
                data[key] = [self._try_isoparse(v) for v in value]
            else:
                data[key] = self._try_isoparse(value)
        return data


class EventJSONEncoder(ISO8601JSONEncoder):
    """Encodes domain objects in this package for serialization."""

    def default(self, obj):
        """Look for domain objects, and use their dict-coercion methods."""
        if isinstance(obj, Event):
            data = asdict(obj)
            data['__type__'] = 'event'
        elif isinstance(obj, Submission):
            data = asdict(obj)
            data.pop('before', None)
            data.pop('after', None)
            data['__type__'] = 'submission'
        elif isinstance(obj, Agent):
            data = asdict(obj)
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
            if obj['__type__'] == 'event':
                obj.pop('__type__')
                return event_factory(**obj)
            elif obj['__type__'] == 'submission':
                obj.pop('__type__')
                return Submission(**obj)
            elif obj['__type__'] == 'agent':
                obj.pop('__type__')
                return agent_factory(**obj)
            elif obj['__type__'] == 'type':
                # Supports deserialization of Event classes.
                #
                # This is fairly dangerous, since we are importing and calling
                # an arbitrary object specified in data. We need to be sure to
                # check that the object originates in this package, and that it
                # is actually a child of Event.
                module_name = obj['__module__']
                if not (module_name.startswith('arxiv.submission')
                        or module_name.startswith('submission')):
                    raise JSONDecodeError(module_name, '', pos=0)
                cls = getattr(import_module(module_name), obj['__name__'])
                if Event not in cls.mro():
                    raise JSONDecodeError(obj['__name__'], '', pos=0)
                return cls
        return obj


def dumps(obj: Any) -> str:
    """Generate JSON from a Python object."""
    return json.dumps(obj, cls=EventJSONEncoder)


def loads(data: str) -> Any:
    """Load a Python object from JSON."""
    return json.loads(data, cls=EventJSONDecoder)
