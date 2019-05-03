"""Supports loading :class:`.Submission` directly from classic data."""

from typing import List, Optional
import copy
from itertools import groupby

from arxiv.license import LICENSES
from arxiv.base import logging

from ... import domain
from . import models
from .patch import patch_withdrawal, patch_jref, patch_cross, patch_hold

logger = logging.getLogger(__name__)
logger.propagate = False


def load(rows: List[models.Submission]) -> domain.Submission:
    """Load a submission entirely from its classic database rows."""
    versions: List[domain.Submission] = []
    submission_id: Optional[str] = None

    # We want to work within versions, and (secondarily) in order of creation
    # time.
    rows = sorted(rows, key=lambda o: o.version)
    logger.debug('Load from rows %s', [r.submission_id for r in rows])
    for version, version_rows in groupby(rows, key=lambda o: o.version):
        # Creation time isn't all that precise in the classic database, so
        # we'll use submission ID instead.
        version_rows = sorted([v for v in version_rows],
                              key=lambda o: o.submission_id)
        logger.debug('Version %s: %s', version, version_rows)
        # We use the original ID to track the entire lifecycle of the
        # submission in NG.
        if version == 1:
            submission_id = version_rows[0].submission_id
            logger.debug('Submission ID: %s', submission_id)

        # Find the creation row. There may be some false starts that have been
        # deleted, so we need to advance to the first non-deleted 'new' or
        # 'replacement' row.
        version_submission: Optional[domain.Submission] = None
        while version_submission is None:
            try:
                row = version_rows.pop(0)
            except IndexError:
                break
            if row.is_new_version() and \
                    (row.type == row.NEW_SUBMISSION or not row.is_deleted()):
                # Get the initial state of the version.
                version_submission = to_submission(row, submission_id)
                logger.debug('Got initial state: %s', version_submission)

        if version_submission is None:
            logger.debug('Nothing to work with for this version')
            continue

        # If this is not the first version, carry forward any requests.
        if len(versions) > 0:
            logger.debug('Bring user_requests forward from last version')
            version_submission.user_requests.update(versions[-1].user_requests)

        for row in version_rows:  # Remaining rows, since we popped the others.
            logger.debug('Handle subsequent row: %s', row)
            # We are treating JREF submissions as though there is no approval
            # process; so we can just ignore deleted JREF rows.
            if row.is_jref() and not row.is_deleted():
                logger.debug('JREF row')
                # This should update doi, journal_ref, report_num.
                version_submission = patch_jref(version_submission, row)
            # For withdrawals and cross-lists, we want to get data from
            # deleted rows since we keep track of all requests in the NG
            # submission.
            elif row.is_withdrawal():
                logger.debug('Withdrawal row')
                # This should update the reason_for_withdrawal (if applied),
                # and add a WithdrawalRequest to user_requests.
                version_submission = patch_withdrawal(version_submission, row)
            elif row.is_crosslist():
                logger.debug('Crosslist row')
                # This should update the secondary classifications (if applied)
                # and add a CrossListClassificationRequest to user_requests.
                version_submission = patch_cross(version_submission, row)

            # We want hold information represented as a Hold on the submission
            # object, not just the status.
            if version_submission.is_on_hold:
                version_submission = patch_hold(version_submission, row)
        versions.append(version_submission)
    submission = copy.deepcopy(versions[-1])
    submission.versions = [ver for ver in versions if ver and ver.announced]
    return submission


