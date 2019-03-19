"""Automated metadata checks."""

from datetime import datetime, timedelta
from typing import Set, List, Tuple, Iterable, Optional
from unidecode import unidecode
import string
from functools import lru_cache as memoize

from arxiv.base.globals import get_application_config

from ..domain.event import Event, SetTitle, SetAbstract, RemoveFlag, \
    AddMetadataFlag
from ..domain.submission import Submission
from ..domain.agent import Agent, User
from ..domain.flag import MetadataFlag, ContentFlag, PossibleDuplicate
from ..services import classic
from ..tasks import is_async
from .util import is_ascii, below_ascii_threshold, proportion_ascii

from .generic import system_event

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
@SetTitle.bind(condition=lambda *a: not system_event(*a))
@is_async
def check_similar_titles(event: SetTitle, before: Submission,
                         after: Submission, creator: Agent,
                         task_id: Optional[str] = None,
                         **kwargs) -> Iterable[Event]:
    """
    Check for other submissions with very similar titles.

    Ask classic for titles of papers submitted within the last several months.
    Add an annotation to the submission if a title is more similar to the
    current submission's title than a configurable threshold.
    """
    # If the title has no tokens, there is nothing to do.
    if not tokenized(event.title):
        return

    flag_type = MetadataFlag.FlagTypes.POSSIBLE_DUPLICATE_TITLE
    candidates: List[Tuple[int, str, Agent]] = classic.get_titles(window())
    for flag_id, flag in after.flags.items():
        if isinstance(flag, MetadataFlag) and flag.flag_type is flag_type:
            yield RemoveFlag(creator=creator, flag_id=flag_id)

    for ident, title, submitter in candidates:
        if above_similarity_threshold(jaccard(event.title, title)):
            yield AddMetadataFlag(creator=creator,
                                  flag_type=flag_type,
                                  flag_data={
                                    'submission_id': ident,
                                    'title': title,
                                    'owner': submitter,
                                    'similarity': jaccard(event.title, title)
                                  },
                                  field='title',
                                  comment='possible duplicate title')


@SetTitle.bind(condition=lambda *a: not system_event(*a))
def check_title_ascii(event: SetTitle, before: Submission,
                      after: Submission, creator: Agent,
                      task_id: Optional[str] = None,
                      **kwargs) -> Iterable[Event]:
    """
    Screen for possible abuse of unicode in titles.

    We support unicode characters in titles, but this can get out of hand.
    This rule adds a flag if the ratio of non-ASCII to ASCII characters
    is too high.
    """
    if below_ascii_threshold(proportion_ascii(event.title)):
        yield AddMetadataFlag(
            creator=creator,
            flag_type=MetadataFlag.FlagTypes.CHARACTER_SET,
            flag_data={'ascii': proportion_ascii(event.title)},
            field='title',
            comment='Possible excessive use of non-ASCII characters.'
        )


@SetAbstract.bind(condition=lambda *a: not system_event(*a))
def check_abstract_ascii(event: SetAbstract, before: Submission,
                         after: Submission, creator: Agent,
                         task_id: Optional[str] = None,
                         **kwargs) -> Iterable[Event]:
    """
    Screen for possible abuse of unicode in abstracts.

    We support unicode characters in abstracts, but this can get out of hand.
    This rule adds a flag if the ratio of non-ASCII to ASCII characters
    is too high.
    """
    if below_ascii_threshold(proportion_ascii(event.abstract)):
        yield AddMetadataFlag(
            creator=creator,
            flag_type=MetadataFlag.FlagTypes.CHARACTER_SET,
            flag_data={'ascii': proportion_ascii(event.abstract)},
            field='abstract',
            description='Possible excessive use of non-ASCII characters.'
        )


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


def above_similarity_threshold(similarity: float) -> bool:
    """Whether or not a Jaccard similarity is above the threshold."""
    threshold = get_application_config().get('TITLE_SIMILARITY_THRESHOLD', 0.7)
    return similarity > threshold


def window() -> datetime:
    """Get the time window for possible duplicate submissions."""
    days = get_application_config().get('TITLE_SIMILARITY_WINDOW', 3*365/12)
    return datetime.now() - timedelta(days)
