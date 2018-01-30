from datetime import datetime
import copy
from typing import Tuple, Dict, Any, Optional
from events.domain import SubmissionMetadata, Submission, License, \
    Classification, Event, Agent, event_factory, agent_factory


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
    """
    Cast a :class:`.Submission` to dict for serialization.

    Parameters
    ----------
    submission : :class:`.Submission`

    Returns
    -------
    dict
    """
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


def serialize_event(event: Event) -> Dict[str, Any]:
    """
    Cast an :class:`.Event` to dict for serialization.

    Parameters
    ----------
    event : :class:`.Event`

    Returns
    -------
    dict
    """
    event_data: Dict[str, Any] = event.to_dict()
    if event.proxy:
        event_data.update({'proxy': serialize_agent(event.proxy)})
    event_data.update({'creator': serialize_agent(event.creator)})
    event_data.update({
        'submission_id': str(event.submission_id),
        'event_id': event.event_id
    })
    return event_data


def _get_agents(extra: dict) -> Tuple[Optional[Agent], Optional[Agent]]:
    """
    Get user and/or API client responsible for the request.

    Parameters
    ----------
    extra : dict

    Returns
    -------
    :class:`Agent`
        User agent. If no user is involved, this will be identical to the
        client agent.
    :class:`Agent`
        Client agent.
    """
    user = extra.get('user')
    client = extra.get('client')
    user_agent = agent_factory('UserAgent', user) if user else None
    client_agent = agent_factory('Client', client) if client else None
    if user_agent:
        return user_agent, client_agent
    return client_agent, client_agent
