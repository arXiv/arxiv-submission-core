"""
An example version mapping module.

This module gathers together all event mappings for version 0.0.0.

The mappings in this module will never be used, since there are no
data prior to version 0.0.0.
"""
from typing import Tuple
from ._base import BaseVersionMapping, EventData

VERSION = '0.0.0'


class SetTitleExample(BaseVersionMapping):
    """Perform no changes whatsoever to the `title` field."""

    class Meta:
        """Metadata about this mapping."""

        event_version = VERSION
        """All of the mappings in this module are for the same version."""

        event_type = 'SetTitle'
        """This mapping applies to :class:`.domain.event.SetTitle`."""

        tests = [
            ({'event_version': '0.0.0', 'title': 'The title'},
             {'event_version': '0.0.0', 'title': 'The best title!!'})
        ]
        """Expected changes to the ``title`` field."""

    def transform_title(self, orig: EventData, key: str, val: str) \
            -> Tuple[str, str]:
        """Make the title the best."""
        parts = val.split()
        return key, " ".join([parts[0], "best"] + parts[1:])

    def transform(self, orig: EventData, xf: EventData) -> EventData:
        """Add some emphasis."""
        return {k: f"{v}!!" for k, v in xf.items() if type(v) is str}
