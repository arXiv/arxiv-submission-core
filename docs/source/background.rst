Background
**********

This section summarizes some of the drivers that contributed to the design
of the NG submission system.

Separation of concerns
======================
In the classic arXiv submission system, there is tight coupling between the
submission and a variety of related objects and processes. For example,
processes like TeX compilation, auto-classification, etc are integrated with
web controllers for the submission UI. A major benefit of this approach is that
it keeps operations close together in the submission workflow. A major drawback
is its relative inflexibility: developing any one component of the submission
system risks generating cascading effects to other components, and assumptions
about the implementation details of components are baked into the system.

One of the major shifts in the NG reimplementation of the submission system is
to pull some of those components apart into self-contained services with
clearly-defined APIs. Our goal is to limit coupling to where it really matters,
and open the door to exchangeability of those components. This should make it
easier to develop individual components without breaking the whole system, and
also make it easier to respond to changing operational policies and procedures.

The :ref:`utility-services` section describes some of the backend components
that will be "compartmentalized" as stand-alone services in NG.

Commands (events) as data
=========================
The classic arXiv submission system is built around an object-centric data
model. Submissions are represented objects whose properties map to rows in a
database table, and workflows are implemented by developing web controllers
that mutate those objects (and the underlying rows). In order to support
administrative requirements of visibility onto activity in the submission
system, a log is updated by those controllers whenever they are executed.
Conditional operations are implemented by adding procedures to those
controllers. This model works well for simple systems in which there is a
single point of entry for submission data: each controller is solely
responsible for a command or set of commands, and so coupling between user
request handling/views and the commands themselves (along with conditional
operations linked to those commands) is not problematic.

A requirement of arXiv-NG is to provide consistent support for evolving and
potentially many accession pathways into arXiv. A limitation of the classic
architecture is that it requires new submission interfaces to reimplement the
commands (and rules) that it exposes, and to reimplement updates to the
administrative log. In the NG submission system, commands (and log updates)
are independent of the interface controllers -- this allows for a greater
deal of flexibility when implementing or changing interfaces. We can achieve
this either by implementing a command controller as standalone service that
handles commands from other applications, or by implementing a software package
that exposes commands as an internal API (arXiv-lib could be seen as an
attempt in that direction, although it is somewhat defeated by its broad scope
and leakage of business logic).

Another major requirement of arXiv-NG is to support triggers and automated
processes that can be configured by administrators, in addition to continuing
to support to the administrative log. A step in this direction would be to
include hooks for triggers behind the command API (above), and load parameters
(e.g. set in a database or a configuration file by an admin) that control
whether/how the trigger is executed. This has the potential to not scale well,
however, as the kinds of triggers and automation required must be anticipated
ahead of time and semi-hard-coded into the system. An alternative approach (the
one adopted here) is to define a set of primitives that explicitly represent
commands and rules, and build interfaces that allow them to be combined
arbitrarily to build workflows. In this approach, instances of command
execution (events) themselves are treated as data. This meets the requirements
of maintaining a high-fidelity comprehensive activity log.

A knock-on benefit of treating command execution/events as data is that it
allows for freer evolution of how we represent submission objects. If event
data are treated as the primary source of truth, the representation of the
submission itself can be treated as a secondary and somewhat disposable
projection. In the short term, as we reimplement components of the submission
system, we will need to guarantee that we generate projections in the classic
submission database that satisfy the requirements of legacy components that
have not yet been reimplemented. For example, when implementing a new
submission UI for NG we can collect and store new forms of data about a
submission in the event data (e.g. data used to populate new metadata fields),
but must also ensure that the appropriate tables in the classic database are
kept up-to-date for the sake of the classic moderation system. In the longer
term, projections of event data can be used to support efficient queries, but
do not constrain the evolution of the submission system in other areas.
