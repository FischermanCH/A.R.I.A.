from __future__ import annotations

from typing import Any

from aria.core.agentic_action_resolution import agentic_runtime_debug_line
from aria.core.action_plan import ActionPlan


def runtime_operation_for_plan(plan: ActionPlan) -> str:
    capability = str(getattr(plan, "capability", "") or "").strip().lower()
    if capability == "ssh_command":
        return "run_command"
    if capability == "api_request":
        return "request"
    if capability == "file_list":
        return "list"
    if capability == "file_write":
        return "write"
    if capability == "file_read":
        return "read"
    if capability == "mqtt_publish":
        return "publish"
    if capability in {"discord_send", "webhook_send", "email_send"}:
        return "send"
    if capability in {"feed_read", "calendar_read", "mail_read", "mail_search", "website_read", "website_list"}:
        return "read"
    return capability or "execute"


def runtime_payload_for_plan(plan: ActionPlan) -> dict[str, Any]:
    capability = str(getattr(plan, "capability", "") or "").strip().lower()
    path = str(getattr(plan, "path", "") or "").strip()
    content = str(getattr(plan, "content", "") or "").strip()
    if capability == "ssh_command":
        return {"command": content}
    if capability == "api_request":
        return {"path": path, "content": content}
    if capability in {"file_list", "file_read", "file_write"}:
        return {"path": path}
    if capability in {"discord_send", "webhook_send", "email_send"}:
        return {"message": content}
    if capability == "mqtt_publish":
        return {"topic": path, "message": content}
    if capability in {"feed_read", "calendar_read", "mail_read", "mail_search", "website_read", "website_list"}:
        return {"selector": path, "query": content}
    return {}


def runtime_debug_line_for_plan(plan: ActionPlan) -> str:
    return agentic_runtime_debug_line(
        capability=str(getattr(plan, "capability", "") or "").strip(),
        connection_kind=str(getattr(plan, "connection_kind", "") or "").strip(),
        connection_ref=str(getattr(plan, "connection_ref", "") or "").strip(),
        operation=runtime_operation_for_plan(plan),
        payload=runtime_payload_for_plan(plan),
    )
