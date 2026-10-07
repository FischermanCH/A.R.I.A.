"""Declarative metadata for stored Recipe boundaries."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "recipe_store",
    "name": "Recipe Store",
    "parent": "recipes",
    "status": "implementation_owner_active",
    "lifecycle": "bootstrap_static",
    "risk": "medium_high",
    "description": "Owns stored Recipe manifest parsing and persistence, validation, Wizard persistence-adapter, and import/export data operations.",
    "python": [
        "aria/modules/recipe_store/manifests.py",
        "aria/modules/recipe_store/manifest_actions.py",
        "aria/modules/recipe_store/template_import.py",
        "aria/modules/recipe_store/wizard_catalog.py",
        "aria/modules/recipe_store/wizard_save.py",
        "aria/modules/recipe_store/native_tools.py",
    ],
    "integration_points": ["aria/modules/recipe_store/native_tools.py::native_tool_contributions"],
    "prompts": [
        "prompts/recipes/",
    ],
    "tests": [
        "tests/test_recipe_manifests.py",
        "tests/test_recipe_samples.py",
        "tests/test_stored_recipe_manifest_view.py",
        "tests/test_recipe_compatibility_kernel_ownership_import_boundary.py",
        "tests/test_recipes_routes.py",
        "tests/test_module_registry.py",
    ],
    "depends_on": [
        "actions",
        "configuration_foundations",
        "platform_primitives",
    ],
    "external_boundaries": [],
    "explicitly_excluded": [
        "stored_recipe_file_mutation",
        "wizard_save_import_delete_execution",
        "runtime_reload",
        "learned_recipe_promotion",
        "recipe_execution",
        "user_data_access",
    ],
    "acceptance": ".codex/aria_acceptance/recipes-ui-store-learning-composition-ownership-rail-alpha744.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "The canonical prompts/recipes/ ownership moves here from the broad recipes umbrella.",
        "Stored Recipe manifest parsing and persistence are canonical in aria.modules.recipe_store.manifests.",
        "Stored Recipe candidate-view helpers and their tests use the canonical recipe_runtime owner; the former internal manifest_view paths are retired.",
        "Manifest actions, template import, Wizard catalog, and Wizard save are canonical in aria.modules.recipe_store.",
        "Historical aria.web Recipe Store paths remain identity-preserving compatibility aliases.",
        "Existing handlers and helpers continue to import recipe store product modules directly.",
        "The alpha738 ownership rail exercises Recipe persistence only with pytest tmp_path and monkeypatched roots.",
    ],
}
