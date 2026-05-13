from __future__ import annotations

from typing import Any, Callable

Translate = Callable[[str, str, str], str]


def build_recipes_overview_checks(
    *,
    lang: str,
    core_recipe_rows: list[dict[str, Any]],
    learned_rows: list[dict[str, Any]],
    custom_rows: list[dict[str, Any]],
    sample_recipe_rows: list[dict[str, str]],
    advanced_mode: bool,
    translate: Translate,
) -> list[dict[str, str]]:
    active_custom_count = sum(1 for row in custom_rows if bool(row.get("enabled")))
    active_core_count = sum(1 for row in core_recipe_rows if bool(row.get("enabled")))
    learned_reviewable_count = sum(1 for row in learned_rows if str(row.get("promotion_state", "")).strip())

    return [
        {
            "title": translate(lang, "recipes.overview_custom_title", "Eigene"),
            "status": "ok" if custom_rows else "warn",
            "summary": str(len(custom_rows)),
            "meta": translate(lang, "recipes.overview_custom_meta", "{count} active").replace(
                "{count}", str(active_custom_count)
            ),
            "href": "/recipes/mine",
        },
        {
            "title": translate(lang, "recipes.overview_learned_title", "Gelernt"),
            "status": "ok" if learned_rows else "warn",
            "summary": str(len(learned_rows)),
            "meta": translate(lang, "recipes.overview_learned_meta", "{count} reviewable / promoted").replace(
                "{count}", str(learned_reviewable_count)
            ),
            "href": "/recipes/learned",
        },
        {
            "title": translate(lang, "recipes.overview_core_title", "Core"),
            "status": "ok" if core_recipe_rows else "warn",
            "summary": str(len(core_recipe_rows)),
            "meta": translate(lang, "recipes.overview_core_meta", "{count} active").replace(
                "{count}", str(active_core_count)
            ),
            "href": "/recipes/system",
        },
        {
            "title": translate(lang, "recipes.overview_templates_title", "Importierbar"),
            "status": "ok" if sample_recipe_rows else "warn",
            "summary": str(len(sample_recipe_rows)),
            "meta": translate(lang, "recipes.overview_templates_meta", "importable samples"),
            "href": "/recipes/templates",
        },
        {
            "title": translate(lang, "recipes.overview_mode_title", "Mode"),
            "status": "ok" if advanced_mode else "warn",
            "summary": (
                translate(lang, "recipes.overview_mode_edit", "Editing")
                if advanced_mode
                else translate(lang, "recipes.overview_mode_readonly", "Read only")
            ),
            "meta": (
                translate(lang, "recipes.overview_mode_meta_admin", "Admin mode enabled")
                if advanced_mode
                else translate(lang, "recipes.overview_mode_meta_readonly", "Changes are currently locked")
            ),
        },
    ]


def build_recipes_next_steps(
    *,
    lang: str,
    has_custom_recipes: bool,
    custom_count: int,
    core_recipe_count: int,
    sample_recipe_count: int,
    translate: Translate,
) -> list[dict[str, str]]:
    return [
        {
            "icon": "plus",
            "title": translate(
                lang,
                "recipes.next_step_create_title_empty" if not has_custom_recipes else "recipes.next_step_create_title_more",
                "Create first recipe" if not has_custom_recipes else "Create new recipe",
            ),
            "desc": translate(
                lang,
                "recipes.next_step_create_desc_empty" if not has_custom_recipes else "recipes.next_step_create_desc_more",
                (
                    "The wizard remains the fastest entry point for a first guided recipe."
                    if not has_custom_recipes
                    else "Use the wizard for another guided recipe without editing JSON by hand first."
                ),
            ),
            "href": "/recipes/start",
            "badge": translate(lang, "recipes.next_step_badge_wizard", "Wizard"),
        },
        {
            "icon": "upload",
            "title": translate(
                lang,
                "recipes.next_step_template_title",
                "Use template" if not has_custom_recipes else "Review another template",
            ),
            "desc": translate(
                lang,
                "recipes.next_step_template_desc",
                "Sample recipes give you a quick starting point when you do not want to build the flow from scratch.",
            ),
            "href": "/recipes/templates",
            "badge": str(sample_recipe_count),
        },
        {
            "icon": "skills",
            "title": translate(
                lang,
                "recipes.next_step_manage_title_mine" if has_custom_recipes else "recipes.next_step_manage_title_system",
                "Review my recipes" if has_custom_recipes else "Explore core / system",
            ),
            "desc": translate(
                lang,
                "recipes.next_step_manage_desc_mine" if has_custom_recipes else "recipes.next_step_manage_desc_system",
                (
                    "Here you only see your own recipes and can refine or clean them up."
                    if has_custom_recipes
                    else "Review the built-in core flows before adding your own recipes next to them."
                ),
            ),
            "href": "/recipes/mine" if has_custom_recipes else "/recipes/system",
            "badge": str(custom_count) if has_custom_recipes else str(core_recipe_count),
        },
    ]
