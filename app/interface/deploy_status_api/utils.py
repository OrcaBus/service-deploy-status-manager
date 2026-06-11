#!/usr/bin/env python

# Imports
import json
import re
from os import environ
import ulid
import boto3
import typing
from datetime import datetime, UTC

from dyntastic import A
from pydantic.alias_generators import (
    to_snake as pydantic_to_snake,
    to_camel as pydantic_to_camel
)

from .globals import (
    ORCABUS_ULID_REGEX_MATCH,
    CLOUD_FORMATION_STACK_PREFIX,
    EVENT_PREFIX, UUID4_REGEX_MATCH_STR
)

if typing.TYPE_CHECKING:
    from .models.stack_event import StackPostEvent
    from .models import CloudFormationStackStatusType
    from mypy_boto3_cloudformation import CloudFormationClient

def get_ulid() -> str:
    return ulid.new().str


def get_ulid_from_datetime(datetime_obj: datetime) -> str:
    return ulid.from_timestamp(datetime_obj.timestamp()).str


def is_orcabus_ulid(query: str) -> bool:
    """
    Matches xxx.<ULID> pattern
    :return:
    """
    return ORCABUS_ULID_REGEX_MATCH.match(query) is not None


async def sanitise_stack_id(stack_id: str) -> str:
    if is_orcabus_ulid(stack_id):
        return stack_id
    elif ORCABUS_ULID_REGEX_MATCH.match(f"{CLOUD_FORMATION_STACK_PREFIX}.{stack_id}"):
        return f"{CLOUD_FORMATION_STACK_PREFIX}.{stack_id}"
    if re.compile(UUID4_REGEX_MATCH_STR).match(stack_id):
        return get_stack_orcabus_id_from_cfn_stack_id(stack_id)
    raise ValueError(f"Invalid stack id '{stack_id}'")


async def sanitise_event_orcabus_id(event_id: str) -> str:
    if is_orcabus_ulid(event_id):
        return event_id
    elif ORCABUS_ULID_REGEX_MATCH.match(f"{EVENT_PREFIX}.{event_id}"):
        return f"{EVENT_PREFIX}.{event_id}"
    raise ValueError(f"Invalid event analysis id '{event_id}'")


async def sanitise_status(status: 'CloudFormationStackStatusType') -> str:
    return status


def datetime_to_isodate(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def datetime_to_hf_format(dt: datetime) -> str:
    return f"{str(int(dt.strftime("%d")))} {dt.strftime("%b")}, {dt.strftime("%Y")}"


def datetime_to_isoformat(dt: datetime) -> str:
    return dt.isoformat(sep="T", timespec="seconds").replace("+00:00", "Z")


def to_snake(s: str) -> str:
    # Pydantic adds an underscore between a lowercase letter and a digit
    # We want to remove this underscore
    return re.sub(r'([a-z])_([0-9])', lambda m: f'{m.group(1)}{m.group(2)}', pydantic_to_snake(s))


def to_camel(s: str) -> str:
    # Pydantic to_camel is not reproducible
    # 'raw_md5sum' -> to_camel -> 'rawMd5Sum' -> to_camel -> 'rawmd5Sum'
    # But we also have trouble with
    # r1_gzip -> to_camel -> 'r1Gzip' (as it should be)
    # So we convert to snake case first
    s = to_snake(s)
    # And extend any 'digit' + underscore + letter to 'digit' + double under score + letter
    s = re.sub(r'([0-9])_([a-z])', lambda m: f'{m.group(1)}__{m.group(2)}', s)
    # Then we convert to camel
    s = pydantic_to_camel(s)
    # Pydantic adds a capital letter after a digit
    # We want to remove this capital letter
    s = re.sub(r'([0-9])([A-Z])', lambda m: f'{m.group(1)}{m.group(2).lower()}', s)
    # We then want to remove the double underscore
    s = re.sub(r'([0-9])__([A-Z])', lambda m: f'{m.group(1)}{m.group(2)}', s)
    return s


# AWS Things
def get_deploy_status_endpoint_url() -> str:
    return environ.get("DEPLOY_STATUS_BASE_URL") + "/api/v1/deployStatus/"

def get_default_post_entry() -> 'StackPostEvent':
    from .models.stack_event import StackPostEvent
    return StackPostEvent(**dict({
        "stackId": "default-stack-id",
        "stackName": "default-stack-name",
        "eventId": "default-event-id",
        "status": 'SUBMITTED',
        "stackStatus": "CREATE_COMPLETE",
        "modificationTimestamp": datetime.now(UTC).isoformat(timespec="seconds")
    }))


def get_cfn_client() -> 'CloudFormationClient':
    return boto3.client('cloudformation')


def get_stack_orcabus_id_from_cfn_stack_id(stack_id: str) -> str:
    # Get all stacks
    from .models.stack import StackData

    stack_obj_list = StackData.scan(
        filter_condition=A.stack_id == stack_id,
    )

    if len(stack_obj_list) == 0:
        raise ValueError(f"Could not find stack id {stack_id} in db")

    return stack_obj_list[0].orcabus_id


def get_latest_event_for_stack_synced(
    latest_event_id: str,
    stack_name: str
):
    # Import event data locally
    from .models.event import EventData
    event_object = EventData.get(
        latest_event_id,
        range_key=stack_name,
    )

    # Return non-null outputs
    return dict(filter(
        lambda kv_iter_: kv_iter_[1] is not None,
        {
            "eventOrcabusId": event_object.orcabus_id,
            "status": event_object.status,
            "modificationTimestamp": event_object.modification_timestamp,
            "gitCommitId": (event_object.git_commit_id if event_object.git_commit_id is not None else None),
        }.items()
    ))
