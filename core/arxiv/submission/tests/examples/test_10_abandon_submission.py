"""Example 10: abandoning submissions and requests."""

from unittest import TestCase, mock
import tempfile
from datetime import datetime
from pytz import UTC

from flask import Flask

from ...services import classic
from ... import save, load, load_fast, domain, exceptions, core

CCO = 'http://creativecommons.org/publicdomain/zero/1.0/'
TEX = domain.submission.SubmissionContent.Format('tex')


class TestAbandonSubmission(TestCase):
    """Submitter has started a submission."""

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
                                                      **self.defaults)
            )

    def tearDown(self):
        """Clear the database after each test."""
        with self.app.app_context():
            classic.drop_all()

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def test_abandon_new_submission(self):
        """Submitter abandons new submission."""
        with self.app.app_context():
            self.submission, self.events = save(
                domain.event.Rollback(**self.defaults),
                submission_id=self.submission.submission_id
            )

        with self.app.app_context():
            submission, events = load(self.submission.submission_id)
            self.assertEqual(submission.status,
                             domain.submission.Submission.DELETED,
                             "The submission is DELETED.")

        with self.app.app_context():
            submission = load_fast(self.submission.submission_id)
            self.assertEqual(submission.status,
                             domain.submission.Submission.DELETED,
                             "The submission is DELETED.")

        # Check the database state.
        with self.app.app_context():
            session = classic.current_session()
            db_rows = session.query(classic.models.Submission) \
                .order_by(classic.models.Submission.submission_id.asc()) \
                .all()

            self.assertEqual(len(db_rows), 1,
                             "There are one rows in the submission table")
            self.assertEqual(db_rows[0].type,
                             classic.models.Submission.NEW_SUBMISSION,
                             "The first row has type 'new'")
            self.assertEqual(db_rows[0].status,
                             classic.models.Submission.USER_DELETED,
                             "The first row is USER_DELETED")


class TestAbandonReplacement(TestCase):
    """Submitter has started a replacement and then rolled it back."""

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

        with self.app.app_context():
            submission, events = save(
                domain.event.CreateSubmissionVersion(**self.defaults),
                submission_id=self.submission.submission_id
            )

        with self.app.app_context():
            self.submission, self.events = save(
                domain.event.Rollback(**self.defaults),
                submission_id=self.submission.submission_id
            )

    def tearDown(self):
        """Clear the database after each test."""
        with self.app.app_context():
            classic.drop_all()

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def test_abandon_replacement_submission(self):
        """The replacement is cancelled."""
        with self.app.app_context():
            submission, events = load(self.submission.submission_id)
            self.assertEqual(submission.status,
                             domain.submission.Submission.ANNOUNCED,
                             "The submission is ANNOUNCED.")
            self.assertEqual(submission.version, 1, "Back to v1")

        with self.app.app_context():
            submission = load_fast(self.submission.submission_id)
            self.assertEqual(submission.status,
                             domain.submission.Submission.ANNOUNCED,
                             "The submission is ANNOUNCED.")
            self.assertEqual(submission.version, 1, "Back to v1")

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
                             "The first row is ANNOUNCED")
            self.assertEqual(db_rows[1].type,
                             classic.models.Submission.REPLACEMENT,
                             "The second row has type 'replacement'")
            self.assertEqual(db_rows[1].status,
                             classic.models.Submission.USER_DELETED,
                             "The second row is USER_DELETED")

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def test_can_start_new_replacement(self):
        """The user can start a new replacement."""
        with self.app.app_context():
            submission, events = save(
                domain.event.CreateSubmissionVersion(**self.defaults),
                submission_id=self.submission.submission_id
            )

        with self.app.app_context():
            submission, events = load(self.submission.submission_id)
            self.assertEqual(submission.status,
                             domain.submission.Submission.WORKING,
                             "The submission is WORKING.")
            self.assertEqual(submission.version, 2, "On to v2")

        with self.app.app_context():
            submission = load_fast(self.submission.submission_id)
            self.assertEqual(submission.status,
                             domain.submission.Submission.WORKING,
                             "The submission is WORKING.")
            self.assertEqual(submission.version, 2, "On to v2")

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
                             "The first row is ANNOUNCED")
            self.assertEqual(db_rows[1].type,
                             classic.models.Submission.REPLACEMENT,
                             "The second row has type 'replacement'")
            self.assertEqual(db_rows[1].status,
                             classic.models.Submission.USER_DELETED,
                             "The second row is USER_DELETED")
            self.assertEqual(db_rows[2].type,
                             classic.models.Submission.REPLACEMENT,
                             "The third row has type 'replacement'")
            self.assertEqual(db_rows[2].status,
                             classic.models.Submission.NOT_SUBMITTED,
                             "The third row is NOT_SUBMITTED")


