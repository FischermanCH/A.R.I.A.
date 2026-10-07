from __future__ import annotations

import asyncio
from collections import Counter
from types import SimpleNamespace

import pytest

from aria.modules.action_confirmation.ledger import ActionConfirmationLedger
from aria.modules.configuration_foundations.config import Settings
from aria.modules.native_agent import pipeline_bridge, tool_registry
from aria.modules.native_agent.handler import NativeAgentOutcome
from aria.modules.native_agent.pending_store import NativePendingStore
from aria.modules.pipeline_orchestrator.pipeline import Pipeline
from aria.modules.sdk import NativeToolBinding, NativeToolContext, NativeToolContract, NativeToolResult


async def _handler(_context, _arguments):  # noqa: ANN001
    return NativeToolResult('{"status":"ok"}', "test")


def _binding(
    index: int, *, description: str = "Generic maintenance operation.", name: str | None = None,
) -> NativeToolBinding:
    return NativeToolBinding(NativeToolContract(
        owner_module_id="test",
        name=name or f"tool_{index:02d}",
        description=description,
        input_schema={"type": "object", "properties": {}, "required": []},
        effect="read_only",
        confirmation_required=False,
        source_authority="test:synthetic",
        user_scoped=True,
        rollout_flag="test",
        order=index,
    ), _handler)


def _tools(total: int = 41) -> tuple[NativeToolBinding, ...]:
    rows = [
        _binding(index, name=(f"mcp__demo__tool_{index:02d}" if index >= 37 else None))
        for index in range(total)
    ]
    if total > 37:
        rows[7] = _binding(7, description="Create a database backup snapshot.")
        rows[37] = _binding(
            37,
            description="Archive a backup of database storage.",
            name="mcp__demo__tool_37",
        )
    if total > 39:
        rows[39] = _binding(
            39,
            description="Read the current weather forecast.",
            name="mcp__demo__tool_39",
        )
    return tuple(rows)


class _SemanticEmbedder:
    model = "fake-embedding"

    def __init__(self, *, fail: bool = False, malformed: bool = False) -> None:
        self.fail = fail
        self.malformed = malformed
        self.calls: list[list[str]] = []

    async def embed(self, inputs, **_kwargs):  # noqa: ANN001, ANN003
        batch = list(inputs)
        self.calls.append(batch)
        if self.fail:
            raise RuntimeError("embedding unavailable")
        if self.malformed:
            return SimpleNamespace(vectors=[])

        def vector(text: str) -> list[float]:
            lowered = text.lower()
            if "backup" in lowered:
                return [1.0, 0.0]
            if "weather" in lowered:
                return [0.0, 1.0]
            return [-1.0, 0.0]

        return SimpleNamespace(vectors=[vector(text) for text in batch])


def _selector(embedder, cache=None):  # noqa: ANN001
    selector_type = getattr(tool_registry, "EmbeddingNativeToolRelevanceSelector")
    return selector_type(embedding_client=embedder, descriptor_cache=cache if cache is not None else {})


def test_large_catalog_semantically_ranks_and_wrapper_preserves_rank_order() -> None:
    tools = _tools()
    selector = _selector(_SemanticEmbedder())

    selected = asyncio.run(tool_registry.select_relevant_native_tools(
        "Please backup the database", tools, selector=selector, top_k=2,
    ))

    assert [binding.contract.name for binding in selected[:37]] == [f"tool_{index:02d}" for index in range(37)]
    assert [binding.contract.name for binding in selected[37:]] == [
        "mcp__demo__tool_37", "mcp__demo__tool_39",
    ]
    assert selector.last_telemetry.active is True
    assert selector.last_telemetry.selected == 2
    assert selector.last_telemetry.total == 4
    assert selector.last_telemetry.fallback is False


def test_small_catalog_returns_every_tool_without_invoking_selector_or_embedder() -> None:
    tools = _tools(40)
    embedder = _SemanticEmbedder()
    selector = _selector(embedder)

    selected = asyncio.run(tool_registry.select_relevant_native_tools(
        "Please backup the database", tools, selector=selector,
    ))

    assert selected == tools
    assert embedder.calls == []
    assert selector.last_telemetry.active is False


def test_large_core_only_catalog_keeps_every_tool_without_selector_call() -> None:
    tools = tuple(_binding(index) for index in range(45))
    embedder = _SemanticEmbedder()
    selector = _selector(embedder)

    selected = asyncio.run(tool_registry.select_relevant_native_tools(
        "Please backup the database", tools, selector=selector,
    ))

    assert selected == tools
    assert embedder.calls == []


