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

Note: data validation should not be implemented here! Events/commands in
:mod:`events` should define required parameters, perform all validation,
and carry out any required transformation/cleanup.
"""
from typing import Tuple, Optional, Dict, Callable, List

import events


def handle_submission(data: dict, agents: dict) -> Tuple[events.Event]:
    """
    Handle the submission payload.

    We assume that schema validation has been performed already, so it's not
    up to us to verify the shape of the data.

    Parameters
    ----------
    data : dict
    agents : dict
        Values are :class:`events.Agent` instances.

    Returns
    -------
    tuple
        Zero or more uncommitted :class:`events.Event` instances.
    """
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
        _events += handler(value, agents)
    return tuple(_events)


def handle_submitter_is_author(data: bool, agents: dict) \
        -> Tuple[events.Event]:
    """
    Handle the ``submitter_is_author`` field in submission payload.

    Parameters
    ----------
    data : dict
    agents : dict
        Values are :class:`events.Agent` instances.

    Returns
    -------
    tuple
        Zero or more uncommitted :class:`events.Event` instances.
    """
    return events.AssertAuthorship(**agents, submitter_is_author=data),


def handle_license(data: dict, agents: dict) -> Tuple[events.Event]:
    """Handle the ``license`` field in submission payload."""
    return events.SelectLicense(
        **agents,
        license_name=data.get('name', ''),
        license_uri=data['uri']
    ),


def handle_submitter_accepts_policy(data: dict, agents: dict) \
        -> Tuple[events.Event]:
    """
    Handle the ``submitter_accepts_policy`` field in submission payload.

    Parameters
    ----------
    data : dict
    agents : dict
        Values are :class:`events.Agent` instances.

    Returns
    -------
    tuple
        Zero or more uncommitted :class:`events.Event` instances.
    """
    if data:
        return events.AcceptPolicy(**agents),
    return tuple()


def handle_submitter_contact_verified(data: dict, agents: dict) \
        -> Tuple[events.Event]:
    """
    Handle the ``submitter_contact_verified`` field in submission payload.

    Parameters
    ----------
    data : dict
    agents : dict
        Values are :class:`events.Agent` instances.

    Returns
    -------
    tuple
        Zero or more uncommitted :class:`events.Event` instances.
    """
    if data:
        return events.VerifyContactInformation(**agents),
    return tuple()


def handle_primary_classification(data: dict, agents: dict) \
        -> Optional[Tuple[events.Event]]:
    """Handle the ``primary_classification`` field in submission payload."""
    return events.SetPrimaryClassification(
        **agents,
        category=data['category']
    ),


def handle_secondary_classification(data: list, agents: dict) \
        -> Tuple[events.Event]:
    """
    Handle the ``secondary_classification`` field in submission payload.

    Parameters
    ----------
    data : dict
    agents : dict
        Values are :class:`events.Agent` instances.

    Returns
    -------
    tuple
        Zero or more uncommitted :class:`events.Event` instances.
    """
    return tuple([
        events.AddSecondaryClassification(**agents, category=clsn['category'])
        for clsn in data
    ])


def handle_metadata(data: dict, agents: dict) -> Tuple[events.Event]:
    """
    Handle the ``metadata`` field in the submission payload.

    Parameters
    ----------
    data : dict
    agents : dict
        Values are :class:`events.Agent` instances.

    Returns
    -------
    tuple
        Zero or more uncommitted :class:`events.Event` instances.
    """
    # Most of this could be in a list comprehension, but it may help to
    # keep this verbose in case we want to intervene on values.
    _events = []
    if 'title' in data:
        _events.append(events.SetTitle(**agents, title=data['title']))
    if 'abstract' in data:
        _events.append(events.SetAbstract(**agents, abstract=data['abstract']))
    if 'comments' in data:
        _events.append(events.SetComments(**agents, comments=data['comments']))
    if 'msc_class' in data:
        _events.append(events.SetMSCClassification(
            **agents,
            msc_class=data['msc_class'])
        )
    if 'acm_class' in data:
        _events.append(events.SetACMClassification(
            **agents,
            acm_class=data['acm_class'])
        )
    if 'journal_ref' in data:
        _events.append(events.SetJournalReference(
            **agents,
            journal_ref=data['journal_ref'])
        )
    if 'report_num' in data:
        _events.append(events.SetReportNumber(
            **agents,
            report_num=data['report_num'])
        )
    if 'doi' in data:
        _events.append(events.SetDOI(**agents, doi=data['doi']))

    if not _events:
        return tuple()
    return tuple(_events)


def handle_authors(data: dict, agents: dict) -> Tuple[events.Event]:
    """
    Handle authors in the submission payload.

    Parameters
    ----------
    data : dict
    agents : dict
        Values are :class:`events.Agent` instances.

    Returns
    -------
    tuple
        Zero or more uncommitted :class:`events.Event` instances.
    """
    if not data:
        return tuple()
    _authors = []
    for i, au in enumerate(data):
        if 'order' not in au:
            au['order'] = i
        _authors.append(events.Author(**au))
    return events.UpdateAuthors(**agents, authors=_authors),


def handle_finalization(data: dict, agents: dict) -> Tuple[events.Event]:
    """
    Handle finalization flag in the submission payload.

    Parameters
    ----------
    data : dict
    agents : dict
        Values are :class:`events.Agent` instances.

    Returns
    -------
    tuple
        Zero or more uncommitted :class:`events.Event` instances.
    """
    if data:
        return events.FinalizeSubmission(**agents),
    else:
        return events.UnFinalizeSubmission(**agents),


def handle_source_content(data: dict, agents: dict) -> Tuple[events.Event]:
    """
    Handle source content data in the submission payload.

    Parameters
    ----------
    data : dict
    agents : dict
        Values are :class:`events.Agent` instances.

    Returns
    -------
    tuple
        Zero or more uncommitted :class:`events.Event` instances.
    """
    if not data:
        return tuple()
    return events.AttachSourceContent(
        **agents,
        location=data.get('location'),
        format=data.get('format'),
        checksum=data.get('checksum'),
        mime_type=data.get('mime_type'),
        identifier=data.get('identifier'),
        size=data.get('size'),
    ),


HANDLERS: List[Tuple[Tuple[str], Callable]] = [
    (('submitter_is_author', ), handle_submitter_is_author),
    (('license', ), handle_license),
    (('submitter_accepts_policy', ), handle_submitter_accepts_policy),
    (('submitter_contact_verified', ), handle_submitter_contact_verified),
    (('primary_classification', ), handle_primary_classification),
    (('secondary_classification', ), handle_secondary_classification),
    (('metadata', ), handle_metadata),
    (('metadata', 'authors'), handle_authors),
    (('source_content', ), handle_source_content),
    (('finalized', ), handle_finalization)
]
"""
Describes how data in the payload should be handled.

Each item is a two-tuple, defining the key-path to some data in the
submission payload and the handler function that should be applied.

A key-path is a tuple of keys to be applied recursively to access the data.
E.g. the key-path ``('metadata', 'authors')`` will access
``payload['metadata']['authors']`` and pass the referent to the corresponding
handler.

Extra data in the payload is simply ignored.
"""
