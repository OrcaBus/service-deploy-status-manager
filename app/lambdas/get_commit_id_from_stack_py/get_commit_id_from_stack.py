#!/usr/bin/env python3

"""
Given a stack name -
Get the commit id from the stack

aws cloudformation describe-stacks \
  --stack-name OrcaBusBeta-Icav2WesManagerStatelessDeployStack \
  --query "Stacks[0].Outputs" \
  --output json | \
jq

But in python
"""

# Standard imports
import typing
import boto3

# Mypy type checks
if typing.TYPE_CHECKING:
    from mypy_boto3_cloudformation import CloudFormationClient

# Globals
GIT_COMMIT_ID_OUTPUT_KEY_OPTIONS = [
    "umccr-org:GitCommitId",
    "GitCommitId"
]


def get_cfn_client() -> 'CloudFormationClient':
    return boto3.client('cloudformation')


def handler(event, context):
    """
    Get the stack name event and return a commit id from the stack
    """

    # Get inputs
    stack_name = event['stackName']

    stack_list = get_cfn_client().describe_stacks(
        StackName=stack_name
    )['Stacks']

    # Check stack list not empty
    if len(stack_list) == 0:
        raise ValueError('No stacks found')

    # Get first stack
    stack_obj = stack_list[0]

    # Get git commit id from stack
    try:
        stack_git_output = next(filter(
            lambda output_iter_: output_iter_['OutputKey'] in GIT_COMMIT_ID_OUTPUT_KEY_OPTIONS,
            stack_obj.get('Outputs', [])
        ))
        return {
            "gitCommitId": stack_git_output['OutputValue']
        }
    except StopIteration:
        return {
            "gitCommitId": None
        }
