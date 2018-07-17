"""
Integration tests for the classic database service.

These tests assume that SQLAlchemy's MySQL backend is implemented correctly:
instead of using a live MySQL database, they use an in-memory SQLite database.
This is mostly fine (they are intended to be more-or-less swappable). The one
iffy bit is the JSON datatype, which is not available by default in the SQLite
backend, and so we inject a simple one here. End to end tests with a live MySQL
database will provide more confidence in this area.
"""

from unittest import TestCase, mock
import os
from datetime import datetime
from contextlib import contextmanager
import json

from flask import Flask

from ...domain.agent import User
from ...domain.submission import License, Submission, Author
from ...domain.event import CreateSubmission, \
    FinalizeSubmission, SetPrimaryClassification, AddSecondaryClassification, \
    SelectLicense, SetPrimaryClassification, AcceptPolicy, \
    VerifyContactInformation, SetTitle, SetAbstract, SetDOI, \
    SetMSCClassification, SetACMClassification, SetJournalReference, \
    SetComments, UpdateAuthors
from . import init_app, create_all, drop_all, models, store_events, DBEvent, \
    get_submission, current_session, get_licenses, exceptions


@contextmanager
def in_memory_db():
    """Provide an in-memory sqlite database for testing purposes."""
    app = Flask('foo')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    with app.app_context():
        init_app(app)
        create_all()
        try:
            yield current_session()
        except Exception:
            raise
        finally:
            drop_all()


class TestGetLicenses(TestCase):
    """Test :func:`.get_licenses`."""

    def test_get_all_active_licenses(self):
        """Return a :class:`.License` for each active license in the db."""
        # mock_util.json_factory.return_value = SQLiteJSON

        with in_memory_db() as session:
            session.add(models.License(
                name="http://arxiv.org/licenses/assumed-1991-2003",
                sequence=9,
                label="Assumed arXiv.org perpetual, non-exclusive license to",
                active=0
            ))
            session.add(models.License(
                name="http://creativecommons.org/licenses/publicdomain/",
                sequence=4,
                label="Creative Commons Public Domain Declaration",
                active=1
            ))
            session.commit()
            licenses = get_licenses()

        self.assertEqual(len(licenses), 1,
                         "Only the active license should be returned.")
        self.assertIsInstance(licenses[0], License,
                              "Should return License instances.")
        self.assertEqual(licenses[0].uri,
                         "http://creativecommons.org/licenses/publicdomain/",
                         "Should use name column to populate License.uri")
        self.assertEqual(licenses[0].name,
                         "Creative Commons Public Domain Declaration",
                         "Should use label column to populate License.name")


class TestStoreEvents(TestCase):
    """Test :func:`.store_events`."""

    def test_store_event(self):
        """Store a single event."""
        with in_memory_db() as session:
            user = User(12345, 'joe@joe.joe')
            ev = CreateSubmission(creator=user)
            submission = ev.apply()
            submission = store_events(ev, submission=submission)

            db_submission = session.query(models.Submission)\
                .get(submission.submission_id)

        self.assertEqual(db_submission.submission_id, submission.submission_id,
                         "The submission should be updated with the PK id.")
        self.assertEqual(db_submission.submitter_id,
                         submission.creator.native_id,
                         "The native ID of the creator should be used")
        self.assertEqual(db_submission.status, db_submission.NOT_SUBMITTED,
                         "Submission in database should be in status 0 (not"
                         " submitted) by default.")

    def test_store_events_with_metadata(self):
        """Store events and attendant submission with metadata."""
        metadata = {
            'title': 'foo title',
            'abstract': 'very abstract',
            'comments': 'indeed',
            'msc_class': 'foo msc',
            'acm_class': 'COMPUTER-Y',
            'doi': '10.01234/5678',
            'journal_ref': 'Nature 1: 1',
            'authors': [Author(order=0, forename='Joe', surname='Bloggs')]
        }
        with in_memory_db() as session:
            user = User(12345, 'joe@joe.joe')
            ev = CreateSubmission(creator=user)
            ev2 = SetTitle(creator=user, title=metadata['title'])
            ev3 = SetAbstract(creator=user, abstract=metadata['abstract'])
            ev4 = SetComments(creator=user, comments=metadata['comments'])
            ev5 = SetMSCClassification(creator=user,
                                       msc_class=metadata['msc_class'])
            ev6 = SetACMClassification(creator=user,
                                       acm_class=metadata['acm_class'])
            ev7 = SetJournalReference(creator=user,
                                      journal_ref=metadata['journal_ref'])
            ev8 = SetDOI(creator=user, doi=metadata['doi'])

            submission = ev.apply()
            submission = ev2.apply(submission)
            submission = ev3.apply(submission)
            submission = ev4.apply(submission)
            submission = ev5.apply(submission)
            submission = ev6.apply(submission)
            submission = ev7.apply(submission)
            submission = ev8.apply(submission)
            submission = store_events(ev, ev2, ev3, ev4, ev5, ev6, ev7, ev8,
                                      submission=submission)

            db_submission = session.query(models.Submission)\
                .get(submission.submission_id)

            db_events = session.query(DBEvent).all()

        for key, value in metadata.items():
            if key == 'authors':
                continue
            self.assertEqual(getattr(db_submission, key), value,
                             f"The value of {key} should be {value}")
        self.assertEqual(db_submission.authors,
                         submission.metadata.authors_display,
                         "The canonical author string should be used to"
                         " update the submission in the database.")

        self.assertEqual(len(db_events), 8, "Eight events should be stored")
        for db_event in db_events:
            self.assertEqual(db_event.submission_id, submission.submission_id,
                             "The submission id should be set")

    def test_store_events_with_finalized_submission(self):
        """Store events and a finalized submission."""
        with in_memory_db() as session:
            user = User(12345, 'joe@joe.joe')
            ev = CreateSubmission(creator=user)
            ev2 = FinalizeSubmission(creator=user)
            submission = ev.apply()
            submission = ev2.apply(submission)
            submission = store_events(ev, ev2, submission=submission)

            db_submission = session.query(models.Submission)\
                .get(submission.submission_id)
            db_events = session.query(DBEvent).all()

        self.assertEqual(db_submission.submission_id, submission.submission_id,
                         "The submission should be updated with the PK id.")
        self.assertEqual(len(db_events), 2, "Two events should be stored")
        for db_event in db_events:
            self.assertEqual(db_event.submission_id, submission.submission_id,
                             "The submission id should be set")

    def test_store_events_with_classification(self):
        """Store events including classification."""
        user = User(12345, 'joe@joe.joe')
        ev = CreateSubmission(creator=user)
        ev2 = SetPrimaryClassification(creator=user,
                                       category='physics.soc-ph')
        ev3 = AddSecondaryClassification(creator=user,
                                         category='physics.acc-ph')
        submission = ev.apply()
        submission = ev2.apply(submission)
        submission = ev3.apply(submission)

        with in_memory_db() as session:
            submission = store_events(ev, ev2, ev3, submission=submission)

            db_submission = session.query(models.Submission)\
                .get(submission.submission_id)
            db_events = session.query(DBEvent).all()

        self.assertEqual(db_submission.submission_id, submission.submission_id,
                         "The submission should be updated with the PK id.")
        self.assertEqual(len(db_events), 3, "Three events should be stored")
        for db_event in db_events:
            self.assertEqual(db_event.submission_id, submission.submission_id,
                             "The submission id should be set")
        self.assertEqual(len(db_submission.categories), 2,
                         "Two category relations should be set")
        self.assertEqual(db_submission.primary_classification.category,
                         submission.primary_classification.category,
                         "Primary classification should be set.")


