from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from aria.modules import MODULE_MANIFESTS
from aria.modules.configuration_foundations.config import LLMConfig
from aria.modules.document_memory import native_tools as document_native_tools
from aria.modules.native_agent.handler import MAX_TOOL_RESULT_CHARS, run_native_agent_turn
from aria.modules.native_agent.tool_registry import assemble_native_tools, select_relevant_native_tools
from aria.modules.sdk import NativeToolBinding, NativeToolContract, NativeToolResult
from aria.modules.skill_contracts.contracts import SkillResult


def _response(*, content: str = "", tool_name: str = "", arguments: dict | None = None):
    calls = []
    finish = "stop"
    if tool_name:
        calls = [SimpleNamespace(id=f"call-{tool_name}", function=SimpleNamespace(
            name=tool_name, arguments=json.dumps(arguments or {}),
        ))]
        finish = "tool_use"
    return SimpleNamespace(choices=[SimpleNamespace(
        message=SimpleNamespace(content=content, tool_calls=calls), finish_reason=finish,
    )])


def _owner(*, foreign: str = "") -> SimpleNamespace:
    async def memory(user_id, _arguments):
        return ({"source_authority": "memory:context_collections", "scope_user_id": foreign or user_id,
                 "type": "preference", "text": "prefers concise answers", "timestamp": "now",
                 "collection": "preferences", "embedding_fingerprint": "internal-secret"},)

    async def learning(user_id, _kind):
        return ({"source_authority": "learning:runtime_stores", "scope_user_id": foreign or user_id,
                 "type": "reflection", "title": "Review", "summary": "Use exact IDs", "text": "",
                 "status": "active", "timestamp": "now", "governor_policy": "internal-secret"},)

    async def notes(user_id, _arguments):
        return ({"source_authority": "notes:markdown_store", "scope_user_id": foreign or user_id,
                 "note_id": "note-1", "title": "Runbook", "folder": "Ops", "excerpt": "Restart safely",
                 "updated_at": "now", "relative_path": "private/path.md"},)

    async def documents(user_id, _arguments):
        return ({"source_authority": "documents:document_store", "scope_user_id": foreign or user_id,
                 "document_id": "doc-1", "document_name": "Manual", "excerpt": "Safe procedure",
                 "answer": "Use the safe procedure", "collection": "internal-collection"},)

    return SimpleNamespace(
        settings=SimpleNamespace(), memory_skill=object(),
        _native_agent_memory_context_loader=memory,
        _native_agent_learning_context_loader=learning,
        _native_agent_notes_loader=notes,
        _native_agent_documents_loader=documents,
    )


def _tools(owner=None):  # noqa: ANN001
    return assemble_native_tools(
        MODULE_MANIFESTS, runtime_owner=owner or _owner(),
        enabled_rollout_flags={"native_agent_memory_enabled", "native_agent_connections_enabled"},
    )


@pytest.mark.parametrize(("tool_name", "arguments", "needle", "forbidden"), (
    ("memory_context_read", {"query": "preferences"}, "prefers concise answers", "embedding_fingerprint"),
    ("notes_read_search_inventory", {"action": "open", "note_id": "note-1"}, "Restart safely", "relative_path"),
    ("documents_read_search_inventory", {"action": "answer", "query": "procedure"}, "safe procedure", "embedding_fingerprint"),
))
def test_native_read_tool_roundtrip_is_source_bound_and_allowlisted(
    tmp_path, tool_name: str, arguments: dict, needle: str, forbidden: str,
) -> None:
    calls: list[dict] = []

    async def completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return _response(tool_name=tool_name, arguments=arguments)
        result = kwargs["messages"][-1]["content"]
        assert needle in result
        assert forbidden not in result
        return _response(content=f"answer from {tool_name}")

    outcome = asyncio.run(run_native_agent_turn(
        message="read my data", user_id="u1", turn_id=tool_name,
        llm_config=LLMConfig(model="fake"), tool_bindings=_tools(),
        completion=completion, trace_root=tmp_path,
    ))

    assert outcome.kind == "final_answer"
    assert outcome.used_tool_names == (tool_name,)
    assert all("response_format" not in call for call in calls)


