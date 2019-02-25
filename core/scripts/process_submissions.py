"""
Script to validate the events model using classic db submissiions.

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

from arxiv.submission import save, domain, CreateSubmission, ConfirmAuthorship,\
    ConfirmContactInformation, ConfirmPolicy, SetTitle, SetAbstract, \
    SetComments, SetDOI, SetReportNumber, SetJournalReference, \
    SetUploadPackage, SetLicense, SetPrimaryClassification, \
    AddSecondaryClassification, SetAuthors, FinalizeSubmission, load

from arxiv.submission.domain.submission import Submission
from arxiv.submission.services import classic

from arxiv.submission.exceptions import InvalidStack, InvalidEvent

INVALID_STATUSES = ['0', '20', '29', '30']


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
    """Process a tsvfile using DictReader."""
    with open(tsvfile) as tsvfh:
        reader = DictReader(tsvfh, delimiter='\t')
        for submission in reader:
            for key, value in submission.items():
                if value == 'NULL':
                    submission[key] = None
            if int(submission['event_version']) > 1:
                continue
            try:
                submission_id = process_submission(submission)
                verify_submission(submission, submission_id)
            except (InvalidStack, InvalidEvent) as e:
                logging.error('{}: {}'.format(submission['submission_id'], e))


def process_submission(s):
    """Process a submission from a tsvfile row."""
    # TODO: Make sure forename surname separation are better
    try:
        forename, surname = s['submitter_name'].rsplit(maxsplit=1)
    except ValueError:
        forename = ''
        surname = s['submitter_name']
    submitter = domain.User(s['submitter_id'], email=s['submitter_email'],
                            forename=forename, surname=surname,
                            endorsements=[s['category']])

    metadata = dict([
        ('title', s['title']),
        ('abstract', s['abstract']),
        ('comments', s['comments']),
        ('report_num', s['report_num']),
        ('doi', s['doi']),
        ('journal_ref', s['journal_ref'])
    ])

    submission, stack = save(
        CreateSubmission(creator=submitter)
    )

    if s.get('is_author') == '1':
        submission, stack = save(
            ConfirmAuthorship(
                creator=submitter,
                submitter_is_author=True
            ),
            submission_id=submission.submission_id
        )
    else:
        submission, stack = save(
            ConfirmAuthorship(
                creator=submitter,
                submitter_is_author=False
            ),
            submission_id=submission.submission_id
        )

    if s.get('agree_policy') == '1':
        submission, stack = save(
            ConfirmPolicy(creator=submitter),
            submission_id=submission.submission_id
        )

    if s.get('userinfo') == '1':
        submission, stack = save(
            ConfirmContactInformation(creator=submitter),
            submission_id=submission.submission_id
        )

    submission, stack = save(
        SetAuthors(
            authors_display=s['authors'],
            creator=submitter
        ),
        SetPrimaryClassification(creator=submitter, category=s['category']),
        submission_id=submission.submission_id
    )
    if s['title']:
        submission, stack = save(
            SetTitle(creator=submitter, title=metadata['title']),
            submission_id=submission.submission_id
        )
    if s['abstract']:
        submission, stack = save(
            SetAbstract(creator=submitter, abstract=metadata['abstract']),
            submission_id=submission.submission_id
        )
    if metadata['comments']:
        submission, stack = save(
            SetComments(creator=submitter, comments=metadata['comments']),
            submission_id=submission.submission_id
        )

    if metadata['journal_ref']:
        submission, stack = save(
            SetJournalReference(creator=submitter,
                                journal_ref=metadata['journal_ref']),
            submission_id=submission.submission_id
        )

    if metadata['doi']:
        submission, stack = save(
            SetDOI(creator=submitter, doi=metadata['doi']),
            submission_id=submission.submission_id
        )

    if metadata['report_num']:
        submission, stack = save(
            SetReportNumber(creator=submitter,
                            report_num=metadata['report_num']),
            submission_id=submission.submission_id
        )

    # Parse the license
    license_uri = s.get('license')
    if license_uri:
        submission, stack = save(
            SetLicense(creator=submitter, license_uri=license_uri),
            submission_id=submission.submission_id
        )

    if s.get('package'):
        submission, stack = save(
            SetUploadPackage(
                format=s['source_format'],
                checksum='0',
                identifier=1,
                creator=submitter
            ),
            submission_id=submission.submission_id
        )

    if s.get('status') not in INVALID_STATUSES:
        submission, stack = save(
            FinalizeSubmission(creator=submitter),
            submission_id=submission.submission_id
        )

    return submission.submission_id

    # If it goes to the end, then verify that results come in
    # load() returns a submission object, then verify it looks as expected

def verify_submission(s, submission_id):
    """Validate event database storage of classic db import data."""
    submission, stack = load(submission_id)

    if s['title']:
        assert submission.metadata.title == SetTitle.cleanup(s['title'])
    if s['abstract']:
        assert submission.metadata.abstract == SetAbstract.cleanup(s['abstract'])
    if s['comments']:
        assert submission.metadata.comments == SetComments.cleanup(s['comments'])
    if s['report_num']:
        assert submission.metadata.report_num == SetReportNumber.cleanup(s['report_num'])
    if s['doi']:
        assert submission.metadata.doi == SetDOI.cleanup(s['doi'])
    if s['journal_ref']:
        assert submission.metadata.journal_ref == SetJournalReference.cleanup(s['journal_ref'])

    if s.get('userinfo') == '1':
        assert submission.submitter_contact_verified, \
            "ConfirmContactInformationError"
    else:
        assert not submission.submitter_contact_verified

    if s.get('agree_policy') == '1':
        assert submission.submitter_accepts_policy, "ConfirmPolicy Error"
    else:
        assert not submission.submitter_accepts_policy

    if s.get('license'):
        assert submission.license.uri == s['license']

    if s.get('is_author') == '1':
        assert submission.submitter_is_author, \
            "ConfirmAuthorship not aligned: returns False, should be True"
    else:
        assert not submission.submitter_is_author, \
            "ConfirmAuthorship does not match: returns True, should be False"

    if s.get('status') not in INVALID_STATUSES:
        assert submission.status == Submission.SUBMITTED
    else:
        assert submission.status == Submission.WORKING


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('tsvfile', help='TSV file')
    args = parser.parse_args()

    with in_memory_db() as session:
        process_csv(args.tsvfile, session)
