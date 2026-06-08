from __future__ import annotations

import asyncio

import pytest

from aria.core.action_plan import ActionPlan
from aria.core.executor_registry import ExecutorRegistry


async def _executor(plan: ActionPlan, **_kwargs: object) -> str:
    return f"{plan.connection_kind}:{plan.capability}:{plan.connection_ref}"


def test_executor_registry_accepts_only_contract_backed_bindings() -> None:
    registry = ExecutorRegistry()
    registry.register("ssh", "ssh_command", _executor)

    result = asyncio.run(
        registry.execute(ActionPlan(capability="ssh_command", connection_kind="ssh", connection_ref="dns-node-01"))
    )

    assert result == "ssh:ssh_command:dns-node-01"


def test_executor_registry_rejects_bindings_missing_from_connection_action_contract() -> None:
    registry = ExecutorRegistry()

    with pytest.raises(ValueError, match="Connection Action Contract"):
        registry.register("rss", "ssh_command", _executor)

    with pytest.raises(ValueError, match="Connection Action Contract"):
        registry.register("new_provider", "new_capability", _executor)
