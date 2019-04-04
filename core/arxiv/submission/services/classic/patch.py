"""Methods for updating :class:`.Submission` with state outside event scope."""

from typing import List, Dict, Any
from ... import domain
from . import models


def patch_hold(submission: domain.Submission,
               row: models.Submission) -> domain.Submission:
    """Patch hold-related data from this database row."""
    if not row.is_new_version():
        raise ValueError('Only applies to new and replacement rows')

    if row.status == row.ON_HOLD:
        created = row.get_updated()
        creator = domain.agent.System(__name__)
        event_id = domain.Event.get_id(created, 'AddHold', creator)
        hold = domain.Hold(event_id=event_id, creator=creator,
                           created=created,
                           hold_type=domain.Hold.Type.PATCH)
        submission.holds[event_id] = hold
    return submission


def patch_jref(submission: domain.Submission,
               row: models.Submission) -> domain.Submission:
    """
    Patch a :class:`.domain.submission.Submission` with JREF data outside the event scope.

    Parameters
    ----------
    submission : :class:`.domain.submission.Submission`
        The submission object to patch.

    Returns
    -------
    :class:`.domain.submission.Submission`
        The same submission that was passed; now patched with JREF data
        outside the scope of the event model.

    """
    submission.metadata.doi = row.doi
    submission.metadata.journal_ref = row.journal_ref
    submission.metadata.report_num = row.report_num
    return submission


# This should update the reason_for_withdrawal (if applied),
# and add a WithdrawalRequest to user_requests.
def patch_withdrawal(submission: domain.Submission, row: models.Submission,
                     request_number: int = -1) -> domain.Submission:
    req_type = domain.WithdrawalRequest
    data = {'reason_for_withdrawal': row.get_withdrawal_reason()}
    return _patch_request(req_type, data, submission, row, request_number)


def patch_cross(submission: domain.Submission, row: models.Submission,
                request_number: int = -1) -> domain.Submission:
    req_type = domain.CrossListClassificationRequest
    clsns = [domain.Classification(dbc.category) for dbc in row.categories
             if not dbc.is_primary
             and dbc.category not in submission.secondary_categories]
    data = {'classifications': clsns}
    return _patch_request(req_type, data, submission, row, request_number)


def _patch_request(req_type: type, data: Dict[str, Any],
                   submission: domain.Submission, row: models.Submission,
                   request_number: int = -1) -> domain.Submission:
    status = req_type.PENDING   # Will be pending if on hold, too.
    if row.is_announced():
        status = req_type.APPLIED
    elif row.is_deleted():
        status = req_type.CANCELLED
    elif row.is_rejected():
        status = req_type.REJECTED
    data.update({'status': status})
    request_id = req_type.generate_request_id(submission, request_number)

    if request_number < 0:
        creator = domain.User(native_id=row.submitter_id,
                              email=row.submitter_email)
        user_request = req_type(creator=creator, created=row.get_created(),
                                updated=row.get_updated(),
                                request_id=request_id, **data)
    else:
        user_request = submission.user_requests[request_id]
        if any([setattr_changed(user_request, field, value)
                for field, value in data.items()]):
            user_request.updated = row.get_updated()
    submission.user_requests[request_id] = user_request

    if status == req_type.APPLIED:
        submission = user_request.apply(submission)
    return submission


def setattr_changed(obj: Any, field: str, value: Any) -> bool:
    """
    Set an attribute on an object only if the value does not match provided.

    Parameters
    ----------
    obj : object
    field : str
        The name of the attribute on ``obj`` to set.
    value : object

    Returns
    -------
    bool
        True if the attribute was set; otherwise False.

    """
    if getattr(obj, field) != value:
        setattr(obj, field, value)
        return True
    return False
