"""
Tests for integration with the classic system.

Provides test cases for the new events model's ability to replicate the classic
model. The function `TestClassicUIWorkflow.test_classic_workflow()` provides
keyword arguments to pass different types of data through the workflow.

TODO: Presently, `test_classic_workflow` expects `core.domain` objects. That
should change to instantiate each object at runtime for database imports.
"""

from unittest import TestCase, mock
from datetime import datetime
import tempfile
from pytz import UTC
from flask import Flask

from arxiv.base import Base
from arxiv import mail
from ..util import in_memory_db
from ... import *
from ...services import classic


class TestClassicUIWorkflow(TestCase):
    """Replicate the classic submission UI workflow."""

    def setUp(self):
        """An arXiv user is submitting a new paper."""
        self.app = Flask(__name__)
        self.app.config['EMAIL_ENABLED'] = False
        Base(self.app)
        init_app(self.app)
        mail.init_app(self.app)
        self.submitter = domain.User(1234, email='j.user@somewhere.edu',
                                     forename='Jane', surname='User',
                                     endorsements=['cs.DL', 'cs.IR'])
        self.unicode_submitter = domain.User(12345,
                                             email='j.user@somewhere.edu',
                                             forename='大', surname='用户',
                                             endorsements=['cs.DL', 'cs.IR'])

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def test_classic_workflow(self, submitter=None, metadata=None,
                              authors=None):
        """Submitter proceeds through workflow in a linear fashion."""

        # Instantiate objects that have not yet been instantiated or use defaults.
        if submitter is None:
            submitter = self.submitter
        if metadata is None:
            metadata = [
                ('title', 'Foo title'),
                ('abstract', "One morning, as Gregor Samsa was waking up..."),
                ('comments', '5 pages, 2 turtle doves'),
                ('report_num', 'asdf1234'),
                ('doi', '10.01234/56789'),
                ('journal_ref', 'Foo Rev 1, 2 (1903)')
            ]
        metadata = dict(metadata)


        # TODO: Process data in dictionary form to Author objects.
        if authors is None:
            authors = [Author(order=0,
                              forename='Bob',
                              surname='Paulson',
                              email='Robert.Paulson@nowhere.edu',
                              affiliation='Fight Club'
                        )]

        with in_memory_db(self.app) as session:
            # Submitter clicks on 'Start new submission' in the user dashboard.
            submission, stack = save(
                CreateSubmission(creator=submitter)
            )
            self.assertIsNotNone(submission.submission_id,
                                 "A submission ID is assigned")
            self.assertEqual(len(stack), 1, "A single command is executed.")

            db_submission = session.query(classic.models.Submission)\
                .get(submission.submission_id)
            self.assertEqual(db_submission.submission_id,
                             submission.submission_id,
                             "A row is added to the submission table")
            self.assertEqual(db_submission.submitter_id,
                             submitter.native_id,
                             "Submitter ID set on submission")
            self.assertEqual(db_submission.submitter_email,
                             submitter.email,
                             "Submitter email set on submission")
            self.assertEqual(db_submission.submitter_name, submitter.name,
                             "Submitter name set on submission")
            self.assertEqual(db_submission.created.replace(tzinfo=UTC),
                             submission.created,
                             "Creation datetime set correctly")

            # TODO: What else to check here?

            # /start: Submitter completes the start submission page.
            license_uri = 'http://creativecommons.org/publicdomain/zero/1.0/'
            submission, stack = save(
                ConfirmContactInformation(creator=submitter),
                ConfirmAuthorship(
                    creator=submitter,
                    submitter_is_author=True
                ),
                SetLicense(
                    creator=submitter,
                    license_uri=license_uri,
                    license_name='CC0 1.0'
                ),
                ConfirmPolicy(creator=submitter),
                SetPrimaryClassification(
                    creator=submitter,
                    category='cs.DL'
                ),
                submission_id=submission.submission_id
            )

            self.assertEqual(len(stack), 6,
                             "Six commands have been executed in total.")

            db_submission = session.query(classic.models.Submission)\
                .get(submission.submission_id)
            self.assertEqual(db_submission.userinfo, 1,
                             "Contact verification set correctly in database.")
            self.assertEqual(db_submission.is_author, 1,
                             "Authorship status set correctly in database.")
            self.assertEqual(db_submission.license, license_uri,
                             "License set correctly in database.")
            self.assertEqual(db_submission.agree_policy, 1,
                             "Policy acceptance set correctly in database.")
            self.assertEqual(len(db_submission.categories), 1,
                             "A single category is associated in the database")
            self.assertEqual(db_submission.categories[0].is_primary, 1,
                             "Primary category is set correct in the database")
            self.assertEqual(db_submission.categories[0].category, 'cs.DL',
                             "Primary category is set correct in the database")

            # /addfiles: Submitter has uploaded files to the file management
            # service, and verified that they compile. Now they associate the
            # content package with the submission.
            submission, stack = save(
                SetUploadPackage(
                    creator=submitter,
                    checksum="a9s9k342900skks03330029k",
                    source_format=domain.submission.SubmissionContent.Format('tex'),
                    identifier=123,
                    uncompressed_size=593992,
                    compressed_size=593992
                ),
                submission_id=submission.submission_id
            )

            self.assertEqual(len(stack), 7,
                             "Seven commands have been executed in total.")
            db_submission = session.query(classic.models.Submission)\
                .get(submission.submission_id)
            self.assertEqual(db_submission.must_process, 1,
                             "There is no compilation yet")
            self.assertEqual(db_submission.source_size, 593992,
                             "Source package size set correctly in database")
            self.assertEqual(db_submission.source_format, 'tex',
                             "Source format set correctly in database")

            # /metadata: Submitter adds metadata to their submission, including
            # authors. In this package, we model authors in more detail than
            # in the classic system, but we should preserve the canonical
            # format in the db for legacy components' sake.
            submission, stack = save(
                SetTitle(creator=self.submitter, title=metadata['title']),
                SetAbstract(creator=self.submitter,
                            abstract=metadata['abstract']),
                SetComments(creator=self.submitter,
                            comments=metadata['comments']),
                SetJournalReference(creator=self.submitter,
                                    journal_ref=metadata['journal_ref']),
                SetDOI(creator=self.submitter, doi=metadata['doi']),
                SetReportNumber(creator=self.submitter,
                                report_num=metadata['report_num']),
                SetAuthors(creator=submitter, authors=authors),
                submission_id=submission.submission_id
            )
            db_submission = session.query(classic.models.Submission) \
                .get(submission.submission_id)
            self.assertEqual(db_submission.title, dict(metadata)['title'],
                             "Title updated as expected in database")
            self.assertEqual(db_submission.abstract,
                             dict(metadata)['abstract'],
                             "Abstract updated as expected in database")
            self.assertEqual(db_submission.comments,
                             dict(metadata)['comments'],
                             "Comments updated as expected in database")
            self.assertEqual(db_submission.report_num,
                             dict(metadata)['report_num'],
                             "Report number updated as expected in database")
            self.assertEqual(db_submission.doi, dict(metadata)['doi'],
                             "DOI updated as expected in database")
            self.assertEqual(db_submission.journal_ref,
                             dict(metadata)['journal_ref'],
                             "Journal ref updated as expected in database")

            author_str = ';'.join(
                [f"{author.forename} {author.surname} ({author.affiliation})"
                for author in authors]
            )
            self.assertEqual(db_submission.authors,
                             author_str,
                             "Authors updated in canonical format in database")
            self.assertEqual(len(stack), 14,
                             "Fourteen commands have been executed in total.")

            # /preview: Submitter adds a secondary classification.
            submission, stack = save(
                AddSecondaryClassification(
                    creator=submitter,
                    category='cs.IR'
                ),
                submission_id=submission.submission_id
            )
            db_submission = session.query(classic.models.Submission)\
                .get(submission.submission_id)

            self.assertEqual(len(db_submission.categories), 2,
                             "A secondary category is added in the database")
            secondaries = [
                db_cat for db_cat in db_submission.categories
                if db_cat.is_primary == 0
            ]
            self.assertEqual(len(secondaries), 1,
                             "A secondary category is added in the database")
            self.assertEqual(secondaries[0].category, 'cs.IR',
                             "A secondary category is added in the database")
            self.assertEqual(len(stack), 15,
                             "Fifteen commands have been executed in total.")

            # /preview: Submitter finalizes submission.
            finalize = FinalizeSubmission(creator=submitter)
            submission, stack = save(
                finalize, submission_id=submission.submission_id
            )
            db_submission = session.query(classic.models.Submission)\
                .get(submission.submission_id)

            self.assertEqual(db_submission.status, db_submission.SUBMITTED,
                             "Submission status set correctly in database")
            self.assertEqual(db_submission.submit_time.replace(tzinfo=UTC),
                             finalize.created,
                             "Submit time is set.")
            self.assertEqual(len(stack), 16,
                             "Sixteen commands have been executed in total.")

    def test_unicode_submitter(self):
        """Submitter proceeds through workflow in a linear fashion."""
        submitter = self.unicode_submitter
        metadata = [
            ('title', '优秀的称号'),
            ('abstract', "当我有一天正在上学的时候当我有一天正在上学的时候"),
            ('comments', '5页2龟鸠'),
            ('report_num', 'asdf1234'),
            ('doi', '10.01234/56789'),
            ('journal_ref', 'Foo Rev 1, 2 (1903)')
        ]
        authors = [Author(order=0, forename='惊人', surname='用户',
                          email='amazing.user@nowhere.edu',
                          affiliation='Fight Club')]
        with self.app.app_context():
            self.app.config['ENABLE_CALLBACKS'] = 0
            self.test_classic_workflow(submitter=submitter, metadata=metadata,
                                       authors=authors)

    def test_texism_titles(self):
        """Submitter proceeds through workflow in a linear fashion."""
        metadata = [
            ('title', 'Revisiting $E = mc^2$'),
            ('abstract', "$E = mc^2$ is a foundational concept in physics"),
            ('comments', '5 pages, 2 turtle doves'),
            ('report_num', 'asdf1234'),
            ('doi', '10.01234/56789'),
            ('journal_ref', 'Foo Rev 1, 2 (1903)')
        ]
        with self.app.app_context():
            self.app.config['ENABLE_CALLBACKS'] = 1
            self.test_classic_workflow(metadata=metadata)


