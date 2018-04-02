# Submission event core package

This package provides an event-based API for CRUD operations on submissions
and submission-related (meta)data. Management of submission content (i.e.
source files) is out of scope.

Rather than perform CRUD operations directly on submission objects, all
operations that modify submission data are performed through the creation of
submission events. This ensures that we have a precise and complete record of
activities concerning submissions, and provides an explicit definition of
operations that can be performed within the arXiv submission system.
