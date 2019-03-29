"""JSON serialization for submission core."""

from typing import Any, Union, List
import json
from datetime import datetime, date
from dataclasses import asdict
from enum import Enum
from importlib import import_module
from .domain import Trigger, ProcessData

from arxiv.submission.serializer import EventJSONEncoder, EventJSONDecoder


class ProcessJSONEncoder(EventJSONEncoder):
    """Encodes domain objects in this package for serialization."""

    def default(self, obj):
        """Serialize objects in this application domain."""
        if type(obj) is Trigger:
            data = {'__type__': 'Trigger',
                    '__data__': asdict(obj)}
        elif type(obj) is ProcessData:
            data = {'__type__': 'ProcessData',
                    '__data__': asdict(obj)}
        else:
            data = super(ProcessJSONEncoder, self).default(obj)
        return data


class ProcessJSONDecoder(EventJSONDecoder):
    """Decode :class:`.Trigger` and other domain objects from JSON data."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Pass :func:`object_hook` to the base constructor."""
        kwargs['object_hook'] = kwargs.get('object_hook', self.object_hook)
        super(ProcessJSONDecoder, self).__init__(*args, **kwargs)

    def object_hook(self, obj: dict, **extra: Any) -> Any:
        """Decode domain objects in this package."""
        if '__type__' in obj:
            if obj['__type__'] == 'Trigger':
                return Trigger(**obj['__data__'])
            elif obj['__type__'] == 'ProcessData':
                return ProcessData(**obj['__data__'])
        return super(ProcessJSONDecoder, self).object_hook(obj, **extra)


def dumps(obj: Any) -> str:
    """Generate JSON from a Python object."""
    return json.dumps(obj, cls=ProcessJSONEncoder)


def loads(data: str) -> Any:
    """Load a Python object from JSON."""
    return json.loads(data, cls=ProcessJSONDecoder)
