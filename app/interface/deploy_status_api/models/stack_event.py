#!/usr/bin/env python3

"""
Generate the stack event objects

These are a hybrid of stack and event attributes to be written to the database.

These models are also returned when collecting stack summaries
"""

# Standard imports
import typing
from typing import (
    Optional,
    TypedDict,
    Union,
    NotRequired
)
from datetime import datetime

# API imports
from pydantic import BaseModel, ConfigDict

# Local imports
from ..utils import (
    to_camel,
)
from . import (
    CloudFormationStackStatusType,
    CloudFormationStackStatusWithCfnOutputType,
    CloudFormationStackStatusWithoutCfnOutputType
)


class StackEventResponseWithCfnOutputDict(TypedDict):
    stackOrcabusId: str
    stackId: str
    stackName: str
    eventOrcabusId: str
    eventId: str
    status: CloudFormationStackStatusWithCfnOutputType
    modificationTimestamp: datetime
    gitCommitId: NotRequired[str]


class StackEventResponseWithoutCfnOutputDict(TypedDict):
    stackOrcabusId: str
    stackId: str
    stackName: str
    eventOrcabusId: str
    eventId: str
    status: CloudFormationStackStatusWithoutCfnOutputType
    modificationTimestamp: datetime


StackEventResponseDict = Union[StackEventResponseWithCfnOutputDict, StackEventResponseWithoutCfnOutputDict]


class StackPostEvent(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True
    )
    stack_id: str
    stack_name: str
    event_id: str
    git_commit_id: Optional[str] = None
    stack_status: CloudFormationStackStatusType
    modification_timestamp: datetime


class StackEventResponse(StackPostEvent):
    stack_orcabus_id: str
    event_orcabus_id: str

    # Set the model_dump method response
    if typing.TYPE_CHECKING:
        def model_dump(self, **kwargs) -> StackEventResponseDict:
            pass
