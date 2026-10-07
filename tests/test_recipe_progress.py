from __future__ import annotations

import asyncio
from types import SimpleNamespace

from aria.modules.platform_primitives.recipe_progress import RecipeProgressStore
from aria.modules.recipe_runtime.steps import RecipeStepExecutor
from aria.modules.skill_contracts.contracts import SkillResult


class RecordingProgressStore(RecipeProgressStore):
    def __init__(self) -> None:
        super().__init__(ttl_seconds=120)
        self.events: list[dict[str, object]] = []

    def update(self, user_id: str, **values: object) -> None:
        super().update(user_id, **values)
        snapshot = self.get(user_id)
        if snapshot is not None:
            self.events.append(snapshot)


def _runtime() -> SimpleNamespace:
    calls: list[str] = []

    async def execute_custom_ssh_command(**kwargs):
        ref = str(kwargs["connection_ref"])
        calls.append(ref)
        if ref == "host-b":
            return SkillResult(skill_name="recipe_fleet", content="", success=False, error="offline")
        return SkillResult(skill_name="recipe_fleet", content=f"ok:{ref}", success=True)

    return SimpleNamespace(
        calls=calls,
        normalize_spaces=lambda value: str(value).strip(),
        truncate_text=lambda value, limit=1200: str(value)[:limit],
        execute_custom_ssh_command=execute_custom_ssh_command,
    )


def test_recipe_progress_store_is_user_scoped_and_expires() -> None:
    now = [100.0]
    store = RecipeProgressStore(ttl_seconds=120, clock=lambda: now[0])
    store.update("alice", phase="running", step_index=1, step_total=2, step_type="ssh_run")
    store.update("bob", phase="running", step_index=2, step_total=3, step_type="llm_transform")

    assert store.get("alice")["step_total"] == 2
    assert store.get("bob")["step_total"] == 3
    assert store.get("charlie") is None

    now[0] = 221.0
    assert store.get("alice") is None
    assert store.get("bob") is None


def test_recipe_executor_emits_step_and_fanout_host_progress_without_changing_result() -> None:
    runtime = _runtime()
    store = RecordingProgressStore()
    row = {
        "id": "fleet",
        "name": "Fleet",
        "steps": [
            {
                "id": "check-1",
                "type": "ssh_run",
                "on_error": "continue",
                "_aria_ssh_fanout_group": "1:check",
                "_aria_ssh_fanout_index": 1,
                "_aria_ssh_fanout_total": 2,
                "params": {"connection_ref": "host-a", "command": "uptime"},
            },
            {
                "id": "check-2",
                "type": "ssh_run",
                "on_error": "continue",
                "_aria_ssh_fanout_group": "1:check",
                "_aria_ssh_fanout_index": 2,
                "_aria_ssh_fanout_total": 2,
                "params": {"connection_ref": "host-b", "command": "uptime"},
            },
        ],
    }

    result = asyncio.run(RecipeStepExecutor(runtime).execute(
        row, "run", language="en", user_id="alice", progress_store=store,
    ))

    assert result.success is True
    assert runtime.calls == ["host-a", "host-b"]
    assert any(event["host_ref"] == "host-a" and event["ok_count"] == 1 for event in store.events)
    assert any(
        event["host_ref"] == "host-b" and event["host_index"] == 2
        and event["host_total"] == 2 and event["ok_count"] == 1 and event["error_count"] == 1
        for event in store.events
    )
    assert all(event["step_total"] == 2 for event in store.events)
    assert store.get("bob") is None


def test_recipe_executor_without_progress_context_is_behaviorally_unchanged() -> None:
    runtime = _runtime()
    row = {
        "id": "single",
        "name": "Single",
        "steps": [{"id": "check", "type": "ssh_run", "params": {"connection_ref": "host-a", "command": "uptime"}}],
    }

    result = asyncio.run(RecipeStepExecutor(runtime).execute(row, "run", language="en"))

    assert result.success is True
    assert runtime.calls == ["host-a"]
