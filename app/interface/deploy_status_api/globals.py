#!/usr/bin/env python3

# Standard imports
import re

# Add context prefix - Cloud Formation Stack
CLOUD_FORMATION_STACK_PREFIX = "cfs"  # Cloud Formation Stack
EVENT_PREFIX = "cfe"  # Cloud Formation Event

# https://regex101.com/r/zJRC62/1
ORCABUS_ULID_REGEX_MATCH = re.compile(r'^[a-z0-9]{3}\.[A-Z0-9]{26}$')

# Validate pydantic fields
UUID4_REGEX_MATCH_STR = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
URI_MATCH_STR = r'^(?:s3|icav2)://[^\s]+$'

# Envs
EVENT_BUS_NAME_ENV_VAR = "EVENT_BUS_NAME"
EVENT_SOURCE_ENV_VAR = "EVENT_SOURCE"
EVENT_DETAIL_TYPE_ANALYSIS_STATE_CHANGE_ENV_VAR = "EVENT_DETAIL_TYPE_ANALYSIS_STATE_CHANGE"

DYNAMODB_DEPLOY_STATUS_ANALYSIS_TABLE_NAME_ENV_VAR = "DYNAMODB_DEPLOY_STATUS_ANALYSIS_TABLE_NAME"
DYNAMODB_HOST_ENV_VAR = "DYNAMODB_HOST"
