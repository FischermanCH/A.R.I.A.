from __future__ import annotations

import asyncio
from types import SimpleNamespace

from aria.core.agentic_context_runtime import AgenticContextRuntimeMixin
from aria.core.agentic_context_runtime import SurfaceLoaderRuntime
from aria.core.aria_turn_arbitration import AriaTurnArbitration
from aria.core.aria_turn_arbitration import AriaTurnPlan
from aria.core.context_surfaces import ContextRequest
from aria.skills.base import SkillResult


class _MemorySkill:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def execute(self, query: str, params: dict):
        self.calls.append({"query": query, "params": dict(params)})
        return SkillResult(skill_name="memory_recall", success=True, content="")


class _Owner:
    def __init__(self) -> None:
        self.settings = SimpleNamespace(
            memory=SimpleNamespace(
                top_k=5,
                collections=SimpleNamespace(facts=SimpleNamespace(prefix="aria_facts")),
            )
        )
        self.memory_skill = _MemorySkill()

    def _aria_turn_memory_exists_evidence_query(self, arbitration: AriaTurnArbitration) -> str:
        for request in arbitration.plan.context_requests:
            if request.surface_id == "memory":
                return request.query
        return ""


def test_surface_loader_runtime_loads_memory_exists_without_pipeline_loader_method() -> None:
    owner = _Owner()
    runtime = SurfaceLoaderRuntime(owner)
    arbitration = AriaTurnArbitration(
        plan=AriaTurnPlan(
            intents=("local_retrieval",),
            needs_context=True,
            context_directions=("memory",),
            context_requests=(ContextRequest(surface_id="memory", mode="exists", query="Donald Trump"),),
        )
    )

    result = asyncio.run(
        runtime.load_memory_exists(
            arbitration=arbitration,
            user_id="u1",
            memory_collection="",
            session_collection="",
            context_overrides={
                "memory_target_collections": ["aria_facts_u1"],
                "include_documents": False,
                "memory_top_k": 2,
            },
        )
    )

    assert result.skill_name == "memory_recall"
    assert owner.memory_skill.calls == [
        {
            "query": "Donald Trump",
            "params": {
                "action": "recall",
                "top_k": 2,
                "user_id": "u1",
                "collection": "aria_facts_u1",
                "target_collections": ["aria_facts_u1"],
                "include_documents": False,
                "docs_only": False,
            },
        }
    ]


def test_surface_loader_runtime_passes_docs_only_to_memory_recall() -> None:
    owner = _Owner()
    runtime = SurfaceLoaderRuntime(owner)
    arbitration = AriaTurnArbitration(
        plan=AriaTurnPlan(
            intents=("local_retrieval",),
            needs_context=True,
            context_directions=("docs",),
            context_requests=(ContextRequest(surface_id="docs", mode="search", query="UI-Regel"),),
        )
    )

    result = asyncio.run(
        runtime.load_memory_exists(
            arbitration=arbitration,
            user_id="u1",
            memory_collection="",
            session_collection="",
            context_overrides={
                "include_documents": True,
                "docs_only": True,
                "memory_top_k": 2,
            },
        )
    )

    assert result.skill_name == "memory_recall"
    assert owner.memory_skill.calls[-1]["params"]["include_documents"] is True
    assert owner.memory_skill.calls[-1]["params"]["docs_only"] is True


def test_deep_docs_context_requests_document_corpus_scan() -> None:
    arbitration = AriaTurnArbitration(
        plan=AriaTurnPlan(
            intents=("local_retrieval",),
            needs_context=True,
            context_directions=("docs",),
            context_depth="deep",
            context_requests=(ContextRequest(surface_id="docs", mode="search", query="Glucosamin"),),
        )
    )

    overrides = AgenticContextRuntimeMixin()._aria_turn_context_overrides(arbitration, user_id="u1")

    assert overrides["include_documents"] is True
    assert overrides["docs_only"] is True
    assert overrides["document_corpus_scan"] is True


