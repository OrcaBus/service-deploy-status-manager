#!/usr/bin/env python3

"""

"""


# Standard imports
import typing
import boto3
from datetime import datetime


# Mypy type checks
if typing.TYPE_CHECKING:
    from mypy_boto3_cloudformation import CloudFormationClient

# Globals
AWS_CLOUD_FORMATION_STACK_RESOURCE_TYPE = 'AWS::CloudFormation::Stack'


def get_cfn_client() -> 'CloudFormationClient':
    return boto3.client('cloudformation')


def handler(event, context):
    """

    """

    # Get inputs
    stack_name = event['stackName']
    stack_status = event['status']
    client_request_token = event['clientRequestToken']

    stack_event = next(filter(
        lambda stack_event_iter_: (
            (
                stack_event_iter_['ResourceType'] == AWS_CLOUD_FORMATION_STACK_RESOURCE_TYPE
            ) and
            (
               stack_event_iter_['ResourceStatus'] == stack_status
            ) and
            (
                stack_event_iter_['ClientRequestToken'] == client_request_token
            )
        ),
        get_cfn_client().describe_stack_events(
            StackName=stack_name,
        )['StackEvents']
    ))

    return {
        "eventId": stack_event['EventId'],
        "timestamp": stack_event['Timestamp'].isoformat(timespec='seconds'),
    }
