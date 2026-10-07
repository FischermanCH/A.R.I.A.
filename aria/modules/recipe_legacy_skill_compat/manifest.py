"""Declarative metadata for legacy Recipe skill compatibility."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "recipe_legacy_skill_compat",
    "name": "Recipe Legacy Skill Compatibility",
    "parent": "recipes",
    "status": "compatibility_contract_active",
    "lifecycle": "contract_only",
    "risk": "medium_high",
    "description": "Owns legacy skill runtime, route alias, custom-skill adapter, and prompt-root metadata without removing compatibility or executing skills.",
    "routes_prefixes": [
        "/skills",
    ],
    "prompts": [
        "prompts/skills/",
    ],
    "python": [
    ],
    "tests": [
        "tests/test_recipe_manifests.py",
        "tests/test_recipe_runtime.py",
        "tests/test_recipes_routes.py",
        "tests/test_module_registry.py",
        "tests/test_recipe_compatibility_kernel_ownership_import_boundary.py",
    ],
    "depends_on": [
        "recipe_runtime",
        "recipe_store",
        "recipes_ui",
    ],
    "external_boundaries": [],
    "explicitly_excluded": [
        "legacy_route_removal",
        "legacy_prompt_migration_or_delete",
        "skill_or_recipe_execution",
        "stored_recipe_mutation",
        "runtime_reload",
    ],
    "acceptance": ".codex/aria_acceptance/recipe-compatibility-ownership-rail-alpha743.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "The /skills route prefix and prompts/skills/ root move here from the broad recipes umbrella.",
        "Compatibility behavior and visible redirects remain unchanged.",
        "The three historical core names are identity aliases to canonical recipe store/runtime modules.",
    ],
}
