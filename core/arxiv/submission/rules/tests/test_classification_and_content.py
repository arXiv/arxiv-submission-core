"""Tests for classification and content processing rules."""

from unittest import TestCase, mock
import copy
from datetime import datetime
from pytz import UTC
from arxiv.integration.api import status, exceptions

from ...domain.event import ConfirmPreview, AddProcessStatus, AddContentFlag, \
    AddClassifierResults, AddFeature
from ...domain.agent import User, System
from ...domain.submission import Submission, SubmissionContent
from ...domain.process import ProcessStatus
from ...domain.flag import ContentFlag
from ...domain.annotation import Feature
from ...services import plaintext, classifier
from .. import classification_and_content as c_and_c
from ... import tasks


sys = System(__name__)


class TestPlainTextContentExtraction(TestCase):
    """When the submitter confirms the PDF preview, we extract plain text."""

    def setUp(self):
        """We have a submission."""
        self.creator = User(native_id=1234, email='something@else.com')
        self.submission = Submission(
            submission_id=2347441,
            creator=self.creator,
            owner=self.creator,
            created=datetime.now(UTC),
            source_content=SubmissionContent(
                identifier='5678',
                source_format=SubmissionContent.Format('pdf'),
                checksum='a1b2c3d4',
                uncompressed_size=58493,
                compressed_size=58493
            )
        )

    @mock.patch(f'{tasks.__name__}.get_application_config',
                mock.MagicMock(return_value={'ENABLE_ASYNC': 0}))
    @mock.patch(f'{c_and_c.__name__}.PlainTextService')
    def test_extract_text(self, mock_plaintext):
        """Submitter confirms PDF preview, and we attempt to extract text."""
        # Not complete on the first call.
        mock_plaintext.extraction_is_complete.side_effect = [False, True]

        event = ConfirmPreview(creator=self.creator)
        before, after = self.submission, event.apply(self.submission)

        events = [
            e for e in c_and_c.extract_plain_text(event, before, after, sys)
        ]
        self.assertEqual(len(events), 2, "Two events are generated")
        for e in events:
            self.assertIsInstance(e, AddProcessStatus,
                                  "Generates AddProcessStatus events")
            self.assertEqual(e.process,
                             ProcessStatus.Process.PLAIN_TEXT_EXTRACTION,
                             "Pertaining to plain text extraction")
        self.assertEqual(events[0].status,
                         ProcessStatus.Status.REQUESTED,
                         "The first status is requested")
        self.assertEqual(events[1].status,
                         ProcessStatus.Status.SUCCEEDED,
                         "The second status is succeeded")

    @mock.patch(f'{tasks.__name__}.get_application_config',
                mock.MagicMock(return_value={'ENABLE_ASYNC': 0}))
    @mock.patch(f'{c_and_c.__name__}.PlainTextService')
    def test_extraction_request_fails(self, mock_plaintext):
        """There is a problem requesting plain text extraction."""
        # The initial extraction request fails.
        exception_message = "exception message"

        def raise_failure(*args, **kwargs):
            raise exceptions.RequestForbidden(exception_message,
                                              mock.MagicMock())

        mock_plaintext.request_extraction.side_effect = raise_failure

        event = ConfirmPreview(creator=self.creator)
        before, after = self.submission, event.apply(self.submission)

        events = [
            e for e in c_and_c.extract_plain_text(event, before, after, sys)
        ]
        self.assertEqual(len(events), 1, "One event is generated")

        self.assertIsInstance(events[0], AddProcessStatus,
                              "Generates AddProcessStatus event")
        self.assertEqual(events[0].process,
                         ProcessStatus.Process.PLAIN_TEXT_EXTRACTION,
                         "Pertaining to plain text extraction")
        self.assertEqual(events[0].status,
                         ProcessStatus.Status.FAILED,
                         "The first status is failure")
        self.assertIn(exception_message, events[0].reason,
                      "The reason for failure is provided")
        self.assertIn("RequestForbidden", events[0].reason,
                      "The reason for failure is provided")

    @mock.patch(f'{tasks.__name__}.get_application_config',
                mock.MagicMock(return_value={'ENABLE_ASYNC': 0}))
    @mock.patch(f'{c_and_c.__name__}.PlainTextService')
    def test_extraction_fails_after_start(self, mock_plaintext):
        """Extraction fails after starting."""
        # The initial extraction request fails.
        exception_message = "exception message"

        def raise_failure(*args, **kwargs):
            raise plaintext.ExtractionFailed(exception_message,
                                             mock.MagicMock())
        mock_plaintext.extraction_is_complete.side_effect = raise_failure

        event = ConfirmPreview(creator=self.creator)
        before, after = self.submission, event.apply(self.submission)

        events = [
            e for e in c_and_c.extract_plain_text(event, before, after, sys)
        ]
        self.assertEqual(len(events), 2, "Two events are generated")
        for e in events:
            self.assertIsInstance(e, AddProcessStatus,
                                  "Generates AddProcessStatus events")
            self.assertEqual(e.process,
                             ProcessStatus.Process.PLAIN_TEXT_EXTRACTION,
                             "Pertaining to plain text extraction")
        self.assertEqual(events[0].status,
                         ProcessStatus.Status.REQUESTED,
                         "The first status is requested")
        self.assertEqual(events[1].status,
                         ProcessStatus.Status.FAILED,
                         "The second status is failed")
        self.assertIn(exception_message, events[1].reason,
                      "The reason for failure is provided")
        self.assertIn("ExtractionFailed", events[1].reason,
                      "The reason for failure is provided")


