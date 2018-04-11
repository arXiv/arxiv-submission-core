"""
Data handling logic for submission data payload.

Each handler (a function) should accept two parameters:

- ``data`` is the value of the field that it handles. This can be anything that
  is deserializable from a JSON document.
- ``agents`` is a dict with the ``creator``, ``proxy``, and ``client`` agents
  to use when creating new events.

The primary controller in this module is the :func:`.handle_submission`, which
delegates work to the handlers. The global ``HANDLERS`` defined at the end of
this module describes how delegation should occur.
"""
from typing import Tuple, Optional, Dict, Callable, List

import events


def handle_submission(data: dict, agents: dict) -> Tuple[events.Event]:
    """Handle the submission payload."""
    _events = []
    for key_path, handler in HANDLERS:
        value = data
        for key in key_path:
            if key not in value:
                value = None
                break
            value = value[key]
        if value is None:
            continue
        new_events = handler(value, agents)
        if new_events is not None:
            _events += new_events
    return tuple(_events)


def handle_submitter_is_author(data: bool, agents: dict) \
        -> Tuple[events.Event]:
    """Handle the ``submitter_is_author`` field in submission payload."""
    return events.AssertAuthorship(**agents, submitter_is_author=data),


def handle_license(data: dict, agents: dict) -> Tuple[events.Event]:
    """Handle the ``license`` field in submission payload."""
    return events.SelectLicense(
        **agents,
        license_name=data.get('name', ''),
        license_uri=data['uri']
    ),


def handle_submitter_accepts_policy(data: dict, agents: dict) \
        -> Optional[Tuple[events.Event]]:
    """Handle the ``submitter_accepts_policy field in submission payload."""
    if data:
        return events.AcceptPolicy(**agents),
    return


def handle_primary_classification(data: dict, agents: dict) \
        -> Optional[Tuple[events.Event]]:
    """Handle the ``primary_classification`` field in submission payload."""
    return events.SetPrimaryClassification(
        **agents,
        category=data['category']
    ),


def handle_secondary_classification(data: list, agents: dict) \
        -> Optional[Tuple[events.Event]]:
    """Handle the ``secondary_classification`` field in submission payload."""
    return tuple([
        events.AddSecondaryClassification(**agents, category=clsn['category'])
        for clsn in data
    ])


def handle_metadata(data: dict, agents: dict) -> Optional[Tuple[events.Event]]:
    """Handle the ``metadata`` field in the submission payload."""
    # Most of this could be in a list comprehension, but it may help to
    # keep this verbose in case we want to intervene on values.
    _metadata = []
    for key in events.UpdateMetadata.FIELDS:
        if key not in data:
            continue
        _metadata.append((key, data[key]))
    return events.UpdateMetadata(**agents, metadata=_metadata),


def handle_authors(data: dict, agents: dict) -> Optional[Tuple[events.Event]]:
    """Handle authors in the submission payload."""
    _authors = []
    for i, au in enumerate(data):
        if 'order' not in au:
            au['order'] = i
        _authors.append(events.Author(**au))
    return events.UpdateAuthors(**agents, authors=_authors),


HANDLERS: List[Tuple[Tuple[str], Callable]] = [
    (('submitter_is_author', ), handle_submitter_is_author),
    (('license', ), handle_license),
    (('submitter_accepts_policy', ), handle_submitter_accepts_policy),
    (('primary_classification', ), handle_primary_classification),
    (('secondary_classification', ), handle_secondary_classification),
    (('metadata', ), handle_metadata),
    (('metadata', 'authors'), handle_authors)
]
"""
Describes how data in the payload should be handled.

Each item is a two-tuple, defining the key-path to some data in the
submission payload and the handler function that should be applied.

A key-path is a tuple of keys to be applied recursively to access the data.
E.g. the key-path ``('metadata', 'authors')`` will access
``payload['metadata']['authors']`` and pass the referent to the corresponding
handler.
"""
