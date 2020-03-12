# arXiv Submission

This repository houses development related to the arXiv-NG
submission system. 

## What's in the repo

- The [events core package](core/) provides integrations with the
  submission database and notification streams, and exposes a Python API for
  event-based operations on submission (meta)data. Any web services that
  modify submission data must do so via this package.
- The [submission agent](agent/) is a Kinesis consumer that orchestrates
  backend processes based on rules triggered by submission events.

### In progress/stale

These components are considerably behind, or only partially
complete. After the 2019-10 transition the status of all of these
unknown.

Future development milestones will focus on these services, possibly
in separate repositories.

- The [API service](metadata/) provides the client-facing interface for
  submission-related requests. **Status: In progress**
- The [Webhooks service](webhooks/) provides an API for creating and managing
  submission-related webhooks. **Status: Schema only**
- A toy [Gateway service](gateway/) provides a minimal NGINX server configured
  to utilize the authentication service (below). It provides (proxy) access to
  client-facing services, including the API service. This is close (but not
  identical) to what is run in production. **Status: Unknown after 2019-10 transition**
- [admin](admin/) contains fragments related to admin
  quality assurance checks. **Status: Unknown after 2019-10 transition**
- The [filesystem](filesystem/) is an app to make sure that the NG
  submission system can put files in the right place on the legacy
  filesystem when (and only when) a submission is finalized. **Status: Unknown after 2019-10 transition**


## Related components/dependencies

