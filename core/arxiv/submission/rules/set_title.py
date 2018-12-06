from datetime import datetime, timedelta
from typing import Set, List, Tuple
from unidecode import unidecode

from .bind import bind_event
from ..domain.event import SetTitle, AddAnnotation
from ..domain.submission import Submission
from ..domain.annotation import PossibleDuplicate
from ..domain.agent import Agent, User
from ..services import classic


STOPWORDS = set('a,an,and,as,at,by,for,from,in,of,on,s,the,to,with'.split(','))

_tok_memo = {}


def tokenized(phrase: str) -> Set[str]:
    if phrase not in _tok_memo:
        _tok_memo[phrase] = set(unidecode(phrase.lower()).split()) - STOPWORDS
    return _tok_memo[phrase]


def intersection(phrase_a: str, phrase_b: str) -> int:
    return len(tokenized(phrase_a) & tokenized(phrase_b))


def union(phrase_a: str, phrase_b: str) -> int:
    return len(tokenized(phrase_a) | tokenized(phrase_b))


def jaccard(phrase_a: str, phrase_b: str) -> float:
    return intersection(phrase_a, phrase_b) / union(phrase_a, phrase_b)


# Check for other submissions with very similar titles.
# Query Submission (``arXiv_submissions`` table) for submissions with titles
# that were created within the last 3 months.

# Select previous matches for this submission id, and delete them -- from
# SubmissionNearDuplicates (``arXiv_submission_near_duplicates`` table)

# Get a Jaccard similarity indexer function
# (arXiv::Submit::Jaccard::JaccardIndex->make_jaccard_indexer)

# Among the results of the arXiv_submissions query, find submissions that are
# more similar than some threshold, skipping any user-deleted submissions.

# For each match > threshold, add a new duplicate record to the
# ``arXiv_submission_near_duplicates`` table with its score, and create
# corresponding entries in the admin log (``arXiv_admin_log`` table).


@bind_event(SetTitle)
def check_for_similar_titles(event: SetTitle, before: Submission,
                             after: Submission, creator: Agent) -> List[Event]:
    """."""
    if not tokenized(event.title):
        return
    threshold = 0.7     # TODO: this needs to be configurable.
    time_window = datetime.now() - timedelta(months=3)
    candidates: List[Tuple[int, str, Agent]] = classic.get_titles(
        with_terms=tokenized(event.title),
        since=time_window
    )
    return (AddAnnotation(creator=creator,
                          annotation=PossibleDuplicate(
                            matching_id=ident,
                            matching_title=title,
                            matching_owner=submitter))
            for ident, title, submitter in candidates
            if jaccard(event.title, title) > threshold)
