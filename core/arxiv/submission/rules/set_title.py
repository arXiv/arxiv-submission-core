"""Rules for the :class:`.SetTitle` command."""

from datetime import datetime, timedelta
from typing import Set, List, Tuple, Iterable
from unidecode import unidecode
import string
from functools import lru_cache
from itertools import chain

from arxiv.base.globals import get_application_config


from ..domain.event import Event, SetTitle, AddAnnotation, RemoveAnnotation
from ..domain.submission import Submission
from ..domain.annotation import PossibleDuplicate, PossibleMetadataProblem
from ..domain.agent import Agent, User
from ..services import classic
from ..tasks import is_async

from .generic import system_event

STOPWORDS = set('a,an,and,as,at,by,for,from,in,of,on,s,the,to,with,is,was,if,'
                'then,that,these,those,them,thus'.split(','))

REMOVE_PUNCTUATION = str.maketrans(string.punctuation,
                                   ' '*len(string.punctuation))
"""Translator that converts punctuation characters into single spaces."""


@SetTitle.bind(condition=lambda *a: not system_event(*a))
@is_async
def check_for_similar_titles(event: SetTitle, before: Submission,
                             after: Submission, creator: Agent) \
        -> Iterable[Event]:
    """
    Check for other submissions with very similar titles.

    Query Submission (``arXiv_submissions`` table) for submissions with titles
    that were created within the last 3 months.

    Select previous matches for this submission id, and delete them -- from
    SubmissionNearDuplicates (``arXiv_submission_near_duplicates`` table)

    Get a Jaccard similarity indexer function
    (arXiv::Submit::Jaccard::JaccardIndex->make_jaccard_indexer)

    Among the results of the arXiv_submissions query, find submissions that are
    more similar than some threshold, skipping any user-deleted submissions.

    For each match > threshold, add a new duplicate record to the
    ``arXiv_submission_near_duplicates`` table with its score, and create
    corresponding entries in the admin log (``arXiv_admin_log`` table).
    """
    # If the title has no tokens, there is nothing to do.
    if not tokenized(event.title):
        return

    candidates: List[Tuple[int, str, Agent]] = classic.get_titles(window())
    remove = (RemoveAnnotation(creator=creator, annotation_id=annotation_id)
              for annotation_id, annotation in after.annotations.items()
              if isinstance(annotation, PossibleDuplicate))

    add = (AddAnnotation(creator=creator,
                         annotation=PossibleDuplicate(
                            creator=creator,
                            matching_id=ident,
                            matching_title=title,
                            matching_owner=submitter))
           for ident, title, submitter in candidates
           if above_similarity_threshold(jaccard(event.title, title)))
    return chain(remove, add)


@SetTitle.bind(condition=lambda *a: not system_event(*a))
def check_for_excessive_unicode(event: SetTitle, before: Submission,
                                after: Submission, creator: Agent) \
        -> Iterable[Event]:
    """
    Screen for possible abuse of unicode in titles.

    We support unicode characters in titles, but this can get out of hand.
    This rule adds an annotation if the ratio of non-ASCII to ASCII characters
    is too high.
    """
    if below_ascii_threshold(proportion_ascii(event.title)):
        return [AddAnnotation(
            creator=creator,
            annotation=PossibleMetadataProblem(
                creator=creator,
                field_name='title',
                description='Possible excessive use of non-ASCII characters.'
            )
        )]
    return []


def proportion_ascii(phrase: str) -> float:
    """Calculate the proportion of a string comprised of ASCII characters."""
    return len([c for c in phrase if is_ascii(c)])/len(phrase)


@lru_cache(maxsize=1028)    # Memoized
def normalize(phrase: str) -> str:
    """Prepare a phrase for tokenization."""
    return unidecode(phrase.lower()).translate(REMOVE_PUNCTUATION)


@lru_cache(maxsize=2056)    # Memoized
def tokenized(phrase: str) -> Set[str]:
    """Split a phrase into tokens and remove stopwords."""
    return set(normalize(phrase).split()) - STOPWORDS


def intersection(phrase_a: str, phrase_b: str) -> int:
    """The number tokens shared by two phrases."""
    return len(tokenized(phrase_a) & tokenized(phrase_b))


def union(phrase_a: str, phrase_b: str) -> int:
    """The total number tokens in two phrases."""
    return len(tokenized(phrase_a) | tokenized(phrase_b))


def jaccard(phrase_a: str, phrase_b: str) -> float:
    """The Jaccard similarity of two phrases."""
    return intersection(phrase_a, phrase_b) / union(phrase_a, phrase_b)


def above_similarity_threshold(similarity: float) -> bool:
    """Whether or not a Jaccard similarity is above the threshold."""
    threshold = get_application_config().get('TITLE_SIMILARITY_THRESHOLD', 0.7)
    return similarity > threshold


def below_ascii_threshold(proportion: float) -> bool:
    """Whether or not the proportion of ASCII characters is too low."""
    threshold = get_application_config().get('TITLE_ASCII_THRESHOLD', 0.5)
    return proportion < threshold


def window() -> datetime:
    """Get the time window for possible duplicate submissions."""
    days = get_application_config().get('TITLE_SIMILARITY_WINDOW', 3*365/12)
    return datetime.now() - timedelta(days)


@lru_cache(maxsize=1028)
def is_ascii(string: str) -> bool:
    """Determine whether or not a string is ASCII."""
    try:
        bytes(string, encoding='ascii')
        return True
    except UnicodeEncodeError:
        return False