class TestReplacementIntegration(TestCase):
    """Test integration with the classic database with replacements."""

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
        """An arXiv user is submitting a new paper."""
        self.submitter = domain.User(1234, email='j.user@somewhere.edu',
                                    forename='Jane', surname='User',
                                    endorsements=['cs.DL'])

        # Create and finalize a new submission.
        cc0 = 'http://creativecommons.org/publicdomain/zero/1.0/'
        with self.app.app_context():
            classic.create_all()
            metadata=dict([
                ('title', 'Foo title'),
                ('abstract', "One morning, as Gregor Samsa was..."),
                ('comments', '5 pages, 2 turtle doves'),
                ('report_num', 'asdf1234'),
                ('doi', '10.01234/56789'),
                ('journal_ref', 'Foo Rev 1, 2 (1903)')
            ])
            self.submission, _ = save(
                CreateSubmission(creator=self.submitter),
                ConfirmContactInformation(creator=self.submitter),
                ConfirmAuthorship(
                    creator=self.submitter,
                    submitter_is_author=True
                ),
                SetLicense(
                    creator=self.submitter,
                    license_uri=cc0,
                    license_name='CC0 1.0'
                ),
                ConfirmPolicy(creator=self.submitter),
                SetPrimaryClassification(
                    creator=self.submitter,
                    category='cs.DL'
                ),
                SetUploadPackage(
                    creator=self.submitter,
                    checksum="a9s9k342900skks03330029k",
                    source_format=domain.submission.SubmissionContent.Format('tex'),
                    identifier=123,
                    uncompressed_size=593992,
                    compressed_size=593992
                ),
                SetTitle(creator=self.submitter, title=metadata['title']),
                SetAbstract(creator=self.submitter,
                            abstract=metadata['abstract']),
                SetComments(creator=self.submitter,
                            comments=metadata['comments']),
                SetJournalReference(
                    creator=self.submitter,
                    journal_ref=metadata['journal_ref']
                ),
                SetDOI(creator=self.submitter, doi=metadata['doi']),
                SetReportNumber(creator=self.submitter,
                                report_num=metadata['report_num']),
                SetAuthors(
                    creator=self.submitter,
                    authors=[Author(
                        order=0,
                        forename='Bob',
                        surname='Paulson',
                        email='Robert.Paulson@nowhere.edu',
                        affiliation='Fight Club'
                    )]
                ),
                FinalizeSubmission(creator=self.submitter)
            )

        # Now publish.
        with self.app.app_context():
            session = classic.current_session()

            # Publication agent publishes the paper.
            db_submission = session.query(classic.models.Submission)\
                .get(self.submission.submission_id)
            db_submission.status = db_submission.ANNOUNCED
            dated = (datetime.now() - datetime.utcfromtimestamp(0))
            primary = self.submission.primary_classification.category
            db_submission.document = classic.models.Document(
                document_id=1,
                paper_id='1901.00123',
                title=self.submission.metadata.title,
                authors=self.submission.metadata.authors_display,
                dated=dated.total_seconds(),
                primary_subject_class=primary,
                created=datetime.now(UTC),
                submitter_email=self.submission.creator.email,
                submitter_id=self.submission.creator.native_id
            )
            db_submission.doc_paper_id = '1901.00123'
            session.add(db_submission)
            session.commit()

    def tearDown(self):
        """Clear the database after each test."""
        with self.app.app_context():
            classic.drop_all()

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def test_replacement(self):
        """User has started a replacement submission."""
        with self.app.app_context():
            submission_to_replace, _ = load(self.submission.submission_id)
            creation_event = CreateSubmissionVersion(creator=self.submitter)
            replacement, _ = save(creation_event, submission_id=self.submission.submission_id)

        with self.app.app_context():
            replacement, _ = load(replacement.submission_id)

            session = classic.current_session()
            db_replacement = session.query(classic.models.Submission) \
                .filter(classic.models.Submission.doc_paper_id == replacement.arxiv_id) \
                .order_by(classic.models.Submission.submission_id.desc()) \
                .first()

        # Verify that the round-trip on the replacement submission worked as
        # expected.
        self.assertEqual(replacement.arxiv_id, submission_to_replace.arxiv_id)
        self.assertEqual(replacement.version,
                         submission_to_replace.version + 1)
        self.assertEqual(replacement.status, Submission.WORKING)
        self.assertTrue(submission_to_replace.announced)
        self.assertFalse(replacement.announced)

        self.assertIsNone(replacement.source_content)

        self.assertFalse(replacement.submitter_contact_verified)
        self.assertFalse(replacement.submitter_accepts_policy)
        self.assertFalse(replacement.submitter_confirmed_preview)
        self.assertFalse(replacement.submitter_contact_verified)

        # Verify that the database is in the right state for downstream
        # integrations.
        self.assertEqual(db_replacement.status,
                         classic.models.Submission.NEW)
        self.assertEqual(db_replacement.type,
                         classic.models.Submission.REPLACEMENT)
        self.assertEqual(db_replacement.doc_paper_id, '1901.00123')


