"""Native read-only tool contribution owned by Connections Runtime Status."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
from typing import Any

from aria.modules.connections_runtime_status.inventory_source import CONNECTION_PROFILE_SOURCE_AUTHORITY, load_connection_inventory
from aria.modules.sdk import NativeToolBinding, NativeToolContext, NativeToolContract, NativeToolResult


def _connection_rows(items: Sequence[dict[str, Any]], *, user_id: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in items:
        if str(item.get("source_authority") or "").strip() != CONNECTION_PROFILE_SOURCE_AUTHORITY:
            raise ValueError("native_agent_connection_source_authority_mismatch")
        if str(item.get("scope_user_id") or "").strip() != user_id:
            raise ValueError("native_agent_connection_scope_mismatch")
        kind = str(item.get("kind") or "").strip()
        ref = str(item.get("ref") or "").strip()
        if not kind or not ref:
            raise ValueError("native_agent_connection_identity_missing")
        rows.append({
            "kind": kind, "ref": ref,
            "display_name": str(item.get("display_name") or ref).strip() or ref,
            "target": str(item.get("target") or "").strip(),
        })
    return rows


def native_tool_contributions(runtime_owner: Any) -> tuple[NativeToolBinding, ...]:
    async def load_safe_rows(context: NativeToolContext, connection_kind: str = "") -> list[dict[str, str]]:
        loader = getattr(runtime_owner, "_native_agent_connection_loader", None)
        items = await loader(context.user_id, connection_kind) if callable(loader) else await load_connection_inventory(
            runtime_owner.settings, user_id=context.user_id, connection_kind=connection_kind,
        )
        return _connection_rows(items, user_id=context.user_id)

    async def list_connections(context: NativeToolContext, arguments: Mapping[str, Any]) -> NativeToolResult:
        if set(arguments) - {"connection_kind"} or not isinstance(arguments.get("connection_kind", ""), str):
            raise ValueError("native_agent_connection_arguments_invalid")
        connection_kind = str(arguments.get("connection_kind") or "").strip()
        try:
            rows = await load_safe_rows(context, connection_kind)
        except ValueError as exc:
            if str(exc) != "connection_inventory_kind_unknown":
                raise
            available_rows = await load_safe_rows(context)
            content = json.dumps({
                "status": "connection_kind_unknown",
                "requested_connection_kind": connection_kind,
                "available_connection_kinds": sorted({row["kind"] for row in available_rows}),
                "connections": [],
                "message": "No connection profiles match the requested kind. Use one of the available exact kinds.",
            }, ensure_ascii=True, sort_keys=True)
            return NativeToolResult(content=content, intent="connections")
        content = json.dumps(
            {"status": "ok", "connections": rows} if rows else {
                "status": "no_connections", "connections": [],
                "message": "No connection profiles are available to this user for the requested scope.",
            }, ensure_ascii=True, sort_keys=True,
        )
        return NativeToolResult(content=content, intent="connections")

    async def lookup_connection(context: NativeToolContext, arguments: Mapping[str, Any]) -> NativeToolResult:
        allowed_arguments = {"connection_ref", "connection_kind"}
        if (
            set(arguments) - allowed_arguments
            or "connection_ref" not in arguments
            or not isinstance(arguments.get("connection_ref"), str)
            or not isinstance(arguments.get("connection_kind", ""), str)
        ):
            raise ValueError("native_agent_connection_lookup_arguments_invalid")
        connection_ref = str(arguments["connection_ref"]).strip()
        if not connection_ref:
            raise ValueError("native_agent_connection_lookup_arguments_invalid")
        connection_kind = str(arguments.get("connection_kind") or "").strip()
        matches = [
            row for row in await load_safe_rows(context, connection_kind)
            if row["ref"] == connection_ref
        ]
        if len(matches) == 1:
            result = {"status": "ok", "connection": matches[0]}
        elif matches:
            result = {"status": "ok", "connections": matches, "match_count": len(matches)}
        else:
            result = {
                "status": "connection_not_found", "connection_ref": connection_ref,
                "message": "No connection profile exists for this exact reference in the current user scope.",
            }
        content = json.dumps(
            result, ensure_ascii=True, sort_keys=True,
        )
        return NativeToolResult(content=content, intent="connections")

    return (
        NativeToolBinding(
            contract=NativeToolContract(
                owner_module_id="connections_runtime_status", name="list_connections",
                description="List all connection profiles available to the current user, optionally filtered by connection kind. This tool is read-only.",
                input_schema={"type": "object", "properties": {"connection_kind": {"type": "string"}}, "required": []},
                effect="read_only", confirmation_required=False,
                source_authority=CONNECTION_PROFILE_SOURCE_AUTHORITY, user_scoped=True,
                rollout_flag="native_agent_connections_enabled", order=200,
            ), handler=list_connections,
        ),
        NativeToolBinding(
            contract=NativeToolContract(
                owner_module_id="connections_runtime_status", name="lookup_connection",
                description="Look up connection profiles by exact reference, optionally filtered by kind, and return safe metadata only. This tool is read-only and never returns secrets.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "connection_ref": {"type": "string"},
                        "connection_kind": {"type": "string"},
                    },
                    "required": ["connection_ref"],
                },
                effect="read_only", confirmation_required=False,
                source_authority=CONNECTION_PROFILE_SOURCE_AUTHORITY, user_scoped=True,
                rollout_flag="native_agent_connections_enabled", order=210,
            ), handler=lookup_connection,
        ),
    )
