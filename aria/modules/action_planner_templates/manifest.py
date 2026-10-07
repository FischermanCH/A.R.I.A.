"""Declarative metadata for action planner template boundaries."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "action_planner_templates",
    "name": "Action Planner Templates",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "medium_high",
    "parent": "actions",
    "description": "Owns built-in action template definitions, behavior profiles, plan classes, required inputs, and base previews without changing planner selection behavior.",
    "python": [
        "aria/modules/action_planner_templates/templates.py",
        "aria/modules/action_planner_templates/taxonomy.py",
        "aria/modules/action_planner_templates/candidate_details.py",
        "aria/modules/action_planner_templates/recipe_candidates.py",
        "aria/modules/action_planner_templates/behavior_family_file_operation.py",
        "aria/modules/action_planner_templates/behavior_families.py",
        "aria/modules/action_planner_templates/planner_candidates.py",
        "aria/modules/action_planner_templates/bounded_planner.py",
        "aria/modules/action_planner_templates/planner.py",
    ],
    "tests": [
        "tests/test_execution_dry_run.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "action_contracts",
        "connections_catalog",
        "platform_primitives",
        "action_planner_result_state",
        "recipe_runtime",
        "recipe_store",
    ],
    "external_boundaries": [],
    "explicitly_excluded": [
        "planner_candidate_selection_behavior",
        "llm_dry_run_behavior",
        "recipe_candidate_behavior",
        "routing_admin_behavior",
        "pipeline_orchestration_behavior",
        "action_execution_behavior",
    ],
    "acceptance": ".codex/aria_acceptance/action-planning-connection-status-import-rail-alpha729.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "This submodule is smaller than action_planner as a whole and is the next safe metadata-only boundary.",
        "Product code imports canonical templates; the aria.core path is an identity-preserving compatibility alias.",
        "B2 Stage 3a-2 removed the dead learned Recipe candidate path while retaining stored Recipe candidates.",
    ],
}