@pytest.mark.parametrize("embedder", [None, _SemanticEmbedder(fail=True), _SemanticEmbedder(malformed=True)])
def test_missing_failed_or_malformed_embedding_falls_back_without_exception(
    embedder, caplog,
) -> None:  # noqa: ANN001
    tools = _tools()
    selector = _selector(embedder)

    selected = asyncio.run(tool_registry.select_relevant_native_tools(
        "Please backup the database", tools, selector=selector, top_k=8,
    ))

    assert selected == (*tools[:37], *tools[37:45])
    assert selector.last_telemetry.fallback is True
    assert selector.last_telemetry.selected == 4
    assert selector.last_telemetry.total == 4
    assert "Native Tool relevance selector fallback" in caplog.text


def test_descriptor_embeddings_are_cached_and_only_changed_descriptor_is_refreshed() -> None:
    tools = _tools()
    changed = list(tools)
    changed[5] = _binding(5, description="Create a backup verification report.")
    embedder = _SemanticEmbedder()
    cache: dict[tuple[str, str], tuple[float, ...]] = {}
    selector = _selector(embedder, cache)

    asyncio.run(selector("Please backup the database", tools, 8))
    asyncio.run(selector("Please backup the database", tools, 8))
    asyncio.run(selector("Please backup the database", tuple(changed), 8))

    assert [len(batch) for batch in embedder.calls] == [42, 1, 2]
    descriptor_inputs = Counter(text for batch in embedder.calls for text in batch if "\n" in text)
    assert all(count == 1 for count in descriptor_inputs.values())
    assert len(cache) == 42


def test_same_message_and_catalog_are_deterministic_across_warm_cache() -> None:
    tools = _tools()
    selector = _selector(_SemanticEmbedder())

    first = asyncio.run(selector("Please backup the database", tools, 8))
    second = asyncio.run(selector("Please backup the database", tools, 8))

    assert first == second
    assert first[:2] == ("tool_07", "mcp__demo__tool_37")


def test_missing_selector_guard_remains_for_large_catalog() -> None:
    with pytest.raises(RuntimeError, match="native_tool_relevance_selector_unavailable"):
        asyncio.run(tool_registry.select_relevant_native_tools(
            "Please backup the database", _tools(), selector=None,
        ))


class _PromptLoader:
    def get_persona(self) -> str:
        return "ARIA"


class _LLM:
    usage_meter = None


def _pipeline(embedder: _SemanticEmbedder, tmp_path, *, top_k: int = 16) -> Pipeline:  # noqa: ANN001
    settings = Settings.model_validate({
        "llm": {"model": "fake"},
        "memory": {"enabled": False},
        "agentic_loop": {
            "enabled": True,
            "native_agent_memory_enabled": True,
            "native_tool_selector_top_k": top_k,
        },
        "token_tracking": {"enabled": False, "log_file": str(tmp_path / "tokens.jsonl")},
    })
    owner = Pipeline(
        settings=settings, prompt_loader=_PromptLoader(), llm_client=_LLM(),
        embedding_client=embedder,
    )
    owner._project_root = tmp_path
    owner._stored_recipes_dir = tmp_path / "recipes"
    return owner


def test_pipeline_owner_wires_selector_and_large_catalog_emits_debug_line(
    monkeypatch, tmp_path,
) -> None:  # noqa: ANN001
    embedder = _SemanticEmbedder()
    owner = _pipeline(embedder, tmp_path, top_k=5)
    tools = _tools(69)
    captured: dict[str, object] = {}
    monkeypatch.setattr(pipeline_bridge, "assemble_native_tools", lambda *_args, **_kwargs: tools)
    monkeypatch.setattr(
        pipeline_bridge, "filter_tools_by_configured_connections", lambda rows, _settings: tuple(rows),
    )

    async def fake_run(**kwargs):  # noqa: ANN003
        captured.update(kwargs)
        return NativeAgentOutcome("final_answer", "Done", 1)

    monkeypatch.setattr(pipeline_bridge, "run_native_agent_turn", fake_run)

    result = asyncio.run(pipeline_bridge.run_native_agent_first_stage(
        owner, message="Please backup the database", user_id="alice", request_id="selector-turn",
        source="test", start=0.0,
    ))

    assert result is not None and result.text == "Done"
    assert hasattr(owner, "_native_tool_relevance_selector")
    assert hasattr(owner, "_native_tool_descriptor_embedding_cache")
    assert all(item.contract.name in {row.contract.name for row in captured["tool_bindings"]} for item in tools[:37])
    assert "mcp__demo__tool_37" in {row.contract.name for row in captured["tool_bindings"]}
    assert len(captured["tool_bindings"]) == 42
    assert any(
        line.startswith("Routing Debug: tool_selector active=yes selected=42/69 ms=")
        and line.endswith(" fallback=no")
        for line in result.detail_lines
    )


