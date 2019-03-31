"""Data structures related to QA."""

from datetime import datetime
from typing import Optional, Union
from enum import Enum

from mypy_extensions import TypedDict
from dataclasses import field, dataclass, asdict

from .agent import Agent, agent_factory


PossibleDuplicate = TypedDict('PossibleDuplicate',
                              {'id': int, 'title': str, 'owner': Agent})


@dataclass
class Flag:
    """Base class for flags."""

    event_id: str
    creator: Agent
    created: datetime
    flag_type: str
    flag_data: Optional[Union[int, str, float, dict, list]]
    comment: str
    proxy: Optional[Agent] = field(default=None)
    flag_datatype: str = field(default_factory=str)

    def __post_init__(self):
        """Set derivative fields."""
        self.flag_datatype = self.__class__.__name__
        if self.creator and type(self.creator) is dict:
            self.creator = agent_factory(**self.creator)
        if self.proxy and type(self.proxy) is dict:
            self.proxy = agent_factory(**self.proxy)


@dataclass
class ContentFlag(Flag):
    """A flag related to the content of the submission."""

    class Type(Enum):
        """Supported content flags."""

        LOW_STOP = 'low stopwords'
        """Number of stopwords is abnormally low."""
        LOW_STOP_PERCENT = 'low stopword percentage'
        """Frequency of stopwords is abnormally low."""
        LANGUAGE = 'language'
        """Possibly not English language."""
        CHARACTER_SET = 'character set'
        """Possibly excessive use of non-ASCII characters."""
        LINE_NUMBERS = 'line numbers'
        """Content has line numbers."""


@dataclass
class MetadataFlag(Flag):
    """A flag related to the submission metadata."""

    field: Optional[str] = field(default=None)

    class Type(Enum):
        """Supported metadata flags."""

        POSSIBLE_DUPLICATE_TITLE = 'possible duplicate title'
        LANGUAGE = 'language'
        CHARACTER_SET = 'character_set'


@dataclass
class UserFlag(Flag):
    """A flag related to the submitter."""

    class Type(Enum):
        """Supported user flags."""

        RATE = 'rate'


flag_datatypes = {
    'ContentFlag': ContentFlag,
    'MetadataFlag': MetadataFlag,
    'UserFlag': UserFlag
}


def flag_factory(**data) -> Flag:
    cls = flag_datatypes[data.pop('flag_datatype')]
    if not isinstance(data['flag_type'], cls.Type):
        data['flag_type'] = cls.Type(data['flag_type'])
    return cls(**data)