class TestClassificationRequest(TestCase):
    """When plain text becomes available, we call the auto-classifier."""

    def setUp(self):
        """We have a submission."""
        self.creator = User(native_id=1234, email='something@else.com')
        self.submission = Submission(
            submission_id=2347441,
            creator=self.creator,
            owner=self.creator,
            created=datetime.now(UTC),
            source_content=SubmissionContent(
                identifier='5678',
                source_format=SubmissionContent.Format('pdf'),
                checksum='a1b2c3d4',
                uncompressed_size=58493,
                compressed_size=58493
            )
        )

    @mock.patch(f'{tasks.__name__}.get_application_config',
                mock.MagicMock(return_value={'ENABLE_ASYNC': 0}))
    @mock.patch(f'{c_and_c.__name__}.Classifier')
    @mock.patch(f'{c_and_c.__name__}.PlainTextService')
    def test_call_classifier(self, mock_plaintext, mock_classifier):
        """Extraction succeeds, and we request classification."""
        mock_plaintext.retrieve_content.return_value = b'plain text content'
        mock_classifier.classify.return_value = (
            [classifier.classifier.Suggestion('astro-ph.HE', 0.9)],
            [classifier.classifier.Flag('%stop', '0.001'),
             classifier.classifier.Flag('linenos', '1')],
            classifier.classifier.Counts(32345, 43, 1, 1000)
        )

        event = AddProcessStatus(
            creator=self.creator,
            process=ProcessStatus.Process.PLAIN_TEXT_EXTRACTION,
            status=ProcessStatus.Status.SUCCEEDED,
            service='plaintext',
            version='0.1',
            identifier=self.submission.source_content.identifier
        )
        before, after = self.submission, event.apply(self.submission)

        events = [
            e for e in c_and_c.call_classifier(event, before, after, sys)
        ]

        self.assertIsInstance(events[0], AddProcessStatus,
                              "The first event is an AddProcessStatus")
        self.assertEqual(events[0].process,
                         ProcessStatus.Process.CLASSIFICATION,
                         "Pertaining to classification")
        self.assertEqual(events[0].status,
                         ProcessStatus.Status.REQUESTED,
                         "The first status is requested")

        self.assertIsInstance(events[1], AddProcessStatus,
                              "The second event is an AddProcessStatus")
        self.assertEqual(events[1].process,
                         ProcessStatus.Process.CLASSIFICATION,
                         "Pertaining to classification")
        self.assertEqual(events[1].status,
                         ProcessStatus.Status.SUCCEEDED,
                         "The second status is succeeded")

        event_types = [type(e) for e in events]
        self.assertIn(AddClassifierResults, event_types,
                      "Classifier results are added to the submission")
        self.assertIn(AddContentFlag, event_types,
                      "Flags are added to the submission")
        self.assertIn(AddFeature, event_types,
                      "Features are added to the submission")

    @mock.patch(f'{tasks.__name__}.get_application_config',
                mock.MagicMock(return_value={'ENABLE_ASYNC': 0}))
    @mock.patch(f'{c_and_c.__name__}.Classifier')
    @mock.patch(f'{c_and_c.__name__}.PlainTextService')
    def test_classification_fails(self, mock_plaintext, mock_classifier):
        """The classification request fails."""
        mock_plaintext.ExtractionFailed = plaintext.ExtractionFailed

        # The classification request fails.
        exception_message = "exception message"

        def raise_failure(*args, **kwargs):
            raise exceptions.RequestFailed(exception_message, mock.MagicMock())

        mock_classifier.classify.side_effect = raise_failure
        mock_plaintext.retrieve_content.return_value = b'plain text content'

        event = AddProcessStatus(
            creator=self.creator,
            process=ProcessStatus.Process.PLAIN_TEXT_EXTRACTION,
            status=ProcessStatus.Status.SUCCEEDED,
            service='plaintext',
            version='0.1',
            identifier=self.submission.source_content.identifier
        )
        before, after = self.submission, event.apply(self.submission)

        events = [
            e for e in c_and_c.call_classifier(event, before, after, sys)
        ]

        self.assertIsInstance(events[0], AddProcessStatus,
                              "The first event is an AddProcessStatus")
        self.assertEqual(events[0].process,
                         ProcessStatus.Process.CLASSIFICATION,
                         "Pertaining to classification")
        self.assertEqual(events[0].status,
                         ProcessStatus.Status.REQUESTED,
                         "The first status is requested")

        self.assertIsInstance(events[1], AddProcessStatus,
                              "The second event is an AddProcessStatus")
        self.assertEqual(events[1].process,
                         ProcessStatus.Process.CLASSIFICATION,
                         "Pertaining to classification")
        self.assertEqual(events[1].status,
                         ProcessStatus.Status.FAILED,
                         "The second status is failed")


