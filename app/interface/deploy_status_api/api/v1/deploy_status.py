
"""

Routes for the API V1 Fastq endpoint

This is the list of routes available
-

"""

# Standard imports
from typing import Annotated, List, cast

from fastapi import Depends, Query, Body
from fastapi.routing import APIRouter, HTTPException
from dyntastic import A

from fastapi_tools import QueryPagination

# Model imports
from ...models.event import (
    EventData,
    EventQueryPaginatedResponse,
    EventResponseDict,
)
from ...models.stack import (
    StackData,
    StackQueryPaginatedResponse,
)
from ...models.event_query import EventQueryParameters
from ...models.stack_query import StackQueryParameters
from ...models.stack_event import StackEventResponseDict, StackPostEvent
from ...models.stack_summary import StackSummaryResponseDict
from ...utils import (
    get_default_post_entry, get_latest_event_for_stack_synced
)
from ...events.events import put_stack_event_analysis_update_event
from ...utils import sanitise_stack_id, sanitise_event_orcabus_id

router = APIRouter()


# Define a dependency function that returns the pagination parameters
def get_pagination_params(
    # page must be greater than or equal to 1
    page: int = Query(1, gt=0),
    # rowsPerPage must be greater than 0
    rows_per_page: int = Query(100, gt=0, alias='rowsPerPage')
) -> QueryPagination:
    return {"page": page, "rowsPerPage": rows_per_page}


## Query options
# - Get / endpoint for a given fastq list row id
@router.get(
    "/listStacks",
    tags=["query"]
)
async def list_stacks(
        # Stack Query parameters
        stack_query_parameters: StackQueryParameters = Depends(),
        # Pagination options:
        pagination: QueryPagination = Depends(get_pagination_params)
) -> StackQueryPaginatedResponse:
    # We can query by stack id OR stack name
    # Scan for all stacks
    # This table will NOT fill up, the events table will continue to grow though
    stack_list = list(StackData.scan(
        load_full_item=True
    ))

    # Filter to those in the stack list
    if stack_query_parameters.stack_name_list is not None:
        stack_list = list(filter(
            lambda stack_iter_: stack_iter_.stack_name in stack_query_parameters.stack_name_list,
            stack_list
        ))

    # Otherwise check by stack id
    if stack_query_parameters.stack_id_list is not None:
        stack_list = list(filter(
            lambda stack_iter_: stack_iter_.stack_id in stack_query_parameters.stack_id_list,
            stack_list
        ))

    return StackQueryPaginatedResponse.from_results_list(
        results=list(map(
            lambda stack_iter_: stack_iter_.to_dict(),
            stack_list
        )),
        query_pagination=pagination,
        params_response=dict(filter(
            lambda kv: kv[1] is not None,
            dict(
                **stack_query_parameters.to_params_dict(),
                **pagination
            ).items())
        )
    )


## Query options
# - Get / endpoint for a given fastq list row id
@router.get(
    "/getAllStacksSummary",
    tags=["query"]
)
async def get_all_stacks_summary(
) -> List[StackSummaryResponseDict]:
    # We can query by stack id OR stack name

    # Scan for all stacks
    stack_list = list(StackData.scan(
        load_full_item=True
    ))

    # Merge events and stacks
    stack_summaries = list(map(
        lambda stack_iter_: {
            "stackOrcabusId": stack_iter_.orcabus_id,
            "stackId": stack_iter_.stack_id,
            "stackName": stack_iter_.stack_name,
            **get_latest_event_for_stack_synced(
                latest_event_id=stack_iter_.latest_event_id,
                stack_name=stack_iter_.stack_name,
            )
        },
        stack_list
    ))

    return stack_summaries


## Query options
# - Get / endpoint for a given fastq list row id
@router.get(
    "/{stack_id}/latest",
    tags=["query"]
)
async def get_latest_event_for_stack(
        stack_id: str = Depends(sanitise_stack_id)
) -> EventResponseDict:
    # Get the stack id
    stack_obj = StackData.get(stack_id)

    # Get the event object by the event id
    event_data_obj = EventData.get(
        stack_obj.latest_event_id,
        range_key=stack_obj.stack_name,
    )

    return event_data_obj.to_dict()


