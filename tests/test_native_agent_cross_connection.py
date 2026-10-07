from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from aria.modules.configuration_foundations.config import LLMConfig
from aria.modules.native_agent.handler import run_native_agent_turn
from aria.modules.native_agent.pending_store import NativePendingStore
from aria.modules.platform_primitives.actionable_sequence import (
    CrossHostRecipeSuggestionStore,
    LastActionableSequenceStore,
    ObservedSequenceStore,
)
from aria.modules.sdk import NativeToolBinding, NativeToolContract, NativeToolResult


def _recipe_remember_binding() -> NativeToolBinding:
    async def handler(_context, _arguments):  # noqa: ANN001
        return NativeToolResult("saved", "recipe_remember")

    return NativeToolBinding(NativeToolContract(
        owner_module_id="recipe_runtime",
        name="recipe_remember",
        description="Remember Recipe.",
        input_schema={"type": "object", "properties": {"name": {"type": "string"}}, "required": []},
        effect="mutating",
        confirmation_required=True,
        source_authority="recipes:test",
        user_scoped=True,
        rollout_flag="test",
        order=2,
        relay_result_content=True,
    ), handler)


def _action_binding(tool_name: str) -> NativeToolBinding:
    async def handler(_context, arguments):  # noqa: ANN001
        return NativeToolResult(
            '{"status":"ok"}',
            tool_name,
            actionable_arguments=dict(arguments),
            actionable_outcome="success",
        )

    return NativeToolBinding(NativeToolContract(
        owner_module_id="test",
        name=tool_name,
        description="Perform one read or action.",
        input_schema={"type": "object", "properties": {}, "required": []},
        effect="read_only",
        confirmation_required=False,
        source_authority="test:connection",
        user_scoped=True,
        rollout_flag="test",
        order=1,
    ), handler)


class _SameVectorEmbedder:
    model = "text-embedding-3-small"

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def embed(self, inputs, **_kwargs):  # noqa: ANN001, ANN003
        self.calls.append(list(inputs))
        return SimpleNamespace(vectors=[[1.0, 0.0] for _item in inputs])


async def _run_action(
    *, tmp_path: Path, turn_id: str, tool_name: str, arguments: dict[str, str],
    existing_recipes, observed_store: ObservedSequenceStore | None = None,  # noqa: ANN001
    actionable_store: LastActionableSequenceStore | None = None,
    suggestions: CrossHostRecipeSuggestionStore | None = None,
    embedding_cache: dict[str, tuple[float, ...]] | None = None,
) -> tuple[object, NativePendingStore, _SameVectorEmbedder]:
    calls = 0
    embedder = _SameVectorEmbedder()
    pending = NativePendingStore(tmp_path / f"pending-{turn_id}.sqlite3")

    async def completion(**_kwargs):  # noqa: ANN003
        nonlocal calls
        calls += 1
        if calls == 1:
            function = SimpleNamespace(name=tool_name, arguments=json.dumps(arguments))
            return SimpleNamespace(choices=[SimpleNamespace(
                message=SimpleNamespace(
                    content="", tool_calls=[SimpleNamespace(id=f"call-{turn_id}", function=function)],
                ),
                finish_reason="tool_use",
            )])
        return SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content="Done.", tool_calls=[]),
            finish_reason="stop",
        )])

    outcome = await run_native_agent_turn(
        message=f"run {tool_name}",
        user_id="alice",
        turn_id=turn_id,
        llm_config=LLMConfig(model="fake"),
        tool_bindings=(_action_binding(tool_name), _recipe_remember_binding()),
        completion=completion,
        actionable_sequence_store=actionable_store or LastActionableSequenceStore(),
        observed_sequence_store=observed_store or ObservedSequenceStore(tmp_path / f"observed-{turn_id}.json"),
        existing_recipes=existing_recipes,
        embedding_client=embedder,
        recipe_embedding_cache=embedding_cache if embedding_cache is not None else {},
        cross_host_suggestion_store=suggestions or CrossHostRecipeSuggestionStore(),
        pending_store=pending,
        trace_root=tmp_path / "trace",
    )
    return outcome, pending, embedder


