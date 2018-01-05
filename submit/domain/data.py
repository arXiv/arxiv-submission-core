"""Provides base classes for data and their properties."""

from datetime import datetime
from typing import Any
import hashlib
import copy
from typing import TypeVar, Type, Generator


def _coerce(obj: Any) -> Any:
    if isinstance(obj, Data):
        return obj.to_dict()
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj


class Property(object):
    """Describes a named, typed property on a data structure."""

    def __init__(self, name: str, klass: Type = None,
                 default: Any = None, null: bool = False) -> None:
        """Set the name, type, and default value for the property."""
        self._name = name
        self.klass = klass
        self.default = default
        self.nullable = null

    def __get__(self, instance: Any, owner: type = None) -> Any:
        """
        Retrieve the value of property from the data instance.

        Parameters
        ----------
        instance : object
            The data structure instance on which the property is set.
        owner : type
            The class/type of ``instance``.

        Returns
        -------
        object
            If the data structure is instantiated, returns the value of this
            property. Otherwise returns this :class:`.Property` instance.
        """
        if instance:
            if self._name not in instance.__dict__:
                instance.__dict__[self._name] = self.default
            return instance.__dict__[self._name]
        return self

    def __set__(self, instance: Any, value: Any):
        """
        Set the value of the property on the data instance.

        Parameters
        ----------
        instance : object
            The data structure instance on which the property is set.
        value : object
            The value to which the property should be set.

        Raises
        ------
        TypeError
            Raised when ``value`` is not an instance of the specified type
            for the property.
        """
        if not self.nullable and self.klass is not None \
                and not isinstance(value, self.klass):
            raise TypeError('Must be an %s' % self.klass.__name__)
        instance.__dict__[self._name] = value


DataType = TypeVar('DataType', bound='Data')


class Data(object):
    """Base class for submission system domain data."""

    def __init__(self, **data) -> None:
        """Instantiate a :class:`.Data` with some data."""
        self.update_from_dict(data)

    def to_dict(self) -> dict:
        """
        Create a dict representation of the :class:`.Data` instance.

        Recursively converts child :class:`.Data` instances to their dict
        representation.

        Returns
        -------
        dict
        """
        return {
            attr: _coerce(getattr(self, attr))
            for attr in dir(self.__class__)
            if isinstance(getattr(self.__class__, attr), Property)
        }

    @classmethod
    def _assert_valid(cls, key: str, prop: Property, data: dict) -> None:
        if key not in data and prop.default is None:
            raise KeyError('Missing key %s in data' % key)

    @classmethod
    def _value_from_dict(cls, key: str, value: Any, prop: Property,
                         err_missing: bool) -> Any:
        if isinstance(value, dict):
            try:    # Assignment won't occur if an exception is raised.
                return prop.klass.from_dict(value)
            except KeyError as e:
                if err_missing:
                    raise
        elif not isinstance(value, prop.klass):
            raise ValueError(
                '%s must be a dict or %s' % (key, prop.klass.__name__)
            )
        return value

    @classmethod
    def _data_to_set(cls: Type[DataType], data: dict,
                     err_missing: bool = True) -> Generator:
        """
        Prepare ``data`` to set attributes on a :class:`.Data` instance.

        Parameters
        ----------
        cls : type
        data : dict
        err_missing : bool
            If True, raises a KeyError if a required attribute is missing.
            (default: True)

        Returns
        -------
        generator
            Yields key, value tuples.

        Raises
        ------
        KeyError
            If a required attribute is not found in data (unless
            ``err_missing == False``).
        ValueError
            If the value of an attribute that expects a :class:`.Data` instance
            is not either such an instance, or a dict.
        """
        for key in dir(cls):
            # We're only interested in setting attrs described by Property.
            prop = getattr(cls, key)
            if not isinstance(prop, Property):
                continue

            # If default is not set on the Property, key is required.
            try:
                cls._assert_valid(key, prop, data)
            except KeyError:
                if err_missing:
                    raise
                continue

            value = data.get(key)
            if value is None:   # Use the default value for this property.
                value = prop.default
            elif prop.klass is not None and issubclass(prop.klass, Data):
                value = cls._value_from_dict(key, value, prop, err_missing)
            yield key, value

    @classmethod
    def from_dict(cls, data: dict) -> Any:
        """
        Instantiate a :class:`.Data` instance from a dict.

        Parameters
        ----------
        cls : type
            The class of this :class:`.Data` instance (probably a subclass).
        data : dict
            Items for which the key is a :class:`.Property` instance on ``cls``
            are used to populate fields on the :class:`.Data` instance.

        Returns
        -------
        :class:`.Data`

        Raises
        ------
        KeyError
            If a required key is not found.
        """
        instance = cls()
        for key, value in cls._data_to_set(data):
            setattr(instance, key, value)
        return instance

    def update_from_dict(self: DataType, data: dict) -> None:
        """
        Update :class:`.Property` instances on this :class:`.Data`.

        Parameters
        ----------
        data : dict
            Items matching :class:`.Property` attributes will be used to set
            those attributes on this :class:`Data` instance.
        """
        for key, value in type(self)._data_to_set(data, err_missing=False):
            setattr(self, key, value)

    def copy(self) -> Any:
        """
        Generate a copy of this instance.

        Returns
        -------
        :class:`.Data`
        """
        return copy.deepcopy(self)
