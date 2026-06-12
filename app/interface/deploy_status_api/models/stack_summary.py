# Standard imports
from typing import (
    TypedDict,
    Union,
    NotRequired
)
from datetime import datetime

from . import (
    CloudFormationStackStatusWithCfnOutputType,
    CloudFormationStackStatusWithoutCfnOutputType
)


class StackSummaryResponseWithCfnOutputDict(TypedDict):
    stackId: str
    stackName: str
    status: CloudFormationStackStatusWithCfnOutputType
    modificationTimestamp: datetime
    gitCommitId: NotRequired[str]


class StackSummaryResponseWithoutCfnOutputDict(TypedDict):
    stackId: str
    stackName: str
    status: CloudFormationStackStatusWithoutCfnOutputType
    modificationTimestamp: datetime


StackSummaryResponseDict = Union[StackSummaryResponseWithCfnOutputDict, StackSummaryResponseWithoutCfnOutputDict]
