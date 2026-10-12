from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from aria.modules.configuration_foundations.config import EmbeddingsConfig, LLMConfig, MemoryConfig
from aria.modules.memory_learning_bridge.skill import MemorySkill
from aria.modules.native_agent import handler as native_handler
from aria.modules.native_agent import pipeline_bridge
from aria.modules.native_agent.pending_store import NativePendingStore
from aria.modules.platform_primitives.connection_refs import resolve_native_connection_arguments
from aria.modules.sdk import NativeToolBinding, NativeToolContext, NativeToolContract, NativeToolResult


ROOT = Path(__file__).resolve().parents[1]


def test_alpha984_release_metadata_keeps_public_alpha983() -> None:
    assert 'version = "0.1.0-alpha1007"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    release_meta = (ROOT / "aria/modules/release_update/release_meta.py").read_text(encoding="utf-8")
    assert 'DEFAULT_RELEASE_LABEL = "0.1.0-alpha1007"' in release_meta
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "0.1.0-alpha983" in readme
    assert "## 0.1.0-alpha984" in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 0.1.0-alpha984" in (ROOT / "CHANGELOG.de.md").read_text(encoding="utf-8")


def _point(point_id: str, payload: dict, *, score: float = 0.9) -> SimpleNamespace:
    return SimpleNamespace(id=point_id, payload=payload, score=score)


class DocumentQdrant:
    def __init__(self, collections: dict[str, list[SimpleNamespace]]) -> None:
        self.collections = collections
        self.scroll_calls: list[str] = []
        self.query_calls: list[tuple[str, object]] = []

    async def get_collections(self):  # noqa: ANN201
        return SimpleNamespace(
            collections=[SimpleNamespace(name=name) for name in sorted(self.collections)]
        )

    async def collection_exists(self, collection_name: str) -> bool:
        return collection_name in self.collections

    @staticmethod
    def _matches(payload: dict, query_filter: object) -> bool:
        for condition in list(getattr(query_filter, "must", ()) or ()):
            match = getattr(condition, "match", None)
            if match is not None and payload.get(str(getattr(condition, "key", ""))) != getattr(match, "value", None):
                return False
        return True

    async def scroll(
        self, collection_name: str, scroll_filter=None, limit: int = 200, offset=None,
        with_payload: bool = True, with_vectors: bool = False,
    ):  # noqa: ANN201
        _ = (with_payload, with_vectors)
        self.scroll_calls.append(collection_name)
        rows = [
            row for row in self.collections.get(collection_name, ())
            if scroll_filter is None or self._matches(dict(row.payload or {}), scroll_filter)
        ]
        start = max(0, int(offset or 0))
        next_offset = start + limit if start + limit < len(rows) else None
        return rows[start:start + limit], next_offset

    async def query_points(self, collection_name: str, query, query_filter, limit: int):  # noqa: ANN001, ANN201
        _ = query
        self.query_calls.append((collection_name, query_filter))
        rows = [
            row for row in self.collections.get(collection_name, ())
            if query_filter is None or self._matches(dict(row.payload or {}), query_filter)
        ]
        return SimpleNamespace(points=rows[:limit])


def _skill(fake: DocumentQdrant) -> MemorySkill:
    skill = MemorySkill(
        memory=MemoryConfig(enabled=True, qdrant_url="http://unused:6333", collection="aria_memory", top_k=3),
        embeddings=EmbeddingsConfig(model="fake-embeddings"),
    )
    skill.qdrant = fake
    skill._collection_ready = True
    skill._active_embedding_fingerprint = lambda: "fp"  # type: ignore[method-assign]
    return skill


def test_document_inventory_uses_guides_without_scrolling_document_chunks() -> None:
    guides = [
        _point(f"guide-{index}", {
            "source": "rag_document_guide", "user_id": "alice",
            "document_id": f"doc-{index}", "document_name": f"document-{index}.pdf",
            "target_collection": f"aria_docs_archive_{index}", "source_type": "pdf",
        })
        for index in range(5)
    ]
    collections = {"aria_doc_guides_alice": guides}
    for index in range(5):
        collections[f"aria_docs_archive_{index}"] = [
            _point(f"chunk-{index}-{chunk}", {
                "source": "rag_upload", "type": "knowledge", "user_id": "alice",
                "document_id": f"doc-{index}", "document_name": f"document-{index}.pdf",
                "text": f"chunk {chunk}",
            })
            for chunk in range(40)
        ]
    fake = DocumentQdrant(collections)

    result = asyncio.run(_skill(fake)._recall_document_inventory(user_id="alice", limit=200))

    assert result.success is True
    assert all(f"document-{index}.pdf" in result.content for index in range(5))
    assert fake.scroll_calls == ["aria_doc_guides_alice"]
    detail = "\n".join(result.metadata["detail_lines"])
    assert "source=catalog" in detail
    assert "ms=" in detail