class TestJREFIntegration(TestCase):
    """Test integration with the classic database with JREF submissions."""

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
        """An arXiv user is submitting a new paper."""
        self.submitter = domain.User(1234, email='j.user@somewhere.edu',
                                    forename='Jane', surname='User',
                                    endorsements=['cs.DL'])

        # Create and finalize a new submission.
        cc0 = 'http://creativecommons.org/publicdomain/zero/1.0/'
        with self.app.app_context():
            classic.create_all()
            metadata=dict([
                ('title', 'Foo title'),
                ('abstract', "One morning, as Gregor Samsa was..."),
                ('comments', '5 pages, 2 turtle doves'),
                ('report_num', 'asdf1234')
            ])
            self.submission, _ = save(
                CreateSubmission(creator=self.submitter),
                ConfirmContactInformation(creator=self.submitter),
                ConfirmAuthorship(
                    creator=self.submitter,
                    submitter_is_author=True
                ),
                SetLicense(
                    creator=self.submitter,
                    license_uri=cc0,
                    license_name='CC0 1.0'
                ),
                ConfirmPolicy(creator=self.submitter),
                SetPrimaryClassification(
                    creator=self.submitter,
                    category='cs.DL'
                ),
                SetUploadPackage(
                    creator=self.submitter,
                    checksum="a9s9k342900skks03330029k",
                    source_format=domain.submission.SubmissionContent.Format('tex'),
                    identifier=123,
                    uncompressed_size=593992,
                    compressed_size=593992
                ),
                SetTitle(creator=self.submitter,
                                title=metadata['title']),
                SetAbstract(creator=self.submitter,
                            abstract=metadata['abstract']),
                SetComments(creator=self.submitter,
                            comments=metadata['comments']),
                SetReportNumber(creator=self.submitter,
                                       report_num=metadata['report_num']),
                SetAuthors(
                    creator=self.submitter,
                    authors=[Author(
                        order=0,
                        forename='Bob',
                        surname='Paulson',
                        email='Robert.Paulson@nowhere.edu',
                        affiliation='Fight Club'
                    )]
                ),
                ConfirmPreview(creator=self.submitter),
                FinalizeSubmission(creator=self.submitter)
            )

        # Now publish.
        with self.app.app_context():
            session = classic.current_session()

            # Publication agent publishes the paper.
            db_submission = session.query(classic.models.Submission)\
                .get(self.submission.submission_id)
            db_submission.status = db_submission.ANNOUNCED
            dated = (datetime.now() - datetime.utcfromtimestamp(0))
            primary = self.submission.primary_classification.category
            db_submission.document = classic.models.Document(
                document_id=1,
                paper_id='1901.00123',
                title=self.submission.metadata.title,
                authors=self.submission.metadata.authors_display,
                dated=dated.total_seconds(),
                primary_subject_class=primary,
                created=datetime.now(UTC),
                submitter_email=self.submission.creator.email,
                submitter_id=self.submission.creator.native_id
            )
            db_submission.doc_paper_id = '1901.00123'
            session.add(db_submission)
            session.commit()

    def tearDown(self):
        """Clear the database after each test."""
        with self.app.app_context():
            classic.drop_all()

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def test_jref(self):
        """User has started a JREF submission."""
        with self.app.app_context():
            session = classic.current_session()
            submission_to_jref, _ = load(self.submission.submission_id)
            event = SetJournalReference(
                creator=self.submitter,
                journal_ref='Foo Rev 1, 2 (1903)'
            )
            jref_submission, _ = save(event,
                                      submission_id=self.submission.submission_id)

        with self.app.app_context():
            jref_submission, _ = load(jref_submission.submission_id)
            session = classic.current_session()
            db_jref = session.query(classic.models.Submission) \
                .filter(classic.models.Submission.doc_paper_id == jref_submission.arxiv_id) \
                .filter(classic.models.Submission.type == classic.models.Submission.JOURNAL_REFERENCE) \
                .order_by(classic.models.Submission.submission_id.desc()) \
                .first()

        # Verify that the round-trip on the replacement submission worked as
        # expected.
        self.assertEqual(jref_submission.arxiv_id, submission_to_jref.arxiv_id)
        self.assertEqual(jref_submission.version, submission_to_jref.version,
                         "The paper version should not change")
        self.assertEqual(jref_submission.status, Submission.ANNOUNCED)
        self.assertTrue(submission_to_jref.announced)
        self.assertTrue(jref_submission.announced)

        self.assertIsNotNone(jref_submission.source_content)

        self.assertTrue(jref_submission.submitter_contact_verified)
        self.assertTrue(jref_submission.submitter_accepts_policy)
        self.assertTrue(jref_submission.submitter_confirmed_preview)
        self.assertTrue(jref_submission.submitter_contact_verified)

        # Verify that the database is in the right state for downstream
        # integrations.
        self.assertEqual(db_jref.status,
                         classic.models.Submission.PROCESSING_SUBMISSION)
        self.assertEqual(db_jref.type,
                         classic.models.Submission.JOURNAL_REFERENCE)
        self.assertEqual(db_jref.doc_paper_id, '1901.00123')
        self.assertEqual(db_jref.submitter_id,
                         jref_submission.creator.native_id)


