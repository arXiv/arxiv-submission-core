




Submission & moderation service: components
===========================================

The submission and moderation service implements an event-centric data
architecture. All changes to the content of a submission or its annotations
are commemorated as events, which fully describe the data transformation. Those
events are used as an administrative log, and as hooks for automated policies
and processes. Data events are also emitted by the submission and moderation
service as system notifications that can be consumed and acted upon by
other services and system components.

Datastore (service)
-------------------
The submission & moderation service relies on a relational database to store
and query events, submissions, and annotations. In early phases of the classic
renewal process, this will be the classic MySQL database running in the CULIT
datacenter. Upon migration to the cloud, this will be replaced; likely with
a PostgresQL database running in AWS RDS.

A database service module provides an internal persistence API for events and
other data objects.

External submission API (routes & controllers)
----------------------------------------------
A protected external submission API provides entry-points for bulk deposit by
third parties (existing users of the `arXiv SWORDv1 API
<https://arxiv.org/help/submit_sword>`_), and for client applications that
facilitate direct submission on behalf of authors.

This API may be SWORDv3-compliant. Version 3 of the Simple Web-service Offering
Repository Deposit (SWORD) protocol is currently under development, and

Backend API (routes & controllers)
----------------------------------
The backend API for the submission service provides endpoints for internal
services (e.g. the submission & moderation agent) to update submissions based
on activities in other parts of the submission system. For example, this API
is used to generate proposals for reclassification based on results obtained
from the document classifier service.

User interfaces (routes & controllers)
--------------------------------------
The submission user interface is comprised of form-based views that allow users
to create and update submissions, and track the state of their submission
through the moderation and publication process. The interface supports metadata
entry, source package upload, and integrates with the :ref:`build service
<build-service>` to assist the submitter in preparing a publication-ready
submission package.

The moderation user interface is a single-page client-side application, backed
by purpose-built APIs, that allows moderators to flag, comment, and propose
reclassification of/on submissions. Moderators are able to view and curate
submissions based on their moderation domain.

The administrator interfaces provides visibility onto all parts of the
submission service, including the state and event history of all submissions
and submission annotations in the system. Administrators are able to configure
automated policies and processes, intervene on submission content and metadata,
and act on moderator proposals and comments.


File management service: components
===================================

Uploads
-------
An S3 bucket for submission uploads is proxied by the API gateway.

Uploads must be identified by their submission UUID. Subsequent uploads
for the same submission UUID will overwrite previous uploads.

Uploads to that bucket automatically trigger an Upload event propagated by the
notification broker. That event is primarily consumed by a sanitization agent
that retrieves, inspects, and (if necessary) modifies the contents of the
submission before storing it in the submission file store (an EBS volume).
Since uploads are identified by their submission UUIDs, the successful
sanitization is also commemorated by an event notification, which is in turn
consumed by the submission agent.

To support a seamless experience for browser-based submissions, the client-side
app provided by the submission interface should use an AJAX request to
POST uploads directly to the API gateway endpoint. This cuts down on shuffling
large payloads across the network unnecessarily.

Build service: components
=========================

Plain text extraction service: components
=========================================


Overlap detection service: components
=====================================

Classifier service: components
==============================

Notification service: components
================================
