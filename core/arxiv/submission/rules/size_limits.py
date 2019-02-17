"""Enforces size limit rules."""


from typing import Iterable
from itertools import count
import time

from ..domain.event import Event, AddProcessStatus, ConfirmPreview, \
    AddClassifierResults, AddContentFlag, AddFeature
from ..domain.event.event import Condition
from ..domain.submission import Submission
from ..domain.flag import Flag, ContentFlag
from ..domain.annotation import Feature
from ..domain.agent import Agent, User
from ..domain.process import ProcessStatus
from ..services import classifier, plaintext
from ..tasks import is_async

from arxiv.taxonomy import CATEGORIES, Category
