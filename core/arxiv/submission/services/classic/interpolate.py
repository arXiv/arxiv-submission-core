"""
Inject events from outside the scope of the NG submission system.

A core concept of the :mod:`arxiv.submission.domain.event` model is that
the state of a submission can be obtained by playing forward all of the
commands/events applied to it. That works when all agents that operate
on submission state are generating commands. The problem that we face in
the short term is that some operations will be performed by legacy components
that don't generate command/event data.

The objective of the :class:`ClassicEventInterpolator` is to reconcile
NG events/commands with aspects of the classic database that are outside its
current purview. The logic in this module will need to change as the scope
of the NG submission data architecture expands.
"""

from typing import List, Optional, Dict, Tuple, Any
from datetime import datetime

from arxiv.base import logging
from arxiv import taxonomy
from . import models
from ...domain.submission import Submission, UserRequest, WithdrawalRequest, \
    CrossListClassificationRequest, Hold
from ...domain.event import Event, SetDOI, SetJournalReference, \
    SetReportNumber, ApplyRequest, RejectRequest, Announce, AddHold, \
    CancelRequest, SetPrimaryClassification, AddSecondaryClassification, \
    SetTitle, SetAbstract, SetComments, SetMSCClassification, \
    SetACMClassification, SetAuthors, Reclassify, ConfirmCompiledPreview

from ...domain.agent import System, User
from .load import status_from_classic


logger = logging.getLogger(__name__)
logger.propagate = False
SYSTEM = System(__name__)