@pytest.mark.parametrize("tool_name", (
    "memory_context_read",
    "notes_read_search_inventory", "documents_read_search_inventory",
))
def test_native_read_tools_reject_foreign_user_scope(tmp_path, tool_name: str) -> None:
    arguments = {
        "memory_context_read": {},
        "notes_read_search_inventory": {"action": "inventory"},
        "documents_read_search_inventory": {"action": "inventory"},
    }[tool_name]

    async def completion(**_kwargs):
        return _response(tool_name=tool_name, arguments=arguments)

    outcome = asyncio.run(run_native_agent_turn(
        message="read", user_id="u1", turn_id=f"foreign-{tool_name}",
        llm_config=LLMConfig(model="fake"), tool_bindings=_tools(_owner(foreign="u2")),
        completion=completion, trace_root=tmp_path,
    ))
    assert outcome.kind == "fail_closed"
    assert outcome.reason.endswith("_scope_mismatch")


@pytest.mark.parametrize(("tool_name", "arguments", "empty_status"), (
    ("memory_context_read", {}, "no_memory_context"),
    ("notes_read_search_inventory", {"action": "inventory"}, "no_notes"),
    ("documents_read_search_inventory", {"action": "inventory"}, "no_documents"),
))
def test_native_read_tools_report_honest_empty_results(tmp_path, tool_name, arguments, empty_status) -> None:  # noqa: ANN001
    owner = _owner()

    async def empty(*_args):
        return ()

    setattr(owner, {
        "memory_context_read": "_native_agent_memory_context_loader",
        "notes_read_search_inventory": "_native_agent_notes_loader",
        "documents_read_search_inventory": "_native_agent_documents_loader",
    }[tool_name], empty)
    calls = []

    async def completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return _response(tool_name=tool_name, arguments=arguments)
        assert f'"status": "{empty_status}"' in kwargs["messages"][-1]["content"]
        return _response(content="Nothing stored.")

    outcome = asyncio.run(run_native_agent_turn(
        message="read", user_id="u1", turn_id=f"empty-{tool_name}",
        llm_config=LLMConfig(model="fake"), tool_bindings=_tools(owner),
        completion=completion, trace_root=tmp_path,
    ))
    assert outcome.kind == "final_answer"


def test_registry_has_twenty_read_only_tools_below_selector_threshold() -> None:
    tools = _tools()
    assert [tool.contract.name for tool in tools] == [
        "recall_personal_memory", "memory_context_read",
        "notes_read_search_inventory", "documents_read_search_inventory",
        "list_connections", "lookup_connection",
        "capabilities_inventory", "product_release_read", "recipes_inventory",
        "recipes_explain", "recipes_preview", "web_search_fetch", "website_list", "website_read",
        "rss_feed_read", "calendar_read", "file_list", "file_read", "mail_read", "mail_search",
    ]
    assert all(tool.contract.effect == "read_only" for tool in tools)
    assert all(not tool.contract.confirmation_required for tool in tools)
    assert asyncio.run(select_relevant_native_tools("question", tools, selector=None)) == tools


@pytest.mark.parametrize(("tool_name", "arguments", "reason"), (
    ("memory_context_read", {"user_id": "u2"}, "native_agent_memory_context_arguments_invalid"),
    ("notes_read_search_inventory", {"action": "inventory", "user_id": "u2"}, "native_agent_notes_arguments_invalid"),
    ("documents_read_search_inventory", {"action": "inventory", "user_id": "u2"}, "native_agent_documents_arguments_invalid"),
))
def test_native_read_tools_reject_model_controlled_user_scope(tmp_path, tool_name, arguments, reason) -> None:  # noqa: ANN001
    async def completion(**_kwargs):
        return _response(tool_name=tool_name, arguments=arguments)

    outcome = asyncio.run(run_native_agent_turn(
        message="read u2", user_id="u1", turn_id="model-scope-read",
        llm_config=LLMConfig(model="fake"), tool_bindings=_tools(),
        completion=completion, trace_root=tmp_path,
    ))
    assert outcome.kind == "fail_closed"
    assert outcome.reason == reason


