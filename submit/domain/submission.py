"""Data structures for submissions."""

import hashlib
from datetime import datetime
from submit.domain import Data, Property
from submit.domain.agent import Agent


class Classification(Data):
    """An archive/subject classification for a :class:`.Submission`."""

    group = Property('group', str)
    archive = Property('archive', str)
    subject = Property('subject', str)


class License(Data):
    """An license for distribution of the submission."""

    name = Property('name', str)
    uri = Property('uri', str)


class SubmissionMetadata(Data):
    """Metadata about a :class:`.Submission` instance."""

    title = Property('title', str)
    abstract = Property('abstract', str)
    authors = Property('authors', str)

    doi = Property('doi', str)
    msc_class = Property('msc_class', str)
    acm_class = Property('acm_class', str)
    report_num = Property('report_num', str)
    journal_ref = Property('journal_ref', str)


class Submission(Data):
    """Represents an arXiv submission object."""

    creator = Property('creator', Agent)
    proxy = Property('proxy', Agent, null=True)
    created = Property('created', datetime)
    submission_id = Property('submission_id', int, null=True)
    metadata = Property('metadata', SubmissionMetadata)

    active = Property('active', bool, True)
    finalized = Property('finalized', bool, False)
    published = Property('published', bool, False)
    comments = Property('comments', dict, {})

    primary_classification = Property('primary_classification', Classification)
    secondary_classification = Property('secondary_classification', list)

    submitter_contact_verified = Property('submitter_contact_verified', bool,
                                          False)
    submitter_is_author = Property('submitter_is_author', bool, True)
    submitter_accepts_policy = Property('submitter_accepts_policy', bool,
                                        False)

    license = Property('license', License)