def test_docs_corpus_priority_requests_document_corpus_scan_even_when_shallow() -> None:
    arbitration = AriaTurnArbitration(
        plan=AriaTurnPlan(
            intents=("local_retrieval",),
            needs_context=True,
            context_directions=("docs",),
            context_depth="shallow",
            context_requests=(ContextRequest(surface_id="docs", mode="search", query="Glucosamin"),),
            priority=("local|docs|document|doc-a", "local|docs|documents"),
        )
    )

    overrides = AgenticContextRuntimeMixin()._aria_turn_context_overrides(arbitration, user_id="u1")

    assert overrides["include_documents"] is True
    assert overrides["docs_only"] is True
    assert overrides["document_corpus_scan"] is True


def test_docs_substance_question_requests_corpus_scan_even_when_meta_is_shallow() -> None:
    arbitration = AriaTurnArbitration(
        plan=AriaTurnPlan(
            intents=("local_retrieval",),
            needs_context=True,
            context_directions=("docs",),
            context_depth="shallow",
            context_requests=(
                ContextRequest(
                    surface_id="docs",
                    mode="search",
                    query="Ist Glucosamin Bestandteil eines der Medikamente deren Beipackzettel wir haben",
                ),
            ),
            priority=("local|docs|document|doc-a",),
        )
    )

    overrides = AgenticContextRuntimeMixin()._aria_turn_context_overrides(arbitration, user_id="u1")

    assert overrides["include_documents"] is True
    assert overrides["docs_only"] is True
    assert overrides["document_corpus_scan"] is True


def test_docs_substance_question_keeps_corpus_scope_from_original_prompt_when_meta_query_is_narrowed() -> None:
    arbitration = AriaTurnArbitration(
        plan=AriaTurnPlan(
            intents=("local_retrieval",),
            needs_context=True,
            context_directions=("docs",),
            context_depth="shallow",
            context_requests=(
                ContextRequest(
                    surface_id="docs",
                    mode="search",
                    query="Glucosamin Bestandteil Olumiant",
                    budget={
                        "entity_type": "local_context",
                        "kind": "document_meta",
                        "document_id": "olumiant-doc",
                        "document_name": "at_olumiant_gebrauchsinformation.pdf",
                        "target_collection": "aria_docs_sample_medications",
                    },
                ),
            ),
            priority=("local|docs|document|olumiant-doc",),
        )
    )

    overrides = AgenticContextRuntimeMixin()._aria_turn_context_overrides(
        arbitration,
        user_id="u1",
        message="Ist Glucosamin Bestandteil eines der Medikamente deren Beipackzettel wir haben",
    )

    assert overrides["include_documents"] is True
    assert overrides["docs_only"] is True
    assert overrides["document_corpus_scan"] is True
    assert overrides["document_target_collections"] == ["aria_docs_sample_medications"]


def test_broad_docs_inventory_keeps_collection_scope_instead_of_selected_ids() -> None:
    arbitration = AriaTurnArbitration(
        plan=AriaTurnPlan(
            intents=("local_retrieval",),
            needs_context=True,
            context_directions=("docs",),
            context_depth="shallow",
            context_requests=(
                ContextRequest(
                    surface_id="docs",
                    mode="search",
                    query="liste auf von was fuer medikamenten wir beipackzettel haben",
                    budget={
                        "entity_type": "local_context",
                        "kind": "document_meta",
                        "document_id": "doc-a",
                        "document_name": "Olumiant.pdf",
                        "target_collection": "aria_docs_sample_medications",
                    },
                ),
            ),
            priority=("local|docs|document|doc-a", "local|docs|documents"),
        )
    )

    overrides = AgenticContextRuntimeMixin()._aria_turn_context_overrides(arbitration, user_id="u1")

    assert overrides["document_inventory"] is True
    assert overrides["document_ids"] == []
    assert overrides["document_names"] == []
    assert overrides["document_target_collections"] == ["aria_docs_sample_medications"]