class ClassicEventInterpolator:
    """Interleaves events with classic data to get the current state."""

    def __init__(self, current_row: models.Submission,
                 subsequent_rows: List[models.Submission],
                 events: List[Event]) -> None:
        """Interleave events with classic data to get the current state."""
        self.applied_events: List[Event] = []
        self.current_row = current_row
        self.db_rows = subsequent_rows
        logger.debug("start with current row: %s", self.current_row)
        logger.debug("start with subsequent rows: %s",
                     [(d.type, d.status) for d in self.db_rows])
        self.events = events
        self.submission_id = current_row.submission_id
        # We always start from the beginning (no submission).
        self.submission: Optional[Submission] = None
        self.arxiv_id = self.current_row.get_arxiv_id()

        self.requests = {
            WithdrawalRequest: 0,
            CrossListClassificationRequest: 0
        }

    @property
    def next_row(self) -> models.Submission:
        """Access the next classic database row for this submission."""
        return self.db_rows[0]

    def _insert_request_event(self, rq_class: type, event_class: type) -> None:
        """Create and apply a request-related event."""
        logger.debug('insert request event, %s, %s',
                     rq_class.__name__, event_class.__name__)
        self._inject(event_class(
            creator=SYSTEM,
            created=self.current_row.get_updated(),
            committed=True,
            request_id=rq_class.generate_request_id(
                self.current_row.get_created(),
                rq_class.__name__,
                self.current_row.get_submitter()
            )
        ))

    def _current_row_preceeds_event(self, event: Event) -> bool:
        delta = self.current_row.get_updated() - event.created
        # Classic lacks millisecond precision.
        return (delta).total_seconds() < -1

    def _should_apply_current_row(self, event: Event) -> bool:
        return self.current_row \
            and self._current_row_preceeds_event(event) \
            and self.current_row.is_announced()

    def _should_advance_to_next_row(self, event: Event) -> bool:
        return self._there_are_rows_remaining() \
            and self.next_row.get_created() <= event.created

    def _there_are_rows_remaining(self) -> bool:
        return len(self.db_rows) > 0

    def _advance_to_next_row(self) -> None:
        if self.current_row.is_withdrawal():
            self.requests[WithdrawalRequest] += 1
        if self.current_row.is_crosslist():
            self.requests[CrossListClassificationRequest] += 1
        try:
            self.current_row = self.db_rows.pop(0)
        except IndexError:
            self.current_row = None

    def _can_inject_from_current_row(self) -> bool:
        return (self.current_row.version == 1
                or (self.current_row.is_jref()
                    and not self.current_row.is_deleted())
                or self.current_row.is_withdrawal()
                or self.current_row.is_crosslist()
                or (self.current_row.is_new_version()
                    and not self.current_row.is_deleted()))

    def _should_backport(self, event: Event) -> bool:
        """Evaluate if this event be applied to the last announced version."""
        return type(event) in [SetDOI, SetJournalReference, SetReportNumber] \
            and self.submission.versions \
            and self.submission.version == self.submission.versions[-1].version

    def _inject_from_current_row(self) -> None:
        if self.current_row.is_new_version():
            # Apply any holds created in the admin or moderation system.
            if self.current_row.status == models.Submission.ON_HOLD:
                self._inject(AddHold, hold_type=Hold.Type.PATCH)

            # TODO: these need some explicit event/command representations.
            elif status_from_classic(self.current_row.status) \
                    == Submission.SCHEDULED:
                self.submission.status = Submission.SCHEDULED
            elif status_from_classic(self.current_row.status) \
                    == Submission.DELETED:
                self.submission.status = Submission.DELETED
            elif status_from_classic(self.current_row.status) \
                    == Submission.ERROR:
                self.submission.status = Submission.ERROR

            self._inject_primary_if_changed()
            self._inject_secondaries_if_changed()
            self._inject_metadata_if_changed()
            self._inject_jref_if_changed()

            if self.current_row.must_process == 0:
                self._inject(ConfirmCompiledPreview)

            if self.current_row.is_announced():
                self._inject(Announce, arxiv_id=self.arxiv_id)
        elif self.current_row.is_jref():
            self._inject_jref_if_changed()
        elif self.current_row.is_withdrawal():
            self._inject_request_if_changed(WithdrawalRequest)
        elif self.current_row.is_crosslist():
            self._inject_request_if_changed(CrossListClassificationRequest)

    def _inject_primary_if_changed(self) -> None:
        """Inject primary classification event if a change has occurred."""
        primary = self.current_row.primary_classification
        if primary and primary.category != self.submission.primary_category:
            self._inject(Reclassify, category=primary.category)

    def _inject_secondaries_if_changed(self) -> None:
        """Inject secondary classification events if a change has occurred."""
        # Add any missing secondaries.
        for dbc in self.current_row.categories:
            if dbc.category not in self.submission.secondary_categories \
                    and not dbc.is_primary:
                self._inject(AddSecondaryClassification,
                             category=taxonomy.Category(dbc.category))

    def _inject_metadata_if_changed(self) -> None:
        row = self.current_row  # For readability, below.
        if self.submission.metadata.title != row.title:
            self._inject(SetTitle, title=row.title)
        if self.submission.metadata.abstract != row.abstract:
            self._inject(SetAbstract, abstract=row.abstract)
        if self.submission.metadata.comments != row.comments:
            self._inject(SetComments, comments=row.comments)
        if self.submission.metadata.msc_class != row.msc_class:
            self._inject(SetMSCClassification, msc_class=row.msc_class)
        if self.submission.metadata.acm_class != row.acm_class:
            self._inject(SetACMClassification, acm_class=row.acm_class)
        if self.submission.metadata.authors_display != row.authors:
            self._inject(SetAuthors, authors_display=row.authors)

    def _inject_jref_if_changed(self) -> None:
        row = self.current_row  # For readability, below.
        if self.submission.metadata.doi != self.current_row.doi:
            self._inject(SetDOI, doi=row.doi)
        if self.submission.metadata.journal_ref != row.journal_ref:
            self._inject(SetJournalReference, journal_ref=row.journal_ref)
        if self.submission.metadata.report_num != row.report_num:
            self._inject(SetReportNumber, report_num=row.report_num)

    def _inject_request_if_changed(self, req_type: type) -> None:
        """
        Update a request on the submission, if status changed.

        We will assume that the request itself originated in the NG system,
        so we will NOT create a new request.
        """
        request_id = req_type.generate_request_id(self.submission,
                                                  self.requests[req_type])
        if self.current_row.is_announced():
            self._inject(ApplyRequest, request_id=request_id)
        elif self.current_row.is_deleted():
            self._inject(CancelRequest, request_id=request_id)
        elif self.current_row.is_rejected():
            self._inject(RejectRequest, request_id=request_id)

    def _inject(self, event_type: type, **data: Dict[str, Any]) -> None:
        created = self.current_row.get_updated()
        logger.debug('inject %s', event_type.NAME)
        self._apply(event_type(creator=SYSTEM, created=created, committed=True,
                               submission_id=self.submission_id, **data))

    def _apply(self, event: Event) -> None:
        self.submission = event.apply(self.submission)
        self.applied_events.append(event)

    def _backport_event(self, event: Event) -> None:
        logger.debug('backport event %s', event.NAME)
        self.submission.versions[-1] = \
            event.apply(self.submission.versions[-1])

    def get_submission_state(self) -> Tuple[Submission, List[Event]]:
        """
        Get the current state of the :class:`Submission`.

        This is effectively memoized.

        Returns
        -------
        :class:`.domain.submission.Submission`
            The most recent state of the submission given the provided events
            and database rows.
        list
            Items are :class:`.Event` instances applied to generate the
            returned state. This may include events inferred and interpolated
            from the classic database, not passed in the original set of
            events.

        """
        for event in self.events:
            # As we go, look for moments where a new row in the legacy
            # submission table was created.
            if self._current_row_preceeds_event(event) \
                    or self._should_advance_to_next_row(event):
                # If we find one, patch the domain submission from the
                # preceding row, and load the next row. We want to do this
                # before projecting the event, since we are inferring that the
                # event occurred after a change was made via the legacy system.
                if self._can_inject_from_current_row():
                    self._inject_from_current_row()

            if self._should_advance_to_next_row(event):
                self._advance_to_next_row()

            self._apply(event)    # Now project the event.

            # Backport JREFs to the announced version to which they apply.
            if self._should_backport(event):
                self._backport_event(event)

        # Finally, patch the submission with any remaining changes that may
        # have occurred via the legacy system.
        while self.current_row is not None:
            if self._can_inject_from_current_row():
                self._inject_from_current_row()
            self._advance_to_next_row()
        logger.debug('done; submission in state %s with %i events',
                     self.submission.status, len(self.applied_events))
        return self.submission, self.applied_events
