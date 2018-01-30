Submission Events
-----------------

The arXiv-NG submission system treats changes to or actions concerning a
submission as the primary unit of data. Metadata updates, moderation actions,
and procedures applied automatically by the submission system all generate
submission events.

Events are stored in order, describe the transformation that they represent,
and encode the provenance of the event (who generated the event, and when). We
can play these events forward to calculate the current state of a submission,
or a past state.

A complete list of submission event types can be found in :ref:`event-types`.

When a submission event is created, several things occur:

1. All of the recorded events for the submission are loaded from the database,
   and the new event is inserted into that event stack.
2. The event is validated, based on the event's own data and the state of the
   submission.
3. The event may trigger system or moderation rules, which generate additional
   events that are inserted into the event stack.
4. The final state of the submission is calculated from the event stack, and
   the new events and final state are persisted in the database.
5. New events are propagated to other arXiv services via a
   :ref:`notification-broker`.
6. The :ref:`webhook-service` listens for events from the notification broker,
   and propagates them to API clients who have registered a corresponding
   webhook.