def test_broad_medication_inventory_keeps_collection_scope_even_without_documents_priority() -> None:
    arbitration = AriaTurnArbitration(
        plan=AriaTurnPlan(
            intents=("local_retrieval",),
            needs_context=True,
            context_directions=("docs",),
            context_depth="shallow",
            context_requests=(
                ContextRequest(
                    surface_id="docs",
                    mode="search",
                    query="liste auf von was fuer medikamenten wir beipackzettel haben",
                    budget={
                        "entity_type": "local_context",
                        "kind": "document_meta",
                        "document_id": "doc-a",
                        "document_name": "Olumiant.pdf",
                        "target_collection": "aria_docs_sample_medications",
                    },
                ),
                ContextRequest(
                    surface_id="docs",
                    mode="search",
                    query="liste auf von was fuer medikamenten wir beipackzettel haben",
                    budget={
                        "entity_type": "local_context",
                        "kind": "document_meta",
                        "document_id": "doc-b",
                        "document_name": "Humira.pdf",
                        "target_collection": "aria_docs_sample_medications",
                    },
                ),
                ContextRequest(
                    surface_id="docs",
                    mode="search",
                    query="liste auf von was fuer medikamenten wir beipackzettel haben",
                    budget={
                        "entity_type": "local_context",
                        "kind": "document_meta",
                        "document_id": "doc-c",
                        "document_name": "Simponi.pdf",
                        "target_collection": "aria_docs_sample_medications",
                    },
                ),
            ),
            priority=("local|docs|document|doc-a", "local|docs|document|doc-b", "local|docs|document|doc-c"),
        )
    )

    overrides = AgenticContextRuntimeMixin()._aria_turn_context_overrides(arbitration, user_id="u1")

    assert overrides["document_inventory"] is True
    assert overrides["document_ids"] == []
    assert overrides["document_names"] == []
    assert overrides["document_target_collections"] == ["aria_docs_sample_medications"]


def test_surface_loader_runtime_passes_document_corpus_scan_to_memory_recall() -> None:
    owner = _Owner()
    runtime = SurfaceLoaderRuntime(owner)
    arbitration = AriaTurnArbitration(
        plan=AriaTurnPlan(
            intents=("local_retrieval",),
            needs_context=True,
            context_directions=("docs",),
            context_requests=(ContextRequest(surface_id="docs", mode="search", query="Glucosamin"),),
        )
    )

    result = asyncio.run(
        runtime.load_memory_exists(
            arbitration=arbitration,
            user_id="u1",
            memory_collection="",
            session_collection="",
            context_overrides={
                "include_documents": True,
                "docs_only": True,
                "document_corpus_scan": True,
                "memory_top_k": 2,
            },
        )
    )

    assert result.skill_name == "memory_recall"
    assert owner.memory_skill.calls[-1]["params"]["document_corpus_scan"] is True


def test_surface_loader_runtime_passes_document_target_collections_for_corpus_scan() -> None:
    owner = _Owner()
    runtime = SurfaceLoaderRuntime(owner)
    arbitration = AriaTurnArbitration(
        plan=AriaTurnPlan(
            intents=("local_retrieval",),
            needs_context=True,
            context_directions=("docs",),
            context_requests=(ContextRequest(surface_id="docs", mode="search", query="Glucosamin"),),
        )
    )

    result = asyncio.run(
        runtime.load_memory_exists(
            arbitration=arbitration,
            user_id="u1",
            memory_collection="",
            session_collection="",
            context_overrides={
                "include_documents": True,
                "docs_only": True,
                "document_corpus_scan": True,
                "document_target_collections": ["aria_docs_sample_medications"],
                "memory_top_k": 2,
            },
        )
    )

    assert result.skill_name == "memory_recall"
    assert owner.memory_skill.calls[-1]["params"]["document_corpus_scan"] is True
    assert owner.memory_skill.calls[-1]["params"]["document_target_collections"] == ["aria_docs_sample_medications"]


def _connection_action_arbitration(
    query: str,
    *,
    kind: str,
    refs: tuple[str, ...],
    actions: tuple[str, ...] = (),
    target_scope_authority: str = "",
) -> AriaTurnArbitration:
    return AriaTurnArbitration(
        plan=AriaTurnPlan(
            intents=("chat",),
            needs_context=True,
            context_directions=("connections",),
            context_requests=tuple(
                ContextRequest(
                    surface_id="connections",
                    mode="action",
                    query=query,
                    budget={"entity_type": "connection", "kind": kind, "ref": ref},
                )
                for ref in refs
            ),
            actions=actions,
            priority=tuple(f"connection|{kind}|{ref}" for ref in refs),
            target_scope_authority=target_scope_authority,
            answer_mode="plan_action",
            contract_mode="action",
            risk="medium",
            needs_confirmation=True,
            confidence=0.98,
        ),
        source="aria_meta_catalog_routing",
    )


