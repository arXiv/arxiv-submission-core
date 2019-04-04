"""Example 7: cross-list request."""

from unittest import TestCase, mock
import tempfile
from datetime import datetime
from pytz import UTC

from flask import Flask

from ...services import classic
from ... import save, load, load_fast, domain, exceptions, core

CCO = 'http://creativecommons.org/publicdomain/zero/1.0/'
TEX = domain.submission.SubmissionContent.Format('tex')


class TestCrossListRequested(TestCase):
    """Submitter has requested that a cross-list classification be added."""

    @classmethod
    def setUpClass(cls):
        """Instantiate an app for use with a SQLite database."""
        _, db = tempfile.mkstemp(suffix='.sqlite')
        cls.app = Flask('foo')
        cls.app.config['CLASSIC_DATABASE_URI'] = f'sqlite:///{db}'
        cls.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

        with cls.app.app_context():
            classic.init_app(cls.app)

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def setUp(self):
        """Create, complete, and publish the submission."""
        self.submitter = domain.agent.User(1234, email='j.user@somewhere.edu',
                                           forename='Jane', surname='User',
                                           endorsements=['cs.DL', 'cs.IR'])
        self.defaults = {'creator': self.submitter}
        with self.app.app_context():
            classic.create_all()
            self.title = "the best title"
            self.doi = "10.01234/56789"
            self.category = "cs.DL"
            self.submission, self.events = save(
                domain.event.CreateSubmission(**self.defaults),
                domain.event.ConfirmContactInformation(**self.defaults),
                domain.event.ConfirmAuthorship(**self.defaults),
                domain.event.ConfirmPolicy(**self.defaults),
                domain.event.SetTitle(title=self.title, **self.defaults),
                domain.event.SetLicense(license_uri=CCO,
                                        license_name="CC0 1.0",
                                        **self.defaults),
                domain.event.SetPrimaryClassification(category=self.category,
                                                      **self.defaults),
                domain.event.SetUploadPackage(checksum="a9s9k342900ks03330029",
                                              source_format=TEX,
                                              identifier=123,
                                              uncompressed_size=593992,
                                              compressed_size=593992,
                                              **self.defaults),
                domain.event.SetAbstract(abstract="Very abstract " * 20,
                                         **self.defaults),
                domain.event.SetComments(comments="Fine indeed " * 10,
                                         **self.defaults),
                domain.event.SetJournalReference(journal_ref="Foo 1992",
                                                 **self.defaults),
                domain.event.SetDOI(doi=self.doi, **self.defaults),
                domain.event.SetAuthors(authors_display='Robert Paulson (FC)',
                                        **self.defaults),
                domain.event.FinalizeSubmission(**self.defaults)
            )

        # Announce the submission.
        self.paper_id = '1901.00123'
        with self.app.app_context():
            session = classic.current_session()
            db_row = session.query(classic.models.Submission).first()
            db_row.status = classic.models.Submission.ANNOUNCED
            dated = (datetime.now() - datetime.utcfromtimestamp(0))
            db_row.document = classic.models.Document(
                document_id=1,
                paper_id=self.paper_id,
                title=self.submission.metadata.title,
                authors=self.submission.metadata.authors_display,
                dated=dated.total_seconds(),
                primary_subject_class=self.category,
                created=datetime.now(UTC),
                submitter_email=self.submission.creator.email,
                submitter_id=self.submission.creator.native_id
            )
            db_row.doc_paper_id = self.paper_id
            session.add(db_row)
            session.commit()

        # Request cross-list classification
        self.category = "cs.IR"
        with self.app.app_context():
            self.submission, self.events = save(
                domain.event.RequestCrossList(categories=[self.category],
                                              **self.defaults),
                submission_id=self.submission.submission_id
            )

    def tearDown(self):
        """Clear the database after each test."""
        with self.app.app_context():
            classic.drop_all()

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def test_has_pending_requests(self):
        """The submission has an outstanding publication."""
        with self.app.app_context():
            submission, events = load(self.submission.submission_id)
            self.assertEqual(submission.status,
                             domain.submission.Submission.ANNOUNCED,
                             "The submission is announced.")
            self.assertTrue(submission.has_active_requests,
                            "The submission has an active request.")
            self.assertEqual(len(submission.pending_user_requests), 1,
                             "There is one pending user request.")
            self.assertIsInstance(
                submission.pending_user_requests[0],
                domain.submission.CrossListClassificationRequest
            )
            self.assertIn(self.category,
                          submission.pending_user_requests[0].categories,
                          "Requested category is set on request.")
            self.assertEqual(len(submission.versions), 1,
                             "There is one announced versions")

        with self.app.app_context():
            submission = load_fast(self.submission.submission_id)
            self.assertEqual(submission.status,
                             domain.submission.Submission.ANNOUNCED,
                             "The submission is announced.")
            self.assertTrue(submission.has_active_requests,
                            "The submission has an active request.")
            self.assertEqual(len(submission.pending_user_requests), 1,
                             "There is one pending user request.")
            self.assertIsInstance(
                submission.pending_user_requests[0],
                domain.submission.CrossListClassificationRequest
            )
            self.assertIn(self.category,
                          submission.pending_user_requests[0].categories,
                          "Requested category is set on request.")
            self.assertEqual(len(submission.versions), 1,
                             "There is one announced versions")

        # Check the database state.
        with self.app.app_context():
            session = classic.current_session()
            db_rows = session.query(classic.models.Submission) \
                .order_by(classic.models.Submission.submission_id.asc()) \
                .all()

            self.assertEqual(len(db_rows), 2,
                             "There are two rows in the submission table")
            self.assertEqual(db_rows[0].type,
                             classic.models.Submission.NEW_SUBMISSION,
                             "The first row has type 'new'")
            self.assertEqual(db_rows[0].status,
                             classic.models.Submission.ANNOUNCED,
                             "The first row is announced")
            self.assertEqual(db_rows[1].type,
                             classic.models.Submission.CROSS_LIST,
                             "The second row has type 'cross'")
            self.assertEqual(db_rows[1].status,
                             classic.models.Submission.PROCESSING_SUBMISSION,
                             "The second row is in the processing submission"
                             " state.")

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def test_cannot_replace_submission(self):
        """The submission cannot be replaced."""
        with self.app.app_context():
            with self.assertRaises(exceptions.InvalidEvent):
                save(domain.event.CreateSubmissionVersion(**self.defaults),
                     submission_id=self.submission.submission_id)

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def test_cannot_withdraw_submission(self):
        """The submitter cannot request withdrawal."""
        withdrawal_reason = "the best reason"
        with self.app.app_context():
            with self.assertRaises(exceptions.InvalidEvent):
                save(domain.event.RequestWithdrawal(reason=withdrawal_reason,
                                                    **self.defaults),
                     submission_id=self.submission.submission_id)

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def test_cannot_request_another_crosslist(self):
        """The submitter cannot request a second cross-list."""
        # Cannot submit another cross-list request while one is pending.
        with self.app.app_context():
            with self.assertRaises(exceptions.InvalidEvent):
                save(domain.event.RequestCrossList(categories=["q-fin.CP"],
                                                   **self.defaults),
                     submission_id=self.submission.submission_id)

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def test_request_is_rejected(self):
        """If the request is 'removed' in classic, NG request is rejected."""
        with self.app.app_context():
            session = classic.current_session()
            db_rows = session.query(classic.models.Submission) \
                .order_by(classic.models.Submission.submission_id.asc()) \
                .all()
            db_rows[1].status = classic.models.Submission.REMOVED
            session.add(db_rows[1])
            session.commit()

        with self.app.app_context():
            submission, events = load(self.submission.submission_id)
            self.assertEqual(submission.status,
                             domain.submission.Submission.ANNOUNCED,
                             "The submission is announced.")
            self.assertFalse(submission.has_active_requests,
                             "The submission has no active requests.")
            self.assertEqual(len(submission.pending_user_requests), 0,
                             "There are no pending user request.")
            self.assertEqual(len(submission.rejected_user_requests), 1,
                             "There is one rejected user request.")
            self.assertIsInstance(
                submission.rejected_user_requests[0],
                domain.submission.CrossListClassificationRequest
            )
            self.assertIn(self.category,
                          submission.rejected_user_requests[0].categories,
                          "Requested category is set on request.")
            self.assertNotIn(self.category, submission.secondary_categories,
                             "Requested category is not added to submission")

        with self.app.app_context():
            submission = load_fast(self.submission.submission_id)
            self.assertEqual(submission.status,
                             domain.submission.Submission.ANNOUNCED,
                             "The submission is announced.")
            self.assertFalse(submission.has_active_requests,
                             "The submission has no active requests.")
            self.assertEqual(len(submission.pending_user_requests), 0,
                             "There are no pending user request.")
            self.assertEqual(len(submission.rejected_user_requests), 1,
                             "There is one rejected user request.")
            self.assertIsInstance(
                submission.rejected_user_requests[0],
                domain.submission.CrossListClassificationRequest
            )
            self.assertIn(self.category,
                          submission.rejected_user_requests[0].categories,
                          "Requested category is set on request.")
            self.assertNotIn(self.category, submission.secondary_categories,
                             "Requested category is not added to submission")

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def test_request_is_applied(self):
        """If the request is announced in classic, NG request is 'applied'."""
        with self.app.app_context():
            session = classic.current_session()
            db_rows = session.query(classic.models.Submission) \
                .order_by(classic.models.Submission.submission_id.asc()) \
                .all()
            db_rows[1].status = classic.models.Submission.ANNOUNCED
            session.add(db_rows[1])
            session.commit()

        with self.app.app_context():
            submission, events = load(self.submission.submission_id)
            self.assertEqual(submission.status,
                             domain.submission.Submission.ANNOUNCED,
                             "The submission is announced.")
            self.assertFalse(submission.has_active_requests,
                             "The submission has no active requests.")
            self.assertEqual(len(submission.pending_user_requests), 0,
                             "There are no pending user request.")
            self.assertEqual(len(submission.applied_user_requests), 1,
                             "There is one applied user request.")
            self.assertIsInstance(
                submission.applied_user_requests[0],
                domain.submission.CrossListClassificationRequest
            )
            self.assertIn(self.category,
                          submission.applied_user_requests[0].categories,
                          "Requested category is set on request.")
            self.assertIn(self.category, submission.secondary_categories,
                          "Requested category is added to submission")

        with self.app.app_context():
            submission = load_fast(self.submission.submission_id)
            self.assertEqual(submission.status,
                             domain.submission.Submission.ANNOUNCED,
                             "The submission is announced.")
            self.assertFalse(submission.has_active_requests,
                             "The submission has no active requests.")
            self.assertEqual(len(submission.pending_user_requests), 0,
                             "There are no pending user request.")
            self.assertEqual(len(submission.applied_user_requests), 1,
                             "There is one applied user request.")
            self.assertIsInstance(
                submission.applied_user_requests[0],
                domain.submission.CrossListClassificationRequest
            )
            self.assertIn(self.category,
                          submission.applied_user_requests[0].categories,
                          "Requested category is set on request.")
            self.assertIn(self.category, submission.secondary_categories,
                          "Requested category is added to submission")


