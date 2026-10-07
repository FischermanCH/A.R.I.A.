"""Native read-only RSS tool owned by RSS Runtime."""

from __future__ import annotations

from collections.abc import Mapping
import inspect
import json
from typing import Any

from aria.modules.sdk import NativeToolBinding, NativeToolContext, NativeToolContract, NativeToolResult

RSS_SOURCE_AUTHORITY = "rss:configured_profile"


def native_tool_contributions(runtime_owner: Any) -> tuple[NativeToolBinding, ...]:
    async def feed_read(context: NativeToolContext, arguments: Mapping[str, Any]) -> NativeToolResult:
        if set(arguments) - {"connection_ref", "requested_count"} or not isinstance(arguments.get("connection_ref"), str):
            raise ValueError("native_agent_rss_arguments_invalid")
        ref = str(arguments["connection_ref"]).strip()
        count = arguments.get("requested_count", 0)
        if not ref or not isinstance(count, int) or isinstance(count, bool) or not 0 <= count <= 20:
            raise ValueError("native_agent_rss_arguments_invalid")
        loader = getattr(runtime_owner, "_native_agent_connection_read_loader", None)
        if callable(loader):
            raw = loader(context.user_id, "rss", ref, "read", {"requested_count": count})
            row = await raw if inspect.isawaitable(raw) else raw
            if not isinstance(row, Mapping) or str(row.get("source_authority") or "") != RSS_SOURCE_AUTHORITY:
                raise ValueError("native_agent_rss_source_authority_mismatch")
            if str(row.get("scope_user_id") or "") != context.user_id:
                raise ValueError("native_agent_rss_scope_mismatch")
            content = str(row.get("content") or "").strip()
        else:
            profiles = getattr(getattr(getattr(runtime_owner, "settings", None), "connections", None), "rss", None)
            if not isinstance(profiles, Mapping) or ref not in profiles:
                content = ""
            else:
                runtime = getattr(runtime_owner, "_skill_runtime", None)
                if runtime is None:
                    raise ValueError("native_agent_rss_runtime_unavailable")
                try:
                    content = str(runtime.execute_rss_read(ref, requested_count=count) or "").strip()
                except Exception as exc:  # resolved profile, transport/config failure -> honest degradation
                    return NativeToolResult(json.dumps({
                        "status": "read_failed", "effect": "read_only", "connection_ref": ref,
                        "message": "The configured RSS profile was resolved but could not be read.",
                        "error_class": type(exc).__name__, "detail": str(exc)[:200],
                    }, ensure_ascii=True, sort_keys=True), "rss_feed_read")
        payload = {"status": "ok" if content else "not_found_or_empty", "effect": "read_only", "connection_ref": ref, "content": content}
        if not content:
            payload["message"] = "No feed items were found for this exact RSS profile."
        return NativeToolResult(json.dumps(payload, ensure_ascii=True, sort_keys=True), "rss_feed_read")

    return (NativeToolBinding(contract=NativeToolContract(
        owner_module_id="rss_runtime", name="rss_feed_read",
        description="Read items from one exact configured RSS profile, optionally with a bounded item count. Read-only and credential-free.",
        input_schema={"type": "object", "properties": {"connection_ref": {"type": "string"}, "requested_count": {"type": "integer", "minimum": 0, "maximum": 20}}, "required": ["connection_ref"]},
        effect="read_only", confirmation_required=False, source_authority=RSS_SOURCE_AUTHORITY,
        user_scoped=True, rollout_flag="native_agent_connections_enabled", order=490,
        required_connection_kinds=("rss",),
    ), handler=feed_read),)
