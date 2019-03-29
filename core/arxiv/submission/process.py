from typing import List, Iterable, Callable, TypedDict
import inspect
from functools import wraps
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field

from .domain.event import Event, AddProcessStatus
from .domain.submission import Submission
from .domain.agent import Agent, agent_factory


Trigger = TypedDict('Trigger',  {'event': Event, 'before': Submission,
                                 'after': Submission, 'creator': Agent})
