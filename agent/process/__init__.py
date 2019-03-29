"""Processes supported by this application."""

from .base import Process, ProcessType, step, Recoverable, Failed, Retry
from .classification_and_content import \
    RunAutoclassifier, \
    CheckStopwordPercent, \
    CheckStopwordCount
from .email_notifications import SendConfirmationEmail
from .metadata_checks import \
    CheckForSimilarTitles, \
    CheckTitleForUnicodeAbuse, \
    CheckAbstractForUnicodeAbuse
from .reclassification import \
    ProposeReclassification, \
    ProposeCrossListFromPrimaryCategory, \
    AcceptSystemCrossListProposals
from .size_limits import CheckPDFSize, CheckSubmissionSourceSize
