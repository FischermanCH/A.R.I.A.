"""Native Tool contribution projected from cached MCP discovery."""

from __future__ import annotations

from typing import Any

from aria.modules.sdk import NativeToolBinding


def native_tool_contributions(runtime_owner: Any) -> tuple[NativeToolBinding, ...]:
    manager = getattr(runtime_owner, "_native_mcp_client", None)
    if manager is None:
        return ()
    bindings = getattr(manager, "native_tool_bindings", None)
    return tuple(bindings()) if callable(bindings) else ()
