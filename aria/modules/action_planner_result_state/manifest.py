"""Declarative metadata for action planner result-state boundaries."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "action_planner_result_state",
    "name": "Action Planner Result State",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "medium",
    "parent": "actions",
    "description": "Owns planner execution-state, source, confidence, target-context, sorting, and result-payload label helpers without changing candidate selection.",
    "python": [
        "aria/modules/action_planner_result_state/result_state.py",
    ],
    "tests": [
        "tests/test_execution_dry_run.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "platform_primitives",
    ],
    "external_boundaries": [],
    "explicitly_excluded": [
        "planner_candidate_selection_behavior",
        "llm_dry_run_behavior",
        "candidate_payload_shape_changes",
        "recipe_candidate_behavior",
        "routing_admin_behavior",
        "pipeline_orchestration_behavior",
        "action_execution_behavior",
    ],
    "acceptance": ".codex/aria_acceptance/action-planning-connection-status-import-rail-alpha729.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "This submodule is smaller and cleaner than action_planner_candidate_details.",
        "Product code imports canonical result-state helpers; the aria.core path is an identity-preserving compatibility alias.",
        "No scoring, candidate selection, LLM, recipe, or pipeline behavior is changed.",
    ],
}
