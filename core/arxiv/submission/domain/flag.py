"""Data structures related to QA."""

from datetime import datetime
from typing import Optional, Union
from enum import Enum

from mypy_extensions import TypedDict
from dataclasses import field, dataclass

from .agent import Agent
from .annotation import Annotation


PossibleDuplicate = TypedDict('PossibleDuplicate',
                              {'id': int, 'title': str, 'owner': Agent})


@dataclass
class Flag(Annotation):
    event_id: str
    flag_type: str
    flag_data: Optional[Union[int, str, float, dict, list]]
    description: str


@dataclass
class ContentFlag(Flag):
    class FlagTypes(Enum):
        LOW_STOP = 'low stopwords'
        LOW_STOP_PERCENT = 'low stopword percentage'
        LANGUAGE = 'language'
        CHARACTER_SET = 'character_set'


@dataclass
class MetadataFlag(Flag):
    class FlagTypes(Enum):
        POSSIBLE_DUPLICATE_TITLE = 'possible duplicate title'
        LANGUAGE = 'language'
        CHARACTER_SET = 'character_set'


@dataclass
class UserFlag(Flag):
    class FlagTypes(Enum):
        RATE = 'rate'
