#!/usr/bin/env python3

# Layer imports
from orcabus_api_tools.utils.requests_helpers import (
    get_url, get_request_response_results
)

DEPLOY_STATUS_SUBDOMAIN_NAME = "deploy-status"
LIST_STACKS_END_POINT = "api/v1/deployStatus/listStacks"

# Get url for the subdomain
def get_deploy_status_url(endpoint: str) -> str:
    """
    Get the URL for the data sharing endpoint
    :param endpoint:
    :return:
    """
    return get_url(
        endpoint=endpoint,
        subdomain=DEPLOY_STATUS_SUBDOMAIN_NAME,
    )


def handler(event, context):
    """
    Given a stack name get the stack orcabus id
    """

    stack_name = event["stackName"]

    # Stack orcabus id
    results = get_request_response_results(
        url=get_deploy_status_url(LIST_STACKS_END_POINT),
        params={"stackName": stack_name}
    )

    if len(results) == 0:
        return {
            "stackOrcabusId": None
        }

    return {
        "stackOrcabusId": results[0]["orcabusId"]
    }
