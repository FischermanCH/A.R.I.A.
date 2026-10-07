"""Declarative metadata for shared platform primitives."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "platform_primitives",
    "name": "Platform Primitives",
    "parent": "ui_admin",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "medium",
    "description": "Owns shared language, text/JSON, bounded-decision, prompt-loading, and stage-timing primitives without registering runtime behavior.",
    "python": [
        "aria/modules/platform_primitives/i18n.py",
        "aria/modules/platform_primitives/text_utils.py",
        "aria/modules/platform_primitives/bounded_decision.py",
        "aria/modules/platform_primitives/prompt_loader.py",
        "aria/modules/platform_primitives/stage_timing.py",
        "aria/modules/platform_primitives/recipe_progress.py",
        "aria/modules/platform_primitives/actionable_sequence.py",
        "aria/modules/platform_primitives/observed_claims.py",
    ],
    "tests": [
        "tests/test_i18n.py",
        "tests/test_i18n_core_surfaces.py",
        "tests/test_i18n_language_switch.py",
        "tests/test_i18n_code_literal_audit.py",
        "tests/test_bounded_decision.py",
        "tests/test_prompt_loader.py",
        "tests/test_stage_timing.py",
        "tests/test_recipe_progress.py",
        "tests/test_native_agent_recipe_remember.py",
        "tests/test_native_agent_memory_learning.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [],
    "external_boundaries": [
        {
            "id": "filesystem.prompt_files",
            "category": "data_boundary",
            "disposition": "durable",
        },
        {
            "id": "kernel.injected_llm_client",
            "category": "kernel_platform",
            "disposition": "durable",
        },
    ],
    "explicitly_excluded": [
        "prompt_content_or_path_changes",
        "llm_client_creation_or_real_llm_calls",
        "routing_source_action_or_confirmation_authority",
        "runtime_dispatch_or_execution",
        "productive_prompt_or_user_data_reads",
        "qdrant_connections_or_web_search",
    ],
    "acceptance": ".codex/aria_acceptance/platform-primitives-import-rail-alpha732.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "Implementations are canonical in this module; aria.core paths are identity-preserving aliases.",
        "The manifest is descriptive and creates no loader, LLM client, timer, or filesystem access.",
    ],
}
