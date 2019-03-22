"""Core data structures for the submission and moderation system."""

from .submission import Submission, License, SubmissionMetadata, \
    Classification, Author, Hold, WithdrawalRequest, UserRequest, \
    CrossListClassificationRequest, Compilation, SubmissionContent
from .agent import User, System, Client, Agent, agent_factory
from .event import event_factory, Event
from .annotation import Comment
from .proposal import Proposal