@pytest.mark.parametrize(("tool_name", "loader_name", "arguments"), (
    ("memory_context_read", "_native_agent_memory_context_loader", {}),
    ("notes_read_search_inventory", "_native_agent_notes_loader", {"action": "inventory"}),
    ("documents_read_search_inventory", "_native_agent_documents_loader", {"action": "inventory"}),
))
def test_native_read_tools_reject_wrong_source_authority(tmp_path, tool_name, loader_name, arguments) -> None:  # noqa: ANN001
    owner = _owner()

    async def wrong_source(user_id, *_args):  # noqa: ANN001
        return ({"source_authority": "foreign:store", "scope_user_id": user_id, "text": "unsafe"},)

    setattr(owner, loader_name, wrong_source)

    async def completion(**_kwargs):
        return _response(tool_name=tool_name, arguments=arguments)

    outcome = asyncio.run(run_native_agent_turn(
        message="read", user_id="u1", turn_id=f"source-{tool_name}",
        llm_config=LLMConfig(model="fake"), tool_bindings=_tools(owner),
        completion=completion, trace_root=tmp_path,
    ))
    assert outcome.kind == "fail_closed"
    assert outcome.reason.endswith("_source_authority_mismatch")


def test_every_native_tool_result_is_hard_capped_with_honest_marker(tmp_path) -> None:  # noqa: ANN001
    async def oversized(_context, _arguments):  # noqa: ANN001
        return NativeToolResult(json.dumps({"status": "ok", "evidence": "x" * 30000}), "oversized")

    binding = NativeToolBinding(NativeToolContract(
        owner_module_id="test", name="oversized_read", description="test",
        input_schema={"type": "object", "properties": {}, "required": []},
        effect="read_only", confirmation_required=False, source_authority="test:source",
        user_scoped=True, rollout_flag="test", order=1,
    ), oversized)
    calls: list[dict] = []

    async def completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return _response(tool_name="oversized_read")
        content = kwargs["messages"][-1]["content"]
        assert len(content) <= MAX_TOOL_RESULT_CHARS
        payload = json.loads(content)
        assert payload["status"] == "truncated"
        assert payload["truncation"]["truncated"] is True
        assert payload["truncation"]["original_characters"] > payload["truncation"]["shown_characters"]
        assert "gekuerzt" in payload["truncation"]["notice"]
        return _response(content="Best-effort answer from the shown source excerpt.")

    outcome = asyncio.run(run_native_agent_turn(
        message="read large source", user_id="u1", turn_id="global-cap",
        llm_config=LLMConfig(model="fake"), tool_bindings=(binding,),
        completion=completion, trace_root=tmp_path,
    ))

    assert outcome.kind == "final_answer"
    trace = json.loads((tmp_path / "global-cap.jsonl").read_text().splitlines()[0])
    assert len(trace["tool_result"]) <= MAX_TOOL_RESULT_CHARS


def test_documents_inventory_is_metadata_only_and_content_query_is_bounded(tmp_path) -> None:  # noqa: ANN001
    owner = _owner()
    requested: list[dict] = []

    async def documents(user_id, arguments):  # noqa: ANN001
        requested.append(dict(arguments))
        return tuple({
            "source_authority": "documents:document_store", "scope_user_id": user_id,
            "document_id": f"doc-{index}", "document_name": f"Leaflet {index}",
            "excerpt": f"relevant-{index}-" + "x" * 4000,
            "answer": f"answer-{index}-" + "y" * 4000,
        } for index in range(10))

    owner._native_agent_documents_loader = documents
    documents_tool = next(tool for tool in _tools(owner) if tool.contract.name == "documents_read_search_inventory")

    inventory = asyncio.run(documents_tool.handler(
        SimpleNamespace(user_id="u1"), {"action": "inventory"},
    ))
    inventory_payload = json.loads(inventory.content)
    assert len(inventory_payload["documents"]) == 10
    assert all(row["excerpt"] == "" and row["answer"] == "" for row in inventory_payload["documents"])

    answer = asyncio.run(documents_tool.handler(
        SimpleNamespace(user_id="u1"), {"action": "answer", "query": "active ingredients"},
    ))
    answer_payload = json.loads(answer.content)
    assert requested[-1]["query"] == "active ingredients"
    assert len(answer_payload["documents"]) == 6
    assert all(len(row["excerpt"]) <= 1600 and len(row["answer"]) <= 1600 for row in answer_payload["documents"])
    assert answer_payload["selection"]["truncated"] is True
    assert answer_payload["selection"]["shown"] == 6
    assert answer_payload["selection"]["available"] == 10