- The [authentication service](https://github.com/cul-it/arxiv-auth/tree/develop/authenticator)
  handles sub-requests from the gateway to authorize client requests, and mints
  encrypted JWTs for use by other services.
- The [client registry](https://github.com/cul-it/arxiv-auth/tree/develop/registry)
  provides OAuth2 workflows. Currently supports the `client_credentials` and
  `authorization_code` grant types.
- The [file management service](https://github.com/cul-it/arxiv-filemanager) is
  responsible for handling client/user uploads, and perform sanitization and
  other QA checks.
- The [submission UI](https://github.com/cul-it/arxiv-submission-ui) provides a
  form-driven UI for submission. The UI is built on top of the submission core
  package (this repo).
- The [compiler service](https://github.com/cul-it/arxiv-compiler) is
  responsible for compiling LaTeX sources to PDF, DVI, and other formats.

## Python dependencies

This project uses pipenv to manage Python dependencies. To install dependencies
do:

```bash
$ pipenv install
```

To install dev/testing dependencies, use:

```bash
$ pipenv install --dev
```

## Local deployment with Docker Compose (for testing only)

A Compose file ([docker-compose.yml](docker-compose.yml)) is included in the
root of this repository, and can be used to run the services in this project
for local testing and development purposes.

See the [Docker documentation](https://docs.docker.com/compose/) for
information about using Docker Compose.

### Starting the service cluster

The Compose file included here deploys all services on a custom network, and
exposes the gateway service at port 8000 on your local machine.

To start up (from the root of the repo, containing ``docker-compose.yml``):

```bash
$ docker-compose build
$ docker-compose up
```

This will generate a lot of output, and bind your terminal. Some things to
watch for:

MariaDB starting up successfully:
```
submission-maria            | 2018-04-11 13:49:16 0 [Note] Reading of all Master_info entries succeded
submission-maria            | 2018-04-11 13:49:16 0 [Note] Added new Master_info '' to hash table
submission-maria            | 2018-04-11 13:49:16 0 [Note] mysqld: ready for connections.
submission-maria            | Version: '10.3.5-MariaDB-10.3.5+maria~jessie'  socket: '/var/run/mysqld/mysqld.sock'  port: 3306  mariadb.org binary distribution
```

The metadata API service waiting for the database to be ready:

```
submission-metadata         | application 11/Apr/2018:09:49:13 +0000 - __main__ - None - [arxiv:null] - INFO: "...waiting 4 seconds..."
```

After the DB is available, you should see something like this as the metadata
service initializes the database and adds some data.

```
submission-metadata         | application 11/Apr/2018:09:49:17 +0000 - __main__ - None - [arxiv:null] - INFO: "Checking for database"
submission-metadata         | application 11/Apr/2018:09:49:17 +0000 - __main__ - None - [arxiv:null] - INFO: "Database not yet initialized; creating tables"
submission-metadata         | application 11/Apr/2018:09:49:18 +0000 - __main__ - None - [arxiv:null] - INFO: "Populate with base data..."
submission-metadata         | application 11/Apr/2018:09:49:18 +0000 - __main__ - None - [arxiv:null] - INFO: "Added 10 licenses"
submission-metadata         | application 11/Apr/2018:09:49:18 +0000 - __main__ - None - [arxiv:null] - INFO: "Added 3 policy classes"
submission-metadata         | application 11/Apr/2018:09:49:18 +0000 - __main__ - None - [arxiv:null] - INFO: "Added 150 categories"
submission-metadata         | application 11/Apr/2018:09:49:18 +0000 - __main__ - None - [arxiv:null] - INFO: "Added 500 users"
```

Note that the users generated here are fake. Licenses, categories, etc are all
"realistic".

After generating data, the web service starts:

```
submission-metadata         | spawned uWSGI master process (pid: 13)
submission-metadata         | spawned uWSGI worker 1 (pid: 21, cores: 100)
submission-metadata         | spawned uWSGI worker 2 (pid: 22, cores: 100)
submission-metadata         | spawned uWSGI worker 3 (pid: 23, cores: 100)
submission-metadata         | spawned uWSGI worker 4 (pid: 24, cores: 100)
submission-metadata         | spawned uWSGI worker 5 (pid: 25, cores: 100)
submission-metadata         | spawned uWSGI worker 6 (pid: 26, cores: 100)
submission-metadata         | spawned uWSGI worker 7 (pid: 27, cores: 100)
submission-metadata         | spawned uWSGI worker 8 (pid: 28, cores: 100)
```

### Creating a client

The ``arxiv/registry`` image provides a helper script to create a new API
client.

Be sure to change ``[NETWORK_NAME]`` to the actual name of the Docker network
that the service cluster is using. It should be
``[something]arxiv-submission-local``. E.g, it might be
``arxivsubmissioncore_arxiv-submission-local``. To be sure, run
``docker network ls | grep arxiv-submission-local``.

```bash
docker run -it -e REGISTRY_DATABASE_URI=mysql+mysqldb://foouser:foopass@registry-maria:3306/registry?charset=utf8 --network=[NETWORK NAME] arxiv/registry:0.1 -- python create_client.py
```

Follow the prompts to create your client. For best results, use the default
scopes (just press enter):

```bash
Brief client name: client
Info URL for the client: http://client
What is it: a client
Space-delimited authorized scopes [public:read submission:create submission:update submission:read upload:create upload:update upload:read upload:read_logs]:
Redirect URI: http://localhost:1234/callback
Created client client with ID 2 and secret o86ScxuqcOffbWKxvyGke6e4wFTIukkjiJEc4ofBj7cDmNLz
```

Note the client ID and secret at the end -- you'll need those.

### Client credentials authorization

In production, the submission API will require an authorization code
(three-legged authorization) grant. For local testing, however, it may be more
convenient to use client credentials.

Use your client ID and secret (above) to get an access token.

Include the header: ``Content-Type: application/x-www-form-urlencoded``

Include the following parameters:

- ``grant_type`` -- This should be ``client_credentials``
- ``client_id`` -- This should be your client ID
- ``client_secret`` -- This should be your client secret

```bash
$ curl -XPOST -H "Content-Type: application/x-www-form-urlencoded" -d "grant_type=client_credentials&client_id=2&client_secret=o86ScxuqcOffbWKxvyGke6e4wFTIukkjiJEc4ofBj7cDmNLz" http://127.0.0.1:8000/api/token
{"access_token": "4tkstLJauH65EwpewmpJ0IugdqFLMctHiIjl5IvWxK", "expires_in": 864000, "token_type": "Bearer"}
```

You should get back a JSON document with the following properties:

- ``access_token`` -- That's your access token.
- ``expires_in`` -- Number of seconds until the token expires.
- ``token_type`` -- This should be ``"Bearer"``.

### Create a submission

At this point, you should be able to interact with the submission API.

Be sure to include the headers:
- ``Content-Type: application/json`` -- That's because the submission metadata
  API speaks JSON.
- ``Authorization: Bearer [your access token]`` -- If you don't include a valid
  token, you'll get a 401 Unauthorized response. Or a 403, if you've really
  been unruly.

You can use the pre-baked submission in
``metadata/examples/complete_submission.json`` to get up and running.

```bash
$ curl -i -X POST -H "Content-Type: application/json" \
    -H "Authorization: Bearer 4tkstLJauH65EwpewmpJ0IugdqFLMctHiIjl5IvWxK" \
    --data-binary "@metadata/examples/complete_submission.json" http://localhost:8000/submission/
```

But note that you can create a submission with far less than that!

```bash
$ curl -i -X POST -H "Content-Type: application/json" \
    -H "Authorization: Bearer 4tkstLJauH65EwpewmpJ0IugdqFLMctHiIjl5IvWxK" \
    --data "{}" http://localhost:8000/submission/

HTTP/1.1 201 CREATED
Server: nginx/1.13.12
Date: Mon, 24 Sep 2018 19:47:33 GMT
Content-Type: application/json
Content-Length: 1027
Location: http://localhost:8000/submission/7/
Connection: keep-alive

{"active":true,"arxiv_id":null,"client":{"client_id":"2"},"compilations":[],"created":"2018-09-24T19:47:33.251494","creator":{"affiliation":"","agent_type":"User","email":"","endorsements":["*.*"],"forename":"","identifier":null,"name":"  ","native_id":null,"suffix":"","surname":"","user_id":null},"delegations":{},"finalized":false,"license":null,"metadata":{"abstract":null,"acm_class":null,"authors":[],"authors_display":"","comments":"","doi":null,"journal_ref":null,"msc_class":null,"report_num":null,"title":null},"owner":{"affiliation":"","agent_type":"User","email":"","endorsements":["*.*"],"forename":"","identifier":null,"name":"  ","native_id":null,"suffix":"","surname":"","user_id":null},"primary_classification":null,"proxy":null,"announced":false,"secondary_classification":[],"source_content":null,"status":"working","submission_id":7,"submitter_accepts_policy":null,"submitter_confirmed_preview":false,"submitter_contact_verified":false,"submitter_is_author":null,"updated":"2018-09-24T19:47:33.251494"}
```

You can update a submission by POSTing fields that you want to update.

```bash
$ curl -i -X POST -H "Content-Type: application/json" \
    -H "Authorization: Bearer 4tkstLJauH65EwpewmpJ0IugdqFLMctHiIjl5IvWxK"  \
    --data '{"metadata":{"title":"The theory of life and everything","doi":"10.00123/foo45678"}}' \
    http://localhost:8000/submission/7/

HTTP/1.1 200 OK
Server: nginx/1.13.12
Date: Mon, 24 Sep 2018 20:23:57 GMT
Content-Type: application/json
Content-Length: 1060
Location: http://localhost:8000/submission/7/
Connection: keep-alive

{"active":true,"arxiv_id":null,"client":null,"compilations":[],"created":"2018-09-24T20:22:33.498688","creator":{"affiliation":"","agent_type":"User","email":"","endorsements":["*.*"],"forename":"","identifier":null,"name":"  ","native_id":null,"suffix":"","surname":"","user_id":null},"delegations":{},"finalized":false,"license":null,"metadata":{"abstract":null,"acm_class":null,"authors":[],"authors_display":"","comments":"","doi":"10.00123/foo45678","journal_ref":null,"msc_class":null,"report_num":null,"title":"The theory of life and everything"},"owner":{"affiliation":"","agent_type":"User","email":"","endorsements":["*.*"],"forename":"","identifier":null,"name":"  ","native_id":null,"suffix":"","surname":"","user_id":null},"primary_classification":null,"proxy":null,"announced":false,"secondary_classification":[],"source_content":null,"status":"working","submission_id":7,"submitter_accepts_policy":null,"submitter_confirmed_preview":false,"submitter_contact_verified":false,"submitter_is_author":null,"updated":"2018-09-24T20:23:57.754003"}
```

You can finalize the submission by updating the ``finalize`` field to ``true``.
But if fields are missing, you'll get an error.

```
$ curl -i -X POST -H "Content-Type: application/json" \
    -H "Authorization: Bearer 4tkstLJauH65EwpewmpJ0IugdqFLMctHiIjl5IvWxK" \
    --data '{"finalized": true}' \
    http://localhost:8000/submission/7/

HTTP/1.1 400 BAD REQUEST
Server: nginx/1.13.12
Date: Mon, 24 Sep 2018 20:25:32 GMT
Content-Type: application/json
Content-Length: 62
Connection: keep-alive

{"reason":"Invalid Stack:\n\tMissing primary_classification"}
```

## Documentation

See https://cul-it.github.io/arxiv-submission-core/ for the
latest documentation. ** TODO Fix this broken link.**

### Freshen/build

Update the API doc source refs with:

```bash
sphinx-apidoc -o docs/source/arxiv.submission -e -f -M --implicit-namespaces core/arxiv *test*/*
```

Build HTML docs with:

```bash
cd docs
make html SPHINXBUILD=$(pipenv --venv)/bin/sphinx-build
```

## Contributions

https://github.com/cul-it/arxiv-submission-core/blob/master/CONTRIBUTING.md
