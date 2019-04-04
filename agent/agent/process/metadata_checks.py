"""Automated metadata checks."""

from datetime import datetime, timedelta
from typing import Set, List, Tuple, Iterable, Optional, Callable
from unidecode import unidecode
import string
from functools import lru_cache as memoize

from arxiv.base.globals import get_application_config

from arxiv.submission.domain.event import Event, SetTitle, SetAbstract, \
    RemoveFlag, AddMetadataFlag
from arxiv.submission.domain.submission import Submission
from arxiv.submission.domain.agent import Agent, User
from arxiv.submission.domain.flag import MetadataFlag, ContentFlag, \
    PossibleDuplicate
from arxiv.submission.services import classic
from .util import is_ascii, below_ascii_threshold, proportion_ascii

from ..process import Process, step
from ..domain import Trigger

STOPWORDS = set('a,an,and,as,at,by,for,from,in,of,on,s,the,to,with,is,was,if,'
                'then,that,these,those,them,thus'.split(','))

REMOVE_PUNCTUATION = str.maketrans(string.punctuation,
                                   ' '*len(string.punctuation))
"""Translator that converts punctuation characters into single spaces."""


# Original procedure from classic:
#
# Query Submission (``arXiv_submissions`` table) for submissions with titles
# that were created within the last 3 months.
#
# Select previous matches for this submission id, and delete them -- from
# SubmissionNearDuplicates (``arXiv_submission_near_duplicates`` table)
#
# Get a Jaccard similarity indexer function
# (arXiv::Submit::Jaccard::JaccardIndex->make_jaccard_indexer)
#
# Among the results of the arXiv_submissions query, find submissions that are
# more similar than some threshold, skipping any user-deleted submissions.
#
# For each match > threshold, add a new duplicate record to the
# ``arXiv_submission_near_duplicates`` table with its score, and create
# corresponding entries in the admin log (``arXiv_admin_log`` table).
class CheckForSimilarTitles(Process):
    """
    Check for other submissions with very similar titles.

    Ask classic for titles of papers submitted within the last several months.
    Add an annotation to the submission if a title is more similar to the
    current submission's title than a configurable threshold.
    """

    def _get_title(self, trigger: Trigger) -> str:
        try:
            return trigger.after.metadata.title
        except AttributeError as exc:
            self.fail(exc, 'Missing title or post-event state')

    @step(max_retries=None)
    def get_candidates(self, previous: Optional, trigger: Trigger,
                       emit: Callable) -> List[Tuple[int, str, Agent]]:
        """Get candidate titles from the database."""
        title = self._get_title(trigger)
        # If the title has no tokens, there is nothing to do.
        if not tokenized(title):
            self.fail(message='No usable tokens in title')
            """Get the time window for possible duplicate submissions."""

        days = window(trigger.params['TITLE_SIMILARITY_WINDOW'])
        candidates: List[Tuple[int, str, Agent]] = classic.get_titles(days)
        return candidates

    @step()
    def check_for_duplicates(self, candidates: List[Tuple[int, str, Agent]],
                             trigger: Trigger, emit: Callable) -> None:
        """Look for very similar titles, and add flags if appropriate."""
        title = self._get_title(trigger)
        flag_type = MetadataFlag.Type.POSSIBLE_DUPLICATE_TITLE

        for flag_id, flag in trigger.after.flags.items():
            if isinstance(flag, MetadataFlag) and flag.flag_type is flag_type:
                emit(RemoveFlag(creator=self.agent, flag_id=flag_id))

        for ident, candidate_title, submitter in candidates:
            similarity = jaccard(title, candidate_title)
            if similarity > trigger.params['TITLE_SIMILARITY_THRESHOLD']:
                emit(AddMetadataFlag(
                    creator=self.agent,
                    flag_type=flag_type,
                    flag_data={'submission_id': ident,
                               'title': title,
                               'owner': submitter,
                               'similarity': similarity},
                    field='title',
                    comment='possible duplicate title'))


