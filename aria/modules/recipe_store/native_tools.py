"""Native read-only Recipe inventory owned by Recipe Store."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import inspect
import json
from typing import Any

from aria.modules.recipe_store.manifests import load_stored_recipe_manifests
from aria.modules.sdk import NativeToolBinding, NativeToolContext, NativeToolContract, NativeToolResult

RECIPE_SOURCE_AUTHORITY = "recipes:validated_runtime_manifests"


async def _load_recipes(runtime_owner: Any) -> Sequence[Mapping[str, Any]]:
    loader = getattr(runtime_owner, "_native_agent_recipe_loader", None)
    if callable(loader):
        result = loader()
        return await result if inspect.isawaitable(result) else result
    runtime_loader = getattr(runtime_owner, "_load_stored_recipe_runtime", None)
    if callable(runtime_loader):
        return tuple(runtime_loader())
    rows, _errors = load_stored_recipe_manifests()
    return tuple({**row, "enabled": bool(row.get("enabled_default", True))} for row in rows)


def native_tool_contributions(runtime_owner: Any) -> tuple[NativeToolBinding, ...]:
    async def inventory(_context: NativeToolContext, arguments: Mapping[str, Any]) -> NativeToolResult:
        if arguments:
            raise ValueError("native_agent_recipe_inventory_arguments_invalid")
        rows = [{
            "id": str(item.get("id") or "").strip(),
            "name": str(item.get("name") or "").strip(),
            "description": str(item.get("description") or "").strip(),
            "connections": [str(value).strip() for value in item.get("connections", ()) if str(value).strip()],
        } for item in await _load_recipes(runtime_owner)
            if bool(item.get("enabled", False)) and str(item.get("id") or "").strip()]
        payload = {"status": "ok", "effect": "read_only", "recipes": rows} if rows else {
            "status": "no_enabled_recipes", "effect": "read_only", "recipes": [],
            "message": "No enabled stored Recipes are available.",
        }
        return NativeToolResult(json.dumps(payload, ensure_ascii=True, sort_keys=True), "recipes_inventory")

    return (NativeToolBinding(contract=NativeToolContract(
        owner_module_id="recipe_store", name="recipes_inventory",
        description="List enabled stored Recipes with safe manifest metadata. Read-only and does not execute Recipes.",
        input_schema={"type": "object", "properties": {}, "required": []},
        effect="read_only", confirmation_required=False,
        source_authority=RECIPE_SOURCE_AUTHORITY, user_scoped=False,
        rollout_flag="native_agent_memory_enabled", order=320,
    ), handler=inventory),)
