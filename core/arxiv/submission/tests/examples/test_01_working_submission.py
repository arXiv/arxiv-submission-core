"""Example 1: working submission."""

from unittest import TestCase, mock
import tempfile

from flask import Flask

from ...services import classic
from ... import save, load, load_fast, domain, exceptions
from ... import core


class TestWorkingSubmission(TestCase):
    """
    Submitter creates a new submission, has completed some but not all fields.

    This is a typical scenario in which the user has missed a step, or left
    something required blank. These should get caught early if we designed
    the UI or API right, but it's possible that something slipped through.
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
        """Create and partially complete the submission."""
        self.submitter = domain.agent.User(1234, email='j.user@somewhere.edu',
                                           forename='Jane', surname='User',
                                           endorsements=['cs.DL', 'cs.IR'])
        self.defaults = {'creator': self.submitter}
        with self.app.app_context():
            classic.create_all()
            self.submission, self.events = save(
                domain.event.CreateSubmission(**self.defaults),
                domain.event.ConfirmAuthorship(**self.defaults),
                domain.event.ConfirmPolicy(**self.defaults),
                domain.event.SetTitle(title='the best title', **self.defaults)
            )
        self.submission_id = self.submission.submission_id

    def tearDown(self):
        """Clear the database after each test."""
        with self.app.app_context():
            classic.drop_all()

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def test_is_in_working_state(self):
        """The submission in in the working state."""
        # Check the submission state.
        with self.app.app_context():
            submission, events = load(self.submission.submission_id)
            self.assertEqual(submission.status,
                             domain.submission.Submission.WORKING,
                             "The submission is in the working state")
            self.assertEqual(len(submission.versions), 0,
                             "There are no announced versions")

        with self.app.app_context():
            submission = load_fast(self.submission_id)
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

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def test_can_delete(self):
        """The submission can be deleted."""
        with self.app.app_context():
            save(domain.event.Rollback(**self.defaults),
                 submission_id=self.submission.submission_id)

        with self.app.app_context():
            submission, events = load(self.submission.submission_id)

            self.assertEqual(submission.status,
                             domain.event.Submission.DELETED,
                             "Submission is in the deleted state")
            self.assertFalse(submission.active,
                             "The submission is no longer considered active.")
            self.assertEqual(len(submission.versions), 0,
                             "There are no announced versions")

        with self.app.app_context():
            submission = load_fast(self.submission_id)
            self.assertEqual(submission.status,
                             domain.event.Submission.DELETED,
                             "Submission is in the deleted state")
            self.assertFalse(submission.active,
                             "The submission is no longer considered active.")
            self.assertEqual(len(submission.versions), 0,
                             "There are no announced versions")

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
                             classic.models.Submission.USER_DELETED,
                             "The classic submission is in the DELETED state")

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def test_cannot_finalize_submission(self):
        """The submission cannot be finalized."""
        with self.app.app_context():
            with self.assertRaises(exceptions.InvalidEvent, msg=(
                    "Creating a FinalizeSubmission command results in an"
                    " exception.")):
                save(domain.event.FinalizeSubmission(**self.defaults),
                     submission_id=self.submission.submission_id)

        self.test_is_in_working_state()

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def test_cannot_replace_submission(self):
        """The submission cannot be replaced."""
        with self.app.app_context():
            with self.assertRaises(exceptions.InvalidEvent, msg=(
                    "Creating a CreateSubmissionVersion command results in an"
                    " exception.")):
                save(domain.event.CreateSubmissionVersion(**self.defaults),
                     submission_id=self.submission.submission_id)

        self.test_is_in_working_state()

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def test_cannot_withdraw_submission(self):
        """The submission cannot be withdrawn."""
        with self.app.app_context():
            with self.assertRaises(exceptions.InvalidEvent, msg=(
                    "Creating a RequestWithdrawal command results in an"
                    " exception.")):
                save(domain.event.RequestWithdrawal(reason="the best reason",
                                                    **self.defaults),
                     submission_id=self.submission.submission_id)

        self.test_is_in_working_state()

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def test_cannot_be_unfinalized(self):
        """The submission cannot be unfinalized."""
        with self.app.app_context():
            with self.assertRaises(exceptions.InvalidEvent, msg=(
                    "Creating an UnFinalizeSubmission command results in an"
                    " exception.")):
                save(domain.event.UnFinalizeSubmission(**self.defaults),
                     submission_id=self.submission.submission_id)

        self.test_is_in_working_state()