def test_legacy_inventory_fallback_is_bounded_and_cached() -> None:
    fake = DocumentQdrant({
        "aria_docs_alice": [
            _point("legacy-chunk", {
                "source": "rag_upload", "type": "knowledge", "user_id": "Alice",
                "document_id": "legacy", "document_name": "legacy.pdf", "text": "legacy text",
            })
        ]
    })
    skill = _skill(fake)

    first = asyncio.run(skill._recall_document_inventory(user_id="alice", limit=200))
    first_calls = list(fake.scroll_calls)
    fake.scroll_calls.clear()
    second = asyncio.run(skill._recall_document_inventory(user_id="alice", limit=200))

    assert "legacy.pdf" in first.content and "legacy.pdf" in second.content
    assert first_calls == ["aria_docs_alice"]
    assert fake.scroll_calls == []
    assert "source=fallback" in "\n".join(second.metadata["detail_lines"])


def test_document_inventory_caps_at_two_hundred_and_states_truncation() -> None:
    guides = [
        _point(f"guide-{index}", {
            "source": "rag_document_guide", "user_id": "alice",
            "document_id": f"doc-{index}", "document_name": f"document-{index:03d}.pdf",
            "target_collection": "aria_docs_archive", "source_type": "pdf",
        })
        for index in range(205)
    ]
    fake = DocumentQdrant({"aria_doc_guides_alice": guides})

    result = asyncio.run(_skill(fake)._recall_document_inventory(user_id="alice", limit=999))

    assert result.success is True
    assert len(result.metadata["sources"]) == 200
    assert "[truncated: showing 200 of 205 documents]" in result.content


def test_document_ownership_uses_payload_owner_before_collection_name() -> None:
    fake = DocumentQdrant({
        "aria_docs_whity_medikamente": [
            _point("owned", {
                "source": "rag_upload", "type": "knowledge", "user_id": "Fish_ErMan",
                "document_id": "med-1", "document_name": "medicine.pdf",
                "text": "The private dosage is 5 mg.", "embedding_fingerprint": "fp",
            })
        ]
    })
    skill = _skill(fake)
    target = {
        "type": "document", "label": "DOKUMENT", "collection": "aria_docs_whity_medikamente",
        "top_k": 3, "document_id": "med-1", "owner_user_id": "Fish_ErMan",
    }

    owner_rows = asyncio.run(skill._query_weighted_hits([0.1], "fish_erman", target))
    foreign_rows = asyncio.run(skill._query_weighted_hits([0.1], "whity", target))

    assert [row["text"] for row in owner_rows] == ["The private dosage is 5 mg."]
    assert foreign_rows == []


def test_ownerless_legacy_document_uses_collection_slug_only() -> None:
    fake = DocumentQdrant({
        "aria_docs_Fish_ErMan": [
            _point("legacy", {
                "source": "rag_upload", "type": "knowledge", "document_id": "legacy-1",
                "document_name": "legacy.pdf", "text": "Legacy ownerless content.",
                "embedding_fingerprint": "fp",
            })
        ]
    })
    skill = _skill(fake)
    target = {
        "type": "document", "label": "DOKUMENT", "collection": "aria_docs_Fish_ErMan",
        "top_k": 3, "document_id": "legacy-1", "owner_user_id": "",
    }

    assert asyncio.run(skill._query_weighted_hits([0.1], "fish__erman", target))
    assert asyncio.run(skill._query_weighted_hits([0.1], "whity", target)) == []


def _response(*, content: str = "", tool_calls=(), finish_reason: str = "stop") -> SimpleNamespace:
    return SimpleNamespace(choices=[SimpleNamespace(
        message=SimpleNamespace(content=content, tool_calls=list(tool_calls)), finish_reason=finish_reason,
    )])


def _call(name: str, arguments: dict) -> SimpleNamespace:
    return SimpleNamespace(
        id=f"call-{name}",
        function=SimpleNamespace(name=name, arguments=json.dumps(arguments)),
    )


def _binding(
    *, name: str, effect: str, handler, confirmation_required: bool = False,
    effectful: bool = False,
) -> NativeToolBinding:  # noqa: ANN001
    return NativeToolBinding(NativeToolContract(
        owner_module_id="test", name=name, description="Test tool.",
        input_schema={"type": "object", "properties": {}, "additionalProperties": True},
        effect=effect, confirmation_required=confirmation_required,
        source_authority="test", user_scoped=True, rollout_flag="test",
        effectful=effectful,
    ), handler)