class TestCrossListCancelled(TestCase):
    """Submitter has created and cancelled a cross-list request."""

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
        category = "cs.IR"
        with self.app.app_context():
            self.submission, self.events = save(
                domain.event.RequestCrossList(categories=[category],
                                              **self.defaults),
                submission_id=self.submission.submission_id
            )

        with self.app.app_context():
            request_id = self.submission.active_user_requests[0].request_id
            self.submission, self.events = save(
                domain.event.CancelRequest(request_id=request_id,
                                           **self.defaults),
                submission_id=self.submission.submission_id
            )

    def tearDown(self):
        """Clear the database after each test."""
        with self.app.app_context():
            classic.drop_all()

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def test_request_is_cancelled(self):
        """Submitter has cancelled the cross-list request."""
        with self.app.app_context():
            submission, events = load(self.submission.submission_id)
            self.assertEqual(submission.status,
                             domain.submission.Submission.ANNOUNCED,
                             "The submission is ANNOUNCED.")

        with self.app.app_context():
            submission = load_fast(self.submission.submission_id)
            self.assertEqual(submission.status,
                             domain.submission.Submission.ANNOUNCED,
                             "The submission is ANNOUNCED.")

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
                             "The first row is ANNOUNCED")
            self.assertEqual(db_rows[1].type,
                             classic.models.Submission.CROSS_LIST,
                             "The second row has type 'cross'")
            self.assertEqual(db_rows[1].status,
                             classic.models.Submission.USER_DELETED,
                             "The second row is USER_DELETED")

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def test_user_can_make_another_request(self):
        """User can now make another request."""
        # Request cross-list classification
        category = "cs.IR"
        with self.app.app_context():
            self.submission, self.events = save(
                domain.event.RequestCrossList(categories=[category],
                                              **self.defaults),
                submission_id=self.submission.submission_id
            )

        with self.app.app_context():
            submission, events = load(self.submission.submission_id)
            self.assertEqual(submission.status,
                             domain.submission.Submission.ANNOUNCED,
                             "The submission is ANNOUNCED.")

        with self.app.app_context():
            submission = load_fast(self.submission.submission_id)
            self.assertEqual(submission.status,
                             domain.submission.Submission.ANNOUNCED,
                             "The submission is ANNOUNCED.")

        # Check the database state.
        with self.app.app_context():
            session = classic.current_session()
            db_rows = session.query(classic.models.Submission) \
                .order_by(classic.models.Submission.submission_id.asc()) \
                .all()

            self.assertEqual(len(db_rows), 3,
                             "There are two rows in the submission table")
            self.assertEqual(db_rows[0].type,
                             classic.models.Submission.NEW_SUBMISSION,
                             "The first row has type 'new'")
            self.assertEqual(db_rows[0].status,
                             classic.models.Submission.ANNOUNCED,
                             "The first row is ANNOUNCED")
            self.assertEqual(db_rows[1].type,
                             classic.models.Submission.CROSS_LIST,
                             "The second row has type 'cross'")
            self.assertEqual(db_rows[1].status,
                             classic.models.Submission.USER_DELETED,
                             "The second row is USER_DELETED")
            self.assertEqual(db_rows[2].type,
                             classic.models.Submission.CROSS_LIST,
                             "The third row has type 'cross'")
            self.assertEqual(db_rows[2].status,
                             classic.models.Submission.PROCESSING_SUBMISSION,
                             "The third row is PROCESSING_SUBMISSION")


