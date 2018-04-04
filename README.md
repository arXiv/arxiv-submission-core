# arXiv Submission

This repository houses exploratory development related to the arXiv-NG
submission system.

- The [events core package](core/) is provides integrations with the
  submission database and notification streams, and exposes a Python API for
  event-based operations on submission (meta)data. Any web services that
  modify submission data must do so via this package.
- The [API service](api/) provides the client-facing interface for
  submission-related requests. **Status: In progress**
- The [Webhooks service](webhooks/) provides an API for creating and managing
  submission-related webhooks. **Status: Schema only**
- The [Upload service](upload/) is a mock implementation of the file management
  service, to be fully implemented elsewhere. **Status: Schema only**
- The [Compile service](compile/) is a mock implementation of the compilation
  service, to be fully implemented elsewhere. **Status: Schema only**
- The [Authorization service](authorization/) mocks token-based authorization.
  It handles sub-requests from the gateway to authorize client requests, and
  mints encrypted JWTs for use by other services.
- A toy [Gateway service](gateway/) provides a minimal NGINX server configured
  to utilize the authorization service. It provides (proxy) access to
  client-facing services, including the API service.

This project is in its early stages, and has been subject to considerable
churn. As a consequence, test coverage, documentation, and verification are
incomplete. We will actively address these issues as we go along.

## Local deployment (for testing only)

A Compose file ([docker-compose.yml](docker-compose.yml)) is included in the
root of this repository, and can be used to run the services in this project
for local testing and development purposes.

See the [Docker documentation](https://docs.docker.com/compose/) for
information about using Docker Compose.

The Compose file included here deploys all services on a custom network, and
exposes the gateway service at port 8000 on your local machine.

### Authorization

The toy authorization service simulates access token verification, e.g. after
an [OAuth2 authorization code grant](https://tools.ietf.org/html/rfc6749#section-4.1)
process. The NGINX gateway expects an ``Authorization`` header with an
access token. For example:

``Authorization: Bearer footoken1234``

If the token is valid, the authorizer replaces the access with a JWT that
encodes the identity of the client, the identity of the resource owner (end
user), and an authorization scope.

Token ``as392lks0kk32`` has scope ``submission:write`` and ``submission:read``,
which should grant access to the entire submission API.

Here's what the resulting JWT might look like:

```
eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJjbGllbnQiOiJmb29jbGllbnQiLCJ1c2VyIjoiZm9vdXNlciIsInNjb3BlIjpbInN1Ym1pc3Npb246d3JpdGUiLCJzdWJtaXNzaW9uOnJlYWQiXX0.253M954JUBpokfyP1CEHyk1-sn3Kk42Vyn9W1u59u08
```

Token ``f0da9jso3l2m4`` has scope ``submission:read``, which should allow only
``GET`` requests to relevant endpoints.

See ``submit/external.py`` for all of the available endpoints.

TODO: document endpoints here.

For example:

```
$ curl -I -H "Authorization: Bearer f0da9jso3l2m4" http://localhost:8000/submit/
HTTP/1.1 200 OK
Server: nginx/1.13.8
Date: Tue, 30 Jan 2018 20:06:47 GMT
Content-Type: application/json
Content-Length: 20
Connection: keep-alive
```

But:

```
$ curl -I http://localhost:8000/submit/
HTTP/1.1 403 Forbidden
Server: nginx/1.13.8
Date: Tue, 30 Jan 2018 20:07:13 GMT
Content-Type: application/json
Content-Length: 32
Connection: keep-alive
```
