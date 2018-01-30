# Submission Event Controller Service

The submission event controller service is a backend service responsible for
processing commands from other arXiv services related to the submission and
moderation of papers up through publication.

As the name suggests, data update events are first-class citizens in the
submission system. Hence, the API for this service focuses on the RESTful
creation of immutable events.

OpenAPI v3 documentation for the event API can be found in [schema/openapi.yaml](schema/openapi.yaml), and refers to the JSON Schema
resource definitions located in [schema/resources/](schema/resources/).