def test_aria_turn_seed_full_kind_scope_does_not_bind_priority_refs() -> None:
    arbitration = _connection_action_arbitration(
        "zeige mir den status meiner server",
        kind="ssh",
        refs=("srv-a", "srv-b"),
        actions=("ssh_run_command",),
        target_scope_authority="full_kind",
    )

    draft = AgenticContextRuntimeMixin()._aria_turn_seed_capability_draft(arbitration)

    assert draft is not None
    assert draft.connection_kind == "ssh"
    assert draft.connection_refs == []
    assert "target_scope:multi_target" in draft.notes
    assert "target_scope_authority:full_kind" in draft.notes
    assert "turn_contract_target_refs:full_kind" in draft.notes


def test_aria_turn_seed_semantic_group_scope_binds_refs() -> None:
    arbitration = _connection_action_arbitration(
        "zeige mir den status meiner dev-server",
        kind="ssh",
        refs=("dev-node-01", "dev-node-02"),
        actions=("ssh_run_command",),
        target_scope_authority="semantic_group",
    )

    draft = AgenticContextRuntimeMixin()._aria_turn_seed_capability_draft(arbitration)

    assert draft is not None
    assert draft.connection_refs == ["dev-node-01", "dev-node-02"]
    assert "target_scope_authority:semantic_group" in draft.notes
    assert "turn_contract_target_refs:dev-node-01,dev-node-02" in draft.notes


def test_aria_turn_seed_sftp_read_extracts_file_path_from_live_query() -> None:
    arbitration = _connection_action_arbitration(
        "lies mir die datei /etc/hosts auf dns-node-02",
        kind="sftp",
        refs=("dns-node-02",),
    )

    draft = AgenticContextRuntimeMixin()._aria_turn_seed_capability_draft(arbitration)

    assert draft is not None
    assert draft.capability == "file_read"
    assert draft.connection_kind == "sftp"
    assert draft.explicit_connection_ref == "dns-node-02"
    assert draft.path == "/etc/hosts"
    assert draft.content == ""


def test_aria_turn_seed_blocks_unbound_explicit_identifier_target() -> None:
    runtime = AgenticContextRuntimeMixin()
    runtime.settings = SimpleNamespace(  # type: ignore[attr-defined]
        connections=SimpleNamespace(
            ssh={
                "ops-alert-01": {
                    "host": "192.0.2.160",
                    "title": "NetAlert Monitoring",
                    "aliases": ["monitoring server"],
                    "tags": ["monitoring", "network"],
                }
            }
        )
    )
    arbitration = _connection_action_arbitration(
        "Pruefe den Status von einem ops-unknown-01",
        kind="ssh",
        refs=("ops-alert-01",),
        actions=("connection_action_ssh",),
        target_scope_authority="explicit_refs",
    )

    draft = runtime._aria_turn_seed_capability_draft(arbitration)

    assert draft is not None
    assert draft.capability == "ssh_command"
    assert draft.connection_kind == "ssh"
    assert draft.explicit_connection_ref == ""
    assert draft.requested_connection_ref == "ops-unknown-01"
    assert "explicit_target_authority:blocked_unbound_ref" in draft.notes
    assert "explicit_target_candidate_blocked:ssh/ops-alert-01" in draft.notes


def test_aria_turn_seed_blocks_unbound_target_against_raw_user_prompt() -> None:
    runtime = AgenticContextRuntimeMixin()
    runtime.settings = SimpleNamespace(  # type: ignore[attr-defined]
        connections=SimpleNamespace(
            ssh={
                "ops-alert-01": {
                    "host": "192.0.2.160",
                    "title": "NetAlert Monitoring",
                    "aliases": ["monitoring server"],
                    "tags": ["monitoring", "network"],
                }
            }
        )
    )
    arbitration = _connection_action_arbitration(
        "status check ops-alert-01",
        kind="ssh",
        refs=("ops-alert-01",),
        actions=("connection_action_ssh",),
        target_scope_authority="explicit_refs",
    )

    draft = runtime._aria_turn_seed_capability_draft(
        arbitration,
        user_message="Pruefe den Status von einem ops-unknown-01",
    )

    assert draft is not None
    assert draft.explicit_connection_ref == ""
    assert draft.requested_connection_ref == "ops-unknown-01"
    assert "explicit_target_authority:blocked_unbound_ref" in draft.notes
    assert "explicit_target_candidate_blocked:ssh/ops-alert-01" in draft.notes


