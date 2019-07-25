"""Example 5: submission is being replaced."""

from unittest import TestCase, mock
import tempfile
from datetime import datetime
from pytz import UTC

from flask import Flask

from ...services import classic
from ... import save, load, load_fast, domain, exceptions, core

CCO = 'http://creativecommons.org/publicdomain/zero/1.0/'


class TestReplacementSubmissionInProgress(TestCase):
    """Submitter creates a replacement, and is working on updates."""

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
            self.submission, self.events = save(
                domain.event.CreateSubmissionVersion(**self.defaults),
                submission_id=self.submission.submission_id
            )

    def tearDown(self):
        """Clear the database after each test."""
        with self.app.app_context():
            classic.drop_all()

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def test_is_in_working_state(self):
        """The submission is now in working state."""
        # Check the submission state.
        with self.app.app_context():
            submission, events = load(self.submission.submission_id)
            self.assertEqual(submission.status,
                             domain.submission.Submission.WORKING,
                             "The submission is in the working state")
            self.assertIsInstance(self.events[-2], domain.event.Announce,
                                  "An Announce event is inserted.")
            self.assertIsInstance(self.events[-1],
                                  domain.event.CreateSubmissionVersion,
                                  "A CreateSubmissionVersion event is"
                                  " inserted.")
            self.assertEqual(len(submission.versions), 1,
                             "There is one announced versions")

        with self.app.app_context():
            submission = load_fast(self.submission.submission_id)
            self.assertEqual(submission.status,
                             domain.submission.Submission.WORKING,
                             "The submission is in the working state")
            self.assertIsInstance(self.events[-2], domain.event.Announce,
                                  "An Announce event is inserted.")
            self.assertIsInstance(self.events[-1],
                                  domain.event.CreateSubmissionVersion,
                                  "A CreateSubmissionVersion event is"
                                  " inserted.")
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
                             classic.models.Submission.REPLACEMENT,
                             "The second row has type 'replacement'")
            self.assertEqual(db_rows[1].status,
                             classic.models.Submission.NOT_SUBMITTED,
                             "The second row is in not submitted state")

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def test_cannot_replace_submission_again(self):
        """The submission cannot be replaced again while in working state."""
        with self.app.app_context():
            with self.assertRaises(exceptions.InvalidEvent):
                self.submission, self.events = save(
                    domain.event.CreateSubmissionVersion(**self.defaults),
                    submission_id=self.submission.submission_id
                )

        self.test_is_in_working_state()

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def test_cannot_withdraw_submission(self):
        """The submitter cannot request withdrawal of the submission."""
        with self.app.app_context():
            with self.assertRaises(exceptions.InvalidEvent):
                submission, events = save(
                    domain.event.RequestWithdrawal(reason="the best reason",
                                                   **self.defaults),
                    submission_id=self.submission.submission_id
                )

        self.test_is_in_working_state()

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def test_can_edit_submission_metadata(self):
        """The submission metadata can now be changed."""
        new_title = "A better title"
        with self.app.app_context():
            submission, events = save(
                domain.event.SetTitle(title=new_title, **self.defaults),
                submission_id=self.submission.submission_id
            )

        # Check the submission state.
        with self.app.app_context():
            submission, events = load(self.submission.submission_id)
            self.assertEqual(submission.metadata.title, new_title,
                             "The submission is changed")
            self.assertEqual(submission.status,
                             domain.submission.Submission.WORKING,
                             "The submission is in the working state")
            self.assertIsInstance(events[-3], domain.event.Announce,
                                  "An Announce event is inserted.")
            self.assertIsInstance(events[-2],
                                  domain.event.CreateSubmissionVersion,
                                  "A CreateSubmissionVersion event is"
                                  " inserted.")
            self.assertIsInstance(events[-1],
                                  domain.event.SetTitle,
                                  "Metadata update events are reflected")
            self.assertEqual(len(submission.versions), 1,
                             "There is one announced versions")

        with self.app.app_context():
            submission = load_fast(self.submission.submission_id)
            self.assertEqual(submission.metadata.title, new_title,
                             "The submission is changed")
            self.assertEqual(submission.status,
                             domain.submission.Submission.WORKING,
                             "The submission is in the working state")
            self.assertIsInstance(events[-3], domain.event.Announce,
                                  "An Announce event is inserted.")
            self.assertIsInstance(events[-2],
                                  domain.event.CreateSubmissionVersion,
                                  "A CreateSubmissionVersion event is"
                                  " inserted.")
            self.assertIsInstance(events[-1],
                                  domain.event.SetTitle,
                                  "Metadata update events are reflected")
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
            self.assertEqual(db_rows[0].title, self.submission.metadata.title,
                             "Announced row is unchanged.")
            self.assertEqual(db_rows[1].type,
                             classic.models.Submission.REPLACEMENT,
                             "The second row has type 'replacement'")
            self.assertEqual(db_rows[1].status,
                             classic.models.Submission.NOT_SUBMITTED,
                             "The second row is in not submitted state")
            self.assertEqual(db_rows[1].title, new_title,
                             "Replacement row reflects the change.")

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def test_changing_doi(self):
        """Submitter can set the DOI as part of the new version."""
        new_doi = "10.1000/182"
        new_journal_ref = "Baz 1993"
        new_report_num = "Report 82"
        with self.app.app_context():
            submission, events = save(
                domain.event.SetDOI(doi=new_doi, **self.defaults),
                submission_id=self.submission.submission_id
            )

        with self.app.app_context():
            submission, events = save(
                domain.event.SetJournalReference(journal_ref=new_journal_ref,
                                                 **self.defaults),
                submission_id=self.submission.submission_id
            )

        with self.app.app_context():
            submission, events = save(
                domain.event.SetReportNumber(report_num=new_report_num,
                                             **self.defaults),
                submission_id=self.submission.submission_id
            )

        # Check the submission state.
        with self.app.app_context():
            submission, events = load(self.submission.submission_id)
            self.assertEqual(submission.metadata.doi, new_doi,
                             "The DOI is updated.")
            self.assertEqual(submission.metadata.journal_ref, new_journal_ref,
                             "The journal ref is updated.")
            self.assertEqual(submission.metadata.report_num, new_report_num,
                             "The report number is updated.")
            self.assertEqual(submission.status,
                             domain.submission.Submission.WORKING,
                             "The submission is in the working state.")

            self.assertIsInstance(events[-5], domain.event.Announce,
                                  "An Announce event is inserted.")
            self.assertIsInstance(events[-4],
                                  domain.event.CreateSubmissionVersion,
                                  "A CreateSubmissionVersion event is"
                                  " inserted.")
            self.assertIsInstance(events[-3],
                                  domain.event.SetDOI,
                                  "Metadata update events are reflected")
            self.assertIsInstance(events[-2],
                                  domain.event.SetJournalReference,
                                  "Metadata update events are reflected")
            self.assertIsInstance(events[-1],
                                  domain.event.SetReportNumber,
                                  "Metadata update events are reflected")
            self.assertEqual(len(submission.versions), 1,
                             "There is one announced versions")

        with self.app.app_context():
            submission = load_fast(self.submission.submission_id)
            self.assertEqual(submission.metadata.doi, new_doi,
                             "The DOI is updated.")
            self.assertEqual(submission.metadata.journal_ref, new_journal_ref,
                             "The journal ref is updated.")
            self.assertEqual(submission.metadata.report_num, new_report_num,
                             "The report number is updated.")
            self.assertEqual(submission.status,
                             domain.submission.Submission.WORKING,
                             "The submission is in the working state.")
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
                             classic.models.Submission.REPLACEMENT,
                             "The second row has type replacement")
            self.assertEqual(db_rows[1].status,
                             classic.models.Submission.NOT_SUBMITTED,
                             "The second row is in the not submitted state.")
            self.assertEqual(db_rows[1].doi, new_doi,
                             "The DOI is updated in the database.")
            self.assertEqual(db_rows[1].journal_ref, new_journal_ref,
                             "The journal ref is updated in the database.")
            self.assertEqual(db_rows[1].report_num, new_report_num,
                             "The report number is updated in the database.")

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def test_cannot_be_unfinalized(self):
        """The submission cannot be unfinalized, as it is not finalized."""
        with self.app.app_context():
            with self.assertRaises(exceptions.InvalidEvent):
                save(domain.event.UnFinalizeSubmission(**self.defaults),
                     submission_id=self.submission.submission_id)

        self.test_is_in_working_state()

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def test_can_revert_to_most_recent_announced_version(self):
        """Submitter can abandon changes to their replacement."""
        new_doi = "10.1000/182"
        new_journal_ref = "Baz 1993"
        new_report_num = "Report 82"
        with self.app.app_context():
            submission, events = save(
                domain.event.SetDOI(doi=new_doi, **self.defaults),
                domain.event.SetJournalReference(journal_ref=new_journal_ref,
                                                 **self.defaults),
                domain.event.SetReportNumber(report_num=new_report_num,
                                             **self.defaults),
                submission_id=self.submission.submission_id
            )

        with self.app.app_context():
            submission, events = save(
                domain.event.Rollback(**self.defaults),
                submission_id=self.submission.submission_id
            )

        with self.app.app_context():
            submission, events = load(self.submission.submission_id)
            self.assertEqual(submission.version, 1,
                             "Version number is rolled back")
            self.assertEqual(submission.metadata.doi,
                             self.submission.metadata.doi,
                             "The DOI is reverted.")
            self.assertEqual(submission.metadata.journal_ref,
                             self.submission.metadata.journal_ref,
                             "The journal ref is reverted.")
            self.assertEqual(submission.metadata.report_num,
                             self.submission.metadata.report_num,
                             "The report number is reverted.")
            self.assertEqual(len(submission.versions), 1,
                             "There is one announced versions")

        with self.app.app_context():
            submission = load_fast(self.submission.submission_id)
            self.assertEqual(submission.version, 1,
                             "Version number is rolled back")
            self.assertEqual(submission.metadata.doi,
                             self.submission.metadata.doi,
                             "The DOI is reverted.")
            self.assertEqual(submission.metadata.journal_ref,
                             self.submission.metadata.journal_ref,
                             "The journal ref is reverted.")
            self.assertEqual(submission.metadata.report_num,
                             self.submission.metadata.report_num,
                             "The report number is reverted.")
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
                             classic.models.Submission.REPLACEMENT,
                             "The second row has type replacement")
            self.assertEqual(db_rows[1].status,
                             classic.models.Submission.USER_DELETED,
                             "The second row is in the user deleted state.")

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def test_can_start_a_new_replacement_after_reverting(self):
        """Submitter can start a new replacement after reverting."""
        with self.app.app_context():
            submission, events = save(
                domain.event.Rollback(**self.defaults),
                submission_id=self.submission.submission_id
            )

        with self.app.app_context():
            submission, events = save(
                domain.event.CreateSubmissionVersion(**self.defaults),
                submission_id=self.submission.submission_id
            )

        with self.app.app_context():
            submission, events = load(self.submission.submission_id)
            self.assertEqual(submission.version, 2,
                             "Version number is incremented.")
            self.assertEqual(submission.status,
                             domain.submission.Submission.WORKING,
                             "Submission is in working state")
            self.assertEqual(len(submission.versions), 1,
                             "There is one announced versions")
