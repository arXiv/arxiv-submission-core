"""Tests for retrieving submissions."""

from unittest import TestCase, mock
from datetime import datetime
from pytz import UTC
from flask import Flask

from ....domain.agent import User, System
from ....domain.submission import License, Submission, Author
from ....domain.event import CreateSubmission, \
    FinalizeSubmission, SetPrimaryClassification, AddSecondaryClassification, \
    SetLicense, SetPrimaryClassification, ConfirmPolicy, \
    ConfirmContactInformation, SetTitle, SetAbstract, SetDOI, \
    SetMSCClassification, SetACMClassification, SetJournalReference, \
    SetComments, SetAuthors, Announce, ConfirmAuthorship, ConfirmPolicy, \
    SetUploadPackage
from .. import init_app, create_all, drop_all, models, DBEvent, \
    get_submission, get_user_submissions_fast, current_session, get_licenses, \
    exceptions, store_event, transaction

from .util import in_memory_db


class TestGetSubmission(TestCase):
    """Test :func:`.classic.get_submission`."""

    def test_get_submission_that_does_not_exist(self):
        """Test that an exception is raised when submission doesn't exist."""
        with in_memory_db():
            with self.assertRaises(exceptions.NoSuchSubmission):
                get_submission(1)

    def test_get_submission_with_publish(self):
        """Test that publication state is reflected in submission data."""
        user = User(12345, 'joe@joe.joe',
                    endorsements=['physics.soc-ph', 'cs.DL'])

        events = [
            CreateSubmission(creator=user),
            SetTitle(creator=user, title='Foo title'),
            SetAbstract(creator=user, abstract='Indeed' * 10),
            SetAuthors(creator=user, authors=[
                Author(order=0, forename='Joe', surname='Bloggs',
                       email='joe@blo.ggs'),
                Author(order=1, forename='Jane', surname='Doe',
                       email='j@doe.com'),
            ]),
            SetLicense(creator=user, license_uri='http://foo.org/1.0/',
                       license_name='Foo zero 1.0'),
            SetPrimaryClassification(creator=user, category='cs.DL'),
            ConfirmPolicy(creator=user),
            SetUploadPackage(creator=user, identifier='12345'),
            ConfirmContactInformation(creator=user),
            FinalizeSubmission(creator=user)
        ]

        with in_memory_db():
            # User creates and finalizes submission.
            before = None
            for i, event in enumerate(list(events)):
                event.created = datetime.now(UTC)
                after = event.apply(before)
                event, after = store_event(event, before, after)
                events[i] = event
                before = after
            submission = after

            ident = submission.submission_id

            session = current_session()
            # Moderation happens, things change outside the event model.
            db_submission = session.query(models.Submission).get(ident)

            # Announced!
            db_submission.status = db_submission.ANNOUNCED
            db_document = models.Document(paper_id='1901.00123')
            db_submission.document = db_document
            session.add(db_submission)
            session.add(db_document)
            session.commit()

            # Now get the submission.
            submission_loaded, _ = get_submission(ident)

        self.assertEqual(submission.metadata.title,
                         submission_loaded.metadata.title,
                         "Event-derived metadata should be preserved.")
        self.assertEqual(submission_loaded.arxiv_id, "1901.00123",
                         "arXiv paper ID should be set")
        self.assertEqual(submission_loaded.status, Submission.ANNOUNCED,
                         "Submission status should reflect publish action")

    def test_get_submission_with_hold_and_reclass(self):
        """Test changes made externally are reflected in submission data."""
        user = User(12345, 'joe@joe.joe',
                    endorsements=['physics.soc-ph', 'cs.DL'])
        events = [
            CreateSubmission(creator=user),
            SetTitle(creator=user, title='Foo title'),
            SetAbstract(creator=user, abstract='Indeed' * 20),
            SetAuthors(creator=user, authors=[
                Author(order=0, forename='Joe', surname='Bloggs',
                       email='joe@blo.ggs'),
                Author(order=1, forename='Jane', surname='Doe',
                       email='j@doe.com'),
            ]),
            SetLicense(creator=user, license_uri='http://foo.org/1.0/',
                       license_name='Foo zero 1.0'),
            SetPrimaryClassification(creator=user, category='cs.DL'),
            ConfirmPolicy(creator=user),
            SetUploadPackage(creator=user, identifier='12345'),
            ConfirmContactInformation(creator=user),
            FinalizeSubmission(creator=user)
        ]

        with in_memory_db():
            # User creates and finalizes submission.
            with transaction():
                before = None
                for i, event in enumerate(list(events)):
                    event.created = datetime.now(UTC)
                    after = event.apply(before)
                    event, after = store_event(event, before, after)
                    events[i] = event
                    before = after
                submission = after
                ident = submission.submission_id

            session = current_session()
            # Moderation happens, things change outside the event model.
            db_submission = session.query(models.Submission).get(ident)

            # Reclassification!
            session.delete(db_submission.primary_classification)
            session.add(models.SubmissionCategory(
                submission_id=ident, category='cs.IR', is_primary=1
            ))

            # On hold!
            db_submission.status = db_submission.ON_HOLD
            session.add(db_submission)
            session.commit()

            # Now get the submission.
            submission_loaded, _ = get_submission(ident)

        self.assertEqual(submission.metadata.title,
                         submission_loaded.metadata.title,
                         "Event-derived metadata should be preserved.")
        self.assertEqual(submission_loaded.primary_classification.category,
                         "cs.IR",
                         "Primary classification should reflect the"
                         " reclassification that occurred outside the purview"
                         " of the event model.")
        self.assertEqual(submission_loaded.status, Submission.SUBMITTED,
                         "Submission status should still be submitted.")
        self.assertTrue(submission_loaded.is_on_hold,
                        "Hold status should reflect hold action performed"
                        " outside the purview of the event model.")

    def test_get_submission_list(self):
        """Test that the set of submissions for a user can be retrieved."""
        user = User(42, 'adent@example.org',
                    endorsements=['astro-ph.GA', 'astro-ph.EP'])
        events1 = [
            # first submission
            CreateSubmission(creator=user),
            SetTitle(creator=user, title='Foo title'),
            SetAbstract(creator=user, abstract='Indeed' * 20),
            SetAuthors(creator=user, authors=[
                Author(order=0, forename='Arthur', surname='Dent',
                       email='adent@example.org'),
                Author(order=1, forename='Ford', surname='Prefect',
                       email='fprefect@example.org'),
            ]),
            SetLicense(creator=user, license_uri='http://creativecommons.org/publicdomain/zero/1.0/',
                       license_name='Foo zero 1.0'),
            SetPrimaryClassification(creator=user, category='astro-ph.GA'),
            ConfirmPolicy(creator=user),
            SetUploadPackage(creator=user, identifier='1'),
            ConfirmContactInformation(creator=user),
            FinalizeSubmission(creator=user)
        ]
        events2 = [
            # second submission
            CreateSubmission(creator=user),
            SetTitle(creator=user, title='Bar title'),
            SetAbstract(creator=user, abstract='Indubitably' * 20),
            SetAuthors(creator=user, authors=[
                Author(order=0, forename='Jane', surname='Doe',
                       email='jadoe@example.com'),
                Author(order=1, forename='John', surname='Doe',
                       email='jodoe@example.com'),
            ]),
            SetLicense(creator=user, license_uri='http://creativecommons.org/publicdomain/zero/1.0/',
                       license_name='Foo zero 1.0'),
            SetPrimaryClassification(creator=user, category='astro-ph.GA'),
            ConfirmPolicy(creator=user),
            SetUploadPackage(creator=user, identifier='1'),
            ConfirmContactInformation(creator=user),
            FinalizeSubmission(creator=user)
        ]

        with in_memory_db():
            # User creates and finalizes submission.
            with transaction():
                before = None
                for i, event in enumerate(list(events1)):
                    event.created = datetime.now(UTC)
                    after = event.apply(before)
                    event, after = store_event(event, before, after)
                    events1[i] = event
                    before = after
                submission1 = after
                ident1 = submission1.submission_id

                before = None
                for i, event in enumerate(list(events2)):
                    event.created = datetime.now(UTC)
                    after = event.apply(before)
                    event, after = store_event(event, before, after)
                    events2[i] = event
                    before = after
                submission2 = after
                ident2 = submission2.submission_id

                classic_sub = models.Submission(
                    type='new',
                    submitter_id=42)
                session = current_session()
                session.add(classic_sub)

            # Now get the submissions for this user.
            submissions = get_user_submissions_fast(42)
            submission_loaded1, _ = get_submission(ident1)
            submission_loaded2, _ = get_submission(ident2)

        self.assertEqual(submission1.metadata.title,
                         submission_loaded1.metadata.title,
                         "Event-derived metadata for submission 1 should be preserved.")
        self.assertEqual(submission2.metadata.title,
                         submission_loaded2.metadata.title,
                         "Event-derived metadata for submission 2 should be preserved.")

        self.assertEqual(len(submissions),
                         2,
                         "There should be exactly two NG submissions.")