def test_aria_turn_seed_keeps_prompt_bound_semantic_explicit_target() -> None:
    runtime = AgenticContextRuntimeMixin()
    runtime.settings = SimpleNamespace(  # type: ignore[attr-defined]
        connections=SimpleNamespace(
            ssh={
                "ops-alert-01": {
                    "host": "192.0.2.160",
                    "title": "NetAlert Monitoring",
                    "aliases": ["monitoring server"],
                    "tags": ["monitoring", "network"],
                }
            }
        )
    )
    arbitration = _connection_action_arbitration(
        "Zeige mir den Status vom monitoring server",
        kind="ssh",
        refs=("ops-alert-01",),
        actions=("connection_action_ssh",),
        target_scope_authority="explicit_refs",
    )

    draft = runtime._aria_turn_seed_capability_draft(arbitration)

    assert draft is not None
    assert draft.explicit_connection_ref == "ops-alert-01"
    assert draft.requested_connection_ref == ""
    assert not any(note.startswith("explicit_target_candidate_blocked:") for note in draft.notes)


def test_web_search_action_contract_normalizes_to_web_context() -> None:
    runtime = AgenticContextRuntimeMixin()
    runtime.web_search_skill = object()
    arbitration = AriaTurnArbitration(
        plan=AriaTurnPlan(
            intents=("chat", "runtime_action"),
            surfaces=("connections",),
            actions=("web_search",),
            needs_context=True,
            context_directions=("connections",),
            context_requests=(
                ContextRequest(
                    surface_id="connections",
                    mode="action",
                    query="was ist der neuste amazon kindle",
                    budget={"entity_type": "connection", "kind": "searxng", "ref": "www-search"},
                ),
            ),
            priority=("connection|searxng|www-search",),
            answer_mode="plan_action",
            contract_mode="action",
            evidence_policy="source_bound",
            risk="low",
            needs_confirmation=False,
            confidence=0.93,
            reason="use configured web search",
        ),
        source="aria_meta_catalog_routing",
    )

    normalized = runtime._normalize_web_search_action_contract(
        arbitration,
        message="was ist der neuste amazon kindle",
        user_id="u1",
        request_id="r1",
    )

    assert normalized is not None
    assert normalized.plan.actions == ()
    assert normalized.plan.surfaces == ("web",)
    assert normalized.plan.context_directions == ("web",)
    assert normalized.plan.context_requests[0].surface_id == "web"
    assert normalized.plan.context_requests[0].budget["web_search_action_normalized"] is True
    assert normalized.plan.contract_mode == "answer"


def test_aria_turn_seed_sftp_list_uses_directory_or_default_path() -> None:
    runtime = AgenticContextRuntimeMixin()

    with_path = runtime._aria_turn_seed_capability_draft(
        _connection_action_arbitration("liste die dateien in /var/log auf dns-node-02", kind="sftp", refs=("dns-node-02",))
    )
    without_path = runtime._aria_turn_seed_capability_draft(
        _connection_action_arbitration("liste die dateien auf dns-node-02", kind="sftp", refs=("dns-node-02",))
    )

    assert with_path is not None
    assert with_path.capability == "file_list"
    assert with_path.path == "/var/log"
    assert without_path is not None
    assert without_path.capability == "file_list"
    assert without_path.path == "."


def test_aria_turn_seed_sftp_read_without_absolute_path_does_not_use_prompt_as_path() -> None:
    arbitration = _connection_action_arbitration(
        "lies mir die hosts datei auf dns-node-02",
        kind="sftp",
        refs=("dns-node-02",),
    )

    draft = AgenticContextRuntimeMixin()._aria_turn_seed_capability_draft(arbitration)

    assert draft is not None
    assert draft.capability == "file_read"
    assert draft.path == "/etc/hosts"


