"""
Provides on-the-fly versioned migrations for event data.

The purpose of this module is to facilitate backwards-compatible changes to
the structure of :class:`.domain.event.Event` classes. This problem is similar
to database migrations, except that the "meat" of the event data are dicts
stored as JSON and thus ALTER commands won't get us all that far.

Writing version mappings
========================
Any new version of this software that includes changes to existing
event/command classes that would break events from earlier versions **MUST**
include a version mapping module. The module should include a mapping class
(a subclass of :class:`.BaseVersionMapping`) for each event type for which
there are relevant changes.

See :mod:`.versioning.version_0_0_0_example` for an example.
"""

import copy
from ._base import EventData, BaseVersionMapping, Version

from arxiv.base.globals import get_application_config


def map_to_version(original: EventData, target: str) -> EventData:
    """
    Map raw event data to a later version.

    Loads all version mappings for the original event type subsequent to the
    version of the software at which the data was created, up to and
    includiong the ``target`` version.

    Parameters
    ----------
    original : dict
        Original event data.
    target : str
        The target software version. Must be a valid semantic version, i.e.
        with major, minor, and patch components.

    Returns
    -------
    dict
        Data from ``original`` transformed into a representation suitable for
        use in the target software version.

    """
    original_version = Version.from_event_data(original)
    transformed = copy.deepcopy(original)
    for mapping in BaseVersionMapping.__subclasses__():
        if original['event_type'] == mapping.Meta.event_type \
                and Version(mapping.Meta.event_version) <= Version(target) \
                and Version(mapping.Meta.event_version) > original_version:
            mapper = mapping()
            transformed = mapper(transformed)
    return transformed


def map_to_current_version(original: EventData) -> EventData:
    """
    Map raw event data to the current software version.

    Relies on the ``CORE_VERSION`` parameter in the application configuration.

    Parameters
    ----------
    original : dict
        Original event data.

    Returns
    -------
    dict
        Data from ``original`` transformed into a representation suitable for
        use in the current software version.

    """
    current_version = get_application_config().get('CORE_VERSION', '0.0.0')
    return map_to_version(original, current_version)
