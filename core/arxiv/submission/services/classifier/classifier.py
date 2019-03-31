"""Classifier service integration."""

from typing import Tuple, List, Any, Union, NamedTuple, Optional
from math import exp, log
from functools import wraps

from arxiv.taxonomy import Category
from arxiv.integration.api import status, service


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


class Classifier(service.HTTPIntegration):
    """Represents an interface to the classifier service."""

    VERSION = '0.0'
    SERVICE = 'classic'

    ClassifierResponse = Tuple[List[Suggestion], List[Flag], Optional[Counts]]

    class Meta:
        """Configuration for :class:`Classifier`."""

        service_name = "classifier"

    @property
    def endpoint(self):
        """Get the URL of the classifier endpoint."""
        return f'http://{self._host}:{self._port}/ctxt'

    @classmethod
    def probability(cls, logodds: float) -> float:
        """Convert log odds to a probability."""
        return exp(logodds)/(1 + exp(logodds))

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
                           probability=self.probability(datum['logodds']))
                for datum in data['classifier']]

    def classify(self, content: bytes) -> ClassifierResponse:
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
        data, _, _ = self.json('post', 'ctxt', data=content)
        return self._suggestions(data), self._flags(data), self._counts(data)