def test_pipeline_small_catalog_stays_inert_and_has_no_selector_detail(monkeypatch, tmp_path) -> None:  # noqa: ANN001
    embedder = _SemanticEmbedder()
    owner = _pipeline(embedder, tmp_path)
    tools = _tools(37)
    captured: dict[str, object] = {}
    monkeypatch.setattr(pipeline_bridge, "assemble_native_tools", lambda *_args, **_kwargs: tools)
    monkeypatch.setattr(
        pipeline_bridge, "filter_tools_by_configured_connections", lambda rows, _settings: tuple(rows),
    )

    async def fake_run(**kwargs):  # noqa: ANN003
        captured.update(kwargs)
        return NativeAgentOutcome("final_answer", "Done", 1)

    monkeypatch.setattr(pipeline_bridge, "run_native_agent_turn", fake_run)
    result = asyncio.run(pipeline_bridge.run_native_agent_first_stage(
        owner, message="Please backup the database", user_id="alice", request_id="inert-turn",
        source="test", start=0.0,
    ))

    assert result is not None and len(captured["tool_bindings"]) == 37
    assert embedder.calls == []
    assert not any("tool_selector" in line for line in result.detail_lines)


def test_pipeline_embedding_failure_reports_fallback_and_keeps_turn_alive(monkeypatch, tmp_path) -> None:  # noqa: ANN001
    owner = _pipeline(_SemanticEmbedder(fail=True), tmp_path)
    tools = _tools(69)
    captured: dict[str, object] = {}
    monkeypatch.setattr(pipeline_bridge, "assemble_native_tools", lambda *_args, **_kwargs: tools)
    monkeypatch.setattr(
        pipeline_bridge, "filter_tools_by_configured_connections", lambda rows, _settings: tuple(rows),
    )

    async def fake_run(**kwargs):  # noqa: ANN003
        captured.update(kwargs)
        return NativeAgentOutcome("final_answer", "Fallback turn", 1)

    monkeypatch.setattr(pipeline_bridge, "run_native_agent_turn", fake_run)
    result = asyncio.run(pipeline_bridge.run_native_agent_first_stage(
        owner, message="Please backup the database", user_id="alice", request_id="fallback-turn",
        source="test", start=0.0,
    ))

    assert result is not None and result.text == "Fallback turn"
    assert tuple(captured["tool_bindings"]) == (*tools[:37], *tools[37:53])
    assert any(
        line.startswith("Routing Debug: tool_selector active=yes selected=53/69 ms=")
        and line.endswith(" fallback=yes")
        for line in result.detail_lines
    )


def test_pipeline_confirmation_turn_skips_selector_and_executes_pending_tool_outside_top_k(
    monkeypatch, tmp_path,
) -> None:  # noqa: ANN001
    owner = _pipeline(_SemanticEmbedder(), tmp_path)
    executed: list[dict[str, object]] = []

    async def pending_handler(context: NativeToolContext, arguments):  # noqa: ANN001
        executed.append({"user_id": context.user_id, **dict(arguments)})
        return NativeToolResult('{"status":"ok","source":"pending-tool"}', "tool_40")

    tools = list(_tools())
    tools[40] = NativeToolBinding(NativeToolContract(
        owner_module_id="test",
        name="tool_40",
        description="Execute the pending external action.",
        input_schema={
            "type": "object",
            "properties": {"target": {"type": "string"}},
            "required": ["target"],
            "additionalProperties": False,
        },
        effect="mutating",
        confirmation_required=True,
        source_authority="test:synthetic",
        user_scoped=True,
        rollout_flag="test",
        order=40,
        relay_result_content=True,
    ), pending_handler)
    monkeypatch.setattr(pipeline_bridge, "assemble_native_tools", lambda *_args, **_kwargs: tuple(tools))
    monkeypatch.setattr(
        pipeline_bridge, "filter_tools_by_configured_connections", lambda rows, _settings: tuple(rows),
    )

    selector_calls: list[tuple[str, int]] = []

    async def excluding_selector(message, bindings, top_k):  # noqa: ANN001
        selector_calls.append((str(message), len(bindings)))
        return tuple(binding.contract.name for binding in bindings[:top_k])

    owner._native_tool_relevance_selector = excluding_selector
    owner._native_pending_store = NativePendingStore(tmp_path / "pending.sqlite3")
    owner._native_confirmation_ledger = ActionConfirmationLedger(tmp_path / "ledger.sqlite3")
    token = "napendingtool40"
    owner._native_pending_store.put(
        user_id="alice",
        token=token,
        tool_name="tool_40",
        frozen_arguments={"target": "scene"},
        preview="Execute pending external action for scene.",
        request_message="Execute the external action",
    )

    result = asyncio.run(pipeline_bridge.run_native_agent_first_stage(
        owner,
        message=f"confirm action {token}",
        user_id="alice",
        request_id="confirm-large-catalog",
        source="test",
        start=0.0,
        confirmation_token=token,
    ))

    assert result is not None
    assert result.text == '{"status":"ok","source":"pending-tool"}'
    assert executed == [{"user_id": "alice", "target": "scene"}]
    assert selector_calls == []
    assert not any("tool_selector" in line for line in result.detail_lines)
