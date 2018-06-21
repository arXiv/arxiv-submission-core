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
from contextlib import contextmanager

from flask import Flask

import events
from events.services import classic


@contextmanager
def in_memory_db():
    """Provide an in-memory sqlite database for testing purposes."""
    app = Flask('foo')
    app.config['CLASSIC_DATABASE_URI'] = 'sqlite://'

    with app.app_context():
        classic.init_app(app)
        classic.create_all()
        try:
            yield classic.current_session()
        except Exception:
            raise
        finally:
            classic.drop_all()


class TestClassicUIWorkflow(TestCase):
    """Replicate the classic submission UI workflow."""

    def setUp(self):
        """An arXiv user is submitting a new paper."""
        self.submitter = events.domain.User(1234, email='j.user@somewhere.edu',
                                            forename='Jane', surname='User')
        self.unicode_submitter = events.domain.User(12345, email='j.user@somewhere.edu',
                                            forename='大', surname='用户')

    def test_classic_workflow(self, submitter=None, metadata=None, authors=None):
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


        # TODO: Process data in dictionary form to events.Author objects.
        if authors is None:
            authors = [events.Author(order=0,
                                     forename='Bob',
                                     surname='Paulson',
                                     email='Robert.Paulson@nowhere.edu',
                                     affiliation='Fight Club'
                        )]

        with in_memory_db() as session:
            # Submitter clicks on 'Start new submission' in the user dashboard.
            submission, stack = events.save(
                events.CreateSubmission(creator=submitter)
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
            self.assertEqual(db_submission.created, submission.created,
                             "Creation datetime set correctly")

            # TODO: What else to check here?

            # /start: Submitter completes the start submission page.
            license_uri = 'http://creativecommons.org/publicdomain/zero/1.0/'
            submission, stack = events.save(
                events.VerifyContactInformation(creator=submitter),
                events.AssertAuthorship(
                    creator=submitter,
                    submitter_is_author=True
                ),
                events.SelectLicense(
                    creator=submitter,
                    license_uri=license_uri,
                    license_name='CC0 1.0'
                ),
                events.AcceptPolicy(creator=submitter),
                events.SetPrimaryClassification(
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
            submission, stack = events.save(
                events.AttachSourceContent(
                    creator=submitter,
                    location="https://submit.arxiv.org/upload/123",
                    checksum="a9s9k342900skks03330029k",
                    format='tex',
                    mime_type="application/zip",
                    identifier=123,
                    size=593992
                ),
                submission_id=submission.submission_id
            )

            self.assertEqual(len(stack), 7,
                             "Seven commands have been executed in total.")
            db_submission = session.query(classic.models.Submission)\
                .get(submission.submission_id)
            self.assertEqual(db_submission.must_process, 0,
                             "Processing status is set correctly in database")
            self.assertEqual(db_submission.source_size, 593992,
                             "Source package size set correctly in database")
            self.assertEqual(db_submission.source_format, 'tex',
                             "Source format set correctly in database")

            # /metadata: Submitter adds metadata to their submission, including
            # authors. In this package, we model authors in more detail than
            # in the classic system, but we should preserve the canonical
            # format in the db for legacy components' sake.
            submission, stack = events.save(
                events.SetTitle(creator=self.submitter,
                                title=metadata['title']),
                events.SetAbstract(creator=self.submitter,
                                   abstract=metadata['abstract']),
                events.SetComments(creator=self.submitter,
                                   comments=metadata['comments']),
                events.SetJournalReference(
                    creator=self.submitter,
                    journal_ref=metadata['journal_ref']
                ),
                events.SetDOI(creator=self.submitter, doi=metadata['doi']),
                events.SetReportNumber(creator=self.submitter,
                                       report_num=metadata['report_num']),
                events.UpdateAuthors(
                    creator=submitter,
                    authors=authors
                ),
                submission_id=submission.submission_id
            )
            db_submission = session.query(classic.models.Submission)\
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

            author_str = ';'.join([f"{author.forename} {author.surname} ({author.affiliation})"
                                      for author in authors])
            self.assertEqual(db_submission.authors,
                             author_str,
                             "Authors updated in canonical format in database")

            self.assertEqual(len(stack), 14,
                             "Fourteen commands have been executed in total.")

            # /preview: Submitter adds a secondary classification.
            submission, stack = events.save(
                events.AddSecondaryClassification(
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
            finalize = events.FinalizeSubmission(creator=submitter)
            submission, stack = events.save(
                finalize, submission_id=submission.submission_id
            )
            db_submission = session.query(classic.models.Submission)\
                .get(submission.submission_id)

            self.assertEqual(db_submission.status, db_submission.SUBMITTED,
                             "Submission status set correctly in database")
            self.assertEqual(db_submission.submit_time, finalize.created,
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
        authors = [events.Author(
                        order=0,
                        forename='惊人',
                        surname='用户',
                        email='amazing.user@nowhere.edu',
                        affiliation='Fight Club'
                    )]

        self.test_classic_workflow(
            submitter=submitter, metadata=metadata, authors=authors)

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

        self.test_classic_workflow(metadata=metadata)


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

        with cls.app.app_context():
            classic.init_app(cls.app)

    def setUp(self):
        """An arXiv user is submitting a new paper."""
        self.submitter = events.domain.User(1234, email='j.user@somewhere.edu',
                                            forename='Jane', surname='User')

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
            self.submission, _ = events.save(
                events.CreateSubmission(creator=self.submitter),
                events.VerifyContactInformation(creator=self.submitter),
                events.AssertAuthorship(
                    creator=self.submitter,
                    submitter_is_author=True
                ),
                events.SelectLicense(
                    creator=self.submitter,
                    license_uri=cc0,
                    license_name='CC0 1.0'
                ),
                events.AcceptPolicy(creator=self.submitter),
                events.SetPrimaryClassification(
                    creator=self.submitter,
                    category='cs.DL'
                ),
                events.AttachSourceContent(
                    creator=self.submitter,
                    location="https://submit.arxiv.org/upload/123",
                    checksum="a9s9k342900skks03330029k",
                    format='tex',
                    mime_type="application/zip",
                    identifier=123,
                    size=593992
                ),
                events.SetTitle(creator=self.submitter,
                                title=metadata['title']),
                events.SetAbstract(creator=self.submitter,
                            abstract=metadata['abstract']),
                events.SetComments(creator=self.submitter,
                            comments=metadata['comments']),
                events.SetJournalReference(
                    creator=self.submitter,
                    journal_ref=metadata['journal_ref']
                ),
                events.SetDOI(creator=self.submitter, doi=metadata['doi']),
                events.SetReportNumber(creator=self.submitter,
                                       report_num=metadata['report_num']),
                events.UpdateAuthors(
                    creator=self.submitter,
                    authors=[events.Author(
                        order=0,
                        forename='Bob',
                        surname='Paulson',
                        email='Robert.Paulson@nowhere.edu',
                        affiliation='Fight Club'
                    )]
                ),
                events.FinalizeSubmission(creator=self.submitter)
            )

    def tearDown(self):
        """Clear the database after each test."""
        with self.app.app_context():
            classic.drop_all()

    def test_publication_status_is_reflected(self):
        """The submission has been published/announced."""
        with self.app.app_context():
            session = classic.current_session()

            # Publication agent publishes the paper.
            db_submission = session.query(classic.models.Submission)\
                .get(self.submission.submission_id)
            db_submission.status = db_submission.PUBLISHED
            dated = (datetime.now() - datetime.utcfromtimestamp(0))
            primary = self.submission.primary_classification.category
            db_submission.document = classic.models.Document(
                document_id=1,
                paper_id='1901.00123',
                title=self.submission.metadata.title,
                authors=self.submission.metadata.authors_display,
                dated=dated.total_seconds(),
                primary_subject_class=primary,
                created=datetime.now(),
                submitter_email=self.submission.creator.email,
                submitter_id=self.submission.creator.native_id
            )
            session.add(db_submission)
            session.commit()

            # Submission state should reflect publication status.
            submission, _ = events.load(self.submission.submission_id)
            self.assertEqual(submission.status, submission.PUBLISHED,
                             "Submission should have published status.")
            self.assertEqual(submission.arxiv_id, "1901.00123",
                             "arXiv paper ID should be set")
            self.assertFalse(submission.active,
                             "Published submission should no longer be active")

    def test_publication_status_is_reflected_after_files_expire(self):
        """The submission has been published/announced, and files expired."""
        with self.app.app_context():
            session = classic.current_session()

            # Publication agent publishes the paper.
            db_submission = session.query(classic.models.Submission)\
                .get(self.submission.submission_id)
            db_submission.status = db_submission.DELETED_PUBLISHED
            dated = (datetime.now() - datetime.utcfromtimestamp(0))
            primary = self.submission.primary_classification.category
            db_submission.document = classic.models.Document(
                document_id=1,
                paper_id='1901.00123',
                title=self.submission.metadata.title,
                authors=self.submission.metadata.authors_display,
                dated=dated.total_seconds(),
                primary_subject_class=primary,
                created=datetime.now(),
                submitter_email=self.submission.creator.email,
                submitter_id=self.submission.creator.native_id
            )
            session.add(db_submission)
            session.commit()

            # Submission state should reflect publication status.
            submission, _ = events.load(self.submission.submission_id)
            self.assertEqual(submission.status, submission.PUBLISHED,
                             "Submission should have published status.")
            self.assertEqual(submission.arxiv_id, "1901.00123",
                             "arXiv paper ID should be set")
            self.assertFalse(submission.active,
                             "Published submission should no longer be active")

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
            submission, _ = events.load(self.submission.submission_id)
            self.assertEqual(submission.status, submission.SCHEDULED,
                             "Submission should have scheduled status.")

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
            submission, _ = events.load(self.submission.submission_id)
            self.assertEqual(submission.status, submission.SCHEDULED,
                             "Submission should have scheduled status.")

    def test_scheduled_status_is_reflected_prior_to_announcement(self):
        """The submission is being published; not yet announced."""
        with self.app.app_context():
            session = classic.current_session()

            # Publication agent publishes the paper.
            db_submission = session.query(classic.models.Submission)\
                .get(self.submission.submission_id)
            db_submission.status = db_submission.NEEDS_EMAIL
            session.add(db_submission)
            session.commit()

            # Submission state should reflect scheduled status.
            submission, _ = events.load(self.submission.submission_id)
            self.assertEqual(submission.status, submission.SCHEDULED,
                             "Submission should have scheduled status.")

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
            submission, _ = events.load(self.submission.submission_id)
            self.assertEqual(submission.status, submission.SCHEDULED,
                             "Submission should be scheduled for tomorrow.")

    def test_publication_failed(self):
        """The submission was not published successfully."""
        with self.app.app_context():
            session = classic.current_session()

            # Publication agent publishes the paper.
            db_submission = session.query(classic.models.Submission)\
                .get(self.submission.submission_id)
            db_submission.status = db_submission.ERROR_STATE
            session.add(db_submission)
            session.commit()

            # Submission state should reflect scheduled status.
            submission, _ = events.load(self.submission.submission_id)
            self.assertEqual(submission.status, submission.ERROR,
                             "Submission should have error status.")

    def test_deleted(self):
        """The submission was deleted."""
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
                submission, _ = events.load(self.submission.submission_id)
                self.assertEqual(submission.status, submission.DELETED,
                                 "Submission should have deleted status.")
