"""Example 2: finalized submission."""

from unittest import TestCase, mock
import tempfile

from flask import Flask

from ...services import classic, StreamPublisher

from ... import save, load, load_fast, domain, exceptions
from ... import core

CCO = 'http://creativecommons.org/publicdomain/zero/1.0/'


class TestFinalizedSubmission(TestCase):
    """
    Submitter creates, completes, and finalizes a new submission.

    At this point the submission is in the queue for moderation and
    announcement.
    """

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
        """Create, and complete the submission."""
        self.submitter = domain.agent.User(1234, email='j.user@somewhere.edu',
                                           forename='Jane', surname='User',
                                           endorsements=['cs.DL', 'cs.IR'])
        self.defaults = {'creator': self.submitter}
        with self.app.app_context():
            classic.create_all()
            self.title = "the best title"
            self.doi = "10.01234/56789"
            self.submission, self.events = save(
                domain.event.CreateSubmission(**self.defaults),
                domain.event.ConfirmContactInformation(**self.defaults),
                domain.event.ConfirmAuthorship(**self.defaults),
                domain.event.ConfirmPolicy(**self.defaults),
                domain.event.SetTitle(title=self.title, **self.defaults),
                domain.event.SetLicense(license_uri=CCO,
                                        license_name="CC0 1.0",
                                        **self.defaults),
                domain.event.SetPrimaryClassification(category="cs.DL",
                                                      **self.defaults),
                domain.event.SetUploadPackage(checksum="a9s9k342900ks03330029",
                                              source_format=domain.submission.SubmissionContent.Format('tex'), identifier=123,
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

    def tearDown(self):
        """Clear the database after each test."""
        with self.app.app_context():
            classic.drop_all()

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def test_is_in_submitted_state(self):
        """
        The submission is now submitted.

        This moves the submission into consideration for announcement, and
        is visible to moderators.
        """
        # Check the submission state.
        with self.app.app_context():
            submission, events = load(self.submission.submission_id)
            self.assertEqual(submission.status,
                             domain.submission.Submission.SUBMITTED,
                             "The submission is in the submitted state")
            self.assertEqual(len(submission.versions), 0,
                             "There are no announced versions")

        with self.app.app_context():
            submission = load_fast(self.submission.submission_id)
            self.assertEqual(submission.status,
                             domain.submission.Submission.SUBMITTED,
                             "The submission is in the submitted state")
            self.assertEqual(len(submission.versions), 0,
                             "There are no announced versions")

        # Check the database state.
        with self.app.app_context():
            session = classic.current_session()
            db_rows = session.query(classic.models.Submission).all()

            self.assertEqual(len(db_rows), 1,
                             "There is one row in the submission table")
            row = db_rows[0]
            self.assertEqual(row.type,
                             classic.models.Submission.NEW_SUBMISSION,
                             "The classic submission has type 'new'")
            self.assertEqual(row.status,
                             classic.models.Submission.SUBMITTED,
                             "The classic submission is in the SUBMITTED"
                             " state")

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def test_cannot_replace_submission(self):
        """The submission cannot be replaced: it hasn't yet been announced."""
        with self.app.app_context():
            with self.assertRaises(exceptions.InvalidEvent, msg=(
                    "Creating a CreateSubmissionVersion command results in an"
                    " exception.")):
                save(domain.event.CreateSubmissionVersion(**self.defaults),
                     submission_id=self.submission.submission_id)

        self.test_is_in_submitted_state()

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def test_cannot_withdraw_submission(self):
        """The submission cannot be withdrawn: it hasn't yet been announced."""
        with self.app.app_context():
            with self.assertRaises(exceptions.InvalidEvent, msg=(
                    "Creating a RequestWithdrawal command results in an"
                    " exception.")):
                save(domain.event.RequestWithdrawal(reason="the best reason",
                                                    **self.defaults),
                     submission_id=self.submission.submission_id)

        self.test_is_in_submitted_state()

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def test_cannot_edit_submission(self):
        """The submission cannot be changed: it hasn't yet been announced."""
        with self.app.app_context():
            with self.assertRaises(exceptions.InvalidEvent, msg=(
                    "Creating a SetTitle command results in an exception.")):
                save(domain.event.SetTitle(title="A better title",
                                           **self.defaults),
                     submission_id=self.submission.submission_id)

            with self.assertRaises(exceptions.InvalidEvent, msg=(
                    "Creating a SetDOI command results in an exception.")):
                save(domain.event.SetDOI(doi="10.1000/182", **self.defaults),
                     submission_id=self.submission.submission_id)

        self.test_is_in_submitted_state()

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def test_can_be_unfinalized(self):
        """The submission can be unfinalized."""
        with self.app.app_context():
            save(domain.event.UnFinalizeSubmission(**self.defaults),
                 submission_id=self.submission.submission_id)

        # Check the submission state.
        with self.app.app_context():
            submission, events = load(self.submission.submission_id)
            self.assertEqual(submission.status,
                             domain.submission.Submission.WORKING,
                             "The submission is in the working state")
            self.assertEqual(len(submission.versions), 0,
                             "There are no announced versions")

        with self.app.app_context():
            submission = load_fast(self.submission.submission_id)
            self.assertEqual(submission.status,
                             domain.submission.Submission.WORKING,
                             "The submission is in the working state")
            self.assertEqual(len(submission.versions), 0,
                             "There are no announced versions")

        # Check the database state.
        with self.app.app_context():
            session = classic.current_session()
            db_rows = session.query(classic.models.Submission).all()

            self.assertEqual(len(db_rows), 1,
                             "There is one row in the submission table")
            row = db_rows[0]
            self.assertEqual(row.type,
                             classic.models.Submission.NEW_SUBMISSION,
                             "The classic submission has type 'new'")
            self.assertEqual(row.status,
                             classic.models.Submission.NOT_SUBMITTED,
                             "The classic submission is in the not submitted"
                             " state")