def test_read_only_tool_does_not_authorize_completed_action_claim_and_records_timing(tmp_path) -> None:  # noqa: ANN001
    provider_responses = iter((
        _response(tool_calls=(_call("scene_read", {}),), finish_reason="tool_use"),
        _response(content="Ich habe einen blauen Würfel erstellt."),
        _response(content="Ich habe einen blauen Würfel erstellt."),
    ))

    async def completion(**_kwargs):  # noqa: ANN003
        return next(provider_responses)

    async def read_tool(_context: NativeToolContext, _arguments) -> NativeToolResult:  # noqa: ANN001
        await asyncio.sleep(0)
        return NativeToolResult('{"status":"ok","scene":"empty"}', "scene_read")

    outcome = asyncio.run(native_handler.run_native_agent_turn(
        message="Erstelle einen blauen Würfel.", user_id="alice", turn_id="alpha984-read-claim",
        llm_config=LLMConfig(model="fake"), tool_bindings=(
            _binding(name="scene_read", effect="read_only", handler=read_tool),
        ), completion=completion, trace_root=tmp_path, max_provider_calls=4,
    ))

    assert outcome.reason == "native_agent_action_claim_blocked"
    assert "NICHT ausgeführt" in outcome.message
    assert outcome.tool_timings and outcome.tool_timings[0][0] == "scene_read"
    assert outcome.tool_timings[0][1] >= 0
    assert pipeline_bridge._native_tool_timing_detail_line(outcome).startswith(
        "Routing Debug: tool_timing scene_read="
    )


def test_budget_finalizer_cannot_turn_read_only_observation_into_action_claim(tmp_path) -> None:  # noqa: ANN001
    responses = iter((
        _response(tool_calls=(_call("scene_read", {}),), finish_reason="tool_use"),
        _response(content="Ich habe einen blauen Würfel erstellt."),
    ))

    async def completion(**_kwargs):  # noqa: ANN003
        return next(responses)

    async def read_tool(_context: NativeToolContext, _arguments) -> NativeToolResult:  # noqa: ANN001
        return NativeToolResult('{"status":"ok"}', "scene_read")

    outcome = asyncio.run(native_handler.run_native_agent_turn(
        message="Inspect then create.", user_id="alice", turn_id="read-finalizer-claim",
        llm_config=LLMConfig(model="fake"), tool_bindings=(
            _binding(name="scene_read", effect="read_only", handler=read_tool),
        ), completion=completion, trace_root=tmp_path, max_provider_calls=2,
    ))

    assert outcome.reason == "native_agent_action_claim_blocked"
    assert "NICHT ausgeführt" in outcome.message


def test_successful_mutating_tool_authorizes_completed_action_claim(tmp_path) -> None:  # noqa: ANN001
    provider_responses = iter((
        _response(tool_calls=(_call("cube_create", {}),), finish_reason="tool_use"),
        _response(content="Ich habe einen blauen Würfel erstellt."),
    ))

    async def completion(**_kwargs):  # noqa: ANN003
        return next(provider_responses)

    async def mutate(_context: NativeToolContext, _arguments) -> NativeToolResult:  # noqa: ANN001
        return NativeToolResult('{"status":"ok"}', "cube_create")

    outcome = asyncio.run(native_handler.run_native_agent_turn(
        message="Erstelle einen blauen Würfel.", user_id="alice", turn_id="alpha984-write-claim",
        llm_config=LLMConfig(model="fake"), tool_bindings=(
            _binding(name="cube_create", effect="read_only", handler=mutate, effectful=True),
        ), completion=completion, trace_root=tmp_path,
    ))

    assert outcome.message == "Ich habe einen blauen Würfel erstellt."
    assert outcome.reason == ""


def test_paused_job_snapshot_retains_tool_timings_for_terminal_details(tmp_path) -> None:  # noqa: ANN001
    async def completion(**_kwargs):  # noqa: ANN003
        return _response(tool_calls=(_call("scene_read", {}),), finish_reason="tool_use")

    async def read_tool(_context: NativeToolContext, _arguments) -> NativeToolResult:  # noqa: ANN001
        return NativeToolResult('{"status":"ok"}', "scene_read")

    async def pause_check() -> bool:
        return True

    with pytest.raises(native_handler.NativeAgentPaused) as caught:
        asyncio.run(native_handler.run_native_agent_turn(
            message="Inspect the scene.", user_id="alice", turn_id="timed-pause",
            llm_config=LLMConfig(model="fake"), tool_bindings=(
                _binding(name="scene_read", effect="read_only", handler=read_tool),
            ), completion=completion, trace_root=tmp_path, pause_check=pause_check,
        ))

    assert caught.value.snapshot["tool_timings"][0][0] == "scene_read"


