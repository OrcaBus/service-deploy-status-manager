#!/usr/bin/env python3

"""
Stack Query Classes
"""

# Imports
from typing import Optional, List, Dict
from fastapi import Query, HTTPException

class BaseQueryParameters:
    def __init__(self):
        self.validate_query()

    def validate_query(self):
        raise NotImplementedError("Subclasses must implement validate_query")


class StackQueryParameters(BaseQueryParameters):
    def __init__(
            self,
            # Status query
            stack_id: Optional[str] = Query(
                None,
                alias="stackId",
                description="The stack id to filter by"
            ),
            stack_id_list: Optional[List[str]] = Query(
                None,
                alias="stackIdList[]",
                description=None,
                include_in_schema=False,
                strict=False
            ),
            # Status query
            stack_name: Optional[str] = Query(
                None,
                alias="stackName",
                description="The stack name to filter by"
            ),
            stack_name_list: Optional[List[str]] = Query(
                None,
                alias="stackNameList[]",
                description=None,
                include_in_schema=False,
                strict=False
            ),
    ):
        # Initialise status query parameters
        self.stack_id = stack_id
        self.stack_id_list = stack_id_list

        self.stack_name = stack_name
        self.stack_name_list = stack_name_list

        # Call the super constructor to validate the query
        super().__init__()

    def validate_query(self):
        # Assert that only one of stack_id and stack_id_list is specified
        if self.stack_id is not None and self.stack_id_list is not None:
            raise HTTPException(
                status_code=400,
                detail="Only one of stackId or stackIdList[] is allowed"
            )
        if self.stack_id is not None:
            self.stack_id_list = [self.stack_id]

        # Assert that only one of stack_name and stack_name_list is specified
        if self.stack_name is not None and self.stack_name_list is not None:
            raise HTTPException(
                status_code=400,
                detail="Only one of stackName or stackNameList[] is allowed"
            )
        if self.stack_name is not None:
            self.stack_name_list = [self.stack_name]

    def to_params_dict(self) -> Dict[str, str]:
        for attr in [
            "stack_id_list", "stack_name_list"
        ]:
            value = getattr(self, attr)
            if value is not None:
                return {
                    f"{attr.replace('_list', '[]')}": ','.join(map(str, value))
                }
        return {}
