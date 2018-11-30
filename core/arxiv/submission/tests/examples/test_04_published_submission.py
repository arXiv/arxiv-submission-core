"""Example 4: submission is published."""

from unittest import TestCase
import tempfile
from datetime import datetime
from pytz import UTC

from flask import Flask

from ...services import classic
from ... import save, load, domain, exceptions

CCO = 'http://creativecommons.org/publicdomain/zero/1.0/'


class TestPublishedSubmission(TestCase):
    """Submitter finalizes a new submission, and it is eventually announced."""

    @classmethod
    def setUpClass(cls):
        """Instantiate an app for use with a SQLite database."""
        _, db = tempfile.mkstemp(suffix='.sqlite')
        cls.app = Flask('foo')
        cls.app.config['CLASSIC_DATABASE_URI'] = f'sqlite:///{db}'

        with cls.app.app_context():
            classic.init_app(cls.app)

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
                                              format='tex', identifier=123,
                                              size=593992, **self.defaults),
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

        # Publish the submission.
        self.paper_id = '1901.00123'
        with self.app.app_context():
            session = classic.current_session()
            db_row = session.query(classic.models.Submission).first()
            db_row.status = classic.models.Submission.PUBLISHED
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

    def tearDown(self):
        """Clear the database after each test."""
        with self.app.app_context():
            classic.drop_all()

    def test_is_in_published_state(self):
        """The submission is now published."""
        # Check the submission state.
        with self.app.app_context():
            submission, events = load(self.submission.submission_id)
            self.assertEqual(submission.status,
                             domain.submission.Submission.PUBLISHED,
                             "The submission is in the submitted state")
            self.assertTrue(submission.published, "Submission is published")
            self.assertEqual(len(self.events) + 1, len(events),
                             "The same number of events were retrieved as"
                             " were initially saved, plus the publish event.")

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
                             classic.models.Submission.PUBLISHED,
                             "The classic submission is in the PUBLISHED"
                             " state")

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
            self.assertEqual(len(self.events) + 2, len(events),
                             "The same number of events were retrieved as"
                             " were initially saved, plus the publish event"
                             " and the create version event.")
            self.assertEqual(submission.version, 2,
                             "The version number is incremented by 1")
            self.assertEqual(len(submission.versions), 1,
                             "There is one past version")

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
                             classic.models.Submission.PUBLISHED,
                             "The first row is published")
            self.assertEqual(db_rows[1].type,
                             classic.models.Submission.REPLACEMENT,
                             "The second row has type 'replacement'")
            self.assertEqual(db_rows[1].status,
                             classic.models.Submission.NOT_SUBMITTED,
                             "The second row is in not submitted state")

    def test_can_withdraw_submission(self):
        """The submitter can request withdrawal of the submission."""
        with self.app.app_context():
            submission, events = save(
                domain.event.RequestWithdrawal(reason="the best reason",
                                               **self.defaults),
                submission_id=self.submission.submission_id
            )

        # Check the submission state.
        with self.app.app_context():
            submission, events = load(self.submission.submission_id)
            self.assertEqual(submission.status,
                             domain.submission.Submission.WITHDRAWAL_REQUESTED,
                             "The submission is in the withdrawal requested"
                             " state.")
            self.assertEqual(len(self.events) + 2, len(events),
                             "The same number of events were retrieved as"
                             " were initially saved, plus one for publish"
                             " and another for withdrawal request.")

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
                             classic.models.Submission.PUBLISHED,
                             "The first row is published")
            self.assertEqual(db_rows[1].type,
                             classic.models.Submission.WITHDRAWAL,
                             "The second row has type 'withdrawal'")
            self.assertEqual(db_rows[1].status,
                             classic.models.Submission.PROCESSING_SUBMISSION,
                             "The second row is in the processing submission"
                             " state.")

    def test_cannot_edit_submission_metadata(self):
        """The submission metadata cannot be changed without a new version."""
        with self.app.app_context():
            with self.assertRaises(exceptions.InvalidEvent, msg=(
                    "Creating a SetTitle command results in an exception.")):
                save(domain.event.SetTitle(title="A better title",
                                           **self.defaults),
                     submission_id=self.submission.submission_id)

        self.test_is_in_published_state()

    def test_changing_doi(self):
        """Submitter can set the DOI."""
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
                             domain.submission.Submission.PUBLISHED,
                             "The submission is in the submitted state.")

            self.assertEqual(len(self.events) + 4, len(events),
                             "The same number of events were retrieved as"
                             " were initially saved plus one for the publish"
                             " event and another for setting DOI, another for"
                             " setting journal ref, and another for setting"
                             " report number.")

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
                             classic.models.Submission.PUBLISHED,
                             "The first row is published")
            self.assertEqual(db_rows[1].type,
                             classic.models.Submission.JOURNAL_REFERENCE,
                             "The second row has type journal ref")
            self.assertEqual(db_rows[1].status,
                             classic.models.Submission.PROCESSING_SUBMISSION,
                             "The second row is in the processing submission"
                             " state.")
            self.assertEqual(db_rows[1].doi, new_doi,
                             "The DOI is updated in the database.")
            self.assertEqual(db_rows[1].journal_ref, new_journal_ref,
                             "The journal ref is updated in the database.")
            self.assertEqual(db_rows[1].report_num, new_report_num,
                             "The report number is updated in the database.")

    def test_cannot_be_unfinalized(self):
        """The submission cannot be unfinalized, because it is published."""
        with self.app.app_context():
            with self.assertRaises(exceptions.InvalidEvent):
                save(domain.event.UnFinalizeSubmission(**self.defaults),
                     submission_id=self.submission.submission_id)

        self.test_is_in_published_state()
