"""Integration with classic proposals."""

from . import models, util, log
from ... import domain
from ...domain.event import Event, SetPrimaryClassification, \
    AddSecondaryClassification, AddProposal
from ...domain.submission import Submission


def add(event: AddProposal, before: Submission, after: Submission) -> None:
    """
    Add a category proposal to the database.

    The objective here is simply to create a new proposal entry in the classic
    database when an :class:`domain.event.AddProposal` event is stored.

    Parameters
    ----------
    event : :class:`event.Event`
        The event being committed.
    before : :class:`.Submission`
        State of the submission before the event.
    after : :class:`.Submission`
        State of the submission after the event.

    """
    supported = [SetPrimaryClassification, AddSecondaryClassification]
    if event.proposed_event_type not in supported:
        return

    category = event.proposed_event_data['category']
    is_primary = event.proposed_event_type is SetPrimaryClassification
    with util.transaction() as session:
        comment = None
        if event.comment:
            comment = log.admin_log(__name__, 'admin comment', event.comment,
                                    username=event.creator.username,
                                    hostname=event.creator.hostname,
                                    submission_id=after.submission_id)

        session.add(
            models.CategoryProposal(
                submission_id=after.submission_id,
                category=category,
                is_primary=int(is_primary),
                user_id=event.creator.native_id,
                updated=event.created,
                proposal_status=models.CategoryProposal.UNRESOLVED,
                proposal_comment=comment
            )
        )