def test_shared_connection_resolver_priorities_and_ambiguity() -> None:
    connections = SimpleNamespace(ssh={
        "srv-dev02": SimpleNamespace(title="Development", host="debdev-srv02"),
        "srv-copy": SimpleNamespace(title="Duplicate", host="duplicate.local"),
        "srv-copy-2": SimpleNamespace(title="Duplicate", host="duplicate-2.local"),
    })
    contract = NativeToolContract(
        owner_module_id="test", name="ssh_read", description="", input_schema={},
        effect="read_only", confirmation_required=False, source_authority="test",
        user_scoped=True, rollout_flag="test", required_connection_kinds=("ssh",),
    )

    resolved = resolve_native_connection_arguments(
        contract, {"command": "df -h", "targets": ["DEBDEV-SRV02"]}, connections,
    )
    assert resolved.arguments["targets"] == ["srv-dev02"]
    assert resolved.error is None

    ambiguous = resolve_native_connection_arguments(
        contract, {"command": "df -h", "targets": ["duplicate"]}, connections,
    )
    assert ambiguous.error is not None
    assert ambiguous.error.status == "connection_ambiguous"
    assert ambiguous.error.candidate_refs == ("srv-copy", "srv-copy-2")

    missing = resolve_native_connection_arguments(
        contract, {"command": "df -h", "targets": ["unknown"]}, connections,
    )
    assert missing.error is not None
    assert missing.error.status == "connection_not_found"
    assert "srv-dev02" in missing.error.candidate_refs

    unrelated = NativeToolContract(
        owner_module_id="mcp", name="mcp__demo__inspect", description="", input_schema={},
        effect="read_only", confirmation_required=False, source_authority="mcp",
        user_scoped=True, rollout_flag="test",
    )
    untouched = resolve_native_connection_arguments(
        unrelated, {"connection_ref": "DEBDEV-SRV02"}, connections,
    )
    assert untouched.error is None
    assert untouched.arguments["connection_ref"] == "DEBDEV-SRV02"


def test_confirmation_freezes_and_previews_canonical_connection_ref(tmp_path) -> None:  # noqa: ANN001
    pending = NativePendingStore(tmp_path / "pending.sqlite3")
    preview_arguments: list[dict] = []
    calls = 0

    async def completion(**_kwargs):  # noqa: ANN003
        nonlocal calls
        calls += 1
        if calls == 1:
            return _response(
                tool_calls=(_call("remote_write", {"connection_ref": "DEBDEV-SRV02"}),),
                finish_reason="tool_use",
            )
        return _response(content="Confirm the write to srv-dev02.")

    async def execute(_context: NativeToolContext, _arguments) -> NativeToolResult:  # noqa: ANN001
        raise AssertionError("must not execute before confirmation")

    async def preview(_context: NativeToolContext, arguments) -> str:  # noqa: ANN001
        preview_arguments.append(dict(arguments))
        return f"Write via {arguments['connection_ref']}"

    binding = NativeToolBinding(NativeToolContract(
        owner_module_id="test", name="remote_write", description="Test write.",
        input_schema={
            "type": "object", "properties": {"connection_ref": {"type": "string"}},
            "required": ["connection_ref"],
        },
        effect="mutating", confirmation_required=True, source_authority="test",
        user_scoped=True, rollout_flag="test", required_connection_kinds=("ssh",),
    ), execute, preview)
    outcome = asyncio.run(native_handler.run_native_agent_turn(
        message="Write on debdev-srv02.", user_id="alice", turn_id="connection-preview",
        llm_config=LLMConfig(model="fake"), tool_bindings=(binding,), completion=completion,
        pending_store=pending, trace_root=tmp_path,
        connection_settings=SimpleNamespace(ssh={
            "srv-dev02": SimpleNamespace(title="Development", host="debdev-srv02"),
        }),
    ))

    stored = pending.peek(user_id="alice", token=outcome.confirmation_token)
    assert outcome.kind == "pending_confirmation"
    assert preview_arguments == [{"connection_ref": "srv-dev02"}]
    assert stored is not None and stored.frozen_arguments == {"connection_ref": "srv-dev02"}
