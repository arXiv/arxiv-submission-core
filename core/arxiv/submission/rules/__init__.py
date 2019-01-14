"""
Defines QA rules bound to events.

These are callback routines that are performed either in-thread or
asynchronously by the submission worker when an event is committed. See
:mod:`arxiv.submission.domain.event` for mechanics.

Callbacks are organized into submodules based on the events to which they
are bound. This is purely for convenience.
"""

from . import set_title