def test_aria_turn_seed_sftp_management_hosts_file_uses_etc_hosts() -> None:
    arbitration = _connection_action_arbitration(
        "hosts datei vom management server bitte",
        kind="sftp",
        refs=("ops-mgmt-01",),
    )

    draft = AgenticContextRuntimeMixin()._aria_turn_seed_capability_draft(arbitration)

    assert draft is not None
    assert draft.capability == "file_read"
    assert draft.connection_kind == "sftp"
    assert draft.explicit_connection_ref == "ops-mgmt-01"
    assert draft.path == "/etc/hosts"


def test_aria_turn_seed_sftp_manual_question_without_file_evidence_does_not_list_root() -> None:
    arbitration = AriaTurnArbitration(
        plan=AriaTurnPlan(
            intents=("chat", "runtime_action"),
            needs_context=True,
            context_directions=("connections",),
            context_requests=(
                ContextRequest(
                    surface_id="connections",
                    mode="action",
                    query="was steht im syncthing manual?",
                    budget={"entity_type": "connection", "kind": "sftp", "ref": "sync-node-01"},
                ),
            ),
            priority=("connection|sftp|sync-node-01",),
            actions=(),
            answer_mode="direct_answer",
            contract_mode="action",
            evidence_policy="source_bound",
            risk="low",
            needs_confirmation=False,
            confidence=0.9,
        ),
        source="aria_meta_catalog_routing",
    )

    draft = AgenticContextRuntimeMixin()._aria_turn_seed_capability_draft(arbitration)

    assert draft is None


def test_aria_turn_seed_recovers_sftp_file_action_when_meta_contract_has_no_actions() -> None:
    arbitration = AriaTurnArbitration(
        plan=AriaTurnPlan(
            intents=("chat",),
            needs_context=True,
            context_directions=("connections",),
            context_requests=(
                ContextRequest(
                    surface_id="connections",
                    mode="action",
                    query="hosts datei vom management server bitte",
                    budget={"entity_type": "connection", "kind": "sftp", "ref": "ops-mgmt-01"},
                ),
            ),
            priority=("connection|sftp|ops-mgmt-01",),
            actions=(),
            answer_mode="direct_answer",
            contract_mode="action",
            evidence_policy="source_bound",
            risk="low",
            needs_confirmation=False,
            confidence=0.88,
        ),
        source="aria_meta_catalog_routing",
    )

    draft = AgenticContextRuntimeMixin()._aria_turn_seed_capability_draft(arbitration)

    assert draft is not None
    assert draft.capability == "file_read"
    assert draft.connection_kind == "sftp"
    assert draft.explicit_connection_ref == "ops-mgmt-01"
    assert draft.path == "/etc/hosts"


def test_aria_turn_seed_ssh_singular_catalog_choice_does_not_expand_to_fleet() -> None:
    arbitration = _connection_action_arbitration(
        "zeige mir den status vom monitoring server",
        kind="ssh",
        refs=("ops-alert-01",),
    )

    draft = AgenticContextRuntimeMixin()._aria_turn_seed_capability_draft(arbitration)

    assert draft is not None
    assert draft.capability == "ssh_command"
    assert draft.connection_kind == "ssh"
    assert draft.explicit_connection_ref == "ops-alert-01"
    assert draft.connection_refs == []
    assert "target_scope:multi_target" not in draft.notes


def test_aria_turn_seed_ssh_fleet_query_keeps_multi_target_scope() -> None:
    arbitration = _connection_action_arbitration(
        "wie geht es meinen servern",
        kind="ssh",
        refs=("ops-alert-01", "dev-node-01", "dns-node-02"),
        target_scope_authority="full_kind",
    )

    draft = AgenticContextRuntimeMixin()._aria_turn_seed_capability_draft(arbitration)

    assert draft is not None
    assert draft.capability == "ssh_command"
    assert draft.connection_kind == "ssh"
    assert draft.explicit_connection_ref == ""
    assert draft.connection_refs == []
    assert "target_scope:multi_target" in draft.notes
    assert "target_scope_authority:full_kind" in draft.notes
    assert "turn_contract_target_refs:full_kind" in draft.notes
