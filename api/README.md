# arXiv Submission API service

The arXiv submission API supports programmatic submission mechanisms for
third-party applications.

## OpenAPI Schema

The [schema/](schema/) directory provides a description of the arXiv submission
API based on the OpenAPI 3.0.0 specification. The root API description is
located at ``schema/openapi.yaml``.

The OpenAPI description refers to [JSON Schema](json-schema.org) documents for
the various resources accepted/exposed by the submission API. Those schemas are
used to validate client requests and responses. **Note that OpenAPI 3 is a
subset of the JSON Schema specification**; we therefore only use keywords that
are supported by OpenAPI. [This
issue](https://github.com/OAI/OpenAPI-Specification/issues/333) provides
extensive background (scroll to the bottom for JSON Schema support in OpenAPI
3).

The OpenAPI and JSON Schema documents should be considered a contract for the
submission service API, and suitable as a basis for implementing clients.

# Submission API: Context

The arXiv submission API provides programmatic access to the arXiv submission
system for API consumers.

## Submission Workflows

### Proxy Submission

Proxy submission is when an API client submits on behalf of an arXiv user who
has explicitly delegated authorization to the client.

A client that wishes to perform proxy submission must have ``auth:3legged`` and
``submit:proxy`` scope, and must implement a secure three-legged OAuth
authorization process.

In proxy submission, the arXiv user who has authorized the client to submit
on their behalf will be the primary owner of the submission. This allows the
user to intervene directly on the submission process later on, and provides
some flexibility to clients who may wish only to partially implement the
submission process.

Note that in the classic arXiv system, "proxy submission" referred to bulk
deposit via the SWORDv1 API.

### Bulk Submission

Bulk submission is when an API client submits directly to arXiv without the
involvement of an arXiv user. Bulk submission may be appropriate for
conference proceedings or other large-volume deposits for which it is
impossible or impracticable to involve individual users.

A client that wishes to perform bulk submission must have a ``submit:bulk``
scope.

In bulk submission, the client is the primary owner of the submission. To
give ownership of the submission to an arXiv user, the client must take
explicit action to transfer ownership.

## Access & Authorization

User of the submission API requires client credentials, which can be obtained
via the arXiv API Client Registry. See ...

### Relevant Scopes
Ensure that your client credentials have been granted the necessary scopes for
your use-case. To request that missing scopes be added to your credentials,
see ...

- ``auth:3legged``: Required for proxy submission.
- ``submit:proxy``: Required for proxy submission.
- ``submit:bulk``: Required for bulk submission.

### Two-legged Authorization
Two-legged authorization grants access to resources for which end-user
involvement is not required. This is suitable for bulk submission, but not
proxy submission. This authorization mechanism involves exchanging your
client id and client secret for an access token.

```bash
$ curl -i -L \
>    -d "client_id=[ your client id ]" \
>    -d "client_secret=[ your client secret ]" \
>    -d "grant_type=client_credentials" \
>    "https://api.arxiv.org/auth/token"
{"access_token":"[ your access token ]","token_type":"bearer",
"refresh_token":"[ your refresh token ]","expires_in":3600}
```

Use your access token in subsequent requests by passing it in the Authorization
header. For example:

```bash
$ curl -i -L \
>    -H "Authorization: [ your access token ]" \
>    "https://api.arxiv.org/submit/"
```

When your access token expires, you can request a new one with:

```bash
$ curl -i -L \
>    -d "refresh_token=[ your refresh token ]" \
>    -d "grant_type=refresh_token" \
>    "https://api.arxiv.org/auth/token"
{"access_token":"[ your new access token ]","token_type":"bearer",
"refresh_token":"[ your new refresh token ]","expires_in":3600}
```

### Three-legged Authorization
Three-legged authorization allows arXiv users to delegate API clients to take
actions on their behalf. This is required for proxy submission. Note that your
client credentials must have an associated ``auth:3legged`` scope, and you
must have entered a valid callback URI for your application.

- Client initiates authorization by directing the user to the arXiv API
  authorization endpoint: ``https://api.arxiv.org/auth/authorize?client_id=[ your client ID ]``
- User is asked to log in and authorize your client. If the user does not
  already have an arXiv account, they are given the option to create one at
  this time, and then proceed with authorization.
- If the user authorizes your client, they will be redirected to your
  registered callback URI. A short-lived authorization code will be included
  as a GET parameter, e.g. ``https://yourapp.foo/callback?code=[ auth code ]``
- Client may exchange the short-lived authorization code for a longer-lived
  authorization token:

```bash
$ curl -i -L \
>    -d "client_id=[ your client id ]" \
>    -d "client_secret=[ your client secret ]" \
>    -d "code=[ your auth code ]" \
>    -d "grant_type=authorization_code" \
>    "https://api.arxiv.org/auth/token"
{"access_token":"[ your access token ]","token_type":"bearer",
"refresh_token":"[ your refresh token ]","expires_in":3600}
```

The authorization code may only be used once. Multiple attempts to exchange the
authorization code for an authorization token will invalidate both the
authorization code and the authorization token that was generated on the first
request.

Use your authorization token in subsequent requests by passing it in the
Authorization header. For example:

```bash
$ curl -i -L \
>    -H "Authorization: [ your access token ]" \
>    "https://api.arxiv.org/submit/"
```

## Endorsement

Most subject areas in arXiv require that the submitter be endorsed by another
member of the scientific community. For more information about what endorsement
is and how it works on a per-user level, see...

In addition to the required authorization scopes mentioned above, the API
client must usually also be granted an endorsement scope for the subject areas
to which it intends to submit. Endorsement scopes may be requested through the
arXiv API Client Registry; see ...

Exception: in the case of proxy submission, the user on whose behalf the
client submits  to arXiv may already be endorsed for a particular subject area.
If so, the client need not be endorsed for that subject area for the submission
to proceed.

## Submission Overview

The submission process is essentially the same for proxy and bulk submissions,
as ownership is inferred from the authorization token provided in each
request.

Submission is initiated upon creation of a new submission resource, by
POSTing to the ``/submission/`` endpoint. The submission resource need not be
complete at this time. See ...

The submission source package may then be added by PUTing the package (see
... ) to the source endpoint:
``/submission/{id}/source/``. The response will include a redirect to a status
endpoint; the source package will be sanitized and unpacked, which may take a
little while, and the status endpoint can be monitored for progress.
Alternatively, a webhook may be configured to receive notifications about
source processing events. See ...

When a source package is uploaded, by default the arXiv submission system will
attempt to compile the source to PDF. Automatic compilation may be disabled,
e.g. to allow for a multi-step upload process. To trigger compilation directly,
a POST request may be made to the compilation endpoint:
``/submission/{id}/source/compile/``. The response will include a reference to
a status endpoint that can be monitored for progress; alternatively, a webhook
may be configured to receive notifications about compilation.

If compilation is successful, the resulting PDF may be retrieved from:
``/submission/{id}/build/pdf/``. Compilation log output may be retrieved from
``/submission/{id}/build/log/``.

Note that the source must compile successfully for submission to proceed, and
the submission resource must be updated to confirm that the client/user is
satisfied with the compiled paper. It is up to the client whether/how such
confirmation should occur.

Updates to the submission may be made via subsequent POST requests to the
submission endpoint (``/submission/{id}/``). This allows the client to
spread the submission process over several steps, if desired.

External links may be attached to the submission by POSTing to the links
endpoint, ``/submission/{id}/links/``. This may be used to supplement the
core metadata with links to external resources, such as code, data, multimedia
content, or an URI for an alternate version of the paper (e.g. in a
peer-reviewed journal). See ...

Once all required procedural and descriptive metadata have been added to the
submission, it may be submitted by POSTing to the submit endpoint:
``/submission/{id}/submit/``. See ...

A client may register to receive updates about one or all submissions for which
it is responsible. To register a webhook for a specific submission, a POST
request may be made to ``/submission/{id}/webhooks/``. To register a webhook
for all submissions for which the client is responsible, a POST request may be
made to ``/webhooks/``. See ...

Once the submission has been published, the submission will be updated with
its arXiv identifier and version number. If a webhook is registered, a
publication notification will also be issued.

The client may transfer ownership of the submission to another agent (user or
another client) via the ``/submission/{id}/transfer/`` endpoint. Note that this
is non-reversible without intervention from the recipient. An alternative is
to delegate editing privileges to another agent, via the
``/submission/{id}/delegate/`` endpoint. See ...

# arXiv Submission & Publication Process

## arXiv Submissions & States

An arXiv submission is comprised of a source package and a collection of
procedural and descriptive metadata. The source package is usually comprised of
a scientific paper (generally in LaTeX) and auxiliary resources (e.g. images,
tables, errata); see ...

The primary objectives of the arXiv submission system are rapid dissemination
of scientific findings, and to support QA/QC workflows for arXiv's volunteer
moderators and the operations team. For a glimpse into how arXiv submissions
are processed on a daily basis, see [this recent blog
post](https://blogs.cornell.edu/arxiv/2018/01/19/a-day-in-the-life-of-the-arxiv-admin-team/).

In support of rapid dissemination, a core requirement for the submission
system is that the daily publication/announcement process should continue
even in the absence of human intervention. In other words, if the moderation
and operations teams were disbanded tomorrow, arXiv would continue to accept
and disseminate publications as usual.

At any given time, a submission will be in one of the states described below.

It should be noted that in the arXiv-NG submission system these states are
defined in terms of the the data that describes the submission, **not** by a
flag in the database.

![](../docs/_static/diagrams/submissionState.png)

### Working

When the submission process is initiated, it generally lacks some of the
(meta)data and/or content required for publication. For example, the
submission process may be initiated by sending preliminary information for
only a few metadata fields, leaving the submission source package to be
uploaded separately. Several users and/or API clients may be involved in
contributing information about the submission. The source package must
compile to a publishable PDF before a submission can leave the working
state.

### Processing

Once a submission is finalized (ready for publication), it is subject to
a handful of automated QA/QC checks. For example, we need to be able to
extract plain text content from the compiled paper for subsequent checks.
Depending on the results of those checks, the submission may be bounced
back to the working state to correct problems. Generally, a submission
remains in the processing state for a very short period of time (seconds or
minutes).

### Submitted

If the preliminary checks pass, the submission is considered to be in the
submitted state. Automated checks for technical issues may also be applied
while the submission is in this state, and members of the moderation and
operations teams may inspect the paper for quality or to address issues
flagged by the technical checks. If a moderation flag is applied to the
submission during this process, the submission transitions to the **On
Hold** state (below). If no moderation or administrative flags are raised
on the submission, the submission will automatically transition to the
**Scheduled** state (below) at one of two cutoff times.

### On Hold

A submission in this state has been flagged by a moderator or by an
automated QA/QC process for potential problems. Submissions in this state
are usually inspected by the operations team, who may reach out to the
submission owner. If and when the issues with the submission are resolved,
an administrator will remove the blocking flags from the submission, and
the submission will return to the **Submitted** state.

### Scheduled

Any submissions in the **Submitted** state at the publication cut-off time
(currently 2PM ET) will be automatically scheduled for publication on the
same day (currently 8PM ET). Any remaining submissions in the **Submitted**
state at the next-day cutoff (currently 8PM ET) will be scheduled for
publication on the following day.

### Published

The automated publication process runs daily, currently at 8PM ET. Any
submissions scheduled for the current day will be updated with their
arXiv ID and version, and a publication timestamp. At that time, the
submission is considered **Published**. No further changes
may be made to a submission in this state.
