#!/usr/bin/env python3

"""
Job model, used to for job management
"""

# Standard imports
import typing
from typing import (
    List,
    Optional,
    ClassVar,
    TypedDict,
    Union,
    Dict,
    Any,
    Self,
)
from os import environ
from datetime import datetime

# API imports
from dyntastic import Dyntastic
from fastapi.encoders import jsonable_encoder
from pydantic import Field, BaseModel, ConfigDict, model_validator

# Layer imports
from fastapi_tools import QueryPaginatedResponse

# Local imports
from ..globals import EVENT_PREFIX
from ..utils import (
    to_camel, get_ulid,
    get_deploy_status_endpoint_url, get_ulid_from_datetime
)
from . import (
    CloudFormationStackStatusType,
    CloudFormationStackStatusWithCfnOutputType,
    CloudFormationStackStatusWithoutCfnOutputType
)


class EventResponseWithCfnOutputDict(TypedDict):
    orcabusId: str
    eventId: str
    stackName: str
    status: CloudFormationStackStatusWithCfnOutputType
    modificationTimestamp: datetime
    gitCommitId: str


class EventResponseWithoutCfnOutputDict(TypedDict):
    orcabusId: str
    eventId: str
    stackName: str
    status: CloudFormationStackStatusWithoutCfnOutputType
    modificationTimestamp: datetime


EventResponseDict = Union[EventResponseWithCfnOutputDict, EventResponseWithoutCfnOutputDict]


class EventBase(BaseModel):
    event_id: str
    stack_name: str
    status: CloudFormationStackStatusType
    modification_timestamp: datetime


class EventOrcabusId(BaseModel):
    # fqr.ABCDEFGHIJKLMNOP
    # BCLConvert Metadata attributes
    orcabus_id: str = Field(default_factory=lambda: "ULID.PLACEHOLDER")


class EventWithId(EventBase, EventOrcabusId):
    """
    Order class inheritance this way to ensure that the id field is set first
    """
    git_commit_id: Optional[str] = None

    @model_validator(mode='after')
    def update_ulid(self) -> Self:
        if self.orcabus_id == 'ULID.PLACEHOLDER':
            self.orcabus_id = f"{EVENT_PREFIX}.{get_ulid_from_datetime(self.modification_timestamp)}"
        return self


class EventResponse(EventWithId):
    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
    )

    # Set the model_dump method response
    if typing.TYPE_CHECKING:
        def model_dump(self, **kwargs) -> EventResponseDict:
            pass


class EventCreate(EventBase):
    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True
    )

    def model_dump(self, **kwargs) -> 'EventResponseDict':
        return (
            EventResponse(**super().model_dump()).
            model_dump()
        )


class EventData(EventWithId, Dyntastic):
    """
    The job data object
    """
    __table_name__ = environ['DYNAMODB_EVENT_TABLE_NAME']
    __table_host__ = environ['DYNAMODB_HOST']
    __hash_key__ = "orcabus_id"
    __range_key__ = "stack_name"

    # From dictionary
    @classmethod
    def from_dict(cls, **kwargs: Dict[str, Any]) -> Self:
        return cls(
            **kwargs
        )

    # To Dictionary
    def to_dict(self) -> 'EventResponseDict':
        """
        Alternative serialization path to return objects by camel case
        :return:
        """
        # Initialise the model dump
        model_dump = self.model_dump(
            by_alias=True,
            exclude_none=True,
            exclude_unset=True,
        )

        return jsonable_encoder(
            EventResponse(
                **model_dump
            ).model_dump(by_alias=True)
        )


class EventQueryPaginatedResponse(QueryPaginatedResponse):
    """
    ICAv2 Analysis Query Response, includes a list of analyses
    """
    url_placeholder: ClassVar[str] = get_deploy_status_endpoint_url()
    results: List[EventResponseDict]

    @classmethod
    def resolve_url_placeholder(cls, **kwargs) -> str:
        # Get the url placeholder
        return cls.url_placeholder.format()
