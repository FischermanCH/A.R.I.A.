from __future__ import annotations

from typing import Any

from aria.core.agentic_action_resolution import agentic_runtime_debug_line
from aria.core.action_plan import ActionPlan
from aria.core.connection_action_contract import runtime_operation_for_capability
from aria.core.connection_action_contract import runtime_payload_for_action_plan


def runtime_operation_for_plan(plan: ActionPlan) -> str:
    return runtime_operation_for_capability(str(getattr(plan, "capability", "") or ""))


def runtime_payload_for_plan(plan: ActionPlan) -> dict[str, Any]:
    return runtime_payload_for_action_plan(plan)


def runtime_debug_line_for_plan(plan: ActionPlan) -> str:
    return agentic_runtime_debug_line(
        capability=str(getattr(plan, "capability", "") or "").strip(),
        connection_kind=str(getattr(plan, "connection_kind", "") or "").strip(),
        connection_ref=str(getattr(plan, "connection_ref", "") or "").strip(),
        operation=runtime_operation_for_plan(plan),
        payload=runtime_payload_for_plan(plan),
    )
