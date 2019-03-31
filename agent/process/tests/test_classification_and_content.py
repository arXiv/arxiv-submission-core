"""Tests for classification and content processing rules."""

from unittest import TestCase, mock
import copy
from datetime import datetime
from pytz import UTC
from arxiv.integration.api import status, exceptions

from arxiv.submission.domain.event import ConfirmPreview, AddProcessStatus, \
    AddContentFlag, AddClassifierResults, AddFeature
from arxiv.submission.domain.agent import User, System
from arxiv.submission.domain.submission import Submission, SubmissionContent
from arxiv.submission.domain.process import ProcessStatus
from arxiv.submission.domain.flag import ContentFlag
from arxiv.submission.domain.annotation import Feature
from arxiv.submission.services import plaintext, classifier

from .. import Failed, Recoverable
from .. import PlainTextExtraction, RunAutoclassifier, CheckStopwordCount, \
    CheckStopwordPercent
from .. import classification_and_content as c_and_c
from ...domain import Trigger
from ...runner import ProcessRunner
from ...factory import create_app

sys = System(__name__)


def raise_http_exception(exc, code: int, msg='argle bargle'):
    def side_effect(*args, **kwargs):
        raise exc(msg, mock.MagicMock(status_code=code))
    return side_effect


class TestRequestPlainTextContentExtraction(TestCase):
    """Test :func:`PlainTextExtraction.start_extraction`."""

    def setUp(self):
        """We have a submission."""
        self.app = create_app()
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
        self.event = ConfirmPreview(creator=self.creator)
        self.process = PlainTextExtraction(self.submission.submission_id)

    @mock.patch(f'{c_and_c.__name__}.PlainTextService')
    def test_start_extraction(self, mock_plaintext):
        """We attempt to start plain text extraction."""
        trigger = Trigger(event=self.event, actor=self.creator,
                          before=self.submission, after=self.submission)
        events = []
        with self.app.app_context():
            res = self.process.start_extraction(None, trigger, events.append)

        self.assertIsNone(res, 'No result is returned.')
        self.assertEqual(mock_plaintext.request_extraction.call_args[0][0],
                         self.submission.source_content.identifier,
                         'Request for extraction is made with source ID.')

    @mock.patch(f'{c_and_c.__name__}.PlainTextService')
    def test_missing_source(self, mock_plaintext):
        """There is no source on the submission."""
        submission_without_source = Submission(
            submission_id=2347441,
            creator=self.creator,
            owner=self.creator,
            created=datetime.now(UTC)
        )
        trigger = Trigger(event=self.event, actor=self.creator,
                          before=submission_without_source,
                          after=submission_without_source)
        events = []
        with self.app.app_context():
            with self.assertRaises(Failed):
                # Insufficient information to start extraction.
                self.process.start_extraction(None, trigger, events.append)

    @mock.patch(f'{c_and_c.__name__}.PlainTextService')
    def test_bad_response(self, mock_plaintext):
        """The plain text service responds oddly which we hope is transient."""
        mock_plaintext.request_extraction.side_effect = \
            raise_http_exception(exceptions.BadResponse, 200)
        trigger = Trigger(event=self.event, actor=self.creator,
                          before=self.submission, after=self.submission)
        events = []
        with self.app.app_context():
            with self.assertRaises(Recoverable):
                # The exception is re-raised as a Recoverable error.
                self.process.start_extraction(None, trigger, events.append)

    @mock.patch(f'{c_and_c.__name__}.PlainTextService')
    def test_connection_failed(self, mock_plaintext):
        """Cannot conntect to plain text service."""
        mock_plaintext.request_extraction.side_effect = \
            raise_http_exception(exceptions.ConnectionFailed, -1)
        trigger = Trigger(event=self.event, actor=self.creator,
                          before=self.submission, after=self.submission)
        events = []
        with self.app.app_context():
            with self.assertRaises(Recoverable):
                # The exception is re-raised as a Recoverable error.
                self.process.start_extraction(None, trigger, events.append)

    @mock.patch(f'{c_and_c.__name__}.PlainTextService')
    def test_bad_request(self, mock_plaintext):
        """The request to the plain text service is malformed."""
        mock_plaintext.request_extraction.side_effect = \
            raise_http_exception(exceptions.BadRequest, 400)
        trigger = Trigger(event=self.event, actor=self.creator,
                          before=self.submission, after=self.submission)
        events = []
        with self.app.app_context():
            with self.assertRaises(Failed):
                # The process is explicitly failed.
                self.process.start_extraction(None, trigger, events.append)

    @mock.patch(f'{c_and_c.__name__}.PlainTextService')
    def test_internal_server_error(self, mock_plaintext):
        """The plain text service is down."""
        mock_plaintext.request_extraction.side_effect = \
            raise_http_exception(exceptions.RequestFailed, 500)
        trigger = Trigger(event=self.event, actor=self.creator,
                          before=self.submission, after=self.submission)
        events = []
        with self.app.app_context():
            with self.assertRaises(Recoverable):
                # The process is explicitly failed.
                self.process.start_extraction(None, trigger, events.append)


