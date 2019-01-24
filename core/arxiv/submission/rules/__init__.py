"""
Defines QA rules bound to events.

These are callback routines that are performed either in-thread or
asynchronously by the submission worker when an event is committed. See
:mod:`arxiv.submission.domain.event` for mechanics.
"""

from . import classification_and_content, metadata_checks, reclassification