@pytest.mark.parametrize(
    ("tool_name", "arguments", "step_type", "source_key", "current_key"),
    (
        (
            "file_read",
            {"connection_kind": "sftp", "connection_ref": "files-b", "path": "/logs/current.log"},
            "sftp_read",
            {"remote_path": "/logs/archive.log"},
            "/logs/current.log",
        ),
        (
            "http_api_request",
            {"connection_kind": "http_api", "connection_ref": "api-b", "request_path": "/v2/health"},
            "http_api_request",
            {"request_path": "/v1/health"},
            "/v2/health",
        ),
        (
            "mqtt_publish",
            {"connection_kind": "mqtt", "connection_ref": "mqtt-b", "topic": "sensors/current"},
            "mqtt_publish",
            {"topic": "sensors/archive"},
            "sensors/current",
        ),
    ),
)
def test_same_type_cross_connection_offer_repoints_frozen_recipe(
    tmp_path: Path, tool_name: str, arguments: dict[str, str], step_type: str,
    source_key: dict[str, str], current_key: str,
) -> None:
    target_ref = arguments["connection_ref"]
    source_ref = target_ref.replace("-b", "-a")
    recipe = {
        "id": f"recipe-{step_type}",
        "name": f"Stored {step_type}",
        "enabled": True,
        "steps": (
            {"id": "s1", "type": step_type, "params": {"connection_ref": source_ref, **source_key}},
            {"id": "s2", "type": step_type, "params": {"connection_ref": source_ref, **source_key}},
            {"id": "s3", "type": step_type, "params": {"connection_ref": "leave-alone", **source_key}},
        ),
    }

    outcome, pending, embedder = asyncio.run(_run_action(
        tmp_path=tmp_path,
        turn_id=step_type,
        tool_name=tool_name,
        arguments=arguments,
        existing_recipes=(recipe,),
    ))

    assert embedder.calls == [[current_key, next(iter(source_key.values()))]]
    assert outcome.semantic_match_recipe == recipe["name"]
    assert outcome.semantic_similarity == pytest.approx(1.0)
    assert outcome.suggestion_affordance["kind"] == "cross_host"
    assert outcome.suggestion_affordance["label"] == f"Create copy for {target_ref}"
    frozen = pending.peek(user_id="alice", token=outcome.suggestion_affordance["token"])
    assert frozen is not None and frozen.tool_name == "recipe_remember"
    copied = frozen.frozen_arguments["_frozen_recipe"]
    assert copied["description"] == f"Inactive copy of {recipe['name']} for {target_ref}"
    assert [step["params"]["connection_ref"] for step in copied["steps"]] == [
        target_ref, target_ref, "leave-alone",
    ]


def test_other_primary_step_type_never_matches_even_with_identical_embedding(tmp_path: Path) -> None:
    recipe = {
        "id": "wrong-kind",
        "name": "Wrong kind",
        "enabled": True,
        "steps": ({
            "id": "s1", "type": "http_api_request",
            "params": {"connection_ref": "api-a", "request_path": "/logs/current.log"},
        },),
    }

    outcome, _pending, embedder = asyncio.run(_run_action(
        tmp_path=tmp_path,
        turn_id="different-kind",
        tool_name="file_read",
        arguments={"connection_kind": "sftp", "connection_ref": "files-b", "path": "/logs/current.log"},
        existing_recipes=(recipe,),
    ))

    assert embedder.calls == [["/logs/current.log"]]
    assert outcome.semantic_match_recipe == ""
    assert outcome.semantic_similarity == 0.0
    assert outcome.suggestion_affordance is None


def test_same_connection_never_offers_copy(tmp_path: Path) -> None:
    recipe = {
        "id": "same-connection",
        "name": "Same connection",
        "enabled": True,
        "steps": ({
            "id": "s1", "type": "sftp_read",
            "params": {"connection_ref": "files-a", "remote_path": "/logs/archive.log"},
        },),
    }

    outcome, _pending, embedder = asyncio.run(_run_action(
        tmp_path=tmp_path,
        turn_id="same-connection",
        tool_name="file_read",
        arguments={"connection_kind": "sftp", "connection_ref": "files-a", "path": "/logs/current.log"},
        existing_recipes=(recipe,),
    ))

    assert embedder.calls == [["/logs/current.log", "/logs/archive.log"]]
    assert outcome.semantic_match_recipe == ""
    assert outcome.suggestion_affordance is None


def test_cross_connection_offer_is_one_shot_per_recipe_and_target_pair(tmp_path: Path) -> None:
    recipe = {
        "id": "sftp-copy",
        "name": "SFTP copy",
        "enabled": True,
        "steps": ({
            "id": "s1", "type": "sftp_read",
            "params": {"connection_ref": "files-a", "remote_path": "/logs/archive.log"},
        },),
    }
    observed = ObservedSequenceStore(tmp_path / "observed-shared.json")
    actionable = LastActionableSequenceStore()
    suggestions = CrossHostRecipeSuggestionStore()
    cache: dict[str, tuple[float, ...]] = {}

    outcomes = [
        asyncio.run(_run_action(
            tmp_path=tmp_path,
            turn_id=turn_id,
            tool_name="file_read",
            arguments={"connection_kind": "sftp", "connection_ref": target, "path": path},
            existing_recipes=(recipe,),
            observed_store=observed,
            actionable_store=actionable,
            suggestions=suggestions,
            embedding_cache=cache,
        ))[0]
        for turn_id, target, path in (
            ("pair-1", "files-b", "/logs/current.log"),
            ("pair-2", "files-b", "/logs/today.log"),
            ("pair-3", "files-c", "/logs/current.log"),
        )
    ]

    assert outcomes[0].semantic_match_recipe == "SFTP copy"
    assert outcomes[0].suggestion_affordance["new_host"] == "files-b"
    assert outcomes[1].semantic_match_recipe == ""
    assert outcomes[1].suggestion_affordance is None
    assert outcomes[2].semantic_match_recipe == "SFTP copy"
    assert outcomes[2].suggestion_affordance["new_host"] == "files-c"
