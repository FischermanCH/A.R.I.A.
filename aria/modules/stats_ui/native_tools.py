"""Administrator-only native read tools for passive stats and activity readmodels."""

from __future__ import annotations

from collections.abc import Mapping
import inspect
import json
from typing import Any

from aria.modules.auth_policy.access_policy import is_admin
from aria.modules.read_model import module_registry_diagnostics
from aria.modules.sdk import NativeToolBinding, NativeToolContext, NativeToolContract, NativeToolResult


STATS_SOURCE_AUTHORITY = "stats:usage_readmodel"
ACTIVITY_SOURCE_AUTHORITY = "activity:audit_store"
_ACTIVITY_KINDS = {"all", "recipe", "memory", "system"}
_ACTIVITY_STATUSES = {"all", "ok", "error"}
_STATS_FIELDS = (
    "days", "request_count", "model_total_tokens", "total_cost_usd",
    "validation_issue_count", "dependency_cycle_count",
)
_ACTIVITY_ROW_FIELDS = (
    "timestamp", "kind", "status", "title", "intent", "duration_ms", "success",
)
_ACTIVITY_SUMMARY_FIELDS = ("count", "success", "errors", "avg_duration_ms")


def _forbidden(intent: str) -> NativeToolResult:
    return NativeToolResult(json.dumps({
        "status": "forbidden_admin_only", "effect": "read_only",
        "message": "Administrator access is required.",
    }, ensure_ascii=True, sort_keys=True), intent)


async def _load_stats(runtime_owner: Any) -> Mapping[str, Any]:
    loader = getattr(runtime_owner, "_native_agent_stats_loader", None)
    if callable(loader):
        raw = loader()
        return await raw if inspect.isawaitable(raw) else raw
    tracker = getattr(runtime_owner, "token_tracker", None)
    if tracker is None or not callable(getattr(tracker, "get_stats", None)):
        raise ValueError("native_agent_admin_stats_runtime_unavailable")
    raw = await tracker.get_stats(days=7)
    if not isinstance(raw, Mapping):
        return raw
    diagnostics = module_registry_diagnostics()
    return {
        **raw,
        "validation_issue_count": diagnostics["validation_issue_count"],
        "dependency_cycle_count": diagnostics["dependency_cycle_count"],
    }


async def _load_activities(
    runtime_owner: Any, context: NativeToolContext, *, kind: str, status: str, limit: int,
) -> Mapping[str, Any]:
    loader = getattr(runtime_owner, "_native_agent_activities_loader", None)
    if callable(loader):
        raw = loader(kind, status, limit)
        return await raw if inspect.isawaitable(raw) else raw
    tracker = getattr(runtime_owner, "token_tracker", None)
    if tracker is None or not callable(getattr(tracker, "get_recent_activities", None)):
        raise ValueError("native_agent_admin_activities_runtime_unavailable")
    return await tracker.get_recent_activities(
        user_id=context.user_id, limit=limit, kind=kind, status=status,
    )


def native_tool_contributions(runtime_owner: Any) -> tuple[NativeToolBinding, ...]:
    async def stats(context: NativeToolContext, arguments: Mapping[str, Any]) -> NativeToolResult:
        if arguments:
            raise ValueError("native_agent_admin_stats_arguments_invalid")
        if not is_admin(context.auth_role):
            return _forbidden("admin_stats")
        raw = await _load_stats(runtime_owner)
        if not isinstance(raw, Mapping):
            raise ValueError("native_agent_admin_stats_result_invalid")
        safe = {key: raw.get(key) for key in _STATS_FIELDS}
        return NativeToolResult(json.dumps({
            "status": "ok", "effect": "read_only", "stats": safe,
        }, ensure_ascii=True, sort_keys=True), "admin_stats")

    async def activities(context: NativeToolContext, arguments: Mapping[str, Any]) -> NativeToolResult:
        if set(arguments) - {"kind", "status", "limit"}:
            raise ValueError("native_agent_admin_activities_arguments_invalid")
        kind = arguments.get("kind", "all")
        status = arguments.get("status", "all")
        limit = arguments.get("limit", 20)
        if (
            not isinstance(kind, str) or kind not in _ACTIVITY_KINDS
            or not isinstance(status, str) or status not in _ACTIVITY_STATUSES
            or not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 40
        ):
            raise ValueError("native_agent_admin_activities_arguments_invalid")
        if not is_admin(context.auth_role):
            return _forbidden("admin_activities")
        raw = await _load_activities(runtime_owner, context, kind=kind, status=status, limit=limit)
        if not isinstance(raw, Mapping):
            raise ValueError("native_agent_admin_activities_result_invalid")
        raw_rows = raw.get("rows", ())
        if not isinstance(raw_rows, (list, tuple)):
            raise ValueError("native_agent_admin_activities_result_invalid")
        safe_rows = []
        for raw_row in raw_rows[:limit]:
            if not isinstance(raw_row, Mapping):
                continue
            row = {key: raw_row.get(key) for key in _ACTIVITY_ROW_FIELDS}
            if not str(row.get("status") or "").strip():
                row["status"] = "ok" if bool(row.get("success")) else "error"
            safe_rows.append(row)
        raw_summary = raw.get("summary", {})
        raw_summary = raw_summary if isinstance(raw_summary, Mapping) else {}
        safe_summary = {key: raw_summary.get(key) for key in _ACTIVITY_SUMMARY_FIELDS}
        payload = {
            "rows": safe_rows, "summary": safe_summary, "returned_count": len(safe_rows),
            "limit": limit, "truncated": len(raw_rows) > len(safe_rows),
        }
        return NativeToolResult(json.dumps({
            "status": "ok", "effect": "read_only", "activities": payload,
        }, ensure_ascii=True, sort_keys=True), "admin_activities")

    return (
        NativeToolBinding(contract=NativeToolContract(
            owner_module_id="stats_ui", name="admin_stats",
            description="Read safe aggregate usage and registry diagnostics. Administrator-only and read-only.",
            input_schema={"type": "object", "properties": {}, "required": []},
            effect="read_only", confirmation_required=False,
            source_authority=STATS_SOURCE_AUTHORITY, user_scoped=False,
            rollout_flag="native_agent_admin_enabled", order=620,
        ), handler=stats),
        NativeToolBinding(contract=NativeToolContract(
            owner_module_id="stats_ui", name="admin_activities",
            description="Read a bounded safe activity audit projection. Administrator-only and read-only.",
            input_schema={"type": "object", "properties": {
                "kind": {"type": "string", "enum": sorted(_ACTIVITY_KINDS)},
                "status": {"type": "string", "enum": sorted(_ACTIVITY_STATUSES)},
                "limit": {"type": "integer", "minimum": 1, "maximum": 40},
            }, "required": []}, effect="read_only", confirmation_required=False,
            source_authority=ACTIVITY_SOURCE_AUTHORITY, user_scoped=False,
            rollout_flag="native_agent_admin_enabled", order=630,
        ), handler=activities),
    )
