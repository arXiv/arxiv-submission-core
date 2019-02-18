"""Events/commands related to quality assurance."""

from typing import Optional, Union

from dataclasses import field

from .util import dataclass
from .event import Event
from ..flag import Flag, ContentFlag, MetadataFlag, UserFlag
from ..submission import Submission, SubmissionMetadata, Hold, Waiver
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
    """Add a :class:`.Hold` to a :class:`.Submission`."""

    NAME = "add hold"
    NAMED = "hold added"

    hold_type: Hold.Type = field(default=Hold.Type.PATCH)
    hold_reason: Optional[str] = field(default_factory=str)

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


@dataclass()
class RemoveHold(Event):
    """Remove a :class:`.Hold` from a :class:`.Submission`."""

    NAME = "remove hold"
    NAMED = "hold removed"

    hold_event_id: str = field(default_factory=str)
    hold_type: Hold.Type = field(default=Hold.Type.PATCH)
    removal_reason: Optional[str] = field(default_factory=str)

    def validate(self, submission: Submission) -> None:
        if self.hold_event_id not in submission.holds:
            raise InvalidEvent(self, "No such hold")

    def project(self, submission: Submission) -> Submission:
        """Remove the hold from the submission."""
        submission.holds.pop(self.event_id)
        return submission


@dataclass()
class AddWaiver(Event):
    """Add a :class:`.Waiver` to a :class:`.Submission`."""

    waiver_type: Hold.Type = field(default=Hold.Type.SOURCE_OVERSIZE)
    waiver_reason: str = field(default_factory=str)

    def validate(self, submission: Submission) -> None:
        pass

    def project(self, submission: Submission) -> Submission:
        """Add the :class:`.Waiver` to the :class:`.Submission`."""
        submission.waivers[self.event_id] = Waiver(
            event_id=self.event_id,
            created=self.created,
            creator=self.creator,
            waiver_type=self.waiver_type,
            waiver_reason=self.waiver_reason
        )
        return submission
