"""
Provides integration with the submission events controller backend service.
"""

import requests
from requests.packages.urllib3.util.retry import Retry

import time
from typing import Callable, Optional, Any
import json
from functools import wraps
from urllib.parse import urljoin
import logging

from werkzeug.local import LocalProxy

from api.domain import Submission, Agent, agent_factory
from api.context import get_application_config, get_application_global

from arxiv import status

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class NotFound(ValueError):
    """Raised when a 404 status code is received from the event service."""


class BadRequest(ValueError):
    """Raised when a 400 status code is received from the event service."""


class ServiceDown(IOError):
    """Raised when there is ap roblem connecting to the event service."""


class SubmissionEventsController(object):
    def __init__(self, endpoint: str) -> None:
        """Create a new HTTP session."""
        self.endpoint = endpoint
        self._session = requests.Session()
        self._retry = Retry(
            total=10,
            read=10,
            connect=10,
            status=10,
            backoff_factor=0.5
        )
        self._adapter = requests.adapters.HTTPAdapter(max_retries=self._retry)
        self._session.mount('http://', self._adapter)
        self._session.mount('https://', self._adapter)

    def _deserialize_agent(agent_data: dict) -> Agent:
        return agent_factory(agent_data['agent_type'], agent_data['native_id'])

    @staticmethod
    def _handle(response: requests.models.Response) -> dict:
        logger.debug('Handle response: %i', response.status_code)
        if response.status_code == status.HTTP_404_NOT_FOUND:
            raise NotFound('No such resource: %s' % response.content)
        if response.status_code == status.HTTP_400_BAD_REQUEST:
            raise BadRequest('Bad request: %s' % response.content)
        try:
            data = response.json()
            logger.debug('with data: %s', str(data))
            return data
        except json.decoder.JSONDecodeError as e:
            logger.debug('Failed to parse')
            raise IOError('Failed to parse service response: %s' % e) from e

    # TODO: take a closer look at possibly GIL-related connection issues.
    def _post(self, target_path: str, data: dict = {},
              token: Optional[str] = None) -> requests.models.Response:
        """Execute a POST request."""
        logger.debug('POST to %s with data %s', target_path, str(data))
        try:
            response = self._session.post(
                urljoin(self.endpoint, target_path),
                json=data, headers={'Authorization': token}
            )
        except requests.exceptions.ConnectionError as e:
            time.sleep(0.1)    # Wait for a GIL tick. Temporary fix?
            try:
                response = self._session.post(
                    urljoin(self.endpoint, target_path),
                    json=data, headers={'Authorization': token}
                )
            except requests.exceptions.ConnectionError as e:
                raise ServiceDown(
                    'Could not connect to submission event service: %s' % e
                ) from e
        return response

    def _method(self, method: str, submission_id: str, data: dict = {},
                token: Optional[str] = None) -> requests.models.Response:
        return self._post(
            f'/events/submission/{submission_id}/{method}/',
            data=data, token=token
        )

    def create_submission(self, token: Optional[str] = None) -> Submission:
        """Create a new submission."""
        response = self._post('/events/create_submission/', token=token)
        return Submission(**self._handle(response))

    def update_metadata(self, submission_id: str, metadata: list,
                        token: Optional[str] = None) -> Submission:
        """Update the metadata on a submission."""
        data = {'metadata': metadata}
        response = self._method('update_metadata', submission_id,
                                data=data, token=token)
        return Submission(**self._handle(response))

    def assert_authorship(self, submission_id: str, is_author: bool,
                          token: Optional[str] = None) -> Submission:
        """Indicate whether or not the submitter is an author."""
        data = {'submitter_is_author': is_author}
        response = self._method('assert_authorship', submission_id,
                                data=data, token=token)
        return Submission(**self._handle(response))

    def accept_policy(self, submission_id: str, token: Optional[str] = None) \
            -> Submission:
        """Indicate that the submitter accepts arXiv policies."""
        response = self._method('accept_policy', submission_id, token=token)
        return Submission(**self._handle(response))

    def set_primary_classification(self, submission_id: str, category: str,
                                   token: Optional[str] = None) -> Submission:
        """Set the primary classification on the submission."""
        response = self._method('set_primary_classification', submission_id,
                                data={'category': category}, token=token)
        return Submission(**self._handle(response))

    def add_secondary_classification(self, submission_id: str, category: str,
                                     token: Optional[str] = None)\
            -> Submission:
        """Set the primary classification on the submission."""
        response = self._method('add_secondary_classification', submission_id,
                                data={'category': category}, token=token)
        return Submission(**self._handle(response))


def init_app(app: Optional[LocalProxy] = None) -> None:
    """
    Set required configuration defaults for the application.

    Parameters
    ----------
    app : :class:`werkzeug.local.LocalProxy`
    """
    if app is not None:
        app.config.setdefault('EVENTS_ENDPOINT',
                              'https://localhost:8000/events/')


def get_session(app: Optional[LocalProxy] = None) \
        -> SubmissionEventsController:
    """
    Create a new SubmissionEventsController session.

    Parameters
    ----------
    app : :class:`werkzeug.local.LocalProxy`

    Return
    ------
    :class:`.BazServiceSession`
    """
    config = get_application_config(app)
    return SubmissionEventsController(config.get('EVENTS_ENDPOINT'))


def current_session(app: Optional[LocalProxy] = None) \
        -> SubmissionEventsController:
    """
    Get the current SubmissionEventsController for this context.

    Parameters
    ----------
    app : :class:`werkzeug.local.LocalProxy`

    Return
    ------
    :class:`.SubmissionEventsController`

    """
    g = get_application_global()
    if g:
        if 'events' not in g:
            g.events = get_session(app)  # type: ignore
        return g.events  # type: ignore
    return get_session(app)


@wraps(SubmissionEventsController.create_submission)
def create_submission(token: Optional[str] = None) -> Submission:
    """Create a new submission."""
    return current_session().create_submission(token)


@wraps(SubmissionEventsController.update_metadata)
def update_metadata(submission_id: str, metadata: list,
                    token: Optional[str] = None) -> Submission:
    """Update the metadata on a submission."""
    return current_session().update_metadata(submission_id, metadata, token)


@wraps(SubmissionEventsController.assert_authorship)
def assert_authorship(submission_id: str, is_author: bool,
                      token: Optional[str] = None) -> Submission:
    """Indicate whether or not the submitter is an author."""
    return current_session().assert_authorship(submission_id, is_author, token)


@wraps(SubmissionEventsController.accept_policy)
def accept_policy(submission_id: str, token: Optional[str] = None) \
        -> Submission:
    """Indicate that the submitter accepts arXiv policies."""
    return current_session().accept_policy(submission_id, token)


@wraps(SubmissionEventsController.set_primary_classification)
def set_primary_classification(submission_id: str, category: str,
                               token: Optional[str] = None) -> Submission:
    """Set the primary classification on the submission."""
    return current_session().set_primary_classification(
        submission_id, category, token
    )


@wraps(SubmissionEventsController.add_secondary_classification)
def add_secondary_classification(submission_id: str, category: str,
                                 token: Optional[str] = None) -> Submission:
    """Set the primary classification on the submission."""
    return current_session().add_secondary_classification(
        submission_id, category, token
    )
