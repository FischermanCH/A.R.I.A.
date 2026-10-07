"""First-match handler registry owned by the Runtime Execution Registry module."""

from __future__ import annotations

from dataclasses import dataclass

from aria.modules.runtime_execution_registry.contracts import AgenticExecutionHandler
from aria.modules.runtime_execution_registry.contracts import AgenticExecutionRequest
from aria.modules.runtime_execution_registry.contracts import AgenticExecutionResult
from aria.modules.ssh_runtime.registry import SPECIALIZED_RUNTIME_ADAPTER_IDS as SSH_SPECIALIZED_RUNTIME_ADAPTER_IDS

GENERIC_CAPABILITY_RUNTIME_ADAPTER_ID = "builtin.generic_capability"
SPECIALIZED_RUNTIME_ADAPTER_IDS = ("builtin.rss", *SSH_SPECIALIZED_RUNTIME_ADAPTER_IDS)
RUNTIME_ADAPTER_STATUS_GENERIC = "generic_capability_handler"
RUNTIME_ADAPTER_STATUS_SPECIALIZED = "specialized_handler"
RUNTIME_ADAPTER_STATUS_UNREGISTERED = "unregistered"


def _clean_runtime_adapter_id(value: str) -> str:
    return str(value or "").strip().lower().replace("-", "_")


def agentic_execution_registered_runtime_adapter_ids() -> tuple[str, ...]:
    from aria.modules.action_contracts.connection import connection_action_executor_kinds

    builtin_provider_adapters = {f"builtin.{kind}" for kind in connection_action_executor_kinds()}
    return tuple(
        sorted(
            {
                GENERIC_CAPABILITY_RUNTIME_ADAPTER_ID,
                *SPECIALIZED_RUNTIME_ADAPTER_IDS,
                *builtin_provider_adapters,
            }
        )
    )


def agentic_execution_runtime_adapter_status(runtime_adapter: str) -> str:
    clean = _clean_runtime_adapter_id(runtime_adapter)
    if clean in SPECIALIZED_RUNTIME_ADAPTER_IDS:
        return RUNTIME_ADAPTER_STATUS_SPECIALIZED
    if clean == GENERIC_CAPABILITY_RUNTIME_ADAPTER_ID:
        return RUNTIME_ADAPTER_STATUS_GENERIC
    if clean in set(agentic_execution_registered_runtime_adapter_ids()):
        return RUNTIME_ADAPTER_STATUS_GENERIC
    return RUNTIME_ADAPTER_STATUS_UNREGISTERED


@dataclass(slots=True)
class AgenticExecutionRegistry:
    handlers: list[AgenticExecutionHandler]

    async def execute_first(self, request: AgenticExecutionRequest) -> AgenticExecutionResult | None:
        for handler in self.handlers:
            if handler.can_handle(request):
                return await handler.execute(request)
        return None
