from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable

from aria.core.action_plan import ActionPlan


Executor = Callable[[ActionPlan], Awaitable[str]]


@dataclass(slots=True)
class ExecutorRegistry:
    _executors: dict[tuple[str, str], Executor]

    def __init__(self) -> None:
        self._executors = {}

    def register(self, connection_kind: str, capability: str, executor: Executor) -> None:
        key = (str(connection_kind).strip().lower(), str(capability).strip().lower())
        self._executors[key] = executor

    async def execute(self, plan: ActionPlan) -> str:
        key = (plan.connection_kind.strip().lower(), plan.capability.strip().lower())
        executor = self._executors.get(key)
        if executor is None:
            raise ValueError(f"Kein Executor registriert für {plan.connection_kind}:{plan.capability}")
        return await executor(plan)
