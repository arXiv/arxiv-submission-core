"""Core data structures for the submission and moderation system."""

from .submission import Submission, License, SubmissionMetadata, \
    Classification, Author
from .agent import User, System, Client, Agent
from .event import event_factory, Event
