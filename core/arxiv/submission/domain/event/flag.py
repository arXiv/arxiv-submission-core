"""Events/commands related to quality assurance."""

from typing import Optional, Union

from dataclasses import field

from .util import dataclass
from .event import Event
from ..flag import Flag, ContentFlag, MetadataFlag, UserFlag
from ..submission import Submission, SubmissionMetadata, Hold
from ...exceptions import InvalidEvent


@dataclass()
class AddFlag(Event):
    """Base class for flag events; not for direct use."""

    NAME = "add flag"
    NAMED = "flag added"

    flag_data: Optional[Union[int, str, float, dict, list]] \
        = field(default=None)
    comment: Optional[str] = field(default=None)

    def validate(self, submission: Submission) -> None:
        """Not implemented."""
        raise NotImplementedError("Invoke a child event instead")

    def project(self, submission: Submission) -> Submission:
        """Not implemented."""
        raise NotImplementedError("Invoke a child event instead")


@dataclass()
class RemoveFlag(Event):
    """Remove a :class:`.domain.Flag` from a submission."""

    NAME = "remove flag"
    NAMED = "flag removed"

    flag_id: Optional[str] = field(default=None)
    """This is the ``event_id`` of the event that added the flag."""

    def validate(self, submission: Submission) -> None:
        """Verify that the flag exists."""
        if self.flag_id not in submission.flags:
            raise InvalidEvent(self, f"Unknown flag: {self.flag_id}")

    def project(self, submission: Submission) -> Submission:
        """Remove the flag from the submission."""
        submission.flags.pop(self.flag_id)
        return submission


@dataclass()
class AddContentFlag(AddFlag):
    """Add a :class:`.domain.ContentFlag` related to content."""

    NAME = "add content flag"
    NAMED = "content flag added"

    flag_type: Optional[ContentFlag.FlagTypes] = None

    def validate(self, submission: Submission) -> None:
        """Verify that we have a known flag."""
        if self.flag_type not in ContentFlag.FlagTypes:
            raise InvalidEvent(self, f"Unknown content flag: {self.flag_type}")

    def project(self, submission: Submission) -> Submission:
        """Add the flag to the submission."""
        submission.flags[self.event_id] = ContentFlag(
            event_id=self.event_id,
            created=self.created,
            creator=self.creator,
            proxy=self.proxy,
            flag_type=self.flag_type,
            flag_data=self.flag_data,
            comment=self.comment
        )
        return submission


@dataclass()
class AddMetadataFlag(AddFlag):
    """Add a :class:`.domain.MetadataFlag` related to the metadata."""

    NAME = "add metadata flag"
    NAMED = "metadata flag added"

    flag_type: Optional[MetadataFlag.FlagTypes] = field(default=None)
    field: Optional[str] = field(default=None)
    """Name of the metadata field to which the flag applies."""

    def validate(self, submission: Submission) -> None:
        """Verify that we have a known flag and metadata field."""
        if self.flag_type not in MetadataFlag.FlagTypes:
            raise InvalidEvent(self, f"Unknown meta flag: {self.flag_type}")
        if not hasattr(SubmissionMetadata, self.field):
            raise InvalidEvent(self, "Not a valid metadata field")

    def project(self, submission: Submission) -> Submission:
        """Add the flag to the submission."""
        submission.flags[self.event_id] = MetadataFlag(
            event_id=self.event_id,
            created=self.created,
            creator=self.creator,
            proxy=self.proxy,
            flag_type=self.flag_type,
            flag_data=self.flag_data,
            comment=self.comment
        )
        return submission


@dataclass()
class AddUserFlag(AddFlag):
    """Add a :class:`.domain.UserFlag` related to the submitter."""

    NAME = "add user flag"
    NAMED = "user flag added"

    flag_type: Optional[UserFlag.FlagTypes] = field(default=None)

    def validate(self, submission: Submission) -> None:
        """Verify that we have a known flag."""
        if self.flag_type not in MetadataFlag.FlagTypes:
            raise InvalidEvent(self, f"Unknown user flag: {self.flag_type}")

    def project(self, submission: Submission) -> Submission:
        """Add the flag to the submission."""
        submission.flags[self.event_id] = UserFlag(
            event_id=self.event_id,
            created=self.created,
            creator=self.creator,
            flag_type=self.flag_type,
            flag_data=self.flag_data,
            comment=self.comment
        )
        return submission


@dataclass()
class AddHold(Event):
    """Add a hold to a submission."""

    NAME = "add hold"
    NAMED = "hold added"

    hold_type: str = field(default_factory=str)
    hold_reason: Optional[str] = field(default_factory=list)

    def validate(self, submission: Submission) -> None:
        pass

    def project(self, submission: Submission) -> Submission:
        """Add the hold to the submission."""
        submission.holds[self.event_id] = Hold(
            event_id=self.event_id,
            created=self.created,
            creator=self.creator,
            hold_type=self.hold_type,
            hold_reason=self.hold_reason
        )
        return submission