class CheckTitleForUnicodeAbuse(Process):
    """
    Screen for possible abuse of unicode in titles.

    We support unicode characters in titles, but this can get out of hand.
    This rule adds a flag if the ratio of non-ASCII to ASCII characters
    is too high.
    """

    def _get_title(self, trigger: Trigger) -> str:
        try:
            if trigger.after.metadata.title is None:
                self.fail(message='Missing title or post-event state')
            return trigger.after.metadata.title
        except AttributeError as exc:
            self.fail(exc, 'Missing title or post-event state')

    def _clear_previous_flags(self, trigger: Trigger, emit: Callable) -> None:
        for flag_id, flag in trigger.after.flags.items():
            if isinstance(flag, MetadataFlag) and \
                    flag.flag_type is MetadataFlag.Type.CHARACTER_SET and \
                    flag.field == 'title':
                emit(RemoveFlag(creator=self.agent, flag_id=flag_id))

    @step()
    def check_title(self, previous: Optional, trigger: Trigger,
                    emit: Callable) -> None:
        """Check title for low ASCII content."""
        self._clear_previous_flags(trigger, emit)
        level = proportion_ascii(self._get_title(trigger))
        if level < trigger.params['METADATA_ASCII_THRESHOLD']:
            comment = 'Possible excessive use of non-ASCII characters.'
            emit(AddMetadataFlag(creator=self.agent,
                                 flag_type=MetadataFlag.Type.CHARACTER_SET,
                                 flag_data={'ascii': level},
                                 field='title',
                                 comment=comment))


# @SetAbstract.bind(condition=lambda *a: not system_event(*a))
class CheckAbstractForUnicodeAbuse(Process):
    """
    Screen for possible abuse of unicode in abstracts.

    We support unicode characters in abstracts, but this can get out of hand.
    This rule adds a flag if the ratio of non-ASCII to ASCII characters
    is too high.
    """

    def _get_abstract(self, trigger: Trigger) -> str:
        try:
            if trigger.after.metadata.abstract is None:
                self.fail(message='Missing abstract or post-event state')
            return trigger.after.metadata.abstract
        except AttributeError as exc:
            self.fail(exc, 'Missing abstract or post-event state')

    def _clear_previous_flags(self, trigger: Trigger, emit: Callable) -> None:
        for flag_id, flag in trigger.after.flags.items():
            if isinstance(flag, MetadataFlag) and \
                    flag.flag_type is MetadataFlag.Type.CHARACTER_SET and \
                    flag.field == 'abstract':
                emit(RemoveFlag(creator=self.agent, flag_id=flag_id))

    @step()
    def check_abstract(self, previous: Optional, trigger: Trigger,
                       emit: Callable) -> None:
        """Check abstract for low ASCII content."""
        self._clear_previous_flags(trigger, emit)
        level = proportion_ascii(self._get_abstract(trigger))
        if level < trigger.params['METADATA_ASCII_THRESHOLD']:
            comment = 'Possible excessive use of non-ASCII characters.'
            emit(AddMetadataFlag(creator=self.agent,
                                 flag_type=MetadataFlag.Type.CHARACTER_SET,
                                 flag_data={'ascii': level},
                                 field='abstract',
                                 comment=comment))


@memoize(maxsize=1028)
def normalize(phrase: str) -> str:
    """Prepare a phrase for tokenization."""
    return unidecode(phrase.lower()).translate(REMOVE_PUNCTUATION)


@memoize(maxsize=2056)
def tokenized(phrase: str) -> Set[str]:
    """Split a phrase into tokens and remove stopwords."""
    return set(normalize(phrase).split()) - STOPWORDS


def intersection(phrase_a: str, phrase_b: str) -> int:
    """Calculate the number tokens shared by two phrases."""
    return len(tokenized(phrase_a) & tokenized(phrase_b))


def union(phrase_a: str, phrase_b: str) -> int:
    """Calculate the  total number tokens in two phrases."""
    return len(tokenized(phrase_a) | tokenized(phrase_b))


def jaccard(phrase_a: str, phrase_b: str) -> float:
    """Calculate the Jaccard similarity of two phrases."""
    return intersection(phrase_a, phrase_b) / union(phrase_a, phrase_b)


def window(days: int) -> datetime:
    """Get a datetime from ``days`` days ago."""
    return datetime.now() - timedelta(days)