def test_multi_document_query_uses_one_compact_tool_result_then_answers(tmp_path) -> None:  # noqa: ANN001
    owner = _owner()

    async def documents(user_id, _arguments):  # noqa: ANN001
        return tuple({
            "source_authority": "documents:document_store", "scope_user_id": user_id,
            "document_id": f"doc-{index}", "document_name": f"Leaflet {index}",
            "excerpt": f"Relevant source excerpt {index}", "answer": "",
        } for index in range(12))

    owner._native_agent_documents_loader = documents
    calls: list[dict] = []

    async def completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return _response(
                tool_name="documents_read_search_inventory",
                arguments={"action": "answer", "query": "compare all leaflets"},
            )
        assert len(kwargs["messages"][-1]["content"]) <= MAX_TOOL_RESULT_CHARS
        assert '"shown": 6' in kwargs["messages"][-1]["content"]
        return _response(content="Source-bound comparison of the six shown relevant excerpts; further documents were not shown.")

    outcome = asyncio.run(run_native_agent_turn(
        message="compare all leaflets", user_id="u1", turn_id="multi-doc-compact",
        llm_config=LLMConfig(model="fake"), tool_bindings=_tools(owner),
        completion=completion, trace_root=tmp_path,
    ))

    assert outcome.kind == "final_answer"
    assert outcome.provider_calls == 2
    assert outcome.used_tool_names == ("documents_read_search_inventory",)


def _document_fallback_binding(memory_skill):  # noqa: ANN001
    owner = SimpleNamespace(memory_skill=memory_skill)
    return document_native_tools.native_tool_contributions(owner)[0]


def _inventory_source(index: int, *, collection: str = "aria_docs_u1_medikamente") -> dict:
    return {
        "type": "document",
        "source_type": "document",
        "document_id": f"doc-{index}",
        "document_name": f"Beipackzettel {index}.pdf",
        "collection": collection,
        "chunk_total": index + 2,
        "detail": f"Quelle: Beipackzettel {index}.pdf · {collection}",
    }


def test_document_inventory_fallback_maps_real_skill_sources_instead_of_dropping_listing() -> None:
    sources = tuple(
        [_inventory_source(index) for index in range(5)]
        + [_inventory_source(5, collection="aria_docs_u1_reisen")]
    )
    listing = "\n".join(
        f"- [Dokument: {source['document_name']}] Collection: {source['collection']}"
        for source in sources
    )

    class FakeMemorySkill:
        def __init__(self) -> None:
            self.params: list[dict] = []

        async def execute(self, *, query, params):  # noqa: ANN001
            self.params.append(dict(params))
            return SkillResult(
                skill_name="memory",
                content=listing,
                success=True,
                metadata={"document_inventory": True, "sources": list(sources)},
            )

    skill = FakeMemorySkill()
    binding = _document_fallback_binding(skill)

    # This is the exact Alpha982 failure shape: the listing-as-one-blob is blanked
    # by inventory sanitization and therefore looks empty.
    legacy_items = ({
        "source_authority": document_native_tools.DOCUMENT_SOURCE_AUTHORITY,
        "scope_user_id": "u1",
        "document_id": "",
        "document_name": "",
        "excerpt": listing,
        "answer": "",
    },)
    assert document_native_tools._safe_rows(legacy_items, user_id="u1", action="inventory") == ([], False)

    result = asyncio.run(binding.handler(SimpleNamespace(user_id="u1"), {"action": "inventory"}))
    payload = json.loads(result.content)
    assert payload["status"] == "ok"
    assert len(payload["documents"]) == 6
    assert [row["document_name"] for row in payload["documents"]] == [
        f"Beipackzettel {index}.pdf" for index in range(6)
    ]
    assert payload["documents"][0]["collection"] == "aria_docs_u1_medikamente"
    assert payload["documents"][0]["chunk_count"] == "2"
    assert skill.params == [{
        "action": "recall",
        "user_id": "u1",
        "collection": "",
        "top_k": 200,
        "include_documents": True,
        "docs_only": True,
        "document_inventory": True,
        "document_corpus_scan": True,
    }]

    narrowed = asyncio.run(binding.handler(
        SimpleNamespace(user_id="u1"),
        {"action": "inventory", "query": "medikamente"},
    ))
    narrowed_payload = json.loads(narrowed.content)
    assert len(narrowed_payload["documents"]) == 5
    assert {row["collection"] for row in narrowed_payload["documents"]} == {"aria_docs_u1_medikamente"}


