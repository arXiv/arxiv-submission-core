"""Tests for classic classifier service integration."""

import os
import json
from unittest import TestCase, mock

from arxiv import status
from .. import classifier

DATA_PATH = os.path.join(os.path.split(os.path.abspath(__file__))[0], "data")
SAMPLE_PATH = os.path.join(DATA_PATH, "sampleResponse.json")
SAMPLE_FAILED_PATH = os.path.join(DATA_PATH, 'sampleFailedCyrillic.json')


class TestClassifier(TestCase):
    """Tests for :class:`classifier.Classifier`."""

    @mock.patch(f'{classifier.__name__}.requests.Session')
    def test_classifier_with_service_unavailable(self, mock_Session):
        """The classifier service is unavailable."""
        mock_Session.return_value = mock.MagicMock(
            post=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE
                )
            )
        )
        with self.assertRaises(classifier.RequestFailed):
            classifier.Classifier('foo', 9000)(b'somecontent')

    @mock.patch(f'{classifier.__name__}.requests.Session')
    def test_classifier_cannot_classify(self, mock_Session):
        """The classifier returns without classification suggestions."""
        with open(SAMPLE_FAILED_PATH) as f:
            data = json.load(f)
        mock_Session.return_value = mock.MagicMock(
            post=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.HTTP_200_OK,
                    json=mock.MagicMock(return_value=data)
                )
            )
        )
        suggestions, flags, counts = classifier.Classifier('foo', 9000)(b'foo')
        self.assertEqual(len(suggestions), 0, "There are no suggestions")
        self.assertEqual(len(flags), 4, "There are four flags")
        self.assertEqual(counts.chars, 50475)
        self.assertEqual(counts.pages, 8)
        self.assertEqual(counts.stops, 9)
        self.assertEqual(counts.words, 4799)

    @mock.patch(f'{classifier.__name__}.requests.Session')
    def test_classifier_returns_suggestions(self, mock_Session):
        """The classifier returns classification suggestions."""
        with open(SAMPLE_PATH) as f:
            data = json.load(f)
        mock_Session.return_value = mock.MagicMock(
            post=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.HTTP_200_OK,
                    json=mock.MagicMock(return_value=data)
                )
            )
        )
        expected = {
            'physics.comp-ph': 0.47,
            'cs.MS': 0.47,
            'math.NA': 0.46
        }
        suggestions, flags, counts = classifier.Classifier('foo', 9000)(b'foo')
        self.assertEqual(len(suggestions), 3, "There are three suggestions")
        for suggestion in suggestions:
            self.assertEqual(suggestion.probability,
                             expected[suggestion.category])
        self.assertEqual(len(flags), 0, "There are no flags")
        self.assertEqual(counts.chars, 15107)
        self.assertEqual(counts.pages, 12)
        self.assertEqual(counts.stops, 804)
        self.assertEqual(counts.words, 2860)


class TestClassifierModule(TestCase):
    """Tests for :mod:`classifier`."""

    @mock.patch(f'{classifier.__name__}.get_application_config')
    @mock.patch(f'{classifier.__name__}.requests.Session')
    def test_classifier_unavailable(self, mock_Session, mock_config):
        """The classifier service is unavailable."""
        mock_config.return_value = {
            'CLASSIFIER_HOST': 'foohost',
            'CLASSIFIER_PORT': 1234
        }
        mock_post = mock.MagicMock(
            return_value=mock.MagicMock(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        )
        mock_Session.return_value = mock.MagicMock(post=mock_post)
        with self.assertRaises(classifier.RequestFailed):
            classifier.classify(b'somecontent')
        endpoint = f'http://foohost:1234/ctxt'
        self.assertEqual(mock_post.call_args[0][0], endpoint)

    @mock.patch(f'{classifier.__name__}.get_application_config')
    @mock.patch(f'{classifier.__name__}.requests.Session')
    def test_classifier_cannot_classify(self, mock_Session, mock_config):
        """The classifier returns without classification suggestions."""
        mock_config.return_value = {
            'CLASSIFIER_HOST': 'foohost',
            'CLASSIFIER_PORT': 1234
        }
        with open(SAMPLE_FAILED_PATH) as f:
            data = json.load(f)
        mock_post = mock.MagicMock(
            return_value=mock.MagicMock(
                status_code=status.HTTP_200_OK,
                json=mock.MagicMock(return_value=data)
            )
        )
        mock_Session.return_value = mock.MagicMock(post=mock_post)
        suggestions, flags, counts = classifier.classify(b'foo')
        self.assertEqual(len(suggestions), 0, "There are no suggestions")
        self.assertEqual(len(flags), 4, "There are four flags")
        self.assertEqual(counts.chars, 50475)
        self.assertEqual(counts.pages, 8)
        self.assertEqual(counts.stops, 9)
        self.assertEqual(counts.words, 4799)
        endpoint = f'http://foohost:1234/ctxt'
        self.assertEqual(mock_post.call_args[0][0], endpoint)

    @mock.patch(f'{classifier.__name__}.get_application_config')
    @mock.patch(f'{classifier.__name__}.requests.Session')
    def test_classifier_returns_suggestions(self, mock_Session, mock_config):
        """The classifier returns classification suggestions."""
        mock_config.return_value = {
            'CLASSIFIER_HOST': 'foohost',
            'CLASSIFIER_PORT': 1234
        }
        with open(SAMPLE_PATH) as f:
            data = json.load(f)
        mock_post = mock.MagicMock(
            return_value=mock.MagicMock(
                status_code=status.HTTP_200_OK,
                json=mock.MagicMock(return_value=data)
            )
        )
        mock_Session.return_value = mock.MagicMock(post=mock_post)
        expected = {
            'physics.comp-ph': 0.47,
            'cs.MS': 0.47,
            'math.NA': 0.46
        }
        suggestions, flags, counts = classifier.classify(b'foo')
        self.assertEqual(len(suggestions), 3, "There are three suggestions")
        for suggestion in suggestions:
            self.assertEqual(suggestion.probability,
                             expected[suggestion.category])
        self.assertEqual(len(flags), 0, "There are no flags")
        self.assertEqual(counts.chars, 15107)
        self.assertEqual(counts.pages, 12)
        self.assertEqual(counts.stops, 804)
        self.assertEqual(counts.words, 2860)
        endpoint = f'http://foohost:1234/ctxt'
        self.assertEqual(mock_post.call_args[0][0], endpoint)
