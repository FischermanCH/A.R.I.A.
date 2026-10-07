from __future__ import annotations

from pathlib import Path

from aria.modules.authority_chain_audit.audit import ALLOWED_AUTHORITY_EFFECTS
from aria.modules.authority_chain_audit.audit import AUTHORITY_CHAIN_BOUNDARIES
from aria.modules.authority_chain_audit.audit import RETIRED_CONTEXT_QUERY_SOURCE_MARKERS
from aria.modules.authority_chain_audit.audit import RETIRED_LEGACY_MODULES
from aria.modules.authority_chain_audit.audit import RETIRED_PRODUCTIVE_MARKERS
from aria.modules.authority_chain_audit.audit import RETIRED_SEMANTIC_SOURCE_MARKERS
from aria.modules.authority_chain_audit.audit import authority_chain_boundary_map
from aria.modules.authority_chain_audit.audit import red_authority_boundaries

ROOT = Path(__file__).resolve().parents[1]


def test_authority_manifest_contains_only_current_boundaries() -> None:
    assert set(authority_chain_boundary_map()) == {
        "connection_target_selection",
        "memory_retrieval_failure",
    }
    assert red_authority_boundaries() == ()
    for boundary in AUTHORITY_CHAIN_BOUNDARIES:
        assert boundary.effect in ALLOWED_AUTHORITY_EFFECTS
        assert boundary.manifest_class == "clean"


def test_authority_manifest_source_markers_exist() -> None:
    sources = {
        "routing_admin.resolve_connection_routing_chain": ROOT
        / "aria/modules/connection_routing/admin.py",
        "pipeline.Pipeline": ROOT / "aria/modules/pipeline_orchestrator/pipeline.py",
        "memory_learning_bridge.skill.MemorySkill": ROOT
        / "aria/modules/memory_learning_bridge/skill.py",
    }
    for boundary in AUTHORITY_CHAIN_BOUNDARIES:
        source_paths = sources[boundary.component]
        if not isinstance(source_paths, tuple):
            source_paths = (source_paths,)
        assert any(boundary.source_marker in path.read_text(encoding="utf-8") for path in source_paths)


def test_retired_legacy_modules_stay_deleted() -> None:
    for relative_path in RETIRED_LEGACY_MODULES:
        assert not (ROOT / relative_path).exists()


def test_retired_productive_semantic_markers_stay_removed() -> None:
    for relative_path, marker in RETIRED_PRODUCTIVE_MARKERS:
        assert marker not in (ROOT / relative_path).read_text(encoding="utf-8")


def test_retired_context_and_query_overrides_stay_removed() -> None:
    for relative_path, marker in RETIRED_CONTEXT_QUERY_SOURCE_MARKERS:
        assert marker not in (ROOT / relative_path).read_text(encoding="utf-8")


def test_connection_routing_has_no_free_text_terminal_winner() -> None:
    source = (ROOT / "aria/modules/connection_routing/admin.py").read_text(encoding="utf-8")
    body = source.split("async def resolve_connection_routing_chain", 1)[1]
    assert "_deterministic_connection_match" not in body
    assert "Qdrant routing candidate selected" not in body
    assert "default_single_profile" not in body
    assert 'source="router_llm"' in body
