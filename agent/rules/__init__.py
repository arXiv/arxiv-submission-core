"""
Defines QA rules bound to events.

These are callback routines that are performed either in-thread or
asynchronously by the submission worker when an event is committed. See
:func:`.domain.Event.bind` for mechanics.

Binding callbacks (and registering tasks with :func:`.tasks.is_async`)
relies on decorators; this means that the registration is a side-effect of
importing the module in which they are defined. In other words, it is necessary
that any modules that define rules are imported here.
"""

from typing import Dict, Any
from arxiv.base import logging
from arxiv.submission import Event, Submission
from arxiv.submission.domain.event import \
    SetTitle, \
    SetAbstract, \
    SetUploadPackage, \
    UpdateUploadPackage, \
    ConfirmPreview, \
    FinalizeSubmission, \
    AddFeature, \
    AddClassifierResults, \
    AddProposal

from arxiv.submission.domain.annotation import Feature

from ..domain import Trigger
from .. import process
from ..runner import AsyncProcessRunner
from .base import Rule, REGISTRY, ParamFunc
from .conditions import user_event, system_event, feature_type_is, always
from .params import empty_params, make_params

logger = logging.getLogger(__name__)


def evaluate(event: Event, before: Submission, after: Submission) -> None:
    """Evaluate an event against known rules."""
    for rule in REGISTRY[type(event)]:
        if rule.condition(event, before, after):
            params = rule.params(event, before, after)
            trigger = Trigger(event=event, before=before, after=after,
                              agent=event.creator, params=params)
            process = rule.process(event.submission_id)
            runner = AsyncProcessRunner(process)
            runner.run(trigger)
            logger.info('Event %s on submission %s caused %s with params %s',
                        event.event_id, event.submission_id, process.name,
                        params)


title_params = make_params('TITLE_SIMILARITY_WINDOW',
                           'TITLE_SIMILARITY_THRESHOLD')
reclass_params = make_params('NO_RECLASSIFY_CATEGORIES',
                             'NO_RECLASSIFY_ARCHIVES',
                             'RECLASSIFY_PROPOSAL_THRESHOLD',
                             'AUTO_CROSS_FOR_PRIMARY')
size_params = make_params('UNCOMPRESSED_PACKAGE_MAX', 'COMPRESSED_PACKAGE_MAX')


Rule(ConfirmPreview, user_event, empty_params, process.RunAutoclassifier,
     "Run the autoclassifier when the preview is confirmed by the submitter")
Rule(AddFeature, feature_type_is(Feature.Type.STOPWORD_PERCENT),
     make_params('LOW_STOP_PERCENT'), process.CheckStopwordPercent,
     "Add a flag if the percentage of stopwords is below a threshold value")
Rule(AddFeature, feature_type_is(Feature.Type.STOPWORD_COUNT),
     make_params('LOW_STOP'), process.CheckStopwordCount,
     "Add a flag if the number of stopwords is below a threshold value")
Rule(FinalizeSubmission, always, empty_params, process.SendConfirmationEmail,
     "Send a confirmation e-mail when a submission is finalized")
Rule(SetTitle, user_event, title_params, process.CheckForSimilarTitles,
     "Check for other submissions with similar titles, and add a flag")
Rule(SetTitle, user_event, make_params('METADATA_ASCII_THRESHOLD'),
     process.CheckTitleForUnicodeAbuse,
     "Check the title for excessive non-ASCII characters, and add a flag")
Rule(SetAbstract, user_event, make_params('METADATA_ASCII_THRESHOLD'),
     process.CheckAbstractForUnicodeAbuse,
     "Check the title for excessive non-ASCII characters, and add a flag")
Rule(AddClassifierResults, always, reclass_params,
     process.ProposeReclassification,
     "Evaluate classifier results and propose new classifications")
Rule(FinalizeSubmission, always, reclass_params,
     process.ProposeCrossListFromPrimaryCategory,
     "Propose cross-list categories based on user selected primary category")
Rule(AddProposal, system_event, empty_params,
     process.AcceptSystemCrossListProposals,
     "Accept our own proposals for adding cross-list categories")
Rule(SetUploadPackage, always, size_params, process.CheckSubmissionSourceSize,
     "Check the size of the source when it is created, and add/remove holds")
Rule(UpdateUploadPackage, always, size_params,
     process.CheckSubmissionSourceSize,
     "Check the size of the source when it is updated, and add/remove holds")
Rule(ConfirmPreview, always, make_params('PDF_LIMIT'), process.CheckPDFSize,
     "Check the size of the PDF when the submitter confirms the preview.")
