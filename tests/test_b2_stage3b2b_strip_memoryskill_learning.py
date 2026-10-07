from __future__ import annotations

import inspect
from pathlib import Path
from types import SimpleNamespace

from aria.modules import MODULE_MANIFESTS
from aria.modules.native_agent.tool_registry import assemble_native_tools


ROOT = Path(__file__).resolve().parents[1]


def test_memoryskill_has_only_retained_core_memory_surface() -> None:
    from aria.modules.memory_learning_bridge.skill import MemorySkill

    source = inspect.getsource(MemorySkill)
    for forbidden in (
        "recall_learning_active_hints",
        "apply_learning_retention_global",
        "_apply_learning_retention",
        "_delete_learning_retention_points",
        "_learning_retention_rows",
        "_automatic_learning_retention_enabled",
        "_learning_collection_memory_type",
        "_is_raw_learning_collection",
        "list_learning_points_global",
        "learning_governor",
    ):
        assert forbidden not in source
    for retained in (
        "list_personal_claims",
        "personal_claim_semantic_match",
        "store_document",
        "list_memories",
        "list_memories_global",
        "get_user_collection_stats",
        "rebuild_document_meta_catalogs_for_known_users",
        "cleanup_empty_collections_global",
        "_candidate_collections",
    ):
        assert hasattr(MemorySkill, retained)
    from aria.modules.memory.personal import store_personal_claim

    assert callable(store_personal_claim)


def test_learning_helpers_are_removed_and_admin_query_is_relocated() -> None:
    bridge = ROOT / "aria/modules/memory_learning_bridge"
    assert not (bridge / "procedure_guidance.py").exists()
    assert not (bridge / "admin_query.py").exists()
    assert (ROOT / "aria/modules/memory/admin_query.py").is_file()

    skill_source = (bridge / "skill.py").read_text(encoding="utf-8")
    assert "aria.modules.memory.admin_query" in skill_source
    assert "aria.modules.learning_" not in skill_source
    assert not (ROOT / "aria/modules/learning_feedback").exists()


def test_native_registry_removes_only_learning_context_read() -> None:
    owner = SimpleNamespace(settings=SimpleNamespace(), memory_skill=object())
    flags = {
        "native_agent_memory_enabled",
        "native_agent_connections_enabled",
        "native_agent_admin_enabled",
        "native_agent_write_notes_enabled",
        "native_agent_write_memory_enabled",
        "native_agent_ssh_enabled",
        "native_agent_messaging_enabled",
        "native_agent_infra_write_enabled",
        "native_agent_recipe_execute_enabled",
        "native_agent_recipe_learn_enabled",
        "native_agent_memory_learn_enabled",
        "native_agent_admin_write_enabled",
    }
    tools = assemble_native_tools(MODULE_MANIFESTS, runtime_owner=owner, enabled_rollout_flags=flags)
    contracts = {item.contract.name: item.contract for item in tools}
    assert len(tools) == 37
    assert sum(item.effect == "read_only" for item in contracts.values()) == 24
    assert sum(item.effect == "mutating" for item in contracts.values()) == 13
    assert sum(item.confirmation_required for item in contracts.values()) == 13
    assert "learning_context_read" not in contracts
    assert {"recall_personal_memory", "memory_context_read", "memory_capture"} <= contracts.keys()


def test_manifests_drop_deleted_files_and_legacy_learning_modules() -> None:
    bridge = MODULE_MANIFESTS["memory_learning_bridge"]
    memory = MODULE_MANIFESTS["memory"]
    assert bridge["python"] == ["aria/modules/memory_learning_bridge/skill.py"]
    assert not ({"learning", "learning_candidates", "learning_governance"} & set(bridge["depends_on"]))
    assert "aria/modules/memory/admin_query.py" in memory["python"]
    assert not {"learning", "learning_candidates", "learning_governance", "learning_runtime"} & set(MODULE_MANIFESTS)