class TestPollPlainTextContentExtraction(TestCase):
    """Test :func:`PlainTextExtraction.start_extraction`."""

    def setUp(self):
        """We have a submission."""
        self.app = create_app()
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
        self.event = ConfirmPreview(creator=self.creator)
        self.process = PlainTextExtraction(self.submission.submission_id)

    @mock.patch(f'{c_and_c.__name__}.PlainTextService')
    def test_poll_extraction(self, mock_plaintext):
        """Check the status of the extraction."""
        trigger = Trigger(event=self.event, actor=self.creator,
                          before=self.submission, after=self.submission)
        events = []
        with self.app.app_context():
            res = self.process.poll_extraction(None, trigger, events.append)

        self.assertIsNone(res, 'No result is returned.')
        self.assertEqual(mock_plaintext.extraction_is_complete.call_args[0][0],
                         self.submission.source_content.identifier,
                         'Poll is made with source ID.')

    @mock.patch(f'{c_and_c.__name__}.PlainTextService')
    def test_poll_bad_response(self, mock_plaintext):
        """The plain text service responds oddly which we hope is transient."""
        mock_plaintext.extraction_is_complete.side_effect = \
            raise_http_exception(exceptions.BadResponse, 200)
        trigger = Trigger(event=self.event, actor=self.creator,
                          before=self.submission, after=self.submission)
        events = []
        with self.app.app_context():
            with self.assertRaises(Recoverable):
                # The exception is re-raised as a Recoverable error.
                self.process.poll_extraction(None, trigger, events.append)

    @mock.patch(f'{c_and_c.__name__}.PlainTextService')
    def test_poll_connection_failed(self, mock_plaintext):
        """Cannot conntect to plain text service."""
        mock_plaintext.extraction_is_complete.side_effect = \
            raise_http_exception(exceptions.ConnectionFailed, -1)
        trigger = Trigger(event=self.event, actor=self.creator,
                          before=self.submission, after=self.submission)
        events = []
        with self.app.app_context():
            with self.assertRaises(Recoverable):
                # The exception is re-raised as a Recoverable error.
                self.process.poll_extraction(None, trigger, events.append)

    @mock.patch(f'{c_and_c.__name__}.PlainTextService')
    def test_poll_bad_request(self, mock_plaintext):
        """The request to the plain text service is malformed."""
        mock_plaintext.extraction_is_complete.side_effect = \
            raise_http_exception(exceptions.BadRequest, 400)
        trigger = Trigger(event=self.event, actor=self.creator,
                          before=self.submission, after=self.submission)
        events = []
        with self.app.app_context():
            with self.assertRaises(Failed):
                # The process is explicitly failed.
                self.process.poll_extraction(None, trigger, events.append)

    @mock.patch(f'{c_and_c.__name__}.PlainTextService')
    def test_poll_internal_server_error(self, mock_plaintext):
        """The plain text service is down."""
        mock_plaintext.extraction_is_complete.side_effect = \
            raise_http_exception(exceptions.RequestFailed, 500)
        trigger = Trigger(event=self.event, actor=self.creator,
                          before=self.submission, after=self.submission)
        events = []
        with self.app.app_context():
            with self.assertRaises(Recoverable):
                # The process is explicitly failed.
                self.process.poll_extraction(None, trigger, events.append)


