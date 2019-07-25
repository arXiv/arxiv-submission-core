"""Tests for classic classifier service integration."""

import os
import json
from unittest import TestCase, mock

from arxiv.integration.api import status, exceptions
from .. import classifier

DATA_PATH = os.path.join(os.path.split(os.path.abspath(__file__))[0], "data")
SAMPLE_PATH = os.path.join(DATA_PATH, "sampleResponse.json")
LINENOS_PATH = os.path.join(DATA_PATH, "linenos.json")
SAMPLE_FAILED_PATH = os.path.join(DATA_PATH, 'sampleFailedCyrillic.json')


mock_app = mock.MagicMock(config={
    'CLASSIFIER_ENDPOINT': 'http://foohost:1234',
    'CLASSIFIER_VERIFY': False
})


class TestClassifier(TestCase):
    """Tests for :class:`classifier.Classifier`."""

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_classifier_with_service_unavailable(self, mock_Session):
        """The classifier service is unavailable."""
        mock_Session.return_value = mock.MagicMock(
            post=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.SERVICE_UNAVAILABLE
                )
            )
        )
        with self.assertRaises(exceptions.RequestFailed):
            classifier.Classifier('http://foo:9000').classify(b'somecontent')

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_classifier_cannot_classify(self, mock_Session):
        """The classifier returns without classification suggestions."""
        with open(SAMPLE_FAILED_PATH) as f:
            data = json.load(f)
        mock_Session.return_value = mock.MagicMock(
            post=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.OK,
                    json=mock.MagicMock(return_value=data)
                )
            )
        )
        suggestions, flags, counts = \
            classifier.Classifier('http://foo:9000').classify(b'foo')
        self.assertEqual(len(suggestions), 0, "There are no suggestions")
        self.assertEqual(len(flags), 4, "There are four flags")
        self.assertEqual(counts.chars, 50475)
        self.assertEqual(counts.pages, 8)
        self.assertEqual(counts.stops, 9)
        self.assertEqual(counts.words, 4799)

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_classifier_returns_suggestions(self, mock_Session):
        """The classifier returns classification suggestions."""
        with open(SAMPLE_PATH) as f:
            data = json.load(f)
        mock_Session.return_value = mock.MagicMock(
            post=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.OK,
                    json=mock.MagicMock(return_value=data)
                )
            )
        )
        expected = {
            'physics.comp-ph': 0.47,
            'cs.MS': 0.47,
            'math.NA': 0.46
        }
        suggestions, flags, counts = \
            classifier.Classifier('http://foo:9000').classify(b'foo')
        self.assertEqual(len(suggestions), 3, "There are three suggestions")
        for suggestion in suggestions:
            self.assertEqual(round(suggestion.probability, 2),
                             expected[suggestion.category])
        self.assertEqual(len(flags), 0, "There are no flags")
        self.assertEqual(counts.chars, 15107)
        self.assertEqual(counts.pages, 12)
        self.assertEqual(counts.stops, 804)
        self.assertEqual(counts.words, 2860)

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_classifier_withlinenos(self, mock_Session):
        """The classifier returns classification suggestions."""
        with open(LINENOS_PATH) as f:
            data = json.load(f)
        mock_Session.return_value = mock.MagicMock(
            post=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.OK,
                    json=mock.MagicMock(return_value=data)
                )
            )
        )
        expected = {
            'astro-ph.SR': 0.77,
            'astro-ph.GA': 0.7,
            'astro-ph.EP': 0.69,
            'astro-ph.HE': 0.57,
            'astro-ph.IM': 0.57

        }

        suggestions, flags, counts = \
            classifier.Classifier('http://foo:9000').classify(b'foo')
        self.assertEqual(len(suggestions), 5, "There are five suggestions")
        for suggestion in suggestions:
            self.assertEqual(
                round(suggestion.probability, 2),
                expected[suggestion.category],
                "Expected probability of %s for %s" %
                (expected[suggestion.category], suggestion.category)
            )
        self.assertEqual(len(flags), 2, "There are two flags")
        self.assertIn("%stop", [flag.key for flag in flags])
        self.assertIn("linenos", [flag.key for flag in flags])
        self.assertEqual(counts.chars, 125436)
        self.assertEqual(counts.pages, 30)
        self.assertEqual(counts.stops, 3774)
        self.assertEqual(counts.words, 34211)


class TestClassifierModule(TestCase):
    """Tests for :mod:`classifier`."""

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_classifier_unavailable(self, mock_Session):
        """The classifier service is unavailable."""
        mock_post = mock.MagicMock(
            return_value=mock.MagicMock(
                status_code=status.SERVICE_UNAVAILABLE
            )
        )
        mock_Session.return_value = mock.MagicMock(post=mock_post)
        with self.assertRaises(exceptions.RequestFailed):
            classifier.Classifier.classify(b'somecontent')
        endpoint = f'http://foohost:1234/ctxt'
        self.assertEqual(mock_post.call_args[0][0], endpoint)

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_classifier_cannot_classify(self, mock_Session):
        """The classifier returns without classification suggestions."""
        with open(SAMPLE_FAILED_PATH) as f:
            data = json.load(f)
        mock_post = mock.MagicMock(
            return_value=mock.MagicMock(
                status_code=status.OK,
                json=mock.MagicMock(return_value=data)
            )
        )
        mock_Session.return_value = mock.MagicMock(post=mock_post)
        suggestions, flags, counts = classifier.Classifier.classify(b'foo')
        self.assertEqual(len(suggestions), 0, "There are no suggestions")
        self.assertEqual(len(flags), 4, "There are four flags")
        self.assertEqual(counts.chars, 50475)
        self.assertEqual(counts.pages, 8)
        self.assertEqual(counts.stops, 9)
        self.assertEqual(counts.words, 4799)
        endpoint = f'http://foohost:1234/ctxt'
        self.assertEqual(mock_post.call_args[0][0], endpoint)

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_classifier_returns_suggestions(self, mock_Session):
        """The classifier returns classification suggestions."""
        with open(SAMPLE_PATH) as f:
            data = json.load(f)
        mock_post = mock.MagicMock(
            return_value=mock.MagicMock(
                status_code=status.OK,
                json=mock.MagicMock(return_value=data)
            )
        )
        mock_Session.return_value = mock.MagicMock(post=mock_post)
        expected = {
            'physics.comp-ph': 0.47,
            'cs.MS': 0.47,
            'math.NA': 0.46
        }
        suggestions, flags, counts = classifier.Classifier.classify(b'foo')
        self.assertEqual(len(suggestions), 3, "There are three suggestions")
        for suggestion in suggestions:
            self.assertEqual(round(suggestion.probability, 2),
                             expected[suggestion.category])
        self.assertEqual(len(flags), 0, "There are no flags")
        self.assertEqual(counts.chars, 15107)
        self.assertEqual(counts.pages, 12)
        self.assertEqual(counts.stops, 804)
        self.assertEqual(counts.words, 2860)
        endpoint = f'http://foohost:1234/ctxt'
        self.assertEqual(mock_post.call_args[0][0], endpoint)