@router.get(
    "/{stack_id}/events",
    tags=["query"],
)
async def list_events_for_stack(
        # Stack id
        stack_id: str = Depends(sanitise_stack_id),
        # Query params
        event_query_parameters: EventQueryParameters = Depends(),
        # Pagination options:
        pagination: QueryPagination = Depends(get_pagination_params)
) -> EventQueryPaginatedResponse:
    # Get stack object
    stack_obj = StackData.get(stack_id)

    # Get all event ids for the stack
    events_list = list(EventData.query(
        A.stack_name == stack_obj.stack_name,
        index="event-stack-index",
        load_full_item=True
    ))

    # Filter for status if provided
    if event_query_parameters.status_list is not None:
        events_list = list(filter(
            lambda event_iter_: event_iter_.status in event_query_parameters.status_list,
            events_list
        ))

    # Order by timestamp-desc
    # orcabus_id ulid is timestamp specific
    events_list.sort(
        key=lambda x: x.orcabus_id,
        reverse=True
    )

    return EventQueryPaginatedResponse.from_results_list(
        results=list(map(
            lambda event_iter_: event_iter_.to_dict(),
            events_list
        )),
        query_pagination=pagination,
        params_response=dict(filter(
            lambda kv: kv[1] is not None,
            dict(
                **event_query_parameters.to_params_dict(),
                **pagination
            ).items())
        ),
    )


@router.get(
    "/{stack_id}/events/{event_id}",
    tags=["query"],
)
async def get_stack_event(
        stack_id: str = Depends(sanitise_stack_id),
        event_id: str = Depends(sanitise_event_orcabus_id),
) -> EventResponseDict:

    # Get the stack id
    stack_obj = StackData.get(stack_id)

    # Get all event ids for the stack
    event_obj = EventData.get(event_id, range_key=stack_obj.stack_name)

    # Confirm that the event matches the stack object
    if not stack_obj.stack_name == event_obj.stack_name:
        raise HTTPException(
            status_code=409,
            detail=f"Event not found for stack id {stack_id}",
        )

    return event_obj.to_dict()


# Post event
@router.post(
    '/addStackEvent',
    tags=["post"],
    include_in_schema=False,
)
async def add_stack_event(
    stack_event_object: Annotated[StackPostEvent, Body()] = get_default_post_entry()
) -> StackEventResponseDict:
    # Get the stack object, or create it!
    try:
        stack_obj = next(filter(
            lambda stack_iter_: stack_iter_.stack_name == stack_event_object.stack_name,
            list(StackData.scan(
                load_full_item=True
            ))
        ))
    except StopIteration:
        stack_obj = StackData.from_dict(**{
                "stack_id": stack_event_object.stack_id,
                "stack_name": stack_event_object.stack_name,
                "latest_event_id": "PLACE_HOLDER"
            }
        )

    # Create a new event from the input
    event_obj = EventData.from_dict(
        **dict(filter(
            lambda kv: kv[1] is not None,
            {
                "event_id": stack_event_object.event_id,
                "stack_name": stack_obj.stack_name,
                "status": stack_event_object.stack_status,
                "git_commit_id": stack_event_object.git_commit_id,
                "modification_timestamp": stack_event_object.modification_timestamp,
            }.items()
        ))
    )

    # Get the existing latest event id for the stack
    if (
            # We have an existing event id
            not stack_obj.latest_event_id == "PLACE_HOLDER" and
            # And the existing event id is later than the current id
            stack_obj.latest_event_id > event_obj.orcabus_id
        ):
        pass
    else:
        # Add the event object orcabus id to the stack object id
        stack_obj.latest_event_id = event_obj.orcabus_id

    # Save the stack object to the database
    stack_obj.save()

    # Create / save the new event object
    event_obj.save()

    # Generate an event to say that the event has been digested.
    stack_response_dict: StackEventResponseDict = cast(
        StackEventResponseDict,
        cast(
            object,
            dict(filter(
                lambda kv: kv[1] is not None,
                {
                    "stackOrcabusId": stack_obj.orcabus_id,
                    "stackId": stack_obj.stack_id,
                    "stackName": stack_obj.stack_name,
                    "eventOrcabusId": event_obj.orcabus_id,
                    "eventId": event_obj.event_id,
                    "status": event_obj.status,
                    "modificationTimestamp": event_obj.modification_timestamp,
                    "gitCommitId": event_obj.git_commit_id,
                }.items()
            ))
        )
    )

    # Update event
    put_stack_event_analysis_update_event(
        stack_response_dict
    )

    # Return response as a StackEventResponseDict
    return stack_response_dict