class TestWithdrawalCancelled(TestCase):
    """Submitter has created and cancelled a withdrawal request."""

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
        category = "cs.IR"
        with self.app.app_context():
            self.submission, self.events = save(
                domain.event.RequestWithdrawal(reason='A good reason',
                                               **self.defaults),
                submission_id=self.submission.submission_id
            )

        with self.app.app_context():
            request_id = self.submission.active_user_requests[0].request_id
            self.submission, self.events = save(
                domain.event.CancelRequest(request_id=request_id,
                                           **self.defaults),
                submission_id=self.submission.submission_id
            )

    def tearDown(self):
        """Clear the database after each test."""
        with self.app.app_context():
            classic.drop_all()

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def test_request_is_cancelled(self):
        """Submitter has cancelled the withdrawal request."""
        with self.app.app_context():
            submission, events = load(self.submission.submission_id)
            self.assertEqual(submission.status,
                             domain.submission.Submission.ANNOUNCED,
                             "The submission is ANNOUNCED.")

        with self.app.app_context():
            submission = load_fast(self.submission.submission_id)
            self.assertEqual(submission.status,
                             domain.submission.Submission.ANNOUNCED,
                             "The submission is ANNOUNCED.")

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
                             "The first row is ANNOUNCED")
            self.assertEqual(db_rows[1].type,
                             classic.models.Submission.WITHDRAWAL,
                             "The second row has type 'wdr'")
            self.assertEqual(db_rows[1].status,
                             classic.models.Submission.USER_DELETED,
                             "The second row is USER_DELETED")

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def test_user_can_make_another_request(self):
        """User can now make another request."""
        with self.app.app_context():
            self.submission, self.events = save(
                domain.event.RequestWithdrawal(reason='A better reason',
                                               **self.defaults),
                submission_id=self.submission.submission_id
            )

        with self.app.app_context():
            submission, events = load(self.submission.submission_id)
            self.assertEqual(submission.status,
                             domain.submission.Submission.ANNOUNCED,
                             "The submission is ANNOUNCED.")

        with self.app.app_context():
            submission = load_fast(self.submission.submission_id)
            self.assertEqual(submission.status,
                             domain.submission.Submission.ANNOUNCED,
                             "The submission is ANNOUNCED.")

        # Check the database state.
        with self.app.app_context():
            session = classic.current_session()
            db_rows = session.query(classic.models.Submission) \
                .order_by(classic.models.Submission.submission_id.asc()) \
                .all()

            self.assertEqual(len(db_rows), 3,
                             "There are two rows in the submission table")
            self.assertEqual(db_rows[0].type,
                             classic.models.Submission.NEW_SUBMISSION,
                             "The first row has type 'new'")
            self.assertEqual(db_rows[0].status,
                             classic.models.Submission.ANNOUNCED,
                             "The first row is ANNOUNCED")
            self.assertEqual(db_rows[1].type,
                             classic.models.Submission.WITHDRAWAL,
                             "The second row has type 'wdr'")
            self.assertEqual(db_rows[1].status,
                             classic.models.Submission.USER_DELETED,
                             "The second row is USER_DELETED")
            self.assertEqual(db_rows[2].type,
                             classic.models.Submission.WITHDRAWAL,
                             "The third row has type 'wdr'")
            self.assertEqual(db_rows[2].status,
                             classic.models.Submission.PROCESSING_SUBMISSION,
                             "The third row is PROCESSING_SUBMISSION")

        with self.app.app_context():
            request_id = self.submission.active_user_requests[-1].request_id
            self.submission, self.events = save(
                domain.event.CancelRequest(request_id=request_id,
                                           **self.defaults),
                submission_id=self.submission.submission_id
            )

        with self.app.app_context():
            self.submission, self.events = save(
                domain.event.RequestWithdrawal(reason='A better reason',
                                               **self.defaults),
                submission_id=self.submission.submission_id
            )

        with self.app.app_context():
            request_id = self.submission.active_user_requests[-1].request_id
            self.submission, self.events = save(
                domain.event.CancelRequest(request_id=request_id,
                                           **self.defaults),
                submission_id=self.submission.submission_id
            )
            submission, events = load(self.submission.submission_id)
            self.assertEqual(len(submission.active_user_requests), 0)
