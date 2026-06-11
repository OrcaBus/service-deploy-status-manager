#!/usr/bin/env python3

"""
Add stack event
"""

# Orcabus api tool kits
from orcabus_api_tools.utils.requests_helpers import (
    post_request, get_url
)

DEPLOY_STATUS_SUBDOMAIN_NAME = "deploy-status"
ADD_STACK_EVENT_ENDPOINT = "api/v1/deployStatus/addStackEvent"


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
    Get inputs and create stack event
    """
    post_request(
        url=get_deploy_status_url(ADD_STACK_EVENT_ENDPOINT),
        json_data=dict(filter(
            lambda kv_iter_: kv_iter_[1] is not None,
            event.items()
        ))
    )
