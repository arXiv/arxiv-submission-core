"""
Submission event rules.

A **rule** defines the circumstances under which a process should be carried
out. Specifically, a rule is associated with a particular type of event, and a
function that determines whether the process should be carried out based on the
event properties and/or the state of the submission.

Rules are implemented by instantiating :class:`.Rule` in this module.
"""

from typing import Dict, Any, Iterable, Tuple
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
from .base import Rule, REGISTRY, ParamFunc
from .conditions import is_user_event, is_system_event, is_feature_type, \
    is_always
from .params import empty_params, make_params

logger = logging.getLogger(__name__)
Params = Dict[str, Any]


def evaluate(event: Event, before: Submission, after: Submission) \
        -> Iterable[Tuple[process.Process, Params]]:
    """
    Evaluate an event against known rules.

    Parameters
    ----------
    event : :class:`.domain.Event`
        The event to evaluate.
    before : :class:`.domain.submission.Submission`
        The state of the submission prior to the event.
    after : :class:`.domain.submission.Submission`
        The state of the submission after the event.

    Returns
    -------
    iterable
        Each item is a two-tuple, composed of a triggered :class:`.Process`
        instance and the configuration parameters with which it should be run.

    """
    logger.debug('evaluate event %s (%s)', event.event_id, type(event))
    for rule in REGISTRY[type(event)]:
        if rule.condition(event, before, after):
            logger.debug('event %s matches rule %s', event.event_id, rule.name)
            params = rule.params(event, before, after)
            process = rule.process(event.submission_id)
            yield process, params


title_params = make_params('TITLE_SIMILARITY_WINDOW',
                           'TITLE_SIMILARITY_THRESHOLD')
reclass_params = make_params('NO_RECLASSIFY_CATEGORIES',
                             'NO_RECLASSIFY_ARCHIVES',
                             'RECLASSIFY_PROPOSAL_THRESHOLD',
                             'AUTO_CROSS_FOR_PRIMARY')
size_params = make_params('UNCOMPRESSED_PACKAGE_MAX_BYTES',
                          'COMPRESSED_PACKAGE_MAX_BYTES')


Rule(ConfirmPreview, is_user_event, empty_params, process.RunAutoclassifier,
     "Run the autoclassifier when the preview is confirmed by the submitter")
Rule(AddFeature, is_feature_type(Feature.Type.STOPWORD_PERCENT),
     make_params('LOW_STOP_PERCENT'), process.CheckStopwordPercent,
     "Add a flag if the percentage of stopwords is below a threshold value")
Rule(AddFeature, is_feature_type(Feature.Type.STOPWORD_COUNT),
     make_params('LOW_STOP'), process.CheckStopwordCount,
     "Add a flag if the number of stopwords is below a threshold value")
Rule(FinalizeSubmission, is_always, empty_params,
     process.SendConfirmationEmail,
     "Send a confirmation e-mail when a submission is finalized")
Rule(SetTitle, is_user_event, title_params, process.CheckForSimilarTitles,
     "Check for other submissions with similar titles, and add a flag")
Rule(SetTitle, is_user_event, make_params('METADATA_ASCII_THRESHOLD'),
     process.CheckTitleForUnicodeAbuse,
     "Check the title for excessive non-ASCII characters, and add a flag")
Rule(SetAbstract, is_user_event, make_params('METADATA_ASCII_THRESHOLD'),
     process.CheckAbstractForUnicodeAbuse,
     "Check the title for excessive non-ASCII characters, and add a flag")
Rule(AddClassifierResults, is_always, reclass_params,
     process.ProposeReclassification,
     "Evaluate classifier results and propose new classifications")
Rule(FinalizeSubmission, is_always, reclass_params,
     process.ProposeCrossListFromPrimaryCategory,
     "Propose cross-list categories based on user selected primary category")
Rule(AddProposal, is_system_event, empty_params,
     process.AcceptSystemCrossListProposals,
     "Accept our own proposals for adding cross-list categories")
Rule(SetUploadPackage, is_always, size_params,
     process.CheckSubmissionSourceSize,
     "Check the size of the source when it is created, and add/remove holds")
Rule(UpdateUploadPackage, is_always, size_params,
     process.CheckSubmissionSourceSize,
     "Check the size of the source when it is updated, and add/remove holds")
Rule(ConfirmPreview, is_always, make_params('PDF_LIMIT_BYTES'),
     process.CheckPDFSize,
     "Check the size of the PDF when the submitter confirms the preview.")

Rule(SetUploadPackage, is_always, empty_params, process.CopySourceToLegacy,
     "Copy the source package to the legacy system when it is uploaded.")
Rule(UpdateUploadPackage, is_always, empty_params, process.CopySourceToLegacy,
     "Copy the source package to the legacy system when it is updated.")
Rule(ConfirmPreview, is_always, empty_params, process.CopyPDFPreviewToLegacy,
     "Copy the PDF preview to the legacy system when it is confirmed.")