from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Awaitable, Callable
from urllib.parse import quote_plus

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from aria.core.learned_recipe_store import load_learned_recipe_store_entries
from aria.core.stored_recipe_manifest_view import stored_recipe_candidate_metadata
from aria.web.recipes_route_support import canonical_recipe_surface_return_to as _canonical_recipe_surface_return_to
from aria.web.recipes_route_support import canonical_recipe_surface_path as _canonical_recipe_surface_path
from aria.web.recipes_route_support import is_admin_mode_request as _is_admin_mode_request
from aria.web.recipes_route_support import is_valid_csrf_submission as _is_valid_csrf_submission
from aria.web.recipes_route_support import recipe_surface_path as _recipe_surface_path
from aria.web.recipes_route_support import recipe_surface_return_to as _recipe_surface_return_to
from aria.web.recipes_route_support import redirect_with_return_to as _redirect_with_return_to
from aria.web.recipes_route_support import sanitize_return_to as _sanitize_return_to
from aria.web.recipes_route_support import set_logical_back_url as _set_logical_back_url
from aria.web.recipes_learned_actions import learned_recipe_admin_success_url
from aria.web.recipes_surface_context import build_recipes_next_steps, build_recipes_overview_checks
from aria.web.recipes_template_import import build_sample_recipe_rows, import_sample_recipe_success_url
from aria.web.recipes_manifest_actions import delete_stored_recipe_and_config
from aria.web.recipes_manifest_actions import stored_recipe_export_response
from aria.web.recipes_wizard_save import (
    WizardSaveInput,
    migrate_custom_recipe_config,
    remove_custom_recipe_config,
    save_recipe_from_wizard_form,
)
from aria.web.recipes_wizard_catalog import (
    _RECIPE_TYPE_PRESETS,
    _recipes_routes_text,
    _sanitize_recipe_type,
    _recipe_type_allowed_steps,
    _recipe_type_connection_choices,
    _recipe_type_followup_steps,
    _recipe_type_options,
)
from aria.web.learned_recipe_ui import (
    LEARNED_RECIPE_FILTER_ALL,
    LEARNED_RECIPE_KIND_FILTER_ALL,
    LEARNED_RECIPE_SORT_EXPERIENCE,
    LEARNED_RECIPE_SORT_LAST_SUCCESS,
    LEARNED_RECIPE_SORT_TITLE,
    build_learned_recipe_rows,
    filter_learned_recipe_rows,
    filter_learned_recipe_rows_by_kind,
    learned_recipe_kind_counts,
    learned_recipe_kind_values,
    learned_recipe_filter_counts,
    normalize_learned_recipe_sort,
    normalize_learned_recipe_kind_filter,
    normalize_learned_recipe_filter,
    sort_learned_recipe_rows,
)

from aria.core.recipe_manifests import (
    _collect_recipe_categories,
    _load_stored_recipe_manifests,
    _normalize_recipe_schedule_manifest,
    _normalize_recipe_steps_manifest,
    _recipe_manifest_file,
    _sanitize_recipe_id,
    _save_stored_recipe_manifest,
    _validate_stored_recipe_manifest,
)


SettingsGetter = Callable[[], Any]
UsernameResolver = Callable[[Request], str]
AuthSessionResolver = Callable[[Request], dict[str, Any] | None]
RoleSanitizer = Callable[[str | None], str]
RawConfigReader = Callable[[], dict[str, Any]]
RawConfigWriter = Callable[[dict[str, Any]], None]
RuntimeReloader = Callable[[], None]
Translate = Callable[[str, str, str], str]
LocalizeRecipeDescription = Callable[[dict[str, Any], str], str]
FormatInfoMessage = Callable[[str, str], str]
SuggestKeywords = Callable[..., Awaitable[list[str]]]
DailyTimeToCron = Callable[[str], str]
DailyTimeFromCron = Callable[[str], str]

BASE_DIR = Path(__file__).resolve().parents[2]

# UI-Migrationshinweis:
# Die internen Parameter heissen teilweise noch skill_*, damit alte Forms und
# Config-Backcompat stabil bleiben. Sichtbar nach aussen ist dieser Bereich
# aber recipe-first.


def _build_connection_options(rows: dict[str, Any]) -> list[dict[str, str]]:
    options: list[dict[str, str]] = []
    for ref in sorted(rows.keys()):
        row = rows.get(ref)
        title = str(getattr(row, "title", "") or "").strip()
        label = f"{title} · {ref}" if title and title != ref else ref
        options.append({"ref": ref, "label": label})
    return options


def _build_core_recipe_rows(lang: str, settings: Any, translate: Translate) -> list[dict[str, Any]]:
    return [
        {
            "key": "memory",
            "title": "Memory",
            "desc": translate(lang, "recipes.core_memory_desc", "Speichern und Abrufen von Wissen via Qdrant."),
            "enabled": bool(settings.memory.enabled),
            "implemented": True,
        },
        {
            "key": "auto_memory",
            "title": "Auto-Memory",
            "desc": translate(lang, "recipes.core_auto_memory_desc", "Automatic fact extraction without code words."),
            "enabled": bool(settings.auto_memory.enabled),
            "implemented": True,
        },
    ]


def _build_custom_rows(
    custom_manifests: list[dict[str, Any]],
    custom_cfg: dict[str, Any],
    lang: str,
    localize_stored_recipe_description: LocalizeRecipeDescription,
    daily_time_from_cron: DailyTimeFromCron,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for manifest in custom_manifests:
        custom_section = custom_cfg.get(manifest["id"], {})
        if not isinstance(custom_section, dict):
            custom_section = {}
        rows.append(
            {
                "key": manifest["id"],
                "title": manifest["name"],
                "desc": localize_stored_recipe_description(manifest, lang),
                "enabled": bool(custom_section.get("enabled", manifest.get("enabled_default", True))),
                "implemented": True,
                "category": manifest.get("category", "custom"),
                "prompt_file": str(manifest.get("prompt_file", "") or "").replace("prompts/skills/", "prompts/recipes/"),
                "router_keywords": manifest.get("router_keywords", []),
                "connections": manifest.get("connections", []),
                "steps": manifest.get("steps", []),
                "schedule": manifest.get("schedule", {}),
                "schedule_time_24h": daily_time_from_cron(str((manifest.get("schedule", {}) or {}).get("cron", ""))),
                "config_path": str((manifest.get("ui", {}) or {}).get("config_path", "")).strip(),
                "hint": str((manifest.get("ui", {}) or {}).get("hint", "")).strip(),
                **stored_recipe_candidate_metadata(manifest),
            }
        )
    return rows


def _connection_options_by_kind(settings: Any) -> dict[str, list[dict[str, str]]]:
    connections = getattr(settings, "connections", None)
    return {
        "ssh": _build_connection_options(getattr(connections, "ssh", {}) or {}),
        "sftp": _build_connection_options(getattr(connections, "sftp", {}) or {}),
        "smb": _build_connection_options(getattr(connections, "smb", {}) or {}),
        "rss": _build_connection_options(getattr(connections, "rss", {}) or {}),
        "discord": _build_connection_options(getattr(connections, "discord", {}) or {}),
    }


def _infer_recipe_type(loaded: dict[str, Any] | None) -> str:
    if not isinstance(loaded, dict) or not loaded:
        return "health_check"
    steps = _normalize_recipe_steps_manifest((loaded or {}).get("steps", []))
    if len(steps) != 1:
        return "custom"
    step = steps[0] if isinstance(steps[0], dict) else {}
    step_type = str(step.get("type", "")).strip().lower()
    if step_type == "ssh_run":
        return "health_check"
    if step_type == "rss_read":
        return "monitor"
    if step_type in {"discord_send", "chat_send"}:
        return "notify"
    if step_type in {"sftp_read", "smb_read"}:
        return "fetch"
    if step_type in {"sftp_write", "smb_write"}:
        return "sync"
    return "custom"


def _normalize_custom_cfg(raw: dict[str, Any]) -> dict[str, Any]:
    skills_cfg = raw.get("skills", {})
    if not isinstance(skills_cfg, dict):
        skills_cfg = {}
    custom_cfg = skills_cfg.get("custom", {})
    if not isinstance(custom_cfg, dict):
        custom_cfg = {}
    return custom_cfg


def _build_step_forms(loaded: dict[str, Any] | None) -> list[dict[str, Any]]:
    loaded_steps = _normalize_recipe_steps_manifest((loaded or {}).get("steps", []))
    if not loaded_steps:
        loaded_steps = [{"id": "s1", "name": "", "type": "ssh_run", "params": {}, "on_error": "stop"}]
    step_forms: list[dict[str, Any]] = []
    for index, step in enumerate(loaded_steps, start=1):
        params = step.get("params", {}) if isinstance(step, dict) else {}
        if not isinstance(params, dict):
            params = {}
        step_forms.append(
            {
                "idx": index,
                "enabled": bool(step),
                "id": str(step.get("id", "") if isinstance(step, dict) else "").strip() or f"s{index}",
                "name": str(step.get("name", "") if isinstance(step, dict) else "").strip(),
                "type": str(step.get("type", "") if isinstance(step, dict) else "").strip() or "ssh_run",
                "on_error": str(step.get("on_error", "stop") if isinstance(step, dict) else "stop").strip().lower()
                or "stop",
                "connection_ref": str(params.get("connection_ref", "")).strip(),
                "command": str(params.get("command", "")).strip(),
                "sftp_connection_ref": str(params.get("connection_ref", "")).strip()
                if str(step.get("type", "") if isinstance(step, dict) else "").strip() in {"sftp_read", "sftp_write"}
                else "",
                "sftp_remote_path": str(params.get("remote_path", "")).strip(),
                "sftp_content": str(params.get("content", "")).strip(),
                "smb_connection_ref": str(params.get("connection_ref", "")).strip()
                if str(step.get("type", "") if isinstance(step, dict) else "").strip() in {"smb_read", "smb_write"}
                else "",
                "smb_remote_path": str(params.get("remote_path", "")).strip(),
                "smb_content": str(params.get("content", "")).strip(),
                "rss_connection_ref": str(params.get("connection_ref", "")).strip()
                if str(step.get("type", "") if isinstance(step, dict) else "").strip() == "rss_read"
                else "",
                "prompt": str(params.get("prompt", "")).strip(),
                "discord_connection_ref": str(params.get("connection_ref", "")).strip()
                if str(step.get("type", "") if isinstance(step, dict) else "").strip() == "discord_send"
                else "",
                "webhook_url": str(params.get("webhook_url", "")).strip(),
                "message": str(params.get("message", "")).strip(),
                "chat_message": str(params.get("chat_message", "")).strip(),
            }
        )
    return step_forms


def _sanitize_wizard_mode(value: str | None) -> str:
    mode = str(value or "").strip().lower()
    return "advanced" if mode == "advanced" else "simple"


def _default_wizard_mode(loaded: dict[str, Any] | None) -> str:
    if not isinstance(loaded, dict) or not loaded:
        return "simple"
    steps = loaded.get("steps", [])
    if not isinstance(steps, list):
        steps = []
    if len(steps) > 1:
        return "advanced"
    for step in steps:
        if not isinstance(step, dict):
            continue
        if str(step.get("on_error", "stop")).strip().lower() == "continue":
            return "advanced"
        if isinstance(step.get("condition"), dict) and step.get("condition"):
            return "advanced"
    if str((loaded.get("ui", {}) or {}).get("config_path", "")).strip():
        return "advanced"
    return "simple"


def register_recipe_routes(
    app: FastAPI,
    *,
    templates: Jinja2Templates,
    get_settings: SettingsGetter,
    get_username_from_request: UsernameResolver,
    get_auth_session_from_request: AuthSessionResolver,
    sanitize_role: RoleSanitizer,
    read_raw_config: RawConfigReader,
    write_raw_config: RawConfigWriter,
    reload_runtime: RuntimeReloader,
    translate: Translate,
    localize_stored_recipe_description: LocalizeRecipeDescription,
    format_recipe_routing_info: FormatInfoMessage,
    suggest_skill_keywords_with_llm: SuggestKeywords,
    daily_time_to_cron: DailyTimeToCron,
    daily_time_from_cron: DailyTimeFromCron,
) -> None:
    def _build_recipes_page_context(
        request: Request,
        *,
        saved: int = 0,
        error: str = "",
        info: str = "",
        logical_back_fallback: str = "/recipes",
        page_return_to: str = "/recipes",
        recipes_nav: str = "overview",
        page_heading: str,
        show_overview_checks: bool = False,
        learned_filter: str = LEARNED_RECIPE_FILTER_ALL,
        learned_kind_filter: str = LEARNED_RECIPE_KIND_FILTER_ALL,
        learned_sort: str = LEARNED_RECIPE_SORT_LAST_SUCCESS,
    ) -> dict[str, Any]:
        settings = get_settings()
        username = get_username_from_request(request)
        lang = str(getattr(request.state, "lang", "de") or "de")
        _set_logical_back_url(request, fallback=logical_back_fallback)
        custom_cfg = _normalize_custom_cfg(read_raw_config())
        custom_manifests, custom_errors = _load_stored_recipe_manifests()
        learned_all_rows = build_learned_recipe_rows(load_learned_recipe_store_entries())
        effective_learned_filter = normalize_learned_recipe_filter(learned_filter)
        effective_learned_kind_filter = normalize_learned_recipe_kind_filter(learned_kind_filter, learned_all_rows)
        effective_learned_sort = normalize_learned_recipe_sort(learned_sort)
        learned_rows = filter_learned_recipe_rows(learned_all_rows, effective_learned_filter)
        learned_rows = filter_learned_recipe_rows_by_kind(learned_rows, effective_learned_kind_filter)
        learned_rows = sort_learned_recipe_rows(learned_rows, effective_learned_sort)
        learned_filter_counts = learned_recipe_filter_counts(learned_all_rows)
        learned_kind_counts = learned_recipe_kind_counts(learned_all_rows)
        advanced_mode = bool(getattr(request.state, "can_access_advanced_config", False))
        core_recipe_rows = _build_core_recipe_rows(lang, settings, translate)
        custom_rows = _build_custom_rows(
            custom_manifests,
            custom_cfg,
            lang,
            localize_stored_recipe_description,
            daily_time_from_cron,
        )
        sample_recipe_rows = build_sample_recipe_rows()
        overview_checks = build_recipes_overview_checks(
            lang=lang,
            core_recipe_rows=core_recipe_rows,
            learned_rows=learned_all_rows,
            custom_rows=custom_rows,
            sample_recipe_rows=sample_recipe_rows,
            advanced_mode=advanced_mode,
            translate=translate,
        )
        has_custom_recipes = bool(custom_rows)
        next_steps = build_recipes_next_steps(
            lang=lang,
            has_custom_recipes=has_custom_recipes,
            custom_count=len(custom_rows),
            core_recipe_count=len(core_recipe_rows),
            sample_recipe_count=len(sample_recipe_rows),
            translate=translate,
        )
        return {
            "title": settings.ui.title,
            "username": username,
            "saved": bool(saved),
            "error_message": error,
            "info_message": format_recipe_routing_info(lang, info),
            "core_recipe_rows": core_recipe_rows,
            "learned_rows": learned_rows,
            "learned_all_rows": learned_all_rows,
            "custom_rows": custom_rows,
            "sample_recipe_rows": sample_recipe_rows,
            "custom_errors": custom_errors,
            "recipes_readonly": not advanced_mode,
            "page_return_to": _recipe_surface_path(page_return_to, fallback="/recipes"),
            "overview_checks": overview_checks,
            "active_core_count": sum(1 for row in core_recipe_rows if bool(row.get("enabled"))),
            "active_custom_count": sum(1 for row in custom_rows if bool(row.get("enabled"))),
            "learned_count": len(learned_rows),
            "learned_total_count": len(learned_all_rows),
            "learned_filter": effective_learned_filter,
            "learned_kind_filter": effective_learned_kind_filter,
            "learned_sort": effective_learned_sort,
            "learned_filter_counts": learned_filter_counts,
            "learned_kind_counts": learned_kind_counts,
            "learned_kind_values": learned_recipe_kind_values(learned_all_rows),
            "custom_count": len(custom_rows),
            "sample_count": len(sample_recipe_rows),
            "sample_category_count": len(
                {str(row.get("category", "")).strip().lower() for row in sample_recipe_rows if str(row.get("category", "")).strip()}
            ),
            "next_steps": next_steps,
            "recipes_nav": recipes_nav,
            "recipes_page_heading": page_heading,
            "show_overview_checks": bool(show_overview_checks),
        }

    def _render_recipes_surface(
        request: Request,
        *,
        template_name: str,
        saved: int = 0,
        error: str = "",
        info: str = "",
        logical_back_fallback: str = "/recipes",
        page_return_to: str = "/recipes",
        recipes_nav: str = "overview",
        page_heading: str,
        show_overview_checks: bool = False,
        learned_filter: str = LEARNED_RECIPE_FILTER_ALL,
        learned_kind_filter: str = LEARNED_RECIPE_KIND_FILTER_ALL,
        learned_sort: str = LEARNED_RECIPE_SORT_LAST_SUCCESS,
    ) -> HTMLResponse:
        context = _build_recipes_page_context(
            request,
            saved=saved,
            error=error,
            info=info,
            logical_back_fallback=logical_back_fallback,
            page_return_to=page_return_to,
            recipes_nav=recipes_nav,
            page_heading=page_heading,
            show_overview_checks=show_overview_checks,
            learned_filter=learned_filter,
            learned_kind_filter=learned_kind_filter,
            learned_sort=learned_sort,
        )
        return templates.TemplateResponse(
            request=request,
            name=template_name,
            context=context,
        )

    @app.get("/recipes", response_class=HTMLResponse)
    async def recipes_page(request: Request, saved: int = 0, error: str = "", info: str = "") -> HTMLResponse:
        lang = str(getattr(request.state, "lang", "de") or "de")
        return _render_recipes_surface(
            request,
            template_name="recipes_overview.html",
            saved=saved,
            error=error,
            info=info,
            logical_back_fallback="/",
            page_return_to="/recipes",
            recipes_nav="overview",
            page_heading=translate(lang, "recipes.title", "Recipes"),
            show_overview_checks=True,
        )

    @app.get("/recipes/start", response_class=HTMLResponse)
    async def recipes_start_page(request: Request, saved: int = 0, error: str = "", info: str = "") -> HTMLResponse:
        lang = str(getattr(request.state, "lang", "de") or "de")
        return _render_recipes_surface(
            request,
            template_name="recipes_start.html",
            saved=saved,
            error=error,
            info=info,
            logical_back_fallback="/recipes",
            page_return_to="/recipes/start",
            recipes_nav="start",
            page_heading=translate(lang, "recipes.start_title", "Start recipe"),
        )

    @app.get("/recipes/mine", response_class=HTMLResponse)
    async def recipes_mine_page(request: Request, saved: int = 0, error: str = "", info: str = "") -> HTMLResponse:
        lang = str(getattr(request.state, "lang", "de") or "de")
        return _render_recipes_surface(
            request,
            template_name="recipes_mine.html",
            saved=saved,
            error=error,
            info=info,
            logical_back_fallback="/recipes",
            page_return_to="/recipes/mine",
            recipes_nav="mine",
            page_heading=translate(lang, "recipes.my_recipes_title", "My recipes"),
        )

    @app.get("/recipes/learned", response_class=HTMLResponse)
    async def recipes_learned_page(
        request: Request,
        saved: int = 0,
        error: str = "",
        info: str = "",
        state: str = "",
        kind: str = "",
        sort: str = "",
    ) -> HTMLResponse:
        lang = str(getattr(request.state, "lang", "de") or "de")
        return _render_recipes_surface(
            request,
            template_name="recipes_learned.html",
            saved=saved,
            error=error,
            info=info,
            logical_back_fallback="/recipes",
            page_return_to="/recipes/learned",
            recipes_nav="learned",
            page_heading=translate(lang, "learned_recipes.title", "Learned recipes"),
            learned_filter=state,
            learned_kind_filter=kind,
            learned_sort=sort,
        )

    @app.get("/recipes/system", response_class=HTMLResponse)
    async def recipes_system_page(request: Request, saved: int = 0, error: str = "", info: str = "") -> HTMLResponse:
        lang = str(getattr(request.state, "lang", "de") or "de")
        return _render_recipes_surface(
            request,
            template_name="recipes_system.html",
            saved=saved,
            error=error,
            info=info,
            logical_back_fallback="/recipes",
            page_return_to="/recipes/system",
            recipes_nav="system",
            page_heading=translate(lang, "recipes.system_title", "Core / System"),
        )

    def _redirect_learned_recipe_admin_action(
        request: Request,
        *,
        action: str,
        recipe_id: str,
        csrf_token: str,
        return_to: str,
    ) -> RedirectResponse:
        surface_path = _recipe_surface_return_to(return_to, fallback="/recipes/learned")
        if not _is_admin_mode_request(request, get_auth_session_from_request, sanitize_role):
            return _redirect_with_return_to(f"{surface_path}?error=readonly", request, fallback="/", return_to=return_to)
        expected_csrf = str(getattr(getattr(request, "state", object()), "csrf_token", "") or "")
        if not _is_valid_csrf_submission(csrf_token, expected_csrf):
            return _redirect_with_return_to(f"{surface_path}?error=csrf_failed", request, fallback="/", return_to=return_to)
        try:
            url = learned_recipe_admin_success_url(action=action, recipe_id=recipe_id, surface_path=surface_path)
            return _redirect_with_return_to(url, request, fallback="/", return_to=return_to)
        except (OSError, ValueError) as exc:
            return _redirect_with_return_to(
                f"{surface_path}?error={quote_plus(str(exc))}",
                request,
                fallback="/",
                return_to=return_to,
            )

    @app.post("/recipes/learned/promote")
    async def recipes_learned_promote(
        request: Request,
        recipe_id: str = Form(""),
        csrf_token: str = Form(""),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        return _redirect_learned_recipe_admin_action(
            request,
            action="promote",
            recipe_id=recipe_id,
            csrf_token=csrf_token,
            return_to=return_to,
        )

    @app.post("/recipes/learned/dismiss")
    async def recipes_learned_dismiss(
        request: Request,
        recipe_id: str = Form(""),
        csrf_token: str = Form(""),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        return _redirect_learned_recipe_admin_action(
            request,
            action="dismiss",
            recipe_id=recipe_id,
            csrf_token=csrf_token,
            return_to=return_to,
        )

    @app.post("/recipes/learned/delete")
    async def recipes_learned_delete(
        request: Request,
        recipe_id: str = Form(""),
        csrf_token: str = Form(""),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        return _redirect_learned_recipe_admin_action(
            request,
            action="delete",
            recipe_id=recipe_id,
            csrf_token=csrf_token,
            return_to=return_to,
        )

    @app.get("/recipes/templates", response_class=HTMLResponse)
    async def recipes_templates_page(request: Request, saved: int = 0, error: str = "", info: str = "") -> HTMLResponse:
        lang = str(getattr(request.state, "lang", "de") or "de")
        return _render_recipes_surface(
            request,
            template_name="recipes_templates.html",
            saved=saved,
            error=error,
            info=info,
            logical_back_fallback="/recipes",
            page_return_to="/recipes/templates",
            recipes_nav="templates",
            page_heading=translate(lang, "recipes.templates_title", "Vorlagen"),
        )

    @app.post("/recipes/save")
    async def recipes_save(
        request: Request,
        memory_enabled: str = Form("0"),
        auto_memory_enabled: str = Form("0"),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        surface_path = _recipe_surface_path(return_to, fallback="/recipes")
        if not _is_admin_mode_request(request, get_auth_session_from_request, sanitize_role):
            return _redirect_with_return_to(f"{surface_path}?error=readonly", request, fallback="/", return_to=return_to)
        try:
            form = await request.form()
            raw = read_raw_config()
            raw.setdefault("memory", {})
            if not isinstance(raw["memory"], dict):
                raw["memory"] = {}
            if "memory_enabled" in form:
                raw["memory"]["enabled"] = str(memory_enabled).strip().lower() in {"1", "true", "on", "yes"}

            raw.setdefault("auto_memory", {})
            if not isinstance(raw["auto_memory"], dict):
                raw["auto_memory"] = {}
            if "auto_memory_enabled" in form:
                raw["auto_memory"]["enabled"] = str(auto_memory_enabled).strip().lower() in {"1", "true", "on", "yes"}

            raw.setdefault("skills", {})
            if not isinstance(raw["skills"], dict):
                raw["skills"] = {}
            raw["skills"].setdefault("custom", {})
            if not isinstance(raw["skills"]["custom"], dict):
                raw["skills"]["custom"] = {}

            custom_manifest_rows, _ = _load_stored_recipe_manifests()
            known_ids = {row["id"] for row in custom_manifest_rows}
            rendered_toggle_ids = {
                _sanitize_recipe_id(item)
                for item in form.getlist("custom_toggle_ids")
                if _sanitize_recipe_id(item)
            }
            if rendered_toggle_ids:
                for skill_id in known_ids:
                    if skill_id not in rendered_toggle_ids:
                        continue
                    key = f"custom_enabled__{skill_id}"
                    raw["skills"]["custom"].setdefault(skill_id, {})
                    if not isinstance(raw["skills"]["custom"][skill_id], dict):
                        raw["skills"]["custom"][skill_id] = {}
                    raw["skills"]["custom"][skill_id]["enabled"] = str(form.get(key, "")).strip().lower() in {
                        "1",
                        "true",
                        "on",
                        "yes",
                    }

            write_raw_config(raw)
            reload_runtime()
            return _redirect_with_return_to(f"{surface_path}?saved=1", request, fallback="/", return_to=return_to)
        except (OSError, ValueError) as exc:
            return _redirect_with_return_to(
                f"{surface_path}?error={quote_plus(str(exc))}",
                request,
                fallback="/",
                return_to=return_to,
            )

    @app.get("/recipes/wizard", response_class=HTMLResponse)
    async def recipes_wizard_page(
        request: Request,
        skill_id: str = "",
        mode: str = "",
        saved: int = 0,
        error: str = "",
        info: str = "",
    ) -> HTMLResponse:
        if not _is_admin_mode_request(request, get_auth_session_from_request, sanitize_role):
            return _redirect_with_return_to("/recipes?error=readonly", request, fallback="/recipes")
        settings = get_settings()
        username = get_username_from_request(request)
        lang = str(getattr(request.state, "lang", "de") or "de")
        return_to = _set_logical_back_url(request, fallback="/recipes")
        loaded: dict[str, Any] | None = None
        clean_id = _sanitize_recipe_id(skill_id)
        if clean_id:
            path = _recipe_manifest_file(clean_id)
            if path.exists():
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    if isinstance(payload, dict):
                        loaded = _validate_stored_recipe_manifest(payload)
                except Exception as exc:  # noqa: BLE001
                    error = error or str(exc)

        all_manifests, _ = _load_stored_recipe_manifests()
        category_options = _collect_recipe_categories(all_manifests)
        selected_category = str((loaded or {}).get("category", "")).strip().lower()
        if selected_category and selected_category not in category_options:
            category_options.append(selected_category)

        effective_id = _sanitize_recipe_id((loaded or {}).get("id", "")) or _sanitize_recipe_id((loaded or {}).get("name", ""))
        prompt_preview = f"prompts/recipes/{effective_id or '<recipe-id>'}.md"
        prompt_file_value = str((loaded or {}).get("prompt_file", "")).strip() or (
            f"prompts/recipes/{effective_id}.md" if effective_id else ""
        )
        schema_version_value = str((loaded or {}).get("schema_version", "1.1")).strip() or "1.1"
        connections_value = (loaded or {}).get("connections", [])
        connections_text = ", ".join(connections_value) if isinstance(connections_value, list) else ""
        loaded_schedule = _normalize_recipe_schedule_manifest((loaded or {}).get("schedule", {}))
        loaded_schedule["time_24h"] = daily_time_from_cron(str(loaded_schedule.get("cron", "")))
        wizard_mode = _sanitize_wizard_mode(mode) if mode else _default_wizard_mode(loaded)
        selected_recipe_type = _infer_recipe_type(loaded)

        return templates.TemplateResponse(
            request=request,
            name="recipes_wizard.html",
            context={
                "title": settings.ui.title,
                "username": username,
                "saved": bool(saved),
                "error_message": error,
                "info_message": format_recipe_routing_info(lang, info),
                "recipes_nav": "start",
                "recipes_page_heading": translate(
                    lang,
                    "recipes.wizard_page_heading_edit" if loaded else "recipes.wizard_page_heading_new",
                    "Edit existing recipe" if loaded else "Create new recipe",
                ),
                "recipes_readonly": False,
                "custom_errors": [],
                "show_overview_checks": False,
                "skill": loaded or {},
                "category_options": category_options,
                "ssh_connection_options": _build_connection_options(get_settings().connections.ssh),
                "sftp_connection_options": _build_connection_options(get_settings().connections.sftp),
                "smb_connection_options": _build_connection_options(get_settings().connections.smb),
                "rss_connection_options": _build_connection_options(get_settings().connections.rss),
                "discord_connection_options": _build_connection_options(get_settings().connections.discord),
                "prompt_preview": prompt_preview,
                "prompt_file_value": prompt_file_value,
                "schema_version_value": schema_version_value,
                "connections_text": connections_text,
                "step_forms": _build_step_forms(loaded),
                "schedule": loaded_schedule,
                "return_to": return_to,
                "wizard_mode": wizard_mode,
                "skill_type_options": _recipe_type_options(),
                "selected_skill_type": selected_recipe_type,
                "skill_type_presets_json": _RECIPE_TYPE_PRESETS,
                "skill_type_allowed_steps_json": _recipe_type_allowed_steps(),
                "skill_type_followup_steps_json": _recipe_type_followup_steps(),
                "skill_type_connection_choices_json": _recipe_type_connection_choices(),
                "connection_options_by_kind_json": _connection_options_by_kind(settings),
            },
        )

    @app.post("/recipes/wizard/save")
    async def recipes_wizard_save(
        request: Request,
        original_skill_id: str = Form(""),
        skill_id: str = Form(""),
        skill_name: str = Form(...),
        skill_version: str = Form("0.1.0"),
        skill_description: str = Form(""),
        skill_category: str = Form("custom"),
        skill_type: str = Form("health_check"),
        skill_router_keywords: str = Form(""),
        skill_connections: str = Form(""),
        skill_prompt_file: str = Form(""),
        skill_schema_version: str = Form("1.1"),
        auto_generate_keywords: str = Form("1"),
        schedule_enabled: str = Form("0"),
        schedule_time: str = Form(""),
        schedule_timezone: str = Form("Europe/Zurich"),
        schedule_run_on_startup: str = Form("0"),
        skill_ui_config_path: str = Form(""),
        skill_ui_hint: str = Form(""),
        enabled_default: str = Form("0"),
        wizard_mode: str = Form("simple"),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        lang = str(getattr(request.state, "lang", "de") or "de")
        if not _is_admin_mode_request(request, get_auth_session_from_request, sanitize_role):
            return _redirect_with_return_to("/recipes?error=readonly", request, fallback="/recipes", return_to=return_to)
        try:
            form = await request.form()
            result = await save_recipe_from_wizard_form(
                form=form,
                values=WizardSaveInput(
                    original_skill_id=original_skill_id,
                    skill_id=skill_id,
                    skill_name=skill_name,
                    skill_version=skill_version,
                    skill_description=skill_description,
                    skill_category=skill_category,
                    skill_type=skill_type,
                    skill_router_keywords=skill_router_keywords,
                    skill_connections=skill_connections,
                    skill_prompt_file=skill_prompt_file,
                    skill_schema_version=skill_schema_version,
                    auto_generate_keywords=auto_generate_keywords,
                    schedule_enabled=schedule_enabled,
                    schedule_time=schedule_time,
                    schedule_timezone=schedule_timezone,
                    schedule_run_on_startup=schedule_run_on_startup,
                    skill_ui_config_path=skill_ui_config_path,
                    skill_ui_hint=skill_ui_hint,
                    enabled_default=enabled_default,
                    wizard_mode=wizard_mode,
                ),
                lang=lang,
                daily_time_to_cron=daily_time_to_cron,
                suggest_keywords=suggest_skill_keywords_with_llm,
            )
            raw = read_raw_config()
            raw = migrate_custom_recipe_config(
                raw,
                old_id=result.original_recipe_id,
                new_id=result.recipe_id,
                enabled=result.enabled_default,
            )
            write_raw_config(raw)
            reload_runtime()
            info_suffix = ""
            if result.generated_keyword_count:
                info_suffix = f"&info={quote_plus(f'keywords:auto:{result.generated_keyword_count}')}"
            return _redirect_with_return_to(
                f"/recipes/wizard?skill_id={quote_plus(result.recipe_id)}&mode={quote_plus(result.wizard_mode)}&saved=1{info_suffix}",
                request,
                fallback="/recipes",
                return_to=return_to,
            )
        except (OSError, ValueError) as exc:
            clean_mode = _sanitize_wizard_mode(wizard_mode)
            return _redirect_with_return_to(
                f"/recipes/wizard?mode={quote_plus(clean_mode)}&error={quote_plus(str(exc))}",
                request,
                fallback="/recipes",
                return_to=return_to,
            )

    @app.post("/recipes/import")
    async def recipes_import(
        request: Request,
        csrf_token: str = Form(""),
        skill_file: UploadFile = File(...),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        surface_path = _recipe_surface_path(return_to, fallback="/recipes")
        if not _is_admin_mode_request(request, get_auth_session_from_request, sanitize_role):
            return _redirect_with_return_to(f"{surface_path}?error=readonly", request, fallback="/", return_to=return_to)
        expected_csrf = str(getattr(getattr(request, "state", object()), "csrf_token", "") or "")
        if not _is_valid_csrf_submission(csrf_token, expected_csrf):
            return _redirect_with_return_to(f"{surface_path}?error=csrf_failed", request, fallback="/", return_to=return_to)
        try:
            payload = await skill_file.read()
            raw = json.loads(payload.decode("utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("Import erwartet ein JSON-Objekt.")
            clean = _save_stored_recipe_manifest(raw)
            return _redirect_with_return_to(
                f"{surface_path}?saved=1&info=imported:{quote_plus(clean['id'])}",
                request,
                fallback="/",
                return_to=return_to,
            )
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError, OSError) as exc:
            return _redirect_with_return_to(
                f"{surface_path}?error={quote_plus(str(exc))}",
                request,
                fallback="/",
                return_to=return_to,
            )

    @app.post("/recipes/import-sample")
    async def recipes_import_sample(
        request: Request,
        sample_file: str = Form(""),
        csrf_token: str = Form(""),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        surface_path = _recipe_surface_path(return_to, fallback="/recipes")
        if not _is_admin_mode_request(request, get_auth_session_from_request, sanitize_role):
            return _redirect_with_return_to(f"{surface_path}?error=readonly", request, fallback="/", return_to=return_to)
        expected_csrf = str(getattr(getattr(request, "state", object()), "csrf_token", "") or "")
        if not _is_valid_csrf_submission(csrf_token, expected_csrf):
            return _redirect_with_return_to(f"{surface_path}?error=csrf_failed", request, fallback="/", return_to=return_to)
        try:
            lang = str(getattr(request.state, "lang", "de") or "de")
            url = import_sample_recipe_success_url(sample_file=sample_file, surface_path=surface_path, lang=lang)
            return _redirect_with_return_to(url, request, fallback="/", return_to=return_to)
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError, OSError) as exc:
            return _redirect_with_return_to(
                f"{surface_path}?error={quote_plus(str(exc))}",
                request,
                fallback="/",
                return_to=return_to,
            )

    @app.post("/recipes/delete")
    async def recipes_delete(
        request: Request,
        skill_id: str = Form(""),
        csrf_token: str = Form(""),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        surface_path = _recipe_surface_path(return_to, fallback="/recipes")
        if not _is_admin_mode_request(request, get_auth_session_from_request, sanitize_role):
            return _redirect_with_return_to(f"{surface_path}?error=readonly", request, fallback="/", return_to=return_to)
        expected_csrf = str(getattr(getattr(request, "state", object()), "csrf_token", "") or "")
        if not _is_valid_csrf_submission(csrf_token, expected_csrf):
            return _redirect_with_return_to(f"{surface_path}?error=csrf_failed", request, fallback="/", return_to=return_to)
        try:
            result = delete_stored_recipe_and_config(
                skill_id,
                read_raw_config=read_raw_config,
                write_raw_config=write_raw_config,
                reload_runtime=reload_runtime,
            )
            info_value = quote_plus(f"deleted:{result['id']}")
            return _redirect_with_return_to(
                f"{surface_path}?saved=1&info={info_value}",
                request,
                fallback="/",
                return_to=return_to,
            )
        except (OSError, ValueError) as exc:
            return _redirect_with_return_to(
                f"{surface_path}?error={quote_plus(str(exc))}",
                request,
                fallback="/",
                return_to=return_to,
            )

    @app.get("/recipes/export/{skill_id}")
    async def recipes_export(request: Request, skill_id: str) -> Response:
        if not _is_admin_mode_request(request, get_auth_session_from_request, sanitize_role):
            return JSONResponse({"error": "readonly"}, status_code=403)
        return stored_recipe_export_response(skill_id)


register_skills_routes = register_recipe_routes
_infer_skill_type = _infer_recipe_type
_migrate_custom_skill_config = migrate_custom_recipe_config
_remove_custom_skill_config = remove_custom_recipe_config
