"""Events/commands related to quality assurance."""

from typing import Optional, Union

from dataclasses import field

from .util import dataclass
from .event import Event
from ..flag import Flag, ContentFlag, MetadataFlag, UserFlag
from ..submission import Submission, SubmissionMetadata
from ...exceptions import InvalidEvent


@dataclass()
class AddFlag(Event):
    flag_data: Optional[Union[int, str, float, dict, list]]
    comment: Optional[str]

    def validate(self, submission: Submission) -> None:
        raise InvalidEvent(self, "Invoke a child event instead")

    def project(self, submission: Submission) -> Submission:
        return submission


@dataclass()
class RemoveFlag(Event):
    flag_id: Optional[str] = field(default=None)

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
    flag_type: ContentFlag.FlagTypes

    def validate(self, submission: Submission) -> None:
        if self.flag_type not in ContentFlag.FlagTypes:
            raise InvalidEvent(self, f"Unknown content flag: {self.flag_type}")

    def project(self, submission: Submission) -> Submission:
        submission.flags[self.event_id] = ContentFlag(
            event_id=self.event_id,
            created=self.created,
            creator=self.creator,
            proxy=self.proxy,
            flag_type=self.flag_type,
            flag_data=self.flag_data
        )
        return submission


@dataclass()
class AddMetadataFlag(AddFlag):
    flag_type: MetadataFlag.FlagTypes
    field: str

    def validate(self, submission: Submission) -> None:
        if self.flag_type not in MetadataFlag.FlagTypes:
            raise InvalidEvent(self, f"Unknown meta flag: {self.flag_type}")
        if not hasattr(SubmissionMetadata, self.field):
            raise InvalidEvent(self, "Not a valid metadata field")

    def project(self, submission: Submission) -> Submission:
        submission.flags[self.event_id] = MetadataFlag(
            event_id=self.event_id,
            created=self.created,
            creator=self.creator,
            proxy=self.proxy,
            flag_type=self.flag_type,
            flag_data=self.flag_data
        )
        return submission


@dataclass()
class AddUserFlag(AddFlag):
    flag_type: UserFlag.FlagTypes

    def validate(self, submission: Submission) -> None:
        if self.flag_type not in MetadataFlag.FlagTypes:
            raise InvalidEvent(self, f"Unknown user flag: {self.flag_type}")

    def project(self, submission: Submission) -> Submission:
        submission.flags[event.event_id] = UserFlag(
            event_id=self.event_id,
            created=self.created,
            creator=self.creator,
            flag_type=self.flag_type,
            flag_data=self.flag_data
        )
        return submission


@dataclass()
class AddHold:
    pass
