"""
An example version mapping module.

This module gathers together all event mappings for version 0.0.0.

The mappings in this module will never be used, since there are is no
data prior to version 0.0.0.
"""
from ._base import BaseVersionMapping

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
            ({'event_version': '0.0.0', 'title': 'The title!'},
             {'event_version': '0.0.0', 'title': 'The title!'})
        ]
        """No changes should be made to the `title` field."""
