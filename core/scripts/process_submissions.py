"""
process_submissions

Usage: python process_submissions.py <TSVFILE>

TSVFILE is a TSVFILE containing the export_submissions.sql output.

Over all process (from arxiv-submission-core as working dir):
pipenv install --dev
pipenv shell
cd core
python setup.py develop
cd scripts
mysql -u root -B arXiv < export_submissions.sql > submissions.tsv
python process_submissions.py submissions.tsv
"""

from argparse import ArgumentParser
from contextlib import contextmanager
from csv import DictReader
import logging

from flask import Flask

import events
from events.domain.submission import Submission
from events.services import classic

from events.exceptions import InvalidStack

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

def process_csv(tsvfile, session):
    """
    Process a tsvfile using DictReader so any order of files will be possible.
    """
    with open(tsvfile) as tsvfh:
        reader = DictReader(tsvfh, delimiter='\t')
        for submission in reader:
            try:
                submission_id = process_submission(submission)
                verify_submission(submission, submission_id)
            except (AssertionError, InvalidStack) as e:
                logging.error('{}: {}'.format(submission['submission_id'], e))


def process_submission(s):
    """
    Process a submission using a tsvfile
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
    else:
        submission, stack = events.save(
            events.AssertAuthorship(
                creator=submitter,
                submitter_is_author=False
            ),
            submission_id=submission.submission_id
        )

    if s.get('agree_policy') == '1':
        submission, stack = events.save(
            events.AcceptPolicy(creator=submitter),
            submission_id=submission.submission_id
        )

    if s.get('userinfo') == '1':
        submission, stack = events.save(
            events.VerifyContactInformation(creator=submitter),
            submission_id=submission.submission_id
        )

    submission, stack = events.save(
        events.UpdateAuthors(
            authors_display=s['authors'],
            creator=submitter
        ),
        events.UpdateMetadata(
            creator=submitter,
            metadata=metadata
        ),
        events.SetPrimaryClassification(
            creator=submitter,
            category=s['category']
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

    if s.get('package'):
        submission, stack = events.save(
            events.AttachSourceContent(
                location='https://example.arxiv.org/' + s['package'],
                format=s['source_format'],
                checksum='0',
                identifier=1,
                creator=submitter
            ),
            submission_id=submission.submission_id
        )

    if s.get('status') != '0':
        submission, stack = events.save(
            events.FinalizeSubmission(
                creator=submitter
            ),
            submission_id=submission.submission_id
        )

    return submission.submission_id


    # If it goes to the end, then verify that results come in
    # events.load() returns a submission object, then verify it looks as expected

def verify_submission(s, submission_id):
    submission, stack = events.load(submission_id)

    assert submission.metadata.title == s['title']
    assert submission.metadata.abstract == s['abstract']
    assert submission.metadata.comments == s['comments']
    assert submission.metadata.report_num == s['report_num']
    assert submission.metadata.doi == s['doi']
    assert submission.metadata.journal_ref == s['journal_ref']
    
    if s.get('agree_policy') == '1':
        assert submission.submitter_accepts_policy, "AcceptPolicy Error"
    else:
        assert not submission.submitter_accepts_policy

    if s.get('license'):
        assert submission.license.uri == s['license']

    if s.get('is_author') == '1':
        assert submission.submitter_is_author, "AssertAuthorship not aligned: returns False, should be True"
    else:
        assert not submission.submitter_is_author, "AssertAuthorship does not match: returns True, should be False"

    if s.get('status') != '0':
        assert submission.status == Submission.SUBMITTED
    else:
        assert submission.status == Submission.WORKING

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('tsvfile', help='TSV file')
    args = parser.parse_args()

    with in_memory_db() as session:
        process_csv(args.tsvfile, session)
