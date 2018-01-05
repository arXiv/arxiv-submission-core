"""Data structures for submissions."""

import hashlib
from datetime import datetime
from submit.domain import Data, Property
from submit.domain.agent import Agent


class SubmissionMetadata(Data):
    """Metadata about a :class:`.Submission` instance."""

    title = Property('title', str)
    abstract = Property('abstract', str)
    authors = Property('authors', str)


class Submission(Data):
    """Represents an arXiv submission object."""

    creator = Property('creator', Agent)
    created = Property('created', datetime)
    submission_id = Property('submission_id', int, null=True)
    metadata = Property('metadata', SubmissionMetadata)
    active = Property('active', bool, True)
    finalized = Property('finalized', bool, False)
    comments = Property('comments', dict, {})
    archive = Property('archive', str)
