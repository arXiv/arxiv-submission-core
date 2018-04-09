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
