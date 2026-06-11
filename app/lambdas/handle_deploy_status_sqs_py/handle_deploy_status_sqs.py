#!/usr/bin/env python3

"""
Handle deploy status durable context SQS

Kick off process cf-event sfn. Wait for sfn to give the callback before returning
"""

# Standard library imports
import json
from os import environ
import boto3
import typing
from typing import Dict

# Durable context imports
from aws_durable_execution_sdk_python import (
    DurableContext,
    durable_execution
)
from aws_durable_execution_sdk_python.config import (
    Duration, WaitForCallbackConfig
)
from aws_durable_execution_sdk_python.retries import create_retry_strategy
from aws_durable_execution_sdk_python.types import WaitForCallbackContext

if typing.TYPE_CHECKING:
    from mypy_boto3_dynamodb.client import DynamoDBClient
    from mypy_boto3_stepfunctions.client import SFNClient

# Globals
HANDLE_CFN_STATE_CHANGE_SFN_ARN_ENV_VAR = "HANDLE_CFN_STATE_CHANGE_SFN_ARN"


def get_dynamodb_client() -> 'DynamoDBClient':
    return boto3.client('dynamodb')


def get_sfn_client() -> 'SFNClient':
    return boto3.client('stepfunctions')


def handle_sfn_execution(
        record_body: Dict[str, str],
        context: DurableContext,
):
    def submitter(callback_id: str, callback_context: WaitForCallbackContext):
        """
        Start execution of step function
        """
        # Launch the step function (asynchronously)
        callback_context.logger.info("Start sfn execution")
        get_sfn_client().start_execution(
            stateMachineArn=environ[HANDLE_CFN_STATE_CHANGE_SFN_ARN_ENV_VAR],
            input=json.dumps(
                {
                    "stackId": record_body['stackId'],
                    "stackName": record_body['stackName'],
                    "status": record_body['status'],
                    "clientRequestToken": record_body['clientRequestToken'],
                    "callbackId": callback_id,
                },
                separators=(",", ":")
            )
        )

    # Wait here for the callback to be invoked by the step function
    context.wait_for_callback(
        submitter=submitter,
        name=None,
        config=WaitForCallbackConfig(
            # Almost 15 minutes
            timeout=Duration.from_seconds(890),
            retry_strategy=create_retry_strategy(
                config=None
            )
        ),
    )


@durable_execution
def handler(event, context: DurableContext):
    """
    Expect the following inputs from the event object:
      * inputs
      * engineParameters
      * tags

    :param event:
    :param context:
    :return:
    """

    # Not sure what this will look like from the sqs event source
    for record in event.get("Records", []):
        record_body = json.loads(record.get("body", {}))

        handle_sfn_execution(
            record_body,
            context
        )
