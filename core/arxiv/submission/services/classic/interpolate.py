"""
Provides :class:`ClassicEventInterpolator`.

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

from typing import List, Optional, Dict, Tuple
from arxiv.base import logging
from . import models
from ...domain.submission import Submission, UserRequest, WithdrawalRequest, \
    CrossListClassificationRequest
from ...domain.event import Event, SetDOI, SetJournalReference, \
    SetReportNumber, ApplyRequest, RejectRequest, Publish
from ...domain.agent import System, User


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

    @property
    def next_row(self) -> models.Submission:
        """The next classic database row for this submission."""
        return self.db_rows[0]

    def _insert_publish_event(self) -> None:
        """Create and apply a Publish event."""
        logger.debug('insert publish event')
        self._apply_event(Publish(
            creator=SYSTEM,
            created=self.current_row.get_updated(),
            committed=True,
            arxiv_id=self.arxiv_id,
            submission_id=self.submission_id
        ))

    def _insert_request_event(self, rq_class: type, event_class: type) -> None:
        """Create and apply a request-related event."""
        logger.debug('insert request event, %s, %s',
                     rq_class.__name__, event_class.__name__)
        self._apply_event(event_class(
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
        logger.debug('current row preceeds event?')
        return self.current_row.get_updated() < event.created

    def _should_apply_current_row(self, event: Event) -> bool:
        logger.debug('should apply current row?')
        return self.current_row \
            and self._current_row_preceeds_event(event) \
            and self.current_row.is_published()

    def _should_advance_to_next_row(self, event: Event) -> bool:
        logger.debug('should advance to next row?')
        return self._there_are_rows_remaining() \
            and self.next_row.get_created() <= event.created

    def _there_are_rows_remaining(self) -> bool:
        logger.debug('are there rows remaining? %s', len(self.db_rows) > 0)
        return len(self.db_rows) > 0

    def _advance_to_next_row(self) -> None:
        logger.debug('advance to next row')
        self.current_row = self.db_rows.pop(0)

    def _can_patch_from_current_row(self) -> bool:
        logger.debug('can we patch from the current row?')
        return self.current_row.version == 1 \
            or not self.current_row.is_deleted()

    def _apply_current_row(self) -> None:
        logger.debug('apply the current row')
        if self.current_row.status != models.Submission.PROCESSING_SUBMISSION \
                and (self.current_row.is_crosslist()
                     or self.current_row.is_withdrawal()):
            self._insert_request_event(
                (CrossListClassificationRequest
                 if self.current_row.is_crosslist()
                 else WithdrawalRequest),
                (RejectRequest
                 if self.current_row.is_rejected()
                 else ApplyRequest)
            )
        elif self.current_row.is_new_version():
            self._insert_publish_event()

    def _should_backport_event(self, event: Event) -> bool:
        logger.debug('should we backport this event? %s', event.NAME)
        return type(event) in [SetDOI, SetJournalReference, SetReportNumber] \
            and self.submission.versions \
            and self.submission.version == self.submission.versions[-1].version

    def _patch_from_current_row(self) -> None:
        logger.debug('patch from the current row: %s, %s, %s',
                     self.current_row.submission_id,
                     self.current_row.type, self.current_row.status)
        self.submission = self.current_row.patch(self.submission)
        logger.debug('user requests: %s', self.submission.user_requests)

    def _apply_event(self, event: Event) -> None:
        logger.debug('apply event %s', event.NAME)
        self.submission = event.apply(self.submission)
        self.applied_events.append(event)

    def _backport_event(self, event: Event) -> None:
        logger.debug('backport event %s', event.NAME)
        self.submission.versions[-1] = \
            event.apply(self.submission.versions[-1])

    def _should_apply_current_row_at_the_end(self) -> bool:
        return (self.current_row.is_published()
                or (self.current_row.is_withdrawal()
                    and not self.current_row.is_deleted())
                or (self.current_row.is_crosslist()
                    and not self.current_row.is_deleted()))

    def get_submission_state(self) -> Tuple[Submission, List[Event]]:
        """
        Get the current state of the :class:`Submission`.

        This is effectively memoized.

        Returns
        -------
        :class:`.Submission`
            The most recent state of the submission given the provided events
            and database rows.
        list
            Items are :class:`.Event` instances applied to generate the
            returned state. This may include events inferred and interpolated
            from the classic database, not passed in the original set of
            events.

        """
        for event in self.events:
            # If the classic submission row is published, we want to insert a
            # Publish event in the appropriate spot in the event stack.
            if self._should_apply_current_row(event):
                self._apply_current_row()

            # As we go, look for moments where a new row in the legacy
            # submission table was created.
            if self._should_advance_to_next_row(event):
                # If we find one, patch the domain submission from the
                # preceding row, and load the next row. We want to do this
                # before projecting the event, since we are inferring that the
                # event occurred after a change was made via the legacy system.
                if self._can_patch_from_current_row():
                    self._patch_from_current_row()
                self._advance_to_next_row()

            self._apply_event(event)    # Now project the event.

            # Backport JREFs to the published version to which they apply.
            if self._should_backport_event(event):
                self._backport_event(event)

        # Finally, patch the submission with any remaining changes that may
        # have occurred via the legacy system.
        while self.current_row is not None:
            if self._can_patch_from_current_row():
                self._patch_from_current_row()
                if self._should_apply_current_row_at_the_end():
                    self._apply_current_row()
            if self._there_are_rows_remaining():
                self._advance_to_next_row()
            else:
                self.current_row = None
        return self.submission, self.applied_events
