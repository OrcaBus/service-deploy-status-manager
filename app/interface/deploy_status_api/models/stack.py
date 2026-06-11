#!/usr/bin/env python3

"""
Docs for stack

Stack object contains the following fields:
* orcabusId
* stackId
* stackName
"""


# Standard imports
import typing
from typing import (
    List,
    Self,
    ClassVar,
    TypedDict,
    Union,
    Any,
    Dict,
)
from os import environ
from datetime import datetime

# API imports
from dyntastic import Dyntastic
from fastapi.encoders import jsonable_encoder
from pydantic import Field, BaseModel, ConfigDict

# Layer imports
from fastapi_tools import QueryPaginatedResponse

# Local imports
from ..globals import CLOUD_FORMATION_STACK_PREFIX
from ..utils import (
    to_camel, get_ulid,
    get_deploy_status_endpoint_url
)


class StackResponseDict(TypedDict):
    orcabusId: str
    stackId: str
    latestEventId: str
    stackName: str

class StackBase(BaseModel):
    stack_id: str
    stack_name: str
    latest_event_id: str


class StackOrcabusId(BaseModel):
    # fqr.ABCDEFGHIJKLMNOP
    # BCLConvert Metadata attributes
    orcabus_id: str = Field(default_factory=lambda: f"{CLOUD_FORMATION_STACK_PREFIX}.{get_ulid()}")


class StackOrcabusWithId(StackBase, StackOrcabusId):
    """
    Order class inheritance this way to ensure that the id field is set first
    """


class StackResponse(StackOrcabusWithId):
    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
    )

    # Set the model_dump method response
    if typing.TYPE_CHECKING:
        def model_dump(self, **kwargs) -> StackResponseDict:
            pass


class StackCreate(StackBase):
    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True
    )

    def model_dump(self, **kwargs) -> 'StackResponseDict':
        return (
            StackResponse(**super().model_dump()).
            model_dump()
        )


class StackData(StackOrcabusWithId, Dyntastic):
    """
    The job data object
    """
    __table_name__ = environ['DYNAMODB_STACK_TABLE_NAME']
    __table_host__ = environ['DYNAMODB_HOST']
    __hash_key__ = "orcabus_id"

    # From dictionary
    @classmethod
    def from_dict(cls, **kwargs: Dict[str, Any]) -> Self:
        return cls(
            **kwargs
        )

    # To Dictionary
    def to_dict(self) -> 'StackResponseDict':
        """
        Alternative serialization path to return objects by camel case
        :return:
        """
        # Initialise the model dump
        model_dump = self.model_dump(
            by_alias=True,
            exclude_none=True,
            exclude_unset=True
        )

        return jsonable_encoder(
            StackResponse(
                **model_dump
            ).model_dump(by_alias=True)
        )


class StackQueryPaginatedResponse(QueryPaginatedResponse):
    """
    ICAv2 Analysis Query Response, includes a list of analyses
    """
    url_placeholder: ClassVar[str] = get_deploy_status_endpoint_url()
    results: List[StackResponseDict]

    @classmethod
    def resolve_url_placeholder(cls, **kwargs) -> str:

        # Get the url placeholder
        return cls.url_placeholder.format()
