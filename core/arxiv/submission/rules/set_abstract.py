"""Things that should happen upon the :class:`.SetAbstract` command."""

from datetime import datetime, timedelta
from typing import Set, List, Tuple, Iterable
from unidecode import unidecode
import string
from functools import lru_cache as memoize
from itertools import chain

from arxiv.base.globals import get_application_config


from ..domain.event import Event, SetAbstract, RemoveFlag, AddMetadataFlag
from ..domain.submission import Submission
from ..domain.annotation import PossibleDuplicate, PossibleMetadataProblem
from ..domain.agent import Agent, User
from ..domain.flag import MetadataFlag, ContentFlag
from ..services import classic
from ..tasks import is_async

from .util import is_ascii, below_ascii_threshold, proportion_ascii
from .generic import system_event


@SetAbstract.bind(condition=lambda *a: not system_event(*a))
def check_abstract_ascii(event: SetAbstract, before: Submission,
                         after: Submission, creator: Agent) -> Iterable[Event]:
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
