from __future__ import annotations

import asyncio
from dataclasses import fields
from pathlib import Path

from aria.modules.memory.personal import apply_recent_personal_context_feedback
from aria.modules.runtime_execution_registry.contracts import AgenticExecutionHooks


ROOT = Path(__file__).resolve().parents[1]


def _source(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_runtime_execution_contract_and_handlers_do_not_use_legacy_learning() -> None:
    contracts = _source("aria/modules/runtime_execution_registry/contracts.py")
    handler_sources = "\n".join(
        _source(path)
        for path in (
            "aria/modules/capability_runtime/handler.py",
            "aria/modules/rss_runtime/agentic_execution.py",
            "aria/modules/ssh_runtime/agentic_execution.py",
        )
    )

    assert "learning_runtime" not in contracts
    assert "learning_service" not in {item.name for item in fields(AgenticExecutionHooks)}
    assert ".learning_service" not in handler_sources
    assert "record_capability_success" not in handler_sources


def test_stats_and_memory_admin_surfaces_do_not_read_learning_worker() -> None:
    stats_routes = _source("aria/modules/stats_ui/routes.py")
    stats_template = _source("aria/templates/stats.html")
    memory_routes = _source("aria/modules/memory_admin_ui/routes.py")
    memory_template = _source("aria/templates/memories_auto_memory.html")

    assert "get_learning_worker_status" not in stats_routes
    assert "_build_learning_worker_meta" not in stats_routes
    assert "learning_worker" not in stats_template
    assert "load_learning_receipts" not in memory_routes
    assert "learning_receipts" not in memory_routes
    assert "learning_receipts" not in memory_template
    assert "Anwendungsbelege" not in memory_template
    assert "Application receipts" not in memory_template


def test_personal_feedback_builder_has_no_receipt_dependency_and_links_nothing() -> None:
    personal_source = _source("aria/modules/memory/personal.py")

    class Memory:
        def __init__(self) -> None:
            self.updates: list[object] = []

        async def list_personal_claims(self, **_kwargs: object) -> list[dict[str, object]]:
            return [
                {
                    "id": "point-1",
                    "collection": "aria_preferences_neo",
                    "claim_id": "claim-1",
                    "claim_last_used_at": "2099-01-01T00:00:00+00:00",
                    "claim_last_used_request_id": "request-1",
                }
            ]

        async def update_memory_point_payload(self, *args: object) -> bool:
            self.updates.append(args)
            return True

    memory = Memory()
    result = asyncio.run(
        apply_recent_personal_context_feedback(
            memory,
            user_id="neo",
            sentiment="positive",
            target_request_id="request-1",
        )
    )

    assert "learning_runtime" not in personal_source
    assert "load_learning_receipts" not in personal_source
    assert result == {"linked_claim_ids": [], "request_id": "request-1"}
    assert memory.updates == []


def test_startup_keeps_non_learning_memory_maintenance_and_memories_route() -> None:
    main_source = _source("aria/main.py")
    memory_routes = _source("aria/modules/memory_admin_ui/routes.py")

    assert "apply_learning_retention_global" not in main_source
    assert "Startup learning retention" not in main_source
    assert "rebuild_document_meta_catalogs_for_known_users" in main_source
    assert "cleanup_empty_collections_global" in main_source
    assert "@app.get('/memories'" in memory_routes or '@app.get("/memories"' in memory_routes
    assert "reset-learning-suggestions" in memory_routes


def test_retained_consumers_drop_learning_runtime_manifest_edges() -> None:
    for path in (
        "aria/modules/runtime_execution_registry/manifest.py",
        "aria/modules/capability_runtime/manifest.py",
        "aria/modules/stats_ui/manifest.py",
        "aria/modules/memory_admin_ui/manifest.py",
    ):
        assert '"learning_runtime"' not in _source(path), path

    assert not (ROOT / "aria/modules/learning_runtime").exists()
    assert "class MemorySkill" in _source("aria/modules/memory_learning_bridge/skill.py")
