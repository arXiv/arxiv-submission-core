"""Tests for storing events."""

from unittest import TestCase, mock
from datetime import datetime
from pytz import UTC
from flask import Flask

from ....domain.agent import User, System
from ....domain.submission import License, Submission, Author
from ....domain.event import CreateSubmission, \
    FinalizeSubmission, SetPrimaryClassification, AddSecondaryClassification, \
    SetLicense, ConfirmPolicy, ConfirmContactInformation, SetTitle, \
    SetAbstract, SetDOI, SetMSCClassification, SetACMClassification, \
    SetJournalReference, SetComments, SetAuthors, Announce, \
    ConfirmAuthorship, SetUploadPackage
from .. import init_app, create_all, drop_all, models, DBEvent, \
    get_submission, current_session, get_licenses, exceptions, store_event, \
    transaction


from .util import in_memory_db


class TestStoreEvent(TestCase):
    """Tests for :func:`.store_event`."""

    def setUp(self):
        """Instantiate a user."""
        self.user = User(12345, 'joe@joe.joe',
                         endorsements=['physics.soc-ph', 'cs.DL'])

    def test_store_creation(self):
        """Store a :class:`CreateSubmission`."""
        with in_memory_db():
            session = current_session()
            before = None
            event = CreateSubmission(creator=self.user)
            event.created = datetime.now(UTC)
            after = event.apply(before)

            event, after = store_event(event, before, after)

            db_sb = session.query(models.Submission).get(event.submission_id)

            # Make sure that we get the right submission ID.
            self.assertIsNotNone(event.submission_id)
            self.assertEqual(event.submission_id, after.submission_id)
            self.assertEqual(event.submission_id, db_sb.submission_id)

            self.assertEqual(db_sb.status,  models.Submission.NOT_SUBMITTED)
            self.assertEqual(db_sb.type, models.Submission.NEW_SUBMISSION)
            self.assertEqual(db_sb.version, 1)

    def test_store_events_with_metadata(self):
        """Store events and attendant submission with metadata."""
        metadata = {
            'title': 'foo title',
            'abstract': 'very abstract' * 20,
            'comments': 'indeed',
            'msc_class': 'foo msc',
            'acm_class': 'F.2.2; I.2.7',
            'doi': '10.1000/182',
            'journal_ref': 'Nature 1991 2: 1',
            'authors': [Author(order=0, forename='Joe', surname='Bloggs')]
        }
        with in_memory_db():

            ev = CreateSubmission(creator=self.user)
            ev2 = SetTitle(creator=self.user, title=metadata['title'])
            ev3 = SetAbstract(creator=self.user, abstract=metadata['abstract'])
            ev4 = SetComments(creator=self.user, comments=metadata['comments'])
            ev5 = SetMSCClassification(creator=self.user,
                                       msc_class=metadata['msc_class'])
            ev6 = SetACMClassification(creator=self.user,
                                       acm_class=metadata['acm_class'])
            ev7 = SetJournalReference(creator=self.user,
                                      journal_ref=metadata['journal_ref'])
            ev8 = SetDOI(creator=self.user, doi=metadata['doi'])
            events = [ev, ev2, ev3, ev4, ev5, ev6, ev7, ev8]

            with transaction():
                before = None
                for i, event in enumerate(list(events)):
                    event.created = datetime.now(UTC)
                    after = event.apply(before)
                    event, after = store_event(event, before, after)
                    events[i] = event
                    before = after

            session = current_session()
            db_submission = session.query(models.Submission)\
                .get(after.submission_id)
            db_events = session.query(DBEvent).all()

            for key, value in metadata.items():
                if key == 'authors':
                    continue
                self.assertEqual(getattr(db_submission, key), value,
                                 f"The value of {key} should be {value}")
            self.assertEqual(db_submission.authors,
                             after.metadata.authors_display,
                             "The canonical author string should be used to"
                             " update the submission in the database.")

            self.assertEqual(len(db_events), 8,
                             "Eight events should be stored")
            for db_event in db_events:
                self.assertEqual(db_event.submission_id, after.submission_id,
                                 "The submission id should be set")

    def test_store_events_with_finalized_submission(self):
        """Store events and a finalized submission."""
        metadata = {
            'title': 'foo title',
            'abstract': 'very abstract' * 20,
            'comments': 'indeed',
            'msc_class': 'foo msc',
            'acm_class': 'F.2.2; I.2.7',
            'doi': '10.1000/182',
            'journal_ref': 'Nature 1991 2: 1',
            'authors': [Author(order=0, forename='Joe', surname='Bloggs')]
        }
        with in_memory_db():

            events = [
                CreateSubmission(creator=self.user),
                ConfirmContactInformation(creator=self.user),
                ConfirmAuthorship(creator=self.user, submitter_is_author=True),
                ConfirmContactInformation(creator=self.user),
                ConfirmPolicy(creator=self.user),
                SetTitle(creator=self.user, title=metadata['title']),
                SetAuthors(creator=self.user, authors=[
                    Author(order=0, forename='Joe', surname='Bloggs',
                           email='joe@blo.ggs'),
                    Author(order=1, forename='Jane', surname='Doe',
                           email='j@doe.com'),
                ]),
                SetAbstract(creator=self.user, abstract=metadata['abstract']),
                SetComments(creator=self.user, comments=metadata['comments']),
                SetMSCClassification(creator=self.user,
                                     msc_class=metadata['msc_class']),
                SetACMClassification(creator=self.user,
                                     acm_class=metadata['acm_class']),
                SetJournalReference(creator=self.user,
                                    journal_ref=metadata['journal_ref']),
                SetDOI(creator=self.user, doi=metadata['doi']),
                SetLicense(creator=self.user,
                           license_uri='http://foo.org/1.0/',
                           license_name='Foo zero 1.0'),
                SetUploadPackage(creator=self.user, identifier='12345'),
                SetPrimaryClassification(creator=self.user,
                                         category='physics.soc-ph'),
                FinalizeSubmission(creator=self.user)
            ]

            with transaction():
                before = None
                for i, event in enumerate(list(events)):
                    event.created = datetime.now(UTC)
                    after = event.apply(before)
                    event, after = store_event(event, before, after)
                    events[i] = event
                    before = after

            session = current_session()
            db_submission = session.query(models.Submission) \
                .get(after.submission_id)
            db_events = session.query(DBEvent).all()

            self.assertEqual(db_submission.submission_id, after.submission_id,
                             "The submission should be updated with the PK id")
            self.assertEqual(db_submission.status, models.Submission.SUBMITTED,
                             "Submission should be in submitted state.")
            self.assertEqual(len(db_events), len(events),
                             "%i events should be stored" % len(events))
            for db_event in db_events:
                self.assertEqual(db_event.submission_id, after.submission_id,
                                 "The submission id should be set")

    def test_store_doi_jref_with_publication(self):
        """:class:`SetDOI` or :class:`SetJournalReference` after pub."""
        metadata = {
            'title': 'foo title',
            'abstract': 'very abstract' * 20,
            'comments': 'indeed',
            'msc_class': 'foo msc',
            'acm_class': 'F.2.2; I.2.7',
            'doi': '10.1000/182',
            'journal_ref': 'Nature 1991 2: 1',
            'authors': [Author(order=0, forename='Joe', surname='Bloggs')]
        }

        with in_memory_db():
            events = [
                CreateSubmission(creator=self.user),
                ConfirmContactInformation(creator=self.user),
                ConfirmAuthorship(creator=self.user, submitter_is_author=True),
                ConfirmContactInformation(creator=self.user),
                ConfirmPolicy(creator=self.user),
                SetTitle(creator=self.user, title=metadata['title']),
                SetAuthors(creator=self.user, authors=[
                    Author(order=0, forename='Joe', surname='Bloggs',
                           email='joe@blo.ggs'),
                    Author(order=1, forename='Jane', surname='Doe',
                           email='j@doe.com'),
                ]),
                SetAbstract(creator=self.user, abstract=metadata['abstract']),
                SetComments(creator=self.user, comments=metadata['comments']),
                SetMSCClassification(creator=self.user,
                                     msc_class=metadata['msc_class']),
                SetACMClassification(creator=self.user,
                                     acm_class=metadata['acm_class']),
                SetJournalReference(creator=self.user,
                                    journal_ref=metadata['journal_ref']),
                SetDOI(creator=self.user, doi=metadata['doi']),
                SetLicense(creator=self.user,
                           license_uri='http://foo.org/1.0/',
                           license_name='Foo zero 1.0'),
                SetUploadPackage(creator=self.user, identifier='12345'),
                SetPrimaryClassification(creator=self.user,
                                         category='physics.soc-ph'),
                FinalizeSubmission(creator=self.user)
            ]

            with transaction():
                before = None
                for i, event in enumerate(list(events)):
                    event.created = datetime.now(UTC)
                    after = event.apply(before)
                    event = store_event(event, before, after)
                    events[i] = event
                    before = after

            session = current_session()
            # Announced!
            paper_id = '1901.00123'
            db_submission = session.query(models.Submission) \
                .get(after.submission_id)
            db_submission.status = db_submission.ANNOUNCED
            db_document = models.Document(paper_id=paper_id)
            db_submission.doc_paper_id = paper_id
            db_submission.document = db_document
            session.add(db_submission)
            session.add(db_document)
            session.commit()

            # This would normally happen during a load.
            pub = Announce(creator=System(__name__), arxiv_id=paper_id,
                           committed=True)
            before = pub.apply(before)

            # Now set DOI + journal ref
            doi = '10.1000/182'
            journal_ref = 'foo journal 1994'
            e3 = SetDOI(creator=self.user, doi=doi,
                        submission_id=after.submission_id,
                        created=datetime.now(UTC))
            after = e3.apply(before)
            with transaction():
                store_event(e3, before, after)

            e4 = SetJournalReference(creator=self.user,
                                     journal_ref=journal_ref,
                                     submission_id=after.submission_id,
                                     created=datetime.now(UTC))
            before = after
            after = e4.apply(before)
            with transaction():
                store_event(e4, before, after)

            session = current_session()
            # What happened.
            db_submission = session.query(models.Submission) \
                .filter(models.Submission.doc_paper_id == paper_id) \
                .order_by(models.Submission.submission_id.desc())
            self.assertEqual(db_submission.count(), 2,
                             "Creates a second row for the JREF")
            db_jref = db_submission.first()
            self.assertTrue(db_jref.is_jref())
            self.assertEqual(db_jref.doi, doi)
            self.assertEqual(db_jref.journal_ref, journal_ref)

    def test_store_events_with_classification(self):
        """Store events including classification."""
        ev = CreateSubmission(creator=self.user)
        ev2 = SetPrimaryClassification(creator=self.user,
                                       category='physics.soc-ph')
        ev3 = AddSecondaryClassification(creator=self.user,
                                         category='physics.acc-ph')
        events = [ev, ev2, ev3]

        with in_memory_db():
            with transaction():
                before = None
                for i, event in enumerate(list(events)):
                    event.created = datetime.now(UTC)
                    after = event.apply(before)
                    event, after = store_event(event, before, after)
                    events[i] = event
                    before = after

            session = current_session()
            db_submission = session.query(models.Submission)\
                .get(after.submission_id)
            db_events = session.query(DBEvent).all()

            self.assertEqual(db_submission.submission_id, after.submission_id,
                             "The submission should be updated with the PK id")
            self.assertEqual(len(db_events), 3,
                             "Three events should be stored")
            for db_event in db_events:
                self.assertEqual(db_event.submission_id, after.submission_id,
                                 "The submission id should be set")
            self.assertEqual(len(db_submission.categories), 2,
                             "Two category relations should be set")
            self.assertEqual(db_submission.primary_classification.category,
                             after.primary_classification.category,
                             "Primary classification should be set.")