class TestGetSubmission(TestCase):
    """Test :func:`.get_submission`."""

    def test_get_submission_that_does_not_exist(self):
        """Test that an exception is raised when submission doesn't exist."""
        with in_memory_db():
            with self.assertRaises(exceptions.NoSuchSubmission):
                get_submission(1)

    def test_get_submission_with_publish(self):
        """Test that publication state is reflected in submission data."""
        user = User(12345, 'joe@joe.joe')

        events = [
            CreateSubmission(creator=user),
            SetTitle(creator=user, title='Foo title'),
            SetAbstract(creator=user, abstract='Indeed'),
            UpdateAuthors(creator=user, authors=[
                Author(order=0, forename='Joe', surname='Bloggs',
                       email='joe@blo.ggs'),
                Author(order=1, forename='Jane', surname='Doe',
                       email='j@doe.com'),
            ]),
            SelectLicense(creator=user, license_uri='http://foo.org/1.0/',
                          license_name='Foo zero 1.0'),
            SetPrimaryClassification(creator=user, category='cs.DL'),
            AcceptPolicy(creator=user),
            VerifyContactInformation(creator=user),
            FinalizeSubmission(creator=user)
        ]
        submission = None
        for ev in events:
            submission = ev.apply(submission) if submission else ev.apply()

        with in_memory_db() as session:
            # User creates and finalizes submission.
            submission = store_events(*events, submission=submission)
            ident = submission.submission_id

            # Moderation happens, things change outside the event model.
            db_submission = session.query(models.Submission).get(ident)

            # Published!
            db_submission.status = db_submission.PUBLISHED
            db_document = models.Document(paper_id='1234.5678')
            db_submission.document = db_document
            session.add(db_submission)
            session.add(db_document)
            session.commit()

            # Now get the submission.
            submission_loaded, _ = get_submission(ident)

        self.assertEqual(submission.metadata.title,
                         submission_loaded.metadata.title,
                         "Event-derived metadata should be preserved.")
        self.assertEqual(submission_loaded.arxiv_id, "1234.5678",
                         "arXiv paper ID should be set")
        self.assertEqual(submission_loaded.status, Submission.PUBLISHED,
                         "Submission status should reflect publish action")

    def test_get_submission_with_hold_and_reclass(self):
        """Test changes made externally are reflected in submission data."""
        user = User(12345, 'joe@joe.joe')
        events = [
            CreateSubmission(creator=user),
            SetTitle(creator=user, title='Foo title'),
            SetAbstract(creator=user, abstract='Indeed'),
            UpdateAuthors(creator=user, authors=[
                Author(order=0, forename='Joe', surname='Bloggs',
                       email='joe@blo.ggs'),
                Author(order=1, forename='Jane', surname='Doe',
                       email='j@doe.com'),
            ]),
            SelectLicense(creator=user, license_uri='http://foo.org/1.0/',
                          license_name='Foo zero 1.0'),
            SetPrimaryClassification(creator=user, category='cs.DL'),
            AcceptPolicy(creator=user),
            VerifyContactInformation(creator=user),
            FinalizeSubmission(creator=user)
        ]
        submission = None
        for ev in events:
            submission = ev.apply(submission) if submission else ev.apply()

        with in_memory_db() as session:
            # User creates and finalizes submission.
            submission = store_events(*events, submission=submission)
            ident = submission.submission_id

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
        self.assertEqual(submission_loaded.status, Submission.ON_HOLD,
                         "Submission status should reflect hold action"
                         " performed outside the purview of the event model.")