def test_document_inventory_fallback_explicit_cap_avoids_skill_default_twelve() -> None:
    class FakeMemorySkill:
        async def execute(self, *, query, params):  # noqa: ANN001
            assert params["top_k"] == 200
            sources = [_inventory_source(index) for index in range(15)]
            return SkillResult(
                skill_name="memory",
                content="inventory",
                success=True,
                metadata={"document_inventory": True, "sources": sources},
            )

    binding = _document_fallback_binding(FakeMemorySkill())
    result = asyncio.run(binding.handler(SimpleNamespace(user_id="u1"), {"action": "inventory"}))
    payload = json.loads(result.content)
    assert len(payload["documents"]) == 15
    assert payload["selection"] == {
        "shown": 15,
        "available": 15,
        "truncated": False,
        "notice": "alle ausgewaehlten Treffer sind enthalten",
    }


def test_document_search_fallback_maps_named_source_rows_and_keeps_blob_fallback() -> None:
    class FakeMemorySkill:
        def __init__(self) -> None:
            self.with_sources = True

        async def execute(self, *, query, params):  # noqa: ANN001
            if not self.with_sources:
                return SkillResult(skill_name="memory", content="single legacy excerpt", success=True)
            return SkillResult(
                skill_name="memory",
                content="- [DOKUMENT: Leaflet A] dosage A\n- [DOKUMENT: Leaflet B] dosage B",
                success=True,
                metadata={"sources": [
                    {"document_id": "a", "document_name": "Leaflet A", "collection": "meds", "excerpt": "dosage A"},
                    {"document_id": "b", "document_name": "Leaflet B", "collection": "meds", "excerpt": "dosage B"},
                ]},
            )

    skill = FakeMemorySkill()
    binding = _document_fallback_binding(skill)
    named = asyncio.run(binding.handler(
        SimpleNamespace(user_id="u1"), {"action": "search", "query": "dosage"},
    ))
    named_payload = json.loads(named.content)
    assert [(row["document_name"], row["collection"], row["excerpt"]) for row in named_payload["documents"]] == [
        ("Leaflet A", "meds", "dosage A"),
        ("Leaflet B", "meds", "dosage B"),
    ]

    skill.with_sources = False
    legacy = asyncio.run(binding.handler(
        SimpleNamespace(user_id="u1"), {"action": "search", "query": "legacy"},
    ))
    legacy_payload = json.loads(legacy.content)
    assert legacy_payload["documents"][0]["excerpt"] == "single legacy excerpt"


def test_document_tool_description_distinguishes_inventory_completeness_from_content_search() -> None:
    description = _document_fallback_binding(object()).contract.description.lower()
    assert "inventory" in description
    assert "which documents" in description
    assert "never answers content questions" in description
    assert "search never proves completeness" in description


@pytest.mark.parametrize(("tool_name", "loader_name", "arguments", "content_key"), (
    ("memory_context_read", "_native_agent_memory_context_loader", {}, "text"),
    ("notes_read_search_inventory", "_native_agent_notes_loader", {"action": "inventory"}, "excerpt"),
))
def test_large_context_tools_mark_local_content_truncation(
    tool_name: str, loader_name: str, arguments: dict, content_key: str,
) -> None:
    owner = _owner()
    authority = {
        "memory_context_read": "memory:context_collections",
        "notes_read_search_inventory": "notes:markdown_store",
    }[tool_name]

    async def large(user_id, *_args):  # noqa: ANN001
        return ({
            "source_authority": authority, "scope_user_id": user_id,
            "type": "fact", "title": "title", "summary": "summary",
            "text": "x" * 5000, "note_id": "note-1", "folder": "folder",
            "excerpt": "x" * 5000, "status": "active", "timestamp": "now", "updated_at": "now",
        },)

    setattr(owner, loader_name, large)
    binding = next(tool for tool in _tools(owner) if tool.contract.name == tool_name)
    result = asyncio.run(binding.handler(SimpleNamespace(user_id="u1"), arguments))
    payload = json.loads(result.content)

    assert payload["selection"]["truncated"] is True
    assert "gekuerzt" in payload["selection"]["notice"]
    row_key = {"memory_context_read": "memory_context",
               "notes_read_search_inventory": "notes"}[tool_name]
    assert len(payload[row_key][0][content_key]) <= 1600
