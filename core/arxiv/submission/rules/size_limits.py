"""Enforces size limit rules."""

from typing import Iterable, Union, Optional
from itertools import count
import time

from ..domain.event import Event, SetUploadPackage, UpdateUploadPackage, \
    AddHold, RemoveHold, AddProcessStatus
from ..domain.event.event import Condition
from ..domain.submission import Submission, SubmissionContent, Hold
from ..domain.flag import Flag, ContentFlag
from ..domain.annotation import Feature
from ..domain.agent import Agent, User
from ..domain.process import ProcessStatus
from ..services import plaintext, compiler
from ..tasks import is_async
from ..auth import get_system_token, get_compiler_scopes

from arxiv.taxonomy import CATEGORIES, Category

PackageEvent = Union[SetUploadPackage, UpdateUploadPackage]


COMPRESSED_PACKAGE_MAX = 6_000_000
UNCOMPRESSED_PACKAGE_MAX = 18_000_000
PDF_LIMIT = 15_000_000
"""The maximum size of the resulting PDF."""


@SetUploadPackage.bind(lambda *args, **kwargs: True)    # Always check.
def check_sizes_on_new_source(event: SetUploadPackage, before: Submission,
                              after: Submission, creator: Agent,
                              task_id: Optional[str] = None,
                              **kwargs) -> Iterable[Event]:
    """When a new source package is attached, check for oversize source."""
    return _check_sizes(event, before, after, creator, task_id, **kwargs)


@UpdateUploadPackage.bind(lambda *args, **kwargs: True)    # Always check.
def check_sizes_on_update_source(event: UpdateUploadPackage,
                                 before: Submission, after: Submission,
                                 creator: Agent, task_id: Optional[str] = None,
                                 **kwargs) -> Iterable[Event]:
    """When a source package is updated, check for oversize source."""
    return _check_sizes(event, before, after, creator, task_id, **kwargs)


def pdf_is_compiled(event: Event, *args, **kwargs) -> bool:
    """Condition that the compilation process has finished."""
    return event.process is ProcessStatus.Process.COMPILATION \
        and event.status is ProcessStatus.Status.SUCCEEDED


@AddProcessStatus.bind(pdf_is_compiled)
@is_async
def check_pdf_size(event: AddProcessStatus, before: Submission,
                   after: Submission, creator: Agent,
                   task_id: Optional[str] = None,
                   **kwargs) -> Iterable[Event]:
    """When a PDF is compiled, check for oversize."""
    upload_id, checksum, fmt = compiler.split_task_id(event.identifier)
    token = get_system_token(__name__, event.creator,
                             get_compiler_scopes(event.identifier))
    stat = compiler.Compiler.get_status(upload_id, checksum, token, fmt)
    msg = "PDF is %i bytes" % stat.size_bytes
    if stat.size_bytes > PDF_LIMIT:
        if Hold.Type.PDF_OVERSIZE in after.hold_types:
            return      # Already on hold for this reason; nothing to do.
        yield AddHold(creator=creator, hold_type=Hold.Type.PDF_OVERSIZE,
                      hold_reason=msg)
    else:   # If the submission is on hold due to oversize, remove the hold.
        for hold_event_id, hold in after.holds.items():
            if hold.hold_type is Hold.Type.PDF_OVERSIZE:
                yield RemoveHold(creator=creator, hold_event_id=hold_event_id,
                                 hold_type=Hold.Type.PDF_OVERSIZE,
                                 removal_reason=msg)


def _check_sizes(event: PackageEvent, before: Submission,
                 after: Submission, creator: Agent,
                 task_id: Optional[str] = None,
                 **kwargs) -> Iterable[Event]:
    """Perform the source size check procedure."""
    content = after.source_content
    source_is_oversize = (content.uncompressed_size > UNCOMPRESSED_PACKAGE_MAX
                          or content.compressed_size > COMPRESSED_PACKAGE_MAX)
    msg = "%i bytes; %i bytes compressed" % (content.uncompressed_size,
                                             content.compressed_size)
    if source_is_oversize:
        if Hold.Type.SOURCE_OVERSIZE in after.hold_types:
            return      # Already on hold for this reason; nothing to do.
        yield AddHold(creator=creator, hold_type=Hold.Type.SOURCE_OVERSIZE,
                      hold_reason=msg)
    else:   # If the submission is on hold due to oversize, remove the hold.
        for hold_event_id, hold in after.holds.items():
            if hold.hold_type is Hold.Type.SOURCE_OVERSIZE:
                yield RemoveHold(creator=creator, hold_event_id=hold_event_id,
                                 hold_type=Hold.Type.SOURCE_OVERSIZE,
                                 removal_reason=msg)
