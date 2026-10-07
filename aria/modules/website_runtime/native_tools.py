"""Native read-only watched-website tools owned by Website Runtime."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import inspect
import json
from typing import Any
from urllib.parse import urlparse

from aria.modules.sdk import NativeToolBinding, NativeToolContext, NativeToolContract, NativeToolResult

WEBSITE_SOURCE_AUTHORITY = "website_runtime:configured_profiles"


def _safe_url(value: Any) -> str:
    url = str(value or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
        return ""
    return url


async def _load_rows(runtime_owner: Any, user_id: str) -> Sequence[Mapping[str, Any]]:
    loader = getattr(runtime_owner, "_native_agent_website_loader", None)
    if callable(loader):
        result = loader(user_id)
        return await result if inspect.isawaitable(result) else result
    rows_loader = getattr(runtime_owner, "_website_rows", None)
    rows = rows_loader() if callable(rows_loader) else {}
    return tuple({
        **dict(row), "ref": ref, "source_authority": WEBSITE_SOURCE_AUTHORITY,
        "scope_user_id": user_id,
    } for ref, row in dict(rows or {}).items())


def _safe_rows(items: Sequence[Mapping[str, Any]], *, user_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in items:
        if str(item.get("source_authority") or "") != WEBSITE_SOURCE_AUTHORITY:
            raise ValueError("native_agent_website_source_authority_mismatch")
        if str(item.get("scope_user_id") or "") != user_id:
            raise ValueError("native_agent_website_scope_mismatch")
        ref = str(item.get("ref") or "").strip()
        if not ref:
            raise ValueError("native_agent_website_identity_missing")
        rows.append({
            "ref": ref,
            "title": str(item.get("title") or "").strip(),
            "url": _safe_url(item.get("url")),
            "group_name": str(item.get("group_name") or "").strip(),
            "description": str(item.get("description") or "").strip(),
            "tags": [str(value).strip() for value in item.get("tags", ()) if str(value).strip()][:20],
            "snapshot_text": str(item.get("snapshot_text") or "").strip()[:12000],
        })
    return rows


def native_tool_contributions(runtime_owner: Any) -> tuple[NativeToolBinding, ...]:
    async def load(context: NativeToolContext) -> list[dict[str, Any]]:
        return _safe_rows(await _load_rows(runtime_owner, context.user_id), user_id=context.user_id)

    async def list_websites(context: NativeToolContext, arguments: Mapping[str, Any]) -> NativeToolResult:
        if arguments:
            raise ValueError("native_agent_website_list_arguments_invalid")
        rows = await load(context)
        inventory = [{key: row[key] for key in ("ref", "title", "url", "group_name", "description", "tags")}
                     for row in rows]
        payload = {"status": "ok", "effect": "read_only", "websites": inventory} if inventory else {
            "status": "no_websites", "effect": "read_only", "websites": [],
            "message": "No watched website profiles are available in the current user scope.",
        }
        return NativeToolResult(json.dumps(payload, ensure_ascii=True, sort_keys=True), "website_list")

    async def read_website(context: NativeToolContext, arguments: Mapping[str, Any]) -> NativeToolResult:
        if set(arguments) != {"website_ref"} or not isinstance(arguments.get("website_ref"), str):
            raise ValueError("native_agent_website_read_arguments_invalid")
        website_ref = str(arguments["website_ref"]).strip()
        if not website_ref:
            raise ValueError("native_agent_website_read_arguments_invalid")
        matches = [row for row in await load(context) if row["ref"] == website_ref]
        if len(matches) > 1:
            raise ValueError("native_agent_website_identity_ambiguous")
        payload = {"status": "ok", "effect": "read_only", "website": matches[0]} if matches else {
            "status": "website_not_found", "effect": "read_only", "website_ref": website_ref,
            "message": "No watched website exists for this exact reference in the current user scope.",
        }
        return NativeToolResult(json.dumps(payload, ensure_ascii=True, sort_keys=True), "website_read")

    return (
        NativeToolBinding(contract=NativeToolContract(
            owner_module_id="website_runtime", name="website_list",
            description="List watched website profiles available in the current user scope using safe metadata only. Read-only and performs no fetch.",
            input_schema={"type": "object", "properties": {}, "required": []},
            effect="read_only", confirmation_required=False,
            source_authority=WEBSITE_SOURCE_AUTHORITY, user_scoped=True,
            rollout_flag="native_agent_memory_enabled", order=360,
        ), handler=list_websites),
        NativeToolBinding(contract=NativeToolContract(
            owner_module_id="website_runtime", name="website_read",
            description="Read one exact watched website profile and its available stored snapshot. Read-only and performs no live fetch.",
            input_schema={"type": "object", "properties": {
                "website_ref": {"type": "string"},
            }, "required": ["website_ref"]}, effect="read_only", confirmation_required=False,
            source_authority=WEBSITE_SOURCE_AUTHORITY, user_scoped=True,
            rollout_flag="native_agent_memory_enabled", order=370,
        ), handler=read_website),
    )
