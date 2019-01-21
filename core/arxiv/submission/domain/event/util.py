"""Helpers for event classes."""

from typing import Any

from dataclasses import dataclass as base_dataclass


def event_hash(instance: Any) -> int:
    """Use event ID as object hash."""
    return hash(instance.event_id)  # typing: ignore


def event_eq(instance: Any, other: Any) -> bool:
    """Compare this event to another event."""
    return hash(instance) == hash(other)


def dataclass(**kwargs) -> type:
    def inner(cls):
        if kwargs:
            new_cls = base_dataclass(**kwargs)(cls)
        else:
            new_cls = base_dataclass(cls)
        setattr(new_cls, '__hash__', event_hash)
        setattr(new_cls, '__eq__', event_eq)
        return new_cls
    return inner
