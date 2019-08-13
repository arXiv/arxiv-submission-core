"""Provides :class:`.BaseVersionMapping`."""

from typing import Optional, Callable, Any, Tuple
from datetime import datetime
from mypy_extensions import TypedDict
import semver


class EventData(TypedDict, total=False):
    """Raw event data from the event store."""

    event_version: str
    created: datetime
    event_type: str


class Version(str):
    """A semantic version."""

    @classmethod
    def from_event_data(cls, data: EventData) -> 'Version':
        """Create a :class:`.Version` from :class:`.EventData`."""
        return cls(data['event_version'])

    def __eq__(self, other: object) -> bool:
        """Equality comparison using semantic versioning."""
        if not isinstance(other, str):
            return NotImplemented
        return bool(semver.compare(self, other) == 0)

    def __lt__(self, other: object) -> bool:
        """Less-than comparison using semantic versioning."""
        if not isinstance(other, str):
            return NotImplemented
        return bool(semver.compare(self, other) < 0)

    def __le__(self, other: object) -> bool:
        """Less-than-equals comparison using semantic versioning."""
        if not isinstance(other, str):
            return NotImplemented
        return bool(semver.compare(self, other) <= 0)

    def __gt__(self, other: object) -> bool:
        """Greater-than comparison using semantic versioning."""
        if not isinstance(other, str):
            return NotImplemented
        return bool(semver.compare(self, other) > 0)

    def __ge__(self, other: object) -> bool:
        """Greater-than-equals comparison using semantic versioning."""
        if not isinstance(other, str):
            return NotImplemented
        return bool(semver.compare(self, other) >= 0)


FieldTransformer = Callable[[EventData, str, Any], Tuple[str, Any]]


class BaseVersionMapping:
    """Base class for version mappings."""

    _protected = ['event_type', 'event_version', 'created']

    class Meta:
        event_version = None
        event_type = None

    def __init__(self) -> None:
        """Verify that the instance has required metadata."""
        if not hasattr(self, 'Meta'):
            raise NotImplementedError('Missing `Meta` on child class')
        if getattr(self.Meta, 'event_version', None) is None:
            raise NotImplementedError('Missing version on child class')
        if getattr(self.Meta, 'event_type', None) is None:
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
        tx: Optional[FieldTransformer] \
            = getattr(self, f'transform_{field}', None)
        return tx

    def transform(self, orig: EventData, xf: EventData) -> EventData:
        """Transform the event data as a whole."""
        return xf  # Nothing to do; subclasses can reimplement for fun/profit.

    def _transform(self, original: EventData) -> EventData:
        """Perform transformation of event data."""
        transformed = EventData()
        for key, value in original.items():
            if key not in self._protected:
                field_transformer = self._get_field_transformer(key)
                if field_transformer is not None:
                    key, value = field_transformer(original, key, value)
            # Mypy wants they key to be a string literal here, which runs
            # against the pattern implemented here. We could consider not
            # using a TypedDict. This code is correct for now, just not ideal
            # for type-checking.
            transformed[key] = value    # type: ignore
        transformed = self.transform(original, transformed)
        assert self.Meta.event_version is not None
        transformed['event_version'] = self.Meta.event_version
        return transformed