def to_submission(row: models.Submission,
                  submission_id: Optional[int] = None) -> domain.Submission:
    """
    Generate a representation of submission state from a DB instance.

    Parameters
    ----------
    row : :class:`.models.Submission`
        Database row representing a :class:`.domain.submission.Submission`.
    submission_id : int or None
        If provided the database value is overridden when setting
        :attr:`domain.Submission.submission_id`.

    Returns
    -------
    :class:`.domain.submission.Submission`

    """
    status = status_from_classic(row.status)
    primary = row.primary_classification
    if row.submitter is None:
        submitter = domain.User(native_id=row.submitter_id,
                                email=row.submitter_email)
    else:
        submitter = row.get_submitter()
    if submission_id is None:
        submission_id = row.submission_id

    license: Optional[domain.License] = None
    if row.license:
        label = LICENSES[row.license]['label']
        license = domain.License(uri=row.license, name=label)

    primary_clsn: Optional[domain.Classification] = None
    if primary and primary.category:
        primary_clsn = domain.Classification(category=primary.category)
    secondary_clsn = [domain.Classification(category=db_cat.category)
                      for db_cat in row.categories if not db_cat.is_primary]

    content: Optional[domain.SubmissionContent] = None
    if row.package:
        if row.package.startswith('fm://'):
            identifier, checksum = row.package.split('://', 1)[1].split('@', 1)
        else:
            identifier = row.package
        source_format = domain.SubmissionContent.Format(row.source_format)
        content = domain.SubmissionContent(identifier=identifier,
                                           compressed_size=0,
                                           uncompressed_size=row.source_size,
                                           checksum=checksum,
                                           source_format=source_format)

    submission = domain.Submission(
        submission_id=submission_id,
        creator=submitter,
        owner=submitter,
        status=status,
        created=row.get_created(),
        updated=row.get_updated(),
        source_content=content,
        submitter_is_author=bool(row.is_author),
        submitter_accepts_policy=bool(row.agree_policy),
        submitter_contact_verified=bool(row.userinfo),
        submitter_compiled_preview=not bool(row.must_process),
        submitter_confirmed_preview=bool(row.viewed),
        metadata=domain.SubmissionMetadata(title=row.title,
                                           abstract=row.abstract,
                                           comments=row.comments,
                                           report_num=row.report_num,
                                           doi=row.doi,
                                           msc_class=row.msc_class,
                                           acm_class=row.acm_class,
                                           journal_ref=row.journal_ref),
        license=license,
        primary_classification=primary_clsn,
        secondary_classification=secondary_clsn,
        arxiv_id=row.doc_paper_id,
        version=row.version
    )
    if row.sticky_status == row.ON_HOLD or row.status == row.ON_HOLD:
        submission = patch_hold(submission, row)
    elif row.is_withdrawal():
        submission = patch_withdrawal(submission, row)
    elif row.is_crosslist():
        submission = patch_cross(submission, row)
    return submission


def status_from_classic(classic_status: str) -> str:
    """Map classic status codes to domain submission status."""
    return STATUS_MAP.get(classic_status)


# Map classic status to Submission domain status.
STATUS_MAP = {
    models.Submission.NOT_SUBMITTED: domain.Submission.WORKING,
    models.Submission.SUBMITTED: domain.Submission.SUBMITTED,
    models.Submission.ON_HOLD: domain.Submission.SUBMITTED,
    models.Submission.NEXT_PUBLISH_DAY: domain.Submission.SCHEDULED,
    models.Submission.PROCESSING: domain.Submission.SCHEDULED,
    models.Submission.PROCESSING_SUBMISSION: domain.Submission.SCHEDULED,
    models.Submission.NEEDS_EMAIL: domain.Submission.SCHEDULED,
    models.Submission.ANNOUNCED: domain.Submission.ANNOUNCED,
    models.Submission.DELETED_ANNOUNCED: domain.Submission.ANNOUNCED,
    models.Submission.USER_DELETED:  domain.Submission.DELETED,
    models.Submission.DELETED_EXPIRED: domain.Submission.DELETED,
    models.Submission.DELETED_ON_HOLD: domain.Submission.DELETED,
    models.Submission.DELETED_PROCESSING: domain.Submission.DELETED,
    models.Submission.DELETED_REMOVED: domain.Submission.DELETED,
    models.Submission.DELETED_USER_EXPIRED:  domain.Submission.DELETED,
    models.Submission.ERROR_STATE: domain.Submission.ERROR
}
