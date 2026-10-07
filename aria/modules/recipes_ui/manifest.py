"""Declarative metadata for recipe UI surfaces."""

from __future__ import annotations

from typing import Any


MODULE_MANIFEST: dict[str, Any] = {
    "id": "recipes_ui",
    "name": "Recipes UI",
    "status": "import_boundary_active",
    "lifecycle": "bootstrap_static",
    "risk": "medium",
    "parent": "recipes",
    "description": "Owns existing recipe UI templates and visible recipe UI URLs without owning recipe runtime, persistence, learning, promotion, or action execution.",
    "routes": [
        "/recipes",
        "/recipes/start",
        "/recipes/mine",
        "/recipes/system",
        "/recipes/templates",
        "/recipes/save",
        "/recipes/wizard",
        "/recipes/wizard/save",
        "/recipes/import",
        "/recipes/import-sample",
        "/recipes/duplicate",
        "/recipes/delete",
        "/recipes/export/{skill_id}",
    ],
    "routes_prefixes": [
        "/recipes",
    ],
    "templates": [
        "recipes_overview.html",
        "recipes_start.html",
        "recipes_mine.html",
        "recipes_system.html",
        "recipes_wizard.html",
        "_recipes_custom_section.html",
        "_recipes_nav.html",
        "_recipes_page_header.html",
        "_recipes_samples_section.html",
        "_recipes_save_hint.html",
        "_recipes_start_section.html",
        "_recipes_system_section.html",
        "_recipes_toggle_script.html",
    ],
    "python": [
        "aria/modules/recipes_ui/routes.py",
        "aria/modules/recipes_ui/route_support.py",
        "aria/modules/recipes_ui/surface_context.py",
        "aria/modules/recipes_ui/stored_ui.py",
    ],
    "tests": [
        "tests/test_recipes_routes.py",
        "tests/test_module_registry.py",
        "tests/test_module_registry_read_model.py",
    ],
    "depends_on": [
        "auth_ui",
        "config_ui",
        "recipe_runtime",
        "recipe_store",
    ],
    "external_boundaries": [
        {
            "id": "kernel.templates",
            "category": "kernel_platform",
            "disposition": "durable",
        },
    ],
    "explicitly_excluded": [
        "fastapi_route_registration_from_manifest",
        "recipe_runtime_behavior",
        "stored_recipe_persistence_behavior",
        "wizard_save_import_delete_semantics",
        "recipe_execution",
        "ssh_execution",
        "rss_execution",
        "http_api_execution",
        "messaging_execution",
        "calendar_execution",
        "memory_runtime_access",
        "qdrant_or_user_data_access",
        "chat_pipeline_behavior",
        "auth_session_cookie_behavior",
    ],
    "acceptance": ".codex/aria_acceptance/recipes-ui-store-learning-composition-ownership-rail-alpha744.json",
    "build_allowed": False,
    "runtime_access_allowed": False,
    "notes": [
        "This module is narrower than the broad recipes metadata module.",
        "Recipe routes, surface context, UI contracts, and stored Recipe rendering are canonical in aria.modules.recipes_ui.",
        "Historical aria.web Recipe UI paths remain identity-preserving compatibility aliases.",
        "The UI composes recipe_store and recipe_runtime without either implementation owner depending back on recipes_ui.",
        "navigation_shell consumes Recipe presentation contracts; recipes_ui does not depend back on the shell owner.",
    ],
}
