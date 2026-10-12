"""Declarative activity-journal module boundary."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "activity_journal",
    "name": "Activity Journal",
    "parent": "memory",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "medium_high",
    "description": "Owns the compact user-scoped activity journal, its on-demand read tool, UI and explicit legacy-rollup projection.",
    "routes_prefixes": ["/memories/activity-journal"],
    "routes": [
        "/memories/activity-journal", "/memories/activity-journal/settings",
        "/memories/activity-journal/export", "/memories/activity-journal/entry/delete",
        "/memories/activity-journal/entry/keep", "/memories/activity-journal/delete-range",
        "/memories/activity-journal/legacy/migrate", "/memories/activity-journal/legacy/delete",
    ],
    "templates": ["activity_journal.html"],
    "python": [
        "aria/modules/activity_journal/store.py", "aria/modules/activity_journal/service.py",
        "aria/modules/activity_journal/native_tools.py", "aria/modules/activity_journal/runtime.py",
        "aria/modules/activity_journal/routes.py",
    ],
    "tests": ["tests/test_alpha996_activity_journal.py", "tests/e2e/scenarios.py"],
    "depends_on": [
        "auth_ui", "configuration_foundations", "memory_learning_bridge", "navigation_shell",
        "pipeline_orchestrator", "platform_primitives",
    ],
    "external_boundaries": [
        {"id": "sqlite3", "category": "data_boundary", "disposition": "durable"},
    ],
    "integration_points": ["aria/modules/activity_journal/native_tools.py::native_tool_contributions"],
    "explicitly_excluded": [
        "prompt_injection", "raw_tool_output_storage", "document_or_image_storage",
        "semantic_search", "lesson_proposals", "automatic_rollup_deletion",
    ],
    "acceptance": ".codex/aria_acceptance/activity-journal-alpha996-review-build.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
}
