#!/usr/bin/env python3

"""
Event Query Classes
"""

# Imports
from typing import Optional, List, Dict
from fastapi import Query, HTTPException

# Local imports
from ..models import CloudFormationStackStatusType


class BaseQueryParameters:
    def __init__(self):
        self.validate_query()

    def validate_query(self):
        raise NotImplementedError("Subclasses must implement validate_query")


class EventQueryParameters(BaseQueryParameters):
    def __init__(
            self,
            # Status query
            status: Optional[CloudFormationStackStatusType] = Query(
                None,
                description="The status to filter by, use <code>status[]</code> for multiple values"
            ),
            status_list: Optional[List[CloudFormationStackStatusType]] = Query(
                None,
                alias="status[]",
                description=None,
                include_in_schema=False,
                strict=False
            ),
    ):
        # Initialise status query parameters
        self.status = status
        self.status_list = status_list

        # Call the super constructor to validate the query
        super().__init__()

    def validate_query(self):
        # Assert that only one of status and status_list is specified
        if self.status is not None and self.status_list is not None:
            raise HTTPException(
                status_code=400,
                detail="Only one of status or status[] is allowed"
            )
        if self.status is not None:
            self.status_list = [self.status]

    def to_params_dict(self) -> Dict[str, str]:
        for attr in [
            "status_list",
        ]:
            value = getattr(self, attr)
            if value is not None:
                return {
                    f"{attr.replace('_list', '[]')}": ','.join(map(str, value))
                }
        return {}
