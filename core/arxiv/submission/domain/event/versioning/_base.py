"""Provides :class:`.BaseVersionMapping`."""

from typing import Optional, Callable, Any, Tuple
from datetime import datetime
from mypy_extensions import TypedDict
import semver


class EventData(TypedDict):
    """Raw event data from the event store."""

    _version: str
    created: datetime
    event_type: str


class Version(str):
    """A semantic version."""

    @classmethod
    def from_event_data(cls, data: EventData) -> 'Version':
        """Create a :class:`.Version` from :class:`.EventData`."""
        return cls(data['event_version'])

    def __eq__(self, other: 'Version') -> bool:
        """Equality comparison using semantic versioning."""
        return semver.compare(self, other) == 0

    def __lt__(self, other: 'Version') -> bool:
        """Less-than comparison using semantic versioning."""
        return semver.compare(self, other) < 0

    def __le__(self, other: 'Version') -> bool:
        """Less-than-equals comparison using semantic versioning."""
        return semver.compare(self, other) <= 0

    def __gt__(self, other: 'Version') -> bool:
        """Greater-than comparison using semantic versioning."""
        return semver.compare(self, other) > 0

    def __ge__(self, other: 'Version') -> bool:
        """Greater-than-equals comparison using semantic versioning."""
        return semver.compare(self, other) >= 0


FieldTransformer = Callable[[EventData, str, Any], Tuple[str, Any]]


class BaseVersionMapping:
    """Base class for version mappings."""

    _protected = ['event_type', 'event_version', 'created']

    def __init__(self) -> None:
        """Verify that the instance has required metadata."""
        if not hasattr(self, 'Meta'):
            raise NotImplementedError('Missing `Meta` on child class')
        if not hasattr(self.Meta, 'event_version'):
            raise NotImplementedError('Missing version on child class')
        if not hasattr(self.Meta, 'event_type'):
            raise NotImplementedError('Missing event_type on child class')

    def __call__(self, original: EventData) -> EventData:
        """Transform some :class:`.EventData`."""
        return self._transform(original)

    @classmethod
    def test(cls) -> None:
        """Perform tests on the mapping subclass."""
        try:
            cls()
        except NotImplementedError as e:
            raise AssertionError('Not correctly implemented') from e
        for original, expected in getattr(cls.Meta, 'tests', []):
            assert cls()(original) == expected
        try:
            semver.parse_version_info(cls.Meta.event_version)
        except ValueError as e:
            raise AssertionError('Not a valid semantic version') from e

    def _get_field_transformer(self, field: str) -> Optional[FieldTransformer]:
        """Get a transformation for a field, if it is defined."""
        return getattr(self, f'transform_{field}', None)

    def _transform(self, original: EventData) -> EventData:
        """Perform transformation of event data."""
        transformed = {}
        for key, value in original.items():
            if key not in self._protected:
                field_transformer = self._get_field_transformer(key)
                if field_transformer is not None:
                    key, value = field_transformer(original, key, value)
            transformed[key] = value
        if hasattr(self, 'transform'):
            transformed = self.transform(original, transformed)
        transformed['event_version'] = self.Meta.event_version
        return transformed
