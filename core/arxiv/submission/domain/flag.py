"""Data structures related to QA."""

from datetime import datetime
from enum import Enum
from typing import Optional, Union, Type, Dict, Any

from dataclasses import field, dataclass, asdict
from mypy_extensions import TypedDict

from .agent import Agent, agent_factory


PossibleDuplicate = TypedDict('PossibleDuplicate',
                              {'id': int, 'title': str, 'owner': Agent})


@dataclass
class Flag:
    """Base class for flags."""

    class FlagType(Enum):
        pass

    event_id: str
    creator: Agent
    created: datetime
    flag_data: Optional[Union[int, str, float, dict, list]]
    comment: str
    proxy: Optional[Agent] = field(default=None)
    flag_datatype: str = field(default_factory=str)

    def __post_init__(self) -> None:
        """Set derivative fields."""
        self.flag_datatype = self.__class__.__name__
        if self.creator and isinstance(self.creator, dict):
            self.creator = agent_factory(**self.creator)
        if self.proxy and isinstance(self.proxy, dict):
            self.proxy = agent_factory(**self.proxy)


@dataclass
class ContentFlag(Flag):
    """A flag related to the content of the submission."""

    flag_type: Optional['FlagType'] = field(default=None)

    class FlagType(Enum):
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

    flag_type: Optional['FlagType'] = field(default=None)
    field: Optional[str] = field(default=None)

    class FlagType(Enum):
        """Supported metadata flags."""

        POSSIBLE_DUPLICATE_TITLE = 'possible duplicate title'
        LANGUAGE = 'language'
        CHARACTER_SET = 'character_set'


@dataclass
class UserFlag(Flag):
    """A flag related to the submitter."""

    flag_type: Optional['FlagType'] = field(default=None)

    class FlagType(Enum):
        """Supported user flags."""

        RATE = 'rate'


flag_datatypes: Dict[str, Type[Flag]] = {
    'ContentFlag': ContentFlag,
    'MetadataFlag': MetadataFlag,
    'UserFlag': UserFlag
}


def flag_factory(**data: Any) -> Flag:
    cls = flag_datatypes[data.pop('flag_datatype')]
    if not isinstance(data['flag_type'], cls.FlagType):
        data['flag_type'] = cls.FlagType(data['flag_type'])
    return cls(**data)