class TestRetrievePlainTextContentExtraction(TestCase):
    """Test :func:`PlainTextExtraction.start_extraction`."""

    def setUp(self):
        """We have a submission."""
        self.app = create_app()
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
        self.event = ConfirmPreview(creator=self.creator)
        self.process = PlainTextExtraction(self.submission.submission_id)

    @mock.patch(f'{c_and_c.__name__}.PlainTextService')
    def test_retrieve_content(self, mock_plaintext):
        """Check the status of the extraction."""
        trigger = Trigger(event=self.event, actor=self.creator,
                          before=self.submission, after=self.submission)
        events = []
        with self.app.app_context():
            res = self.process.retrieve_content(None, trigger, events.append)

        self.assertIsNotNone(res, 'Raw content is returned')
        self.assertEqual(mock_plaintext.retrieve_content.call_args[0][0],
                         self.submission.source_content.identifier,
                         'Request is made with source ID.')

    @mock.patch(f'{c_and_c.__name__}.PlainTextService')
    def test_retrieve_content_bad_response(self, mock_plaintext):
        """The plain text service responds oddly which we hope is transient."""
        mock_plaintext.retrieve_content.side_effect = \
            raise_http_exception(exceptions.BadResponse, 200)
        trigger = Trigger(event=self.event, actor=self.creator,
                          before=self.submission, after=self.submission)
        events = []
        with self.app.app_context():
            with self.assertRaises(Recoverable):
                # The exception is re-raised as a Recoverable error.
                self.process.retrieve_content(None, trigger, events.append)

    @mock.patch(f'{c_and_c.__name__}.PlainTextService')
    def test_retrieve_content_connection_failed(self, mock_plaintext):
        """Cannot conntect to plain text service."""
        mock_plaintext.retrieve_content.side_effect = \
            raise_http_exception(exceptions.ConnectionFailed, -1)
        trigger = Trigger(event=self.event, actor=self.creator,
                          before=self.submission, after=self.submission)
        events = []
        with self.app.app_context():
            with self.assertRaises(Recoverable):
                # The exception is re-raised as a Recoverable error.
                self.process.retrieve_content(None, trigger, events.append)

    @mock.patch(f'{c_and_c.__name__}.PlainTextService')
    def test_retrieve_content_bad_request(self, mock_plaintext):
        """The request to the plain text service is malformed."""
        mock_plaintext.retrieve_content.side_effect = \
            raise_http_exception(exceptions.BadRequest, 400)
        trigger = Trigger(event=self.event, actor=self.creator,
                          before=self.submission, after=self.submission)
        events = []
        with self.app.app_context():
            with self.assertRaises(Failed):
                # The process is explicitly failed.
                self.process.retrieve_content(None, trigger, events.append)

    @mock.patch(f'{c_and_c.__name__}.PlainTextService')
    def test_retrieve_content_internal_server_error(self, mock_plaintext):
        """The plain text service is down."""
        mock_plaintext.retrieve_content.side_effect = \
            raise_http_exception(exceptions.RequestFailed, 500)
        trigger = Trigger(event=self.event, actor=self.creator,
                          before=self.submission, after=self.submission)
        events = []
        with self.app.app_context():
            with self.assertRaises(Recoverable):
                # The process is explicitly failed.
                self.process.retrieve_content(None, trigger, events.append)


