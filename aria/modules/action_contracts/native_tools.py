"""Native read-only capability inventory owned by Action Contracts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import inspect
import json
from typing import Any

from aria.modules.action_contracts.connection import connection_action_contracts
from aria.modules.sdk import NativeToolBinding, NativeToolContext, NativeToolContract, NativeToolResult

CAPABILITY_SOURCE_AUTHORITY = "action_contracts:runtime_capabilities"


async def _load_rows(runtime_owner: Any) -> Sequence[Mapping[str, Any]]:
    loader = getattr(runtime_owner, "_native_agent_capability_loader", None)
    if callable(loader):
        result = loader()
        return await result if inspect.isawaitable(result) else result
    return tuple(contract.manifest_row() for contract in connection_action_contracts())


def native_tool_contributions(runtime_owner: Any) -> tuple[NativeToolBinding, ...]:
    async def inventory(_context: NativeToolContext, arguments: Mapping[str, Any]) -> NativeToolResult:
        if arguments:
            raise ValueError("native_agent_capabilities_arguments_invalid")
        rows = [{
            "capability": str(item.get("capability") or "").strip(),
            "operation": str(item.get("operation") or "").strip(),
            "executors": [str(value).strip() for value in item.get("executors", ()) if str(value).strip()],
            "confirmation_required": bool(item.get("confirmation_required", False)),
        } for item in await _load_rows(runtime_owner) if str(item.get("capability") or "").strip()]
        payload = {"status": "ok", "effect": "read_only", "capabilities": rows} if rows else {
            "status": "no_capabilities", "effect": "read_only", "capabilities": [],
            "message": "No runtime capabilities are registered.",
        }
        return NativeToolResult(json.dumps(payload, ensure_ascii=True, sort_keys=True), "capabilities_inventory")

    return (NativeToolBinding(contract=NativeToolContract(
        owner_module_id="action_contracts", name="capabilities_inventory",
        description="Describe registered runtime capabilities, executor bindings and confirmation requirements. Read-only.",
        input_schema={"type": "object", "properties": {}, "required": []},
        effect="read_only", confirmation_required=False,
        source_authority=CAPABILITY_SOURCE_AUTHORITY, user_scoped=False,
        rollout_flag="native_agent_memory_enabled", order=300,
    ), handler=inventory),)
