#!/usr/bin/env python3

"""
Regression tests for the HTTP 500 on
``GET /api/v1/deployStatus/{stack_id}/events``.

Two independent defects caused the 500:

* Defect 1 - ``EventData.to_dict()`` re-wrapped the dumped model without
  ``exclude_none``, reintroducing ``gitCommitId: None`` even though the
  response ``TypedDict`` types ``gitCommitId`` as ``NotRequired[str]`` (never
  ``None``). 232 of 1062 production rows have no git commit id.
* Defect 2 - ``UPDATE_ROLLBACK_FAILED`` was present in neither arm of the
  ``EventResponseDict`` union, so that status failed validation unconditionally.
"""

from datetime import datetime, UTC
from typing import get_args

from deploy_status_api.models import (
    CloudFormationStackStatusType,
    CloudFormationStackStatusWithCfnOutputType,
    CloudFormationStackStatusWithoutCfnOutputType,
)
from deploy_status_api.models.event import (
    EventData,
    EventQueryPaginatedResponse,
)

MODIFICATION_TIMESTAMP = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)


def _build_event(status, git_commit_id=None):
    kwargs = dict(
        event_id="event-123",
        stack_name="my-stack",
        status=status,
        modification_timestamp=MODIFICATION_TIMESTAMP,
    )
    if git_commit_id is not None:
        kwargs["git_commit_id"] = git_commit_id
    return EventData(**kwargs)


def test_no_commit_id_absent_not_null():
    """Defect 1: a with-output status with no commit id must omit gitCommitId."""
    event = _build_event("CREATE_COMPLETE")
    result = event.to_dict()
    assert "gitCommitId" not in result


def test_update_rollback_complete_no_commit_id():
    """Primary reported failure: UPDATE_ROLLBACK_COMPLETE with no commit id."""
    event = _build_event("UPDATE_ROLLBACK_COMPLETE")
    response = EventQueryPaginatedResponse.from_results_list(
        results=[event.to_dict()],
        query_pagination={},
        params_response={},
    )
    assert "gitCommitId" not in response.results[0]


def test_update_rollback_failed_validates():
    """Defect 2: UPDATE_ROLLBACK_FAILED was in neither union arm."""
    for git_commit_id in (None, "abc123def456"):
        event = _build_event("UPDATE_ROLLBACK_FAILED", git_commit_id=git_commit_id)
        response = EventQueryPaginatedResponse.from_results_list(
            results=[event.to_dict()],
            query_pagination={},
            params_response={},
        )
        assert response.results[0]["status"] == "UPDATE_ROLLBACK_FAILED"


def test_commit_id_preserved_when_present():
    """Guard against over-eager stripping of real values / camelCase aliases."""
    event = _build_event("UPDATE_COMPLETE", git_commit_id="deadbeefcafe")
    result = event.to_dict()
    assert result["gitCommitId"] == "deadbeefcafe"
    for key in (
        "orcabusId",
        "eventId",
        "stackName",
        "status",
        "modificationTimestamp",
    ):
        assert key in result


def test_status_literal_parity():
    """Every real CloudFormation status validates in exactly one union arm."""
    full = set(get_args(CloudFormationStackStatusType))
    with_output = set(get_args(CloudFormationStackStatusWithCfnOutputType))
    without_output = set(get_args(CloudFormationStackStatusWithoutCfnOutputType))

    assert with_output | without_output == full
    assert with_output & without_output == set()