class TestCallClassifier(TestCase):
    """Test :func:`RunAutoclassifier.call_classifier`."""

    def setUp(self):
        """We have a submission."""
        self.app = create_app()
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
        self.event = ConfirmPreview(creator=self.creator)
        self.process = RunAutoclassifier(self.submission.submission_id)

    @mock.patch(f'{c_and_c.__name__}.Classifier')
    def test_call_classifier(self, mock_classifier):
        """Request classifier results."""
        content = mock.MagicMock()
        mock_classifier.classify.return_value = (
            [classifier.classifier.Suggestion('astro-ph.HE', 0.9)],
            [classifier.classifier.Flag('%stop', '0.001'),
             classifier.classifier.Flag('linenos', '1')],
            classifier.classifier.Counts(32345, 43, 1, 1000)
        )
        trigger = Trigger(event=self.event, actor=self.creator,
                          before=self.submission, after=self.submission)
        events = []
        with self.app.app_context():
            res = self.process.call_classifier(content, trigger, events.append)

        self.assertIsNone(res, 'No return')
        self.assertEqual(mock_classifier.classify.call_args[0][0],
                         content, 'Request is made with content.')

        event_types = [type(e) for e in events]
        self.assertIn(AddClassifierResults, event_types,
                      "Classifier results are added to the submission")
        self.assertIn(AddContentFlag, event_types,
                      "Flags are added to the submission")
        self.assertIn(AddFeature, event_types,
                      "Features are added to the submission")

    @mock.patch(f'{c_and_c.__name__}.Classifier')
    def test_call_classifier_bad_response(self, mock_classifier):
        """The classifier responds oddly which we hope is transient."""
        mock_classifier.classify.side_effect = \
            raise_http_exception(exceptions.BadResponse, 200)
        trigger = Trigger(event=self.event, actor=self.creator,
                          before=self.submission, after=self.submission)
        events = []
        with self.app.app_context():
            with self.assertRaises(Recoverable):
                # The exception is re-raised as a Recoverable error.
                self.process.call_classifier(None, trigger, events.append)

    @mock.patch(f'{c_and_c.__name__}.Classifier')
    def test_call_classifier_connection_failed(self, mock_classifier):
        """Cannot conntect to classifier service."""
        mock_classifier.classify.side_effect = \
            raise_http_exception(exceptions.ConnectionFailed, -1)
        trigger = Trigger(event=self.event, actor=self.creator,
                          before=self.submission, after=self.submission)
        events = []
        with self.app.app_context():
            with self.assertRaises(Recoverable):
                # The exception is re-raised as a Recoverable error.
                self.process.call_classifier(None, trigger, events.append)

    @mock.patch(f'{c_and_c.__name__}.Classifier')
    def test_call_classifier_bad_request(self, mock_classifier):
        """The request to the classifier service is malformed."""
        mock_classifier.classify.side_effect = \
            raise_http_exception(exceptions.BadRequest, 400)
        trigger = Trigger(event=self.event, actor=self.creator,
                          before=self.submission, after=self.submission)
        events = []
        with self.app.app_context():
            with self.assertRaises(Failed):
                # The process is explicitly failed.
                self.process.call_classifier(None, trigger, events.append)

    @mock.patch(f'{c_and_c.__name__}.Classifier')
    def test_call_classifier_internal_server_error(self, mock_classifier):
        """The classifier service is down."""
        mock_classifier.classify.side_effect = \
            raise_http_exception(exceptions.RequestFailed, 500)
        trigger = Trigger(event=self.event, actor=self.creator,
                          before=self.submission, after=self.submission)
        events = []
        with self.app.app_context():
            with self.assertRaises(Recoverable):
                # The process is explicitly failed.
                self.process.call_classifier(None, trigger, events.append)


