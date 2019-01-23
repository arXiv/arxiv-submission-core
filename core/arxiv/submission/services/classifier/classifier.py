"""Classifier service integration."""

from typing import Tuple, List, Any, Union, NamedTuple, Optional
from math import exp, log
from functools import wraps

from arxiv import status
from arxiv.taxonomy import Category
from arxiv.base.globals import get_application_config, get_application_global

import requests
from requests.packages.urllib3.util.retry import Retry

VERSION = '0.0'
SERVICE = 'classic'


class Flag(NamedTuple):
    """General-purpose QA flag."""

    key: str
    value: Union[int, str, dict]


class Suggestion(NamedTuple):
    """A category suggested by the classifier."""

    category: Category
    probability: int


class Counts(NamedTuple):
    """Various counts of paper content."""

    chars: int
    pages: int
    stops: int
    words: int


class RequestFailed(ConnectionError):
    """The request to the classifier service failed."""


class Classifier(object):
    """Represents an interface to the classifier service."""

    ClassifierResponse = Tuple[List[Suggestion], List[Flag], Optional[Counts]]

    def __init__(self, host: str, port: int) -> None:
        """Set the host and port for the service."""
        self._host = host
        self._port = port
        self._session = requests.Session()
        self._retry = Retry(  # type: ignore
            total=10,
            read=10,
            connect=10,
            status=10,
            backoff_factor=0.5
        )
        self._adapter = requests.adapters.HTTPAdapter(max_retries=self._retry)
        self._session.mount('http://', self._adapter)

    @property
    def endpoint(self):
        """Get the URL of the classifier endpoint."""
        return f'http://{self._host}:{self._port}/ctxt'

    def _probability(self, logodds: float) -> float:
        """Convert log odds to a probability."""
        return round(exp(logodds)/(1 + exp(logodds)), 2)

    def _counts(self, data: dict) -> Optional[Counts]:
        """Parse counts from the response data."""
        counts: Optional[Counts] = None
        if 'counts' in data:
            counts = Counts(**data['counts'])
        return counts

    def _flags(self, data: dict) -> List[Flag]:
        """Parse flags from the response data."""
        return [
            Flag(key, value) for key, value in data.get('flags', {}).items()
        ]

    def _suggestions(self, data: dict) -> List[Suggestion]:
        """Parse classification suggestions from the response data."""
        return [Suggestion(category=Category(datum['category']),
                           probability=self._probability(datum['logodds']))
                for datum in data['classifier']]

    def __call__(self, content: bytes) -> ClassifierResponse:
        """
        Make a classification request to the classifier service.

        Parameters
        ----------
        content : bytes
            Raw text content from an e-print.

        Returns
        -------
        list
            A list of classifications.
        list
            A list of QA flags.
        :class:`Counts` or None
            Feature counts, if provided.

        """
        response = self._session.post(self.endpoint, data=content)
        if response.status_code != status.HTTP_200_OK:
            raise RequestFailed('Failed: %s', response.content)
        data = response.json()
        return self._suggestions(data), self._flags(data), self._counts(data)


def init_app(app: object=None) -> None:
    """Configure an application instance."""
    config = get_application_config(app)
    config.setdefault('CLASSIFIER_HOST', 'localhost')
    config.setdefault('CLASSIFIER_PORT', 8000)


def get_instance(app: object=None) -> Classifier:
    """Create a new :class:`.Classifier`."""
    config = get_application_config()
    host = config.get('CLASSIFIER_HOST', 'localhost')
    port = config.get('CLASSIFIER_PORT', 8000)
    return Classifier(host, port)


def current_instance():
    """Get/create :class:`.Classifier` instance for this context."""
    g = get_application_global()
    if g is None:
        return get_instance()
    if 'classifier' not in g:
        g.classifier = get_instance()
    return g.classifier


@wraps(Classifier.__call__)
def classify(content: bytes) -> Classifier.ClassifierResponse:
    """Make a classification request to the classifier service."""
    return current_instance()(content)