class TestWithdrawalIntegration(TestCase):
    """
    Test integration with the classic database concerning withdrawals.

    The :class:`.domain.submission.Submission` representation has only two
    statuses: :attr:`.domain.submission.WITHDRAWAL_REQUESTED` and
    :attr:`.domain.submission.WITHDRAWN`. Like other post-publish operations,
    we are simply adding events to the single stream for the original
    submission ID. This screens off details that are due to the underlying
    implementation, and focuses on how humans are actually interacting with
    withdrawals.

    On the classic side, we create a new row in the submission table for a
    withdrawal request, and it passes through the same states as a regular
    submission.
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
        """An arXiv user is submitting a new paper."""
        self.submitter = domain.User(1234, email='j.user@somewhere.edu',
                                    forename='Jane', surname='User',
                                    endorsements=['cs.DL'])

        # Create and finalize a new submission.
        cc0 = 'http://creativecommons.org/publicdomain/zero/1.0/'
        with self.app.app_context():
            classic.create_all()
            metadata=dict([
                ('title', 'Foo title'),
                ('abstract', "One morning, as Gregor Samsa was..."),
                ('comments', '5 pages, 2 turtle doves'),
                ('report_num', 'asdf1234'),
                ('doi', '10.01234/56789'),
                ('journal_ref', 'Foo Rev 1, 2 (1903)')
            ])
            self.submission, _ = save(
                CreateSubmission(creator=self.submitter),
                ConfirmContactInformation(creator=self.submitter),
                ConfirmAuthorship(
                    creator=self.submitter,
                    submitter_is_author=True
                ),
                SetLicense(
                    creator=self.submitter,
                    license_uri=cc0,
                    license_name='CC0 1.0'
                ),
                ConfirmPolicy(creator=self.submitter),
                SetPrimaryClassification(
                    creator=self.submitter,
                    category='cs.DL'
                ),
                SetUploadPackage(
                    creator=self.submitter,
                    checksum="a9s9k342900skks03330029k",
                    source_format=domain.submission.SubmissionContent.Format('tex'),
                    identifier=123,
                    uncompressed_size=593992,
                    compressed_size=593992
                ),
                SetTitle(creator=self.submitter, title=metadata['title']),
                SetAbstract(creator=self.submitter,
                            abstract=metadata['abstract']),
                SetComments(creator=self.submitter,
                            comments=metadata['comments']),
                SetJournalReference(
                    creator=self.submitter,
                    journal_ref=metadata['journal_ref']
                ),
                SetDOI(creator=self.submitter, doi=metadata['doi']),
                SetReportNumber(creator=self.submitter,
                                       report_num=metadata['report_num']),
                SetAuthors(
                    creator=self.submitter,
                    authors=[Author(
                        order=0,
                        forename='Bob',
                        surname='Paulson',
                        email='Robert.Paulson@nowhere.edu',
                        affiliation='Fight Club'
                    )]
                ),
                FinalizeSubmission(creator=self.submitter)
            )
        self.submission_id = self.submission.submission_id

        # Announce.
        with self.app.app_context():
            session = classic.current_session()
            db_submission = session.query(classic.models.Submission)\
                .get(self.submission.submission_id)
            db_submission.status = db_submission.ANNOUNCED
            dated = (datetime.now() - datetime.utcfromtimestamp(0))
            primary = self.submission.primary_classification.category
            db_submission.document = classic.models.Document(
                document_id=1,
                paper_id='1901.00123',
                title=self.submission.metadata.title,
                authors=self.submission.metadata.authors_display,
                dated=dated.total_seconds(),
                primary_subject_class=primary,
                created=datetime.now(UTC),
                submitter_email=self.submission.creator.email,
                submitter_id=self.submission.creator.native_id
            )
            db_submission.doc_paper_id = '1901.00123'
            session.add(db_submission)
            session.commit()

    def tearDown(self):
        """Clear the database after each test."""
        with self.app.app_context():
            classic.drop_all()

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def test_request_withdrawal(self):
        """Request a withdrawal."""
        with self.app.app_context():
            session = classic.current_session()
            event = RequestWithdrawal(creator=self.submitter,
                                      reason="short people got no reason")
            submission, _ = save(event, submission_id=self.submission_id)

            submission, _ = load(self.submission_id)
            self.assertEqual(submission.status, domain.Submission.ANNOUNCED)
            request = list(submission.user_requests.values())[0]
            self.assertEqual(request.reason_for_withdrawal, event.reason)

            wdr = session.query(classic.models.Submission) \
                .filter(classic.models.Submission.doc_paper_id == submission.arxiv_id) \
                .order_by(classic.models.Submission.submission_id.desc()) \
                .first()
            self.assertEqual(wdr.status,
                             classic.models.Submission.PROCESSING_SUBMISSION)
            self.assertEqual(wdr.type, classic.models.Submission.WITHDRAWAL)
            self.assertIn(f"Withdrawn: {event.reason}", wdr.comments)


class TestPublicationIntegration(TestCase):
    """
    Test integration with the classic database concerning publication.

    Since the publication process continues to run outside of the event model
    in the short term, we need to be certain that publication-related changes
    are represented accurately in this project.
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
        """An arXiv user is submitting a new paper."""
        self.submitter = domain.User(1234, email='j.user@somewhere.edu',
                                    forename='Jane', surname='User',
                                    endorsements=['cs.DL'])

        # Create and finalize a new submission.
        cc0 = 'http://creativecommons.org/publicdomain/zero/1.0/'
        with self.app.app_context():
            classic.create_all()
            metadata=dict([
                ('title', 'Foo title'),
                ('abstract', "One morning, as Gregor Samsa was..."),
                ('comments', '5 pages, 2 turtle doves'),
                ('report_num', 'asdf1234'),
                ('doi', '10.01234/56789'),
                ('journal_ref', 'Foo Rev 1, 2 (1903)')
            ])
            self.submission, _ = save(
                CreateSubmission(creator=self.submitter),
                ConfirmContactInformation(creator=self.submitter),
                ConfirmAuthorship(
                    creator=self.submitter,
                    submitter_is_author=True
                ),
                SetLicense(
                    creator=self.submitter,
                    license_uri=cc0,
                    license_name='CC0 1.0'
                ),
                ConfirmPolicy(creator=self.submitter),
                SetPrimaryClassification(
                    creator=self.submitter,
                    category='cs.DL'
                ),
                SetUploadPackage(
                    creator=self.submitter,
                    checksum="a9s9k342900skks03330029k",
                    source_format=domain.submission.SubmissionContent.Format('tex'),
                    identifier=123,
                    uncompressed_size=593992,
                    compressed_size=593992
                ),
                SetTitle(creator=self.submitter,
                                title=metadata['title']),
                SetAbstract(creator=self.submitter,
                            abstract=metadata['abstract']),
                SetComments(creator=self.submitter,
                            comments=metadata['comments']),
                SetJournalReference(
                    creator=self.submitter,
                    journal_ref=metadata['journal_ref']
                ),
                SetDOI(creator=self.submitter, doi=metadata['doi']),
                SetReportNumber(creator=self.submitter,
                                       report_num=metadata['report_num']),
                SetAuthors(
                    creator=self.submitter,
                    authors=[Author(
                        order=0,
                        forename='Bob',
                        surname='Paulson',
                        email='Robert.Paulson@nowhere.edu',
                        affiliation='Fight Club'
                    )]
                ),
                FinalizeSubmission(creator=self.submitter)
            )

    def tearDown(self):
        """Clear the database after each test."""
        with self.app.app_context():
            classic.drop_all()

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def test_publication_status_is_reflected(self):
        """The submission has been announced/announced."""
        with self.app.app_context():
            session = classic.current_session()

            # Publication agent publishes the paper.
            db_submission = session.query(classic.models.Submission)\
                .get(self.submission.submission_id)
            db_submission.status = db_submission.ANNOUNCED
            dated = (datetime.now() - datetime.utcfromtimestamp(0))
            primary = self.submission.primary_classification.category
            db_submission.document = classic.models.Document(
                document_id=1,
                paper_id='1901.00123',
                title=self.submission.metadata.title,
                authors=self.submission.metadata.authors_display,
                dated=dated.total_seconds(),
                primary_subject_class=primary,
                created=datetime.now(UTC),
                submitter_email=self.submission.creator.email,
                submitter_id=self.submission.creator.native_id
            )
            session.add(db_submission)
            session.commit()

            # Submission state should reflect publication status.
            submission, _ = load(self.submission.submission_id)
            self.assertEqual(submission.status, submission.ANNOUNCED,
                             "Submission should have announced status.")
            self.assertEqual(submission.arxiv_id, "1901.00123",
                             "arXiv paper ID should be set")
            self.assertFalse(submission.active,
                             "Announced submission should no longer be active")

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def test_publication_status_is_reflected_after_files_expire(self):
        """The submission has been announced/announced, and files expired."""
        paper_id = '1901.00123'
        with self.app.app_context():
            session = classic.current_session()

            # Publication agent publishes the paper.
            db_submission = session.query(classic.models.Submission)\
                .get(self.submission.submission_id)
            db_submission.status = db_submission.DELETED_ANNOUNCED
            dated = (datetime.now() - datetime.utcfromtimestamp(0))
            primary = self.submission.primary_classification.category
            db_submission.document = classic.models.Document(
                document_id=1,
                paper_id=paper_id,
                title=self.submission.metadata.title,
                authors=self.submission.metadata.authors_display,
                dated=dated.total_seconds(),
                primary_subject_class=primary,
                created=datetime.now(UTC),
                submitter_email=self.submission.creator.email,
                submitter_id=self.submission.creator.native_id
            )
            db_submission.doc_paper_id = paper_id
            session.add(db_submission)
            session.commit()

            # Submission state should reflect publication status.
            submission, _ = load(self.submission.submission_id)
            self.assertEqual(submission.status, submission.ANNOUNCED,
                             "Submission should have announced status.")
            self.assertEqual(submission.arxiv_id, "1901.00123",
                             "arXiv paper ID should be set")
            self.assertFalse(submission.active,
                             "Announced submission should no longer be active")

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def test_scheduled_status_is_reflected(self):
        """The submission has been scheduled for publication today."""
        with self.app.app_context():
            session = classic.current_session()

            # Publication agent publishes the paper.
            db_submission = session.query(classic.models.Submission)\
                .get(self.submission.submission_id)
            db_submission.status = db_submission.PROCESSING
            session.add(db_submission)
            session.commit()

            # Submission state should reflect scheduled status.
            submission, _ = load(self.submission.submission_id)
            self.assertEqual(submission.status, submission.SCHEDULED,
                             "Submission should have scheduled status.")

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def test_scheduled_status_is_reflected_processing_submission(self):
        """The submission has been scheduled for publication today."""
        with self.app.app_context():
            session = classic.current_session()

            # Publication agent publishes the paper.
            db_submission = session.query(classic.models.Submission)\
                .get(self.submission.submission_id)
            db_submission.status = db_submission.PROCESSING_SUBMISSION
            session.add(db_submission)
            session.commit()

            # Submission state should reflect scheduled status.
            submission, _ = load(self.submission.submission_id)
            self.assertEqual(submission.status, submission.SCHEDULED,
                             "Submission should have scheduled status.")

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def test_scheduled_status_is_reflected_prior_to_announcement(self):
        """The submission is being announced; not yet announced."""
        with self.app.app_context():
            session = classic.current_session()

            # Publication agent publishes the paper.
            db_submission = session.query(classic.models.Submission)\
                .get(self.submission.submission_id)
            db_submission.status = db_submission.NEEDS_EMAIL
            session.add(db_submission)
            session.commit()

            # Submission state should reflect scheduled status.
            submission, _ = load(self.submission.submission_id)
            self.assertEqual(submission.status, submission.SCHEDULED,
                             "Submission should have scheduled status.")

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def test_scheduled_tomorrow_status_is_reflected(self):
        """The submission has been scheduled for publication tomorrow."""
        with self.app.app_context():
            session = classic.current_session()

            # Publication agent publishes the paper.
            db_submission = session.query(classic.models.Submission)\
                .get(self.submission.submission_id)
            db_submission.status = db_submission.NEXT_PUBLISH_DAY
            session.add(db_submission)
            session.commit()

            # Submission state should reflect scheduled status.
            submission, _ = load(self.submission.submission_id)
            self.assertEqual(submission.status, submission.SCHEDULED,
                             "Submission should be scheduled for tomorrow.")

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def test_publication_failed(self):
        """The submission was not announced successfully."""
        with self.app.app_context():
            session = classic.current_session()

            # Publication agent publishes the paper.
            db_submission = session.query(classic.models.Submission)\
                .get(self.submission.submission_id)
            db_submission.status = db_submission.ERROR_STATE
            session.add(db_submission)
            session.commit()

            # Submission state should reflect scheduled status.
            submission, _ = load(self.submission.submission_id)
            self.assertEqual(submission.status, submission.ERROR,
                             "Submission should have error status.")

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def test_deleted(self):
        """The submission was deleted by the classic system."""
        with self.app.app_context():
            session = classic.current_session()

            for classic_status in classic.models.Submission.DELETED:
                # Publication agent publishes the paper.
                db_submission = session.query(classic.models.Submission)\
                    .get(self.submission.submission_id)
                db_submission.status = classic_status
                session.add(db_submission)
                session.commit()

                # Submission state should reflect scheduled status.
                submission, _ = load(self.submission.submission_id)
                self.assertEqual(submission.status, submission.DELETED,
                                 "Submission should have deleted status.")

    @mock.patch(f'{core.__name__}.StreamPublisher', mock.MagicMock())
    def test_deleted_in_ng(self):
        """The submission was deleted in this package."""
        with self.app.app_context():
            session = classic.current_session()
            self.submission, _ = save(
                Rollback(creator=self.submitter),
                submission_id=self.submission.submission_id
            )

            db_submission = session.query(classic.models.Submission)\
                .get(self.submission.submission_id)
            self.assertEqual(db_submission.status,
                             classic.models.Submission.USER_DELETED)
