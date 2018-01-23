# arXiv Submission API

The arXiv submission API supports programmatic submission mechanisms for
third-party applications.

[JSON Schema](json-schema.org) for the arXiv submission API can be found in
``schema/``.

## OpenAPI Schema

The [](api/) directory provides a description of the arXiv submission API based
on the OpenAPI 3.0.0 specification. The root API description is located at
[](api/openapi.yaml).

The OpenAPI description refers to JSON Schema documents for the various
resources accepted/exposed by the submission API. Those schemas are used to
validate client requests and responses. **Note that OpenAPI 3 is a subset of
the JSON Schema specification**; we therefore only use keywords that are
supported by OpenAPI. [This issue](https://github.com/OAI/OpenAPI-Specification/issues/333)
provides extensive background (scroll to the bottom for JSON Schema support
in OpenAPI 3).

The OpenAPI and JSON Schema documents should be considered a contract for the
submission service API, and suitable as a basis for implementing clients.

## Toy submission service

The current ``Dockerfile`` in the root of this repository provides a toy
submission API, including access token verification.

To start the API, build and run the docker image:

```
docker build ./ -t arxiv/submit-api
docker run -it -p 8000:8000 arxiv/submit-api
```

This will start the submission API service proxied by NGINX. A toy
authorization service is also started to simulate access token verification
in a typical OAuth2 scenario.

If all goes well, the submission service should be available on
http://localhost:8000.

### Authorization

The toy authorization service simulates access token verification, e.g. after
an [OAuth2 authorization code grant](https://tools.ietf.org/html/rfc6749#section-4.1)
process. The NGINX gateway expects an ``Authorization`` header with the
access token. For example:

``Authorization: Bearer footoken1234``

If the token is valid, the authorizer replaces the access with a JWT that
encodes the identity of the client, the identity of the resource owner (end
user), and an authorization scope.

Token ``as392lks0kk32`` has scope ``submission:write`` and ``submission:read``,
which should grant access to the entire submission API.

Here's the resulting JWT for secret "foo" (this is subject to change):

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
Server: nginx/1.10.3 (Ubuntu)
Date: Fri, 17 Nov 2017 20:21:49 GMT
Content-Type: application/json
Content-Length: 83
Connection: keep-alive
```

But:

```
$ curl -I http://localhost:8000/submit/
HTTP/1.1 403 Forbidden
Server: nginx/1.10.3 (Ubuntu)
Date: Fri, 17 Nov 2017 20:21:20 GMT
Content-Type: application/json
Content-Length: 32
Connection: keep-alive
```
