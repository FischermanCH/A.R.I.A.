from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

from aria.core.action_plan import ActionPlan
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
        key = (str(connection_kind).strip().lower(), str(capability).strip().lower())
        self._executors[key] = executor

    async def execute(self, plan: ActionPlan, **kwargs: Any) -> str:
        key = (plan.connection_kind.strip().lower(), plan.capability.strip().lower())
        executor = self._executors.get(key)
        if executor is None:
            raise ValueError(_executor_registry_text("missing_executor", "No executor registered for {connection_kind}:{capability}", connection_kind=plan.connection_kind, capability=plan.capability))
        return await executor(plan, **kwargs)
