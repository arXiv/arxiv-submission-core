"""Data structures for submissions."""

from typing import TypeVar
import hashlib
from datetime import datetime
from api.domain import Data, Property
from api.domain.agent import Agent, agent_factory


SubmissionType = TypeVar('SubmissionType', bound='Submission')


class SubmissionData(Data):
    @classmethod
    def _data_to_set(cls, data: dict, err_missing: bool = True):
        """Override to instantiate :class:`.Agent`s as their child class."""
        for key, value in data.items():
            if isinstance(value, Data):    # Already cast; don't touch.
                continue
            field = getattr(cls, key, None)
            if isinstance(field, Property) and field.klass is Agent:
                data[key] = agent_factory(value['agent_type'],
                                          value['native_id'])
        return super(SubmissionData, cls)._data_to_set(data, err_missing)


class Classification(SubmissionData):
    """An archive/category classification for a :class:`.Submission`."""

    category = Property('category', str)


class License(SubmissionData):
    """An license for distribution of the submission."""

    name = Property('name', str, null=True)
    uri = Property('uri', str)


class Author(SubmissionData):
    """Represents an author of a submission."""

    def __init__(self, **data) -> None:
        """Auto-generate an identifier, if not provided."""
        super(Author, self).__init__(**data)
        if not self.identifier:
            self.identifier = self._generate_identifier()

    def _generate_identifier(self):
        h = hashlib.new('sha1')
        h.update(bytes(':'.join([self.forename, self.surname, self.initials,
                                 self.affiliation, self.email]),
                       encoding='utf-8'))
        return h.hexdigest()

    identifier = Property('identifier', str)
    forename = Property('forename', str, '')
    surname = Property('surname', str, '')
    initials = Property('initials', str, '')
    affiliation = Property('affiliation', str, '')

    email = Property('author_email', str, '')

    order = Property('order', int)

    @property
    def canonical(self):
        """Canonical representation of the author name."""
        name = "%s %s %s" % (self.forename, self.initials, self.surname)
        if self.affiliation:
            return "%s (%s)" % (self.name, self.affiliation)
        return name


class SubmissionMetadata(SubmissionData):
    """Metadata about a :class:`.Submission` instance."""

    title = Property('title', str, null=True)
    abstract = Property('abstract', str, null=True)

    authors = Property('authors', list, [])

    @property
    def authors_canonical(self):
        """Canonical representation of submission authors."""
        return ", ".join(self.authors)

    doi = Property('doi', str, null=True)
    msc_class = Property('msc_class', str, null=True)
    acm_class = Property('acm_class', str, null=True)
    report_num = Property('report_num', str, null=True)
    journal_ref = Property('journal_ref', str, null=True)


class Delegation(SubmissionData):
    """Delegation of editing privileges to a non-owning :class:`.Agent`."""

    @property
    def delegation_id(self):
        """Unique identifer for the delegation instance."""
        h = hashlib.new('sha1')
        h.update(b'%s:%s:%s' % (self.delegate.agent_identifier,
                                self.creator.agent_identifier,
                                self.created.isodate()))
        return h.hexdigest()

    delegate = Property('delegate', Agent)
    creator = Property('creator', Agent)
    created = Property('created', datetime)


class Submission(SubmissionData):
    """Represents an arXiv submission object."""

    creator = Property('creator', Agent)
    owner = Property('owner', Agent)
    delegations = Property('delegations', dict, {})
    proxy = Property('proxy', Agent, null=True)
    created = Property('created', datetime)
    submission_id = Property('submission_id', int, null=True)
    metadata = Property('metadata', SubmissionMetadata)

    active = Property('active', bool, True)
    finalized = Property('finalized', bool, False)
    published = Property('published', bool, False)
    comments = Property('comments', dict, {})

    primary_classification = Property('primary_classification', Classification,
                                      null=True)
    secondary_classification = Property('secondary_classification', list, [])

    submitter_contact_verified = Property('submitter_contact_verified', bool,
                                          False)
    submitter_is_author = Property('submitter_is_author', bool, True)
    submitter_accepts_policy = Property('submitter_accepts_policy', bool,
                                        False)

    license = Property('license', License, null=True)