class TestCrossListApplied(TestCase):
    """Request for cross-list has been approved and applied."""

    @classmethod
    def setUpClass(cls):
        """Instantiate an app for use with a SQLite database."""
        _, db = tempfile.mkstemp(suffix='.sqlite')
        cls.app = Flask('foo')
        cls.app.config['CLASSIC_DATABASE_URI'] = f'sqlite:///{db}'
        cls.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

        with cls.app.app_context():
            classic.init_app(cls.app)

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def setUp(self):
        """Create, complete, and publish the submission."""
        self.submitter = domain.agent.User(1234, email='j.user@somewhere.edu',
                                           forename='Jane', surname='User',
                                           endorsements=['cs.DL', 'cs.IR'])
        self.defaults = {'creator': self.submitter}
        with self.app.app_context():
            classic.create_all()
            self.title = "the best title"
            self.doi = "10.01234/56789"
            self.category = "cs.DL"
            self.submission, self.events = save(
                domain.event.CreateSubmission(**self.defaults),
                domain.event.ConfirmContactInformation(**self.defaults),
                domain.event.ConfirmAuthorship(**self.defaults),
                domain.event.ConfirmPolicy(**self.defaults),
                domain.event.SetTitle(title=self.title, **self.defaults),
                domain.event.SetLicense(license_uri=CCO,
                                        license_name="CC0 1.0",
                                        **self.defaults),
                domain.event.SetPrimaryClassification(category=self.category,
                                                      **self.defaults),
                domain.event.SetUploadPackage(checksum="a9s9k342900ks03330029",
                                              source_format=TEX, identifier=123,
                                              uncompressed_size=593992,
                                              compressed_size=593992,
                                              **self.defaults),
                domain.event.SetAbstract(abstract="Very abstract " * 20,
                                         **self.defaults),
                domain.event.SetComments(comments="Fine indeed " * 10,
                                         **self.defaults),
                domain.event.SetJournalReference(journal_ref="Foo 1992",
                                                 **self.defaults),
                domain.event.SetDOI(doi=self.doi, **self.defaults),
                domain.event.SetAuthors(authors_display='Robert Paulson (FC)',
                                        **self.defaults),
                domain.event.FinalizeSubmission(**self.defaults)
            )

        # Announce the submission.
        self.paper_id = '1901.00123'
        with self.app.app_context():
            session = classic.current_session()
            db_row = session.query(classic.models.Submission).first()
            db_row.status = classic.models.Submission.ANNOUNCED
            dated = (datetime.now() - datetime.utcfromtimestamp(0))
            db_row.document = classic.models.Document(
                document_id=1,
                paper_id=self.paper_id,
                title=self.submission.metadata.title,
                authors=self.submission.metadata.authors_display,
                dated=dated.total_seconds(),
                primary_subject_class=self.category,
                created=datetime.now(UTC),
                submitter_email=self.submission.creator.email,
                submitter_id=self.submission.creator.native_id
            )
            db_row.doc_paper_id = self.paper_id
            session.add(db_row)
            session.commit()

        # Request cross-list classification
        self.category = "cs.IR"
        with self.app.app_context():
            self.submission, self.events = save(
                domain.event.RequestCrossList(categories=[self.category],
                                              **self.defaults),
                submission_id=self.submission.submission_id
            )

        # Apply.
        with self.app.app_context():
            session = classic.current_session()
            db_rows = session.query(classic.models.Submission) \
                .order_by(classic.models.Submission.submission_id.asc()) \
                .all()
            db_rows[1].status = classic.models.Submission.ANNOUNCED
            session.add(db_rows[1])
            session.commit()

    def tearDown(self):
        """Clear the database after each test."""
        with self.app.app_context():
            classic.drop_all()

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def test_has_applied_requests(self):
        """The submission has an applied request."""
        with self.app.app_context():
            submission, events = load(self.submission.submission_id)
            self.assertEqual(submission.status,
                             domain.submission.Submission.ANNOUNCED,
                             "The submission is announced.")
            self.assertFalse(submission.has_active_requests,
                             "The submission has no active requests.")
            self.assertEqual(len(submission.applied_user_requests), 1,
                             "There is one pending user request.")
            self.assertIsInstance(
                submission.applied_user_requests[0],
                domain.submission.CrossListClassificationRequest
            )
            self.assertIn(self.category,
                          submission.applied_user_requests[0].categories,
                          "Requested category is set on request.")
            self.assertEqual(len(submission.versions), 1,
                             "There is one announced versions")

        with self.app.app_context():
            submission = load_fast(self.submission.submission_id)
            self.assertEqual(submission.status,
                             domain.submission.Submission.ANNOUNCED,
                             "The submission is announced.")
            self.assertFalse(submission.has_active_requests,
                             "The submission has no active requests.")
            self.assertEqual(len(submission.applied_user_requests), 1,
                             "There is one pending user request.")
            self.assertIsInstance(
                submission.applied_user_requests[0],
                domain.submission.CrossListClassificationRequest
            )
            self.assertIn(self.category,
                          submission.applied_user_requests[0].categories,
                          "Requested category is set on request.")
            self.assertEqual(len(submission.versions), 1,
                             "There is one announced versions")

        # Check the database state.
        with self.app.app_context():
            session = classic.current_session()
            db_rows = session.query(classic.models.Submission) \
                .order_by(classic.models.Submission.submission_id.asc()) \
                .all()

            self.assertEqual(len(db_rows), 2,
                             "There are two rows in the submission table")
            self.assertEqual(db_rows[0].type,
                             classic.models.Submission.NEW_SUBMISSION,
                             "The first row has type 'new'")
            self.assertEqual(db_rows[0].status,
                             classic.models.Submission.ANNOUNCED,
                             "The first row is announced")
            self.assertEqual(db_rows[1].type,
                             classic.models.Submission.CROSS_LIST,
                             "The second row has type 'cross'")
            self.assertEqual(db_rows[1].status,
                             classic.models.Submission.ANNOUNCED,
                             "The second row is in the processing submission"
                             " state.")

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def test_can_replace_submission(self):
        """The submission can be replaced, resulting in a new version."""
        with self.app.app_context():
            submission, events = save(
                domain.event.CreateSubmissionVersion(**self.defaults),
                submission_id=self.submission.submission_id
            )

        # Check the submission state.
        with self.app.app_context():
            submission, events = load(self.submission.submission_id)
            self.assertEqual(submission.status,
                             domain.submission.Submission.WORKING,
                             "The submission is in the working state")
            self.assertEqual(submission.version, 2,
                             "The version number is incremented by 1")
            self.assertEqual(len(submission.versions), 1,
                             "There is one announced versions")

        with self.app.app_context():
            submission = load_fast(self.submission.submission_id)
            self.assertEqual(submission.status,
                             domain.submission.Submission.WORKING,
                             "The submission is in the working state")
            self.assertEqual(submission.version, 2,
                             "The version number is incremented by 1")
            self.assertEqual(len(submission.versions), 1,
                             "There is one announced versions")

        # Check the database state.
        with self.app.app_context():
            session = classic.current_session()
            db_rows = session.query(classic.models.Submission) \
                .order_by(classic.models.Submission.submission_id.asc()) \
                .all()

            self.assertEqual(len(db_rows), 3,
                             "There are three rows in the submission table")
            self.assertEqual(db_rows[0].type,
                             classic.models.Submission.NEW_SUBMISSION,
                             "The first row has type 'new'")
            self.assertEqual(db_rows[0].status,
                             classic.models.Submission.ANNOUNCED,
                             "The first row is announced")
            self.assertEqual(db_rows[1].type,
                             classic.models.Submission.CROSS_LIST,
                             "The second row has type 'cross'")
            self.assertEqual(db_rows[1].status,
                             classic.models.Submission.ANNOUNCED,
                             "The second row is in the announced state")
            self.assertEqual(db_rows[2].type,
                             classic.models.Submission.REPLACEMENT,
                             "The third row has type 'replacement'")
            self.assertEqual(db_rows[2].status,
                             classic.models.Submission.NOT_SUBMITTED,
                             "The third row is in not submitted state")

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def test_can_withdraw_submission(self):
        """The submitter can request withdrawal of the submission."""
        withdrawal_reason = "the best reason"
        with self.app.app_context():
            submission, events = save(
                domain.event.RequestWithdrawal(reason=withdrawal_reason,
                                               **self.defaults),
                submission_id=self.submission.submission_id
            )

        # Check the submission state.
        with self.app.app_context():
            submission, events = load(self.submission.submission_id)
            self.assertEqual(submission.status,
                             domain.submission.Submission.ANNOUNCED,
                             "The submission is announced.")
            self.assertTrue(submission.has_active_requests,
                            "The submission has an active request.")
            self.assertEqual(len(submission.pending_user_requests), 1,
                             "There is one pending user request.")
            self.assertIsInstance(submission.pending_user_requests[0],
                                  domain.submission.WithdrawalRequest)
            self.assertEqual(
                submission.pending_user_requests[0].reason_for_withdrawal,
                withdrawal_reason,
                "Withdrawal reason is set on request."
            )
            self.assertEqual(len(submission.versions), 1,
                             "There is one announced versions")

        with self.app.app_context():
            submission = load_fast(self.submission.submission_id)
            self.assertEqual(submission.status,
                             domain.submission.Submission.ANNOUNCED,
                             "The submission is announced.")
            self.assertTrue(submission.has_active_requests,
                            "The submission has an active request.")
            self.assertEqual(len(submission.pending_user_requests), 1,
                             "There is one pending user request.")
            self.assertIsInstance(submission.pending_user_requests[0],
                                  domain.submission.WithdrawalRequest)
            self.assertEqual(
                submission.pending_user_requests[0].reason_for_withdrawal,
                withdrawal_reason,
                "Withdrawal reason is set on request."
            )
            self.assertEqual(len(submission.versions), 1,
                             "There is one announced versions")

        # Check the database state.
        with self.app.app_context():
            session = classic.current_session()
            db_rows = session.query(classic.models.Submission) \
                .order_by(classic.models.Submission.submission_id.asc()) \
                .all()

            self.assertEqual(len(db_rows), 3,
                             "There are three rows in the submission table")
            self.assertEqual(db_rows[0].type,
                             classic.models.Submission.NEW_SUBMISSION,
                             "The first row has type 'new'")
            self.assertEqual(db_rows[0].status,
                             classic.models.Submission.ANNOUNCED,
                             "The first row is announced")
            self.assertEqual(db_rows[1].type,
                             classic.models.Submission.CROSS_LIST,
                             "The second row has type 'cross'")
            self.assertEqual(db_rows[1].status,
                             classic.models.Submission.ANNOUNCED,
                             "The second row is in the announced state")
            self.assertEqual(db_rows[2].type,
                             classic.models.Submission.WITHDRAWAL,
                             "The third row has type 'withdrawal'")
            self.assertEqual(db_rows[2].status,
                             classic.models.Submission.PROCESSING_SUBMISSION,
                             "The third row is in the processing submission"
                             " state.")

        # Cannot submit another withdrawal request while one is pending.
        with self.app.app_context():
            with self.assertRaises(exceptions.InvalidEvent):
                save(domain.event.RequestWithdrawal(reason="more reason",
                                                    **self.defaults),
                     submission_id=self.submission.submission_id)

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def test_can_request_crosslist(self):
        """The submitter can request cross-list classification."""
        category = "cs.LO"
        with self.app.app_context():
            submission, events = save(
                domain.event.RequestCrossList(categories=[category],
                                              **self.defaults),
                submission_id=self.submission.submission_id
            )

        # Check the submission state.
        with self.app.app_context():
            submission, events = load(self.submission.submission_id)
            self.assertEqual(submission.status,
                             domain.submission.Submission.ANNOUNCED,
                             "The submission is announced.")
            self.assertTrue(submission.has_active_requests,
                            "The submission has an active request.")
            self.assertEqual(len(submission.pending_user_requests), 1,
                             "There is one pending user request.")
            self.assertIsInstance(
                submission.pending_user_requests[0],
                domain.submission.CrossListClassificationRequest
            )
            self.assertIn(category,
                          submission.pending_user_requests[0].categories,
                          "Requested category is set on request.")
            self.assertEqual(len(submission.versions), 1,
                             "There is one announced versions")

        with self.app.app_context():
            submission = load_fast(self.submission.submission_id)
            self.assertEqual(submission.status,
                             domain.submission.Submission.ANNOUNCED,
                             "The submission is announced.")
            self.assertTrue(submission.has_active_requests,
                            "The submission has an active request.")
            self.assertEqual(len(submission.pending_user_requests), 1,
                             "There is one pending user request.")
            self.assertIsInstance(
                submission.pending_user_requests[0],
                domain.submission.CrossListClassificationRequest
            )
            self.assertIn(category,
                          submission.pending_user_requests[0].categories,
                          "Requested category is set on request.")
            self.assertEqual(len(submission.versions), 1,
                             "There is one announced versions")

        # Check the database state.
        with self.app.app_context():
            session = classic.current_session()
            db_rows = session.query(classic.models.Submission) \
                .order_by(classic.models.Submission.submission_id.asc()) \
                .all()

            self.assertEqual(len(db_rows), 3,
                             "There are three rows in the submission table")
            self.assertEqual(db_rows[0].type,
                             classic.models.Submission.NEW_SUBMISSION,
                             "The first row has type 'new'")
            self.assertEqual(db_rows[0].status,
                             classic.models.Submission.ANNOUNCED,
                             "The first row is announced")
            self.assertEqual(db_rows[1].type,
                             classic.models.Submission.CROSS_LIST,
                             "The second row has type 'cross'")
            self.assertEqual(db_rows[1].status,
                             classic.models.Submission.ANNOUNCED,
                             "The second row is in the announced state")
            self.assertEqual(db_rows[2].type,
                             classic.models.Submission.CROSS_LIST,
                             "The third row has type 'cross'")
            self.assertEqual(db_rows[2].status,
                             classic.models.Submission.PROCESSING_SUBMISSION,
                             "The third row is in the processing submission"
                             " state.")


