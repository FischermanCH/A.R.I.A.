from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

from aria.core.action_plan import ActionPlan
from aria.core.capability_catalog import normalize_capability
from aria.core.connection_action_contract import connection_action_binding_is_supported
from aria.core.connection_catalog import normalize_connection_kind
from aria.core.i18n import I18NStore


Executor = Callable[..., Awaitable[str]]
_EXECUTOR_REGISTRY_I18N = I18NStore(Path(__file__).resolve().parents[1] / "i18n")


def _executor_registry_text(key: str, default: str = "", **values: object) -> str:
    template = _EXECUTOR_REGISTRY_I18N.t("de", f"executor_registry.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template


@dataclass(slots=True)
class ExecutorRegistry:
    _executors: dict[tuple[str, str], Executor]

    def __init__(self) -> None:
        self._executors = {}

    def register(self, connection_kind: str, capability: str, executor: Executor) -> None:
        clean_kind = normalize_connection_kind(connection_kind)
        clean_capability = normalize_capability(capability)
        if not connection_action_binding_is_supported(clean_kind, clean_capability):
            raise ValueError(
                _executor_registry_text(
                    "unsupported_binding",
                    "Unsupported executor binding {connection_kind}:{capability}; add or update the Connection Action Contract first",
                    connection_kind=clean_kind or str(connection_kind or "").strip(),
                    capability=clean_capability or str(capability or "").strip(),
                )
            )
        key = (clean_kind, clean_capability)
        self._executors[key] = executor

    async def execute(self, plan: ActionPlan, **kwargs: Any) -> str:
        key = (normalize_connection_kind(plan.connection_kind), normalize_capability(plan.capability))
        executor = self._executors.get(key)
        if executor is None:
            raise ValueError(_executor_registry_text("missing_executor", "No executor registered for {connection_kind}:{capability}", connection_kind=plan.connection_kind, capability=plan.capability))
        return await executor(plan, **kwargs)
