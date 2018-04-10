from unittest import TestCase, mock
from contextlib import contextmanager
from flask import Flask

import events
from events.services import classic


@contextmanager
def in_memory_db():
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

    def test_classic_workflow(self):
        """Submitter proceeds through workflow in a linear fashion."""
        with in_memory_db() as session:
            # Submitter clicks on 'Start new submission' in the user dashboard.
            submission, stack = events.save(
                events.CreateSubmission(creator=self.submitter)
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
                             self.submitter.native_id,
                             "Submitter ID set on submission")
            self.assertEqual(db_submission.submitter_email,
                             self.submitter.email,
                             "Submitter email set on submission")
            self.assertEqual(db_submission.submitter_name, self.submitter.name,
                             "Submitter name set on submission")
            self.assertEqual(db_submission.created, submission.created,
                             "Creation datetime set correctly")

            # TODO: What else to check here?

            # /start: Submitter completes the start submission page.
            license_uri = 'http://creativecommons.org/publicdomain/zero/1.0/'
            submission, stack = events.save(
                events.VerifyContactInformation(creator=self.submitter),
                events.AssertAuthorship(
                    creator=self.submitter,
                    submitter_is_author=True
                ),
                events.SelectLicense(
                    creator=self.submitter,
                    license_uri=license_uri,
                    license_name='CC0 1.0'
                ),
                events.AcceptPolicy(creator=self.submitter),
                events.SetPrimaryClassification(
                    creator=self.submitter,
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
                    creator=self.submitter,
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
            metadata = [
                ('title', 'Foo title'),
                ('abstract', "One morning, as Gregor Samsa was waking up..."),
                ('comments', '5 pages, 2 turtle doves'),
                ('report_num', 'asdf1234'),
                ('doi', '10.01234/56789'),
                ('journal_ref', 'Foo Rev 1, 2 (1903)')
            ]
            submission, stack = events.save(
                events.UpdateMetadata(
                    creator=self.submitter,
                    metadata=metadata
                ),
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
            self.assertEqual(db_submission.authors, "Bob Paulson (Fight Club)",
                             "Authors updated in canonical format in database")

            self.assertEqual(len(stack), 9,
                             "Nine commands have been executed in total.")

            # /preview: Submitter adds a secondary classification.
            submission, stack = events.save(
                events.AddSecondaryClassification(
                    creator=self.submitter,
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
            self.assertEqual(len(stack), 10,
                             "Ten commands have been executed in total.")

            # /preview: Submitter finalizes submission.
            finalize = events.FinalizeSubmission(creator=self.submitter)
            submission, stack = events.save(
                finalize, submission_id=submission.submission_id
            )
            db_submission = session.query(classic.models.Submission)\
                .get(submission.submission_id)

            self.assertEqual(db_submission.status, db_submission.SUBMITTED,
                             "Submission status set correctly in database")
            self.assertEqual(db_submission.submit_time, finalize.created,
                             "Submit time is set.")
            self.assertEqual(len(stack), 11,
                             "Eleven commands have been executed in total.")
