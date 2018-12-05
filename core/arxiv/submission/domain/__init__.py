"""Core data structures for the submission and moderation system."""

from .submission import Submission, License, SubmissionMetadata, \
    Classification, Author, Hold, WithdrawalRequest, \
    CrossListClassificationRequest
from .agent import User, System, Client, Agent
from .event import event_factory, Event
