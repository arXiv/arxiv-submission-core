"""
Defines QA rules bound to events.

These are callback routines that are performed either in-thread or
asynchronously by the submission worker when an event is committed. See
:func:`.domain.Event.bind` for mechanics.

Binding callbacks (and registering tasks with :func:`.tasks.is_async`)
relies on decorators; this means that the registration is a side-effect of
importing the module in which they are defined. In other words, it is necessary
that any modules that define rules are imported here.
"""

# Importing these modules causes their callbacks to be registered with their
# respective events, and (if they are asynchronous) with the submission worker.
from . import classification_and_content, metadata_checks, reclassification, \
    compilation, size_limits, email_notifications
