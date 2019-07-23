"""
Processes supported by this application.

A **process** is a set of one or more related steps that should be carried out
in order, usually focusing on a single submission. Steps are small units of
work with a specific objective, such as getting a resource from a service or
applying a policy. If a step in a process fails, the subsequent steps are not
carried out. Examples of processes include running the autoclassifier and
annotating a submission with the results, and placing submissions on hold when
they exceed size limits.

Processes are implemented by defining a class that inherits from
:class:`.Process`\.
"""

from .base import Process, ProcessType, step, Recoverable, Failed, Retry
from .classification_and_content import \
    PlainTextExtraction, \
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