class TestCheckStopwordCount(TestCase):
    """Test :func:`CheckStopwordCount.check_stop_count`."""

    def setUp(self):
        """We have a submission."""
        self.app = create_app()
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
        self.event = AddFeature(creator=self.creator)
        self.process = CheckStopwordCount(self.submission.submission_id)

    def test_check_low_stop_count(self):
        """Submisison has a stopword count feature with a low value."""
        self.submission.annotations['abcd1234'] = Feature(
            event_id='abcd1234',
            created=datetime.now(UTC),
            creator=self.creator,
            feature_type=Feature.Type.STOPWORD_COUNT,
            feature_value=5
        )
        events = []
        trigger = Trigger(event=self.event, actor=self.creator,
                          before=self.submission, after=self.submission,
                          params={'LOW_STOP': 6})
        self.process.check_stop_count(None, trigger, events.append)

        self.assertIsInstance(events[0], AddContentFlag,
                              'Generates a flag; the stop count is too low')

    def test_check_ok_stop_count(self):
        """Submisison has a stopword count feature with a low value."""
        self.submission.annotations['abcd1234'] = Feature(
            event_id='abcd1234',
            created=datetime.now(UTC),
            creator=self.creator,
            feature_type=Feature.Type.STOPWORD_COUNT,
            feature_value=7
        )
        events = []
        trigger = Trigger(event=self.event, actor=self.creator,
                          before=self.submission, after=self.submission,
                          params={'LOW_STOP': 6})
        self.process.check_stop_count(None, trigger, events.append)
        self.assertEqual(len(events), 0, 'Generates no flags')

    def test_no_stop_count_feature(self):
        """Submisison has no stopword count features."""
        events = []
        trigger = Trigger(event=self.event, actor=self.creator,
                          before=self.submission, after=self.submission,
                          params={'LOW_STOP': 6})
        with self.assertRaises(Failed):
            self.process.check_stop_count(None, trigger, events.append)


class TestCheckStopwordPercent(TestCase):
    """Test :func:`CheckStopwordPercent.check_stop_percent`."""

    def setUp(self):
        """We have a submission."""
        self.app = create_app()
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
        self.event = AddFeature(creator=self.creator)
        self.process = CheckStopwordPercent(self.submission.submission_id)

    def test_check_low_stop_percent(self):
        """Submisison has a stopword percent feature with a low value."""
        self.submission.annotations['abcd1234'] = Feature(
            event_id='abcd1234',
            created=datetime.now(UTC),
            creator=self.creator,
            feature_type=Feature.Type.STOPWORD_PERCENT,
            feature_value=0.001
        )
        events = []
        trigger = Trigger(event=self.event, actor=self.creator,
                          before=self.submission, after=self.submission,
                          params={'LOW_STOP_PERCENT': 0.005})
        self.process.check_stop_percent(None, trigger, events.append)

        self.assertIsInstance(events[0], AddContentFlag,
                              'Generates a flag; the stop count is too low')

    def test_check_ok_stop_percent(self):
        """Submisison has a stopword percent feature with a low value."""
        self.submission.annotations['abcd1234'] = Feature(
            event_id='abcd1234',
            created=datetime.now(UTC),
            creator=self.creator,
            feature_type=Feature.Type.STOPWORD_PERCENT,
            feature_value=0.01
        )
        events = []
        trigger = Trigger(event=self.event, actor=self.creator,
                          before=self.submission, after=self.submission,
                          params={'LOW_STOP_PERCENT': 0.005})
        self.process.check_stop_percent(None, trigger, events.append)
        self.assertEqual(len(events), 0, 'Generates no flags')

    def test_no_stop_percent_feature(self):
        """Submisison has no stopword percent features."""
        events = []
        trigger = Trigger(event=self.event, actor=self.creator,
                          before=self.submission, after=self.submission,
                          params={'LOW_STOP_PERCENT': 0.005})
        with self.assertRaises(Failed):
            self.process.check_stop_percent(None, trigger, events.append)
