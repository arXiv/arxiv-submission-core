"""Helper functions for API controllers."""

from datetime import datetime
import copy
from typing import Tuple, Dict, Any, Optional
from api.domain import SubmissionMetadata, Submission, License, \
    Classification, Agent, agent_factory


def serialize_metadata(metadata: Optional[SubmissionMetadata]) -> dict:
    """
    Cast a :class:`.SubmissionMetadata` to dict for serialization.

    Parameters
    ----------
    metadata : :class:`.SubmissionMetadata`

    Returns
    -------
    dict
    """
    if not metadata:
        return {}
    return {
        'title': metadata.title,
        'abstract': metadata.abstract,
        'author': metadata.authors,
        'doi': metadata.doi,
        'msc_class': metadata.msc_class,
        'acm_class': metadata.acm_class,
        'report_num': metadata.report_num,
        'journal_ref': metadata.journal_ref,
    }


def serialize_license(license: Optional[License]) -> Optional[dict]:
    """
    Cast a :class:`.License` to dict for serialization.

    Parameters
    ----------
    license : :class:`.License`

    Returns
    -------
    dict
    """
    if not license:
        return None
    return {
        'uri': license.uri,
        'name': license.name
    }


def serialize_classification(classification: Optional[Classification]) \
        -> Optional[dict]:
    """
    Cast a :class:`.Classification` to dict for serialization.

    Parameters
    ----------
    classification : :class:`.Classification`

    Returns
    -------
    dict
    """
    if not classification:
        return None
    return {
        'category': classification.category
    }


def serialize_agent(agent: Optional[Agent]) -> dict:
    """
    Cast an :class:`.Agent` to dict for serialization.

    Parameters
    ----------
    agent : :class:`.Agent`

    Returns
    -------
    dict
    """
    if agent is None:
        return None
    return {
        'agent_type': agent.agent_type,
        'identifier': agent.agent_identifier,
        'native_id': agent.native_id
    }


def serialize_submission(submission: Submission) -> dict:
    """Generate an external state document from a :class:`.Submission`."""
    return {
        'submission_id': str(submission.submission_id),
        'metadata': serialize_metadata(submission.metadata),
        'submitter_is_author': submission.submitter_is_author,
        'submitter_accepts_policy': submission.submitter_accepts_policy,
        'license': serialize_license(submission.license),
        'primary_classification': (
            serialize_classification(submission.primary_classification)
        ),
        'secondary_classification': [
            serialize_classification(clsxn) for clsxn
            in submission.secondary_classification
        ],
        'active': submission.active,
        'finalized': submission.finalized,
        'published': submission.published,
        'creator': serialize_agent(submission.creator),
        'proxy': serialize_agent(submission.proxy),
        'owner': serialize_agent(submission.owner),
    }


def serialize_event(event) -> dict:
    event_data = {'data': event.to_dict()}
    for field in ['created', 'event_type']:
        if field in event_data['data']:
            event_data[field] = copy.deepcopy(event_data['data'][field])
            del event_data['data'][field]
    if event.proxy:
        event_data['proxy'] = serialize_agent(event.proxy)
        del event_data['data']['proxy']
    event_data['creator'] = serialize_agent(event.creator)
    del event_data['data']['creator']
    event_data['submission_id'] = str(event.submission_id)
    event_data['event_id'] = event.event_id
    return event_data