class TestCrossListRejected(TestCase):
    """Request for cross-list has been rejected."""

    @classmethod
    def setUpClass(cls):
        """Instantiate an app for use with a SQLite database."""
        _, db = tempfile.mkstemp(suffix='.sqlite')
        cls.app = Flask('foo')
        cls.app.config['CLASSIC_DATABASE_URI'] = f'sqlite:///{db}'
        cls.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

        with cls.app.app_context():
            classic.init_app(cls.app)

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def setUp(self):
        """Create, complete, and publish the submission."""
        self.submitter = domain.agent.User(1234, email='j.user@somewhere.edu',
                                           forename='Jane', surname='User',
                                           endorsements=['cs.DL', 'cs.IR'])
        self.defaults = {'creator': self.submitter}
        with self.app.app_context():
            classic.create_all()
            self.title = "the best title"
            self.doi = "10.01234/56789"
            self.category = "cs.DL"
            self.submission, self.events = save(
                domain.event.CreateSubmission(**self.defaults),
                domain.event.ConfirmContactInformation(**self.defaults),
                domain.event.ConfirmAuthorship(**self.defaults),
                domain.event.ConfirmPolicy(**self.defaults),
                domain.event.SetTitle(title=self.title, **self.defaults),
                domain.event.SetLicense(license_uri=CCO,
                                        license_name="CC0 1.0",
                                        **self.defaults),
                domain.event.SetPrimaryClassification(category=self.category,
                                                      **self.defaults),
                domain.event.SetUploadPackage(checksum="a9s9k342900ks03330029",
                                              source_format=TEX,
                                              identifier=123,
                                              uncompressed_size=593992,
                                              compressed_size=593992,
                                              **self.defaults),
                domain.event.SetAbstract(abstract="Very abstract " * 20,
                                         **self.defaults),
                domain.event.SetComments(comments="Fine indeed " * 10,
                                         **self.defaults),
                domain.event.SetJournalReference(journal_ref="Foo 1992",
                                                 **self.defaults),
                domain.event.SetDOI(doi=self.doi, **self.defaults),
                domain.event.SetAuthors(authors_display='Robert Paulson (FC)',
                                        **self.defaults),
                domain.event.FinalizeSubmission(**self.defaults)
            )

        # Announce the submission.
        self.paper_id = '1901.00123'
        with self.app.app_context():
            session = classic.current_session()
            db_row = session.query(classic.models.Submission).first()
            db_row.status = classic.models.Submission.ANNOUNCED
            dated = (datetime.now() - datetime.utcfromtimestamp(0))
            db_row.document = classic.models.Document(
                document_id=1,
                paper_id=self.paper_id,
                title=self.submission.metadata.title,
                authors=self.submission.metadata.authors_display,
                dated=dated.total_seconds(),
                primary_subject_class=self.category,
                created=datetime.now(UTC),
                submitter_email=self.submission.creator.email,
                submitter_id=self.submission.creator.native_id
            )
            db_row.doc_paper_id = self.paper_id
            session.add(db_row)
            session.commit()

        # Request cross-list classification
        self.category = "cs.IR"
        with self.app.app_context():
            self.submission, self.events = save(
                domain.event.RequestCrossList(categories=[self.category],
                                              **self.defaults),
                submission_id=self.submission.submission_id
            )

        # Apply.
        with self.app.app_context():
            session = classic.current_session()
            db_rows = session.query(classic.models.Submission) \
                .order_by(classic.models.Submission.submission_id.asc()) \
                .all()
            db_rows[1].status = classic.models.Submission.REMOVED
            session.add(db_rows[1])
            session.commit()

    def tearDown(self):
        """Clear the database after each test."""
        with self.app.app_context():
            classic.drop_all()

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def test_has_rejected_request(self):
        """The submission has a rejected request."""
        with self.app.app_context():
            submission, events = load(self.submission.submission_id)
            self.assertEqual(submission.status,
                             domain.submission.Submission.ANNOUNCED,
                             "The submission is announced.")
            self.assertFalse(submission.has_active_requests,
                             "The submission has no active requests.")
            self.assertEqual(len(submission.pending_user_requests), 0,
                             "There is are no pending user requests.")
            self.assertEqual(len(submission.rejected_user_requests), 1,
                             "There is one rejected user request.")
            self.assertIsInstance(
                submission.rejected_user_requests[0],
                domain.submission.CrossListClassificationRequest
            )
            self.assertIn(self.category,
                          submission.rejected_user_requests[0].categories,
                          "Requested category is set on request.")
            self.assertEqual(len(submission.versions), 1,
                             "There is one announced versions")

        with self.app.app_context():
            submission = load_fast(self.submission.submission_id)
            self.assertEqual(submission.status,
                             domain.submission.Submission.ANNOUNCED,
                             "The submission is announced.")
            self.assertFalse(submission.has_active_requests,
                             "The submission has no active requests.")
            self.assertEqual(len(submission.pending_user_requests), 0,
                             "There is are no pending user requests.")
            self.assertEqual(len(submission.rejected_user_requests), 1,
                             "There is one rejected user request.")
            self.assertIsInstance(
                submission.rejected_user_requests[0],
                domain.submission.CrossListClassificationRequest
            )
            self.assertIn(self.category,
                          submission.rejected_user_requests[0].categories,
                          "Requested category is set on request.")
            self.assertEqual(len(submission.versions), 1,
                             "There is one announced versions")

        # Check the database state.
        with self.app.app_context():
            session = classic.current_session()
            db_rows = session.query(classic.models.Submission) \
                .order_by(classic.models.Submission.submission_id.asc()) \
                .all()

            self.assertEqual(len(db_rows), 2,
                             "There are two rows in the submission table")
            self.assertEqual(db_rows[0].type,
                             classic.models.Submission.NEW_SUBMISSION,
                             "The first row has type 'new'")
            self.assertEqual(db_rows[0].status,
                             classic.models.Submission.ANNOUNCED,
                             "The first row is announced")
            self.assertEqual(db_rows[1].type,
                             classic.models.Submission.CROSS_LIST,
                             "The second row has type 'cross'")
            self.assertEqual(db_rows[1].status,
                             classic.models.Submission.REMOVED,
                             "The second row is in the removed state.")

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def test_can_replace_submission(self):
        """The submission can be replaced, resulting in a new version."""
        with self.app.app_context():
            submission, events = save(
                domain.event.CreateSubmissionVersion(**self.defaults),
                submission_id=self.submission.submission_id
            )

        # Check the submission state.
        with self.app.app_context():
            submission, events = load(self.submission.submission_id)
            self.assertEqual(submission.status,
                             domain.submission.Submission.WORKING,
                             "The submission is in the working state")
            self.assertEqual(submission.version, 2,
                             "The version number is incremented by 1")
            self.assertEqual(len(submission.versions), 1,
                             "There is one announced versions")

        with self.app.app_context():
            submission = load_fast(self.submission.submission_id)
            self.assertEqual(submission.status,
                             domain.submission.Submission.WORKING,
                             "The submission is in the working state")
            self.assertEqual(submission.version, 2,
                             "The version number is incremented by 1")
            self.assertEqual(len(submission.versions), 1,
                             "There is one announced versions")

        # Check the database state.
        with self.app.app_context():
            session = classic.current_session()
            db_rows = session.query(classic.models.Submission) \
                .order_by(classic.models.Submission.submission_id.asc()) \
                .all()

            self.assertEqual(len(db_rows), 3,
                             "There are three rows in the submission table")
            self.assertEqual(db_rows[0].type,
                             classic.models.Submission.NEW_SUBMISSION,
                             "The first row has type 'new'")
            self.assertEqual(db_rows[0].status,
                             classic.models.Submission.ANNOUNCED,
                             "The first row is announced")
            self.assertEqual(db_rows[1].type,
                             classic.models.Submission.CROSS_LIST,
                             "The second row has type 'cross'")
            self.assertEqual(db_rows[1].status,
                             classic.models.Submission.REMOVED,
                             "The second row is in the removed state")
            self.assertEqual(db_rows[2].type,
                             classic.models.Submission.REPLACEMENT,
                             "The third row has type 'replacement'")
            self.assertEqual(db_rows[2].status,
                             classic.models.Submission.NOT_SUBMITTED,
                             "The third row is in not submitted state")

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def test_can_withdraw_submission(self):
        """The submitter can request withdrawal of the submission."""
        withdrawal_reason = "the best reason"
        with self.app.app_context():
            submission, events = save(
                domain.event.RequestWithdrawal(reason=withdrawal_reason,
                                               **self.defaults),
                submission_id=self.submission.submission_id
            )

        # Check the submission state.
        with self.app.app_context():
            submission, events = load(self.submission.submission_id)
            self.assertEqual(submission.status,
                             domain.submission.Submission.ANNOUNCED,
                             "The submission is announced.")
            self.assertTrue(submission.has_active_requests,
                            "The submission has an active request.")
            self.assertEqual(len(submission.pending_user_requests), 1,
                             "There is one pending user request.")
            self.assertIsInstance(submission.pending_user_requests[0],
                                  domain.submission.WithdrawalRequest)
            self.assertEqual(
                submission.pending_user_requests[0].reason_for_withdrawal,
                withdrawal_reason,
                "Withdrawal reason is set on request."
            )
            self.assertEqual(len(submission.versions), 1,
                             "There is one announced versions")

        with self.app.app_context():
            submission = load_fast(self.submission.submission_id)
            self.assertEqual(submission.status,
                             domain.submission.Submission.ANNOUNCED,
                             "The submission is announced.")
            self.assertTrue(submission.has_active_requests,
                            "The submission has an active request.")
            self.assertEqual(len(submission.pending_user_requests), 1,
                             "There is one pending user request.")
            self.assertIsInstance(submission.pending_user_requests[0],
                                  domain.submission.WithdrawalRequest)
            self.assertEqual(
                submission.pending_user_requests[0].reason_for_withdrawal,
                withdrawal_reason,
                "Withdrawal reason is set on request."
            )
            self.assertEqual(len(submission.versions), 1,
                             "There is one announced versions")

        # Check the database state.
        with self.app.app_context():
            session = classic.current_session()
            db_rows = session.query(classic.models.Submission) \
                .order_by(classic.models.Submission.submission_id.asc()) \
                .all()

            self.assertEqual(len(db_rows), 3,
                             "There are three rows in the submission table")
            self.assertEqual(db_rows[0].type,
                             classic.models.Submission.NEW_SUBMISSION,
                             "The first row has type 'new'")
            self.assertEqual(db_rows[0].status,
                             classic.models.Submission.ANNOUNCED,
                             "The first row is announced")
            self.assertEqual(db_rows[1].type,
                             classic.models.Submission.CROSS_LIST,
                             "The second row has type 'cross'")
            self.assertEqual(db_rows[1].status,
                             classic.models.Submission.REMOVED,
                             "The second row is in the removed state")
            self.assertEqual(db_rows[2].type,
                             classic.models.Submission.WITHDRAWAL,
                             "The third row has type 'withdrawal'")
            self.assertEqual(db_rows[2].status,
                             classic.models.Submission.PROCESSING_SUBMISSION,
                             "The third row is in the processing submission"
                             " state.")

        # Cannot submit another withdrawal request while one is pending.
        with self.app.app_context():
            with self.assertRaises(exceptions.InvalidEvent):
                save(domain.event.RequestWithdrawal(reason="more reason",
                                                    **self.defaults),
                     submission_id=self.submission.submission_id)

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def test_can_request_crosslist(self):
        """The submitter can request cross-list classification."""
        category = "cs.LO"
        with self.app.app_context():
            submission, events = save(
                domain.event.RequestCrossList(categories=[category],
                                              **self.defaults),
                submission_id=self.submission.submission_id
            )

        # Check the submission state.
        with self.app.app_context():
            submission, events = load(self.submission.submission_id)
            self.assertEqual(submission.status,
                             domain.submission.Submission.ANNOUNCED,
                             "The submission is announced.")
            self.assertTrue(submission.has_active_requests,
                            "The submission has an active request.")
            self.assertEqual(len(submission.pending_user_requests), 1,
                             "There is one pending user request.")
            self.assertIsInstance(
                submission.pending_user_requests[0],
                domain.submission.CrossListClassificationRequest
            )
            self.assertIn(category,
                          submission.pending_user_requests[0].categories,
                          "Requested category is set on request.")
            self.assertEqual(len(submission.versions), 1,
                             "There is one announced versions")

        with self.app.app_context():
            submission = load_fast(self.submission.submission_id)
            self.assertEqual(submission.status,
                             domain.submission.Submission.ANNOUNCED,
                             "The submission is announced.")
            self.assertTrue(submission.has_active_requests,
                            "The submission has an active request.")
            self.assertEqual(len(submission.pending_user_requests), 1,
                             "There is one pending user request.")
            self.assertIsInstance(
                submission.pending_user_requests[0],
                domain.submission.CrossListClassificationRequest
            )
            self.assertIn(category,
                          submission.pending_user_requests[0].categories,
                          "Requested category is set on request.")
            self.assertEqual(len(submission.versions), 1,
                             "There is one announced versions")

        # Check the database state.
        with self.app.app_context():
            session = classic.current_session()
            db_rows = session.query(classic.models.Submission) \
                .order_by(classic.models.Submission.submission_id.asc()) \
                .all()

            self.assertEqual(len(db_rows), 3,
                             "There are three rows in the submission table")
            self.assertEqual(db_rows[0].type,
                             classic.models.Submission.NEW_SUBMISSION,
                             "The first row has type 'new'")
            self.assertEqual(db_rows[0].status,
                             classic.models.Submission.ANNOUNCED,
                             "The first row is announced")
            self.assertEqual(db_rows[1].type,
                             classic.models.Submission.CROSS_LIST,
                             "The second row has type 'cross'")
            self.assertEqual(db_rows[1].status,
                             classic.models.Submission.REMOVED,
                             "The second row is in the removed state")
            self.assertEqual(db_rows[2].type,
                             classic.models.Submission.CROSS_LIST,
                             "The third row has type 'cross'")
            self.assertEqual(db_rows[2].status,
                             classic.models.Submission.PROCESSING_SUBMISSION,
                             "The third row is in the processing submission"
                             " state.")