class TestCheckStopwordCount(TestCase):
    """When a stopword count feature is added, we check for low value."""

    def setUp(self):
        """We have a submission."""
        self.creator = User(native_id=1234, email='something@else.com')
        self.submission = Submission(
            submission_id=2347441,
            creator=self.creator,
            owner=self.creator,
            created=datetime.now(UTC),
            source_content=SubmissionContent(
                identifier='5678',
                source_format=SubmissionContent.Format('pdf'),
                checksum='a1b2c3d4',
                uncompressed_size=58493,
                compressed_size=58493
            )
        )

    @mock.patch(f'{tasks.__name__}.get_application_config',
                mock.MagicMock(return_value={'ENABLE_ASYNC': 0}))
    @mock.patch(f'{c_and_c.__name__}.LOW_STOP', 20)
    def test_check_stop_count(self):
        """A stopword count feature is added, and we check its value."""
        event = AddFeature(creator=self.creator,
                           feature_type=Feature.FeatureTypes.STOPWORD_COUNT,
                           feature_value=5)
        before, after = self.submission, event.apply(self.submission)

        events = [
            e for e in c_and_c.check_stop_count(event, before, after, sys)
        ]
        self.assertEqual(len(events), 1, "One event is generated")

        self.assertIsInstance(events[0], AddContentFlag,
                              "Generates AddContentFlag event")
        self.assertEqual(events[0].flag_type,
                         ContentFlag.FlagTypes.LOW_STOP,
                         "Adds a low stopword count flag")
        self.assertEqual(events[0].flag_data,
                         event.feature_value,
                         "The stopword count is added as data")
        self.assertEqual(events[0].comment,
                         "Classifier reports low stops or %stops",
                         "A descriptive comment is included")

    @mock.patch(f'{tasks.__name__}.get_application_config',
                mock.MagicMock(return_value={'ENABLE_ASYNC': 0}))
    @mock.patch(f'{c_and_c.__name__}.LOW_STOP', 20)
    def test_check_stop_count_is_ok(self):
        """The stopword count is high enough for comfort."""
        event = AddFeature(creator=self.creator,
                           feature_type=Feature.FeatureTypes.STOPWORD_COUNT,
                           feature_value=25)
        before, after = self.submission, event.apply(self.submission)

        events = [
            e for e in c_and_c.check_stop_count(event, before, after, sys)
        ]
        self.assertEqual(len(events), 0, "No event is generated")


class TestCheckStopwordPercent(TestCase):
    """When a stopword percent feature is added, we check for low value."""

    def setUp(self):
        """We have a submission."""
        self.creator = User(native_id=1234, email='something@else.com')
        self.submission = Submission(
            submission_id=2347441,
            creator=self.creator,
            owner=self.creator,
            created=datetime.now(UTC),
            source_content=SubmissionContent(
                identifier='5678',
                source_format=SubmissionContent.Format('pdf'),
                checksum='a1b2c3d4',
                uncompressed_size=58493,
                compressed_size=58493
            )
        )

    @mock.patch(f'{tasks.__name__}.get_application_config',
                mock.MagicMock(return_value={'ENABLE_ASYNC': 0}))
    @mock.patch(f'{c_and_c.__name__}.LOW_STOP_PERCENT', 0.05)
    def test_check_stop_count(self):
        """A stopword count feature is added, and we check its value."""
        event = AddFeature(creator=self.creator,
                           feature_type=Feature.FeatureTypes.STOPWORD_PERCENT,
                           feature_value=0.01)
        before, after = self.submission, event.apply(self.submission)

        events = [
            e for e in c_and_c.check_stop_percent(event, before, after, sys)
        ]
        self.assertEqual(len(events), 1, "One event is generated")

        self.assertIsInstance(events[0], AddContentFlag,
                              "Generates AddContentFlag event")
        self.assertEqual(events[0].flag_type,
                         ContentFlag.FlagTypes.LOW_STOP_PERCENT,
                         "Adds a low stopword percent flag")
        self.assertEqual(events[0].flag_data,
                         event.feature_value,
                         "The stopword percent is added as data")
        self.assertEqual(events[0].comment,
                         "Classifier reports low stops or %stops",
                         "A descriptive comment is included")

    @mock.patch(f'{tasks.__name__}.get_application_config',
                mock.MagicMock(return_value={'ENABLE_ASYNC': 0}))
    @mock.patch(f'{c_and_c.__name__}.LOW_STOP_PERCENT', 0.05)
    def test_check_stop_percent_is_ok(self):
        """The stopword count is high enough for comfort."""
        event = AddFeature(creator=self.creator,
                           feature_type=Feature.FeatureTypes.STOPWORD_PERCENT,
                           feature_value=0.06)
        before, after = self.submission, event.apply(self.submission)

        events = [
            e for e in c_and_c.check_stop_percent(event, before, after, sys)
        ]
        self.assertEqual(len(events), 0, "No event is generated")
