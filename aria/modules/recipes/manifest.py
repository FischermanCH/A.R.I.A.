"""Declarative metadata for recipes and recipe automation."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "recipes",
    "name": "Recipes",
    "status": "domain_namespace_active",
    "lifecycle": "contract_only",
    "risk": "medium_high",
    "description": "Owns recipe UI, stored recipe manifests, recipe runtime contracts, and legacy skill compatibility until narrower modules are proven.",
    "candidate_submodules": [
        "recipes_ui",
        "recipe_store",
        "recipe_runtime",
        "recipe_legacy_skill_compat",
    ],
    "routes_prefixes": [],
    "python": [],
    "templates": [],
    "prompts": [],
    "tests": [
        "tests/test_recipe_*.py",
        "tests/test_recipes_routes.py",
        "tests/test_stored_recipe_manifest_view.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "auth_ui",
        "navigation_shell",
    ],
    "external_boundaries": [
        {
            "id": "kernel.templates",
            "category": "kernel_platform",
            "disposition": "durable",
        },
    ],
    "explicitly_excluded": [
        "recipe_runtime_behavior",
        "stored_recipe_persistence_behavior",
        "legacy_skill_compat_removal",
        "ssh_execution",
        "rss_execution",
        "http_api_execution",
        "messaging_execution",
        "calendar_execution",
        "memory_runtime_access",
        "chat_pipeline_behavior",
    ],
    "acceptance": ".codex/aria_acceptance/modularization-recipes-metadata-slice.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "Existing app wiring remains in aria/main.py.",
        "Recipe Store, Runtime, UI, and Legacy compatibility are assigned to registered narrower modules.",
        "Some templates and form fields still use skill_* for compatibility; do not remove without proof.",
        "The /recipes UI prefix is owned by recipes_ui; /skills and prompts/skills/ belong to recipe_legacy_skill_compat.",
    ],
}
