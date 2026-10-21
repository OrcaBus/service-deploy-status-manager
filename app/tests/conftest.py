#!/usr/bin/env python3

"""
Test configuration for the interface package.

The interface Lambda depends on the shared ``fastapi_tools`` Lambda layer, which
is not vendored in the repo and is not pip-installable locally. ``EventData``
also reads a handful of env vars at import time. This conftest sets those env
vars and registers a minimal in-process stub for ``fastapi_tools`` so the real
``deploy_status_api`` models import and the real Pydantic response validation
(the thing that produced the HTTP 500) runs unchanged.
"""

import os
import sys
import types
from pathlib import Path
from typing import List

# ---------------------------------------------------------------------------
# (a) Env vars required at import time by EventData / utils
# ---------------------------------------------------------------------------
os.environ.setdefault("DYNAMODB_EVENT_TABLE_NAME", "test-event-table")
os.environ.setdefault("DYNAMODB_HOST", "http://localhost:8000")
os.environ.setdefault("DEPLOY_STATUS_BASE_URL", "http://localhost")

# ---------------------------------------------------------------------------
# (b) Stub the fastapi_tools Lambda layer (not available locally)
# ---------------------------------------------------------------------------
if "fastapi_tools" not in sys.modules:
    from pydantic import BaseModel, ConfigDict

    fastapi_tools_stub = types.ModuleType("fastapi_tools")

    class QueryPagination(dict):
        """Thin stand-in for the layer's pagination container."""

    class QueryPaginatedResponse(BaseModel):
        """
        Minimal stand-in for the layer base class. Subclasses (e.g.
        ``EventQueryPaginatedResponse``) redeclare ``results`` with the real
        response type, so instantiation performs the real validation of each
        item against the response union.
        """

        model_config = ConfigDict(arbitrary_types_allowed=True)

        results: List

        @classmethod
        def from_results_list(cls, results, **kwargs):
            return cls(results=results)

    fastapi_tools_stub.QueryPagination = QueryPagination
    fastapi_tools_stub.QueryPaginatedResponse = QueryPaginatedResponse
    sys.modules["fastapi_tools"] = fastapi_tools_stub

# ---------------------------------------------------------------------------
# (c) Make `import deploy_status_api...` resolve
# ---------------------------------------------------------------------------
interface_dir = Path(__file__).resolve().parent.parent / "interface"
if str(interface_dir) not in sys.path:
    sys.path.insert(0, str(interface_dir))
