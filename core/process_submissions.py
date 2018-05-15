from argparse import ArgumentParser
from contextlib import contextmanager
from csv import DictReader
import logging

from flask import Flask

import events
from events.services import classic

from events.exceptions import InvalidEvent

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

def process_csv(csvfile, session):
    """
    Process a csvfile using DictReader so any order of files will be possible.
    """
    with open(csvfile) as csvfh:
        reader = DictReader(csvfh)
        for submission in reader:
            try:
                submission_id = process_submission(submission, session)
                verify_submission(submission, session, submission_id)
            except (AssertionError, InvalidEvent) as e:
                logging.error('{}: {}'.format(submission['submission_id'], e))
                

def process_submission(s, session):
    """
    Process a submission using a csvfile
    """
    # TODO: Make sure forename surname separation are better
    try:
        forename, surname = s['submitter_name'].rsplit(maxsplit=1)
    except ValueError:
        forename = ''
        surname = s['submitter_name']
    submitter = events.domain.User(s['submitter_id'], email=s['submitter_email'],
                                   forename=forename, surname=surname)

    metadata = [
        ('title', s['title']),
        ('abstract', s['abstract']),
        ('comments', s['comments']),
        ('report_num', s['report_num']),
        ('doi', s['doi']),
        ('journal_ref', s['journal_ref'])
    ]

    submission, stack = events.save(
        events.CreateSubmission(creator=submitter)
    )

    if s.get('is_author') == '1':
        submission, stack = events.save(
            events.AssertAuthorship(
                creator=submitter,
                submitter_is_author=True
            ),
            submission_id=submission.submission_id
        )
    
    if s.get('agree_policy') == '1':
        submission, stack = events.save(
            events.AcceptPolicy(creator=submitter),
            submission_id=submission.submission_id
        )

    submission, stack = events.save(
        events.UpdateAuthors(
            authors_display=s['authors'],
            creator=submitter
        ),
        submission_id=submission.submission_id
    )
    
    # Parse the license
    license_uri = s.get('license')
    if license_uri:
        submission, stack = events.save(
            events.SelectLicense(
                creator=submitter,
                license_uri=license_uri
            ),
            submission_id=submission.submission_id
        )

    submission, stack = events.save(
        events.UpdateMetadata(
            creator=submitter,
            metadata=metadata
        ),
        submission_id=submission.submission_id
    )

    return submission.submission_id


    # If it goes to the end, then verify that results come in
    # events.load() returns a submission object, then verify it looks as expected

def verify_submission(s, session, submission_id):
    submission, stack = events.load(submission_id)

    assert submission.metadata.title == s['title']
    assert submission.metadata.abstract == s['abstract']
    assert submission.metadata.comments == s['comments']
    assert submission.metadata.report_num == s['report_num']
    assert submission.metadata.doi == s['doi']
    assert submission.metadata.journal_ref == s['journal_ref']
    
    if s.get('agree_policy') == '1':
        assert submission.submitter_accepts_policy
    else:
        assert not submission.submitter_accepts_policy

    if s.get('license'):
        assert submission.license.uri == s['license']

    if s.get('is_author') == '1':
        assert submission.submitter_is_author
    else:
        assert not submission.submitter_is_author

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('csvfile', help='CSV file')
    args = parser.parse_args()

    with in_memory_db() as session:
        process_csv(args.csvfile, session)
