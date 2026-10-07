from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote_plus

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from aria.modules import module_route_path, module_template_name
from aria.modules.recipe_runtime.stored_manifest_view import stored_recipe_candidate_metadata
from aria.modules.recipes_ui.route_support import is_admin_mode_request as _is_admin_mode_request
from aria.modules.recipes_ui.route_support import is_valid_csrf_submission as _is_valid_csrf_submission
from aria.modules.recipes_ui.route_support import recipe_surface_path as _recipe_surface_path
from aria.modules.recipes_ui.route_support import redirect_with_return_to as _redirect_with_return_to
from aria.modules.recipes_ui.route_support import set_logical_back_url as _set_logical_back_url
from aria.modules.recipes_ui.surface_context import build_recipes_next_steps, build_recipes_overview_checks
from aria.modules.recipe_store.template_import import build_sample_recipe_rows
from aria.modules.recipes_ui.route_support import import_sample_recipe_success_url
from aria.modules.recipe_store.manifest_actions import delete_stored_recipe_and_config
from aria.modules.recipe_store.manifest_actions import stored_recipe_export_response
from aria.modules.recipe_store.wizard_save import (
    WizardSaveInput,
    migrate_custom_recipe_config,
    remove_custom_recipe_config,
    save_recipe_from_wizard_form,
)
from aria.modules.recipe_store.wizard_catalog import (
    _RECIPE_TYPE_PRESETS,
    _recipe_type_allowed_steps,
    _recipe_type_connection_choices,
    _recipe_type_followup_steps,
    _recipe_type_options,
)
from aria.modules.recipe_store.manifests import (
    canonical_recipe_prompt_file,
    default_recipe_prompt_file,
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
DailyTimeToCron = Callable[[str], str]
DailyTimeFromCron = Callable[[str], str]

BASE_DIR = Path(__file__).resolve().parents[3]

# UI-Migrationshinweis:
# Die internen Parameter heissen teilweise noch skill_*, damit alte Forms und
# Config-Backcompat stabil bleiben. Sichtbar nach aussen ist dieser Bereich
# aber recipe-first.


def _recipes_ui_template_name(template_name: str) -> str:
    resolved = module_template_name("recipes_ui", template_name)
    if resolved is None:
        raise RuntimeError(f"recipes_ui template is not registered: {template_name}")
    return resolved


def _recipes_ui_route_path(route_path: str) -> str:
    resolved = module_route_path("recipes_ui", route_path)
    if resolved is None:
        raise RuntimeError(f"recipes_ui route is not registered: {route_path}")
    return resolved


def _config_ui_route_path(route_path: str) -> str:
    resolved = module_route_path("config_ui", route_path)
    if resolved is None:
        raise RuntimeError(f"config_ui route is not registered: {route_path}")
    return resolved


def _chat_surface_route_path(route_path: str) -> str:
    resolved = module_route_path("chat_surface", route_path)
    if resolved is None:
        raise RuntimeError(f"chat_surface route is not registered: {route_path}")
    return resolved


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
                "prompt_file": canonical_recipe_prompt_file(str(manifest.get("prompt_file", "") or "")),
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
                "timeout_seconds": params.get("timeout_seconds") or "",
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
    daily_time_to_cron: DailyTimeToCron,
    daily_time_from_cron: DailyTimeFromCron,
) -> None:
    def _build_recipes_page_context(
        request: Request,
        *,
        saved: int = 0,
        error: str = "",
        info: str = "",
        logical_back_fallback: str | None = None,
        page_return_to: str | None = None,
        recipes_nav: str = "overview",
        page_heading: str,
        show_overview_checks: bool = False,
        recipes_admin_nav: bool = False,
    ) -> dict[str, Any]:
        settings = get_settings()
        username = get_username_from_request(request)
        lang = str(getattr(request.state, "lang", "de") or "de")
        recipes_home_path = _recipes_ui_route_path("/recipes")
        resolved_logical_back_fallback = logical_back_fallback or recipes_home_path
        resolved_page_return_to = page_return_to or recipes_home_path
        _set_logical_back_url(request, fallback=resolved_logical_back_fallback)
        custom_cfg = _normalize_custom_cfg(read_raw_config())
        custom_manifests, custom_errors = _load_stored_recipe_manifests()
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
            "custom_rows": custom_rows,
            "sample_recipe_rows": sample_recipe_rows,
            "custom_errors": custom_errors,
            "recipes_readonly": not advanced_mode,
            "page_return_to": _recipe_surface_path(resolved_page_return_to, fallback=recipes_home_path),
            "overview_checks": overview_checks,
            "active_core_count": sum(1 for row in core_recipe_rows if bool(row.get("enabled"))),
            "active_custom_count": sum(1 for row in custom_rows if bool(row.get("enabled"))),
            "custom_count": len(custom_rows),
            "sample_count": len(sample_recipe_rows),
            "sample_category_count": len(
                {str(row.get("category", "")).strip().lower() for row in sample_recipe_rows if str(row.get("category", "")).strip()}
            ),
            "next_steps": next_steps,
            "recipes_nav": recipes_nav,
            "recipes_admin_nav": bool(recipes_admin_nav),
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
        logical_back_fallback: str | None = None,
        page_return_to: str | None = None,
        recipes_nav: str = "overview",
        page_heading: str,
        show_overview_checks: bool = False,
        recipes_admin_nav: bool = False,
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
            recipes_admin_nav=recipes_admin_nav,
        )
        return templates.TemplateResponse(
            request=request,
            name=_recipes_ui_template_name(template_name),
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
            logical_back_fallback=_chat_surface_route_path("/"),
            page_return_to=_recipes_ui_route_path("/recipes"),
            recipes_nav="overview",
            page_heading=translate(lang, "base.nav_skills", "Recipes"),
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
            logical_back_fallback=_recipes_ui_route_path("/recipes"),
            page_return_to=_recipes_ui_route_path("/recipes/start"),
            recipes_nav="start",
            page_heading=translate(lang, "recipes.new_templates_title", "New / templates"),
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
            logical_back_fallback=_recipes_ui_route_path("/recipes"),
            page_return_to=_recipes_ui_route_path("/recipes/mine"),
            recipes_nav="mine",
            page_heading=translate(lang, "recipes.my_recipes_title", "My recipes"),
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
            logical_back_fallback=_recipes_ui_route_path("/recipes"),
            page_return_to=_recipes_ui_route_path("/recipes/system"),
            recipes_nav="system",
            page_heading=translate(lang, "recipes.system_title", "Core / System"),
        )

    @app.get("/recipes/templates", response_class=HTMLResponse)
    async def recipes_templates_page(request: Request, saved: int = 0, error: str = "", info: str = "") -> HTMLResponse:
        lang = str(getattr(request.state, "lang", "de") or "de")
        return _render_recipes_surface(
            request,
            template_name="recipes_start.html",
            saved=saved,
            error=error,
            info=info,
            logical_back_fallback=_recipes_ui_route_path("/recipes"),
            page_return_to=_recipes_ui_route_path("/recipes/start"),
            recipes_nav="start",
            page_heading=translate(lang, "recipes.new_templates_title", "New / templates"),
        )

    @app.post("/recipes/save")
    async def recipes_save(
        request: Request,
        memory_enabled: str = Form("0"),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        surface_path = _recipe_surface_path(return_to, fallback=_recipes_ui_route_path("/recipes"))
        if not _is_admin_mode_request(request, get_auth_session_from_request, sanitize_role):
            return _redirect_with_return_to(
                f"{surface_path}?error=readonly",
                request,
                fallback=_chat_surface_route_path("/"),
                return_to=return_to,
            )
        try:
            form = await request.form()
            raw = read_raw_config()
            raw.setdefault("memory", {})
            if not isinstance(raw["memory"], dict):
                raw["memory"] = {}
            if "memory_enabled" in form:
                raw["memory"]["enabled"] = str(memory_enabled).strip().lower() in {"1", "true", "on", "yes"}

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
            return _redirect_with_return_to(
                f"{surface_path}?saved=1",
                request,
                fallback=_chat_surface_route_path("/"),
                return_to=return_to,
            )
        except (OSError, ValueError) as exc:
            return _redirect_with_return_to(
                f"{surface_path}?error={quote_plus(str(exc))}",
                request,
                fallback=_chat_surface_route_path("/"),
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
            recipes_path = _recipes_ui_route_path("/recipes")
            return _redirect_with_return_to(f"{recipes_path}?error=readonly", request, fallback=recipes_path)
        settings = get_settings()
        username = get_username_from_request(request)
        lang = str(getattr(request.state, "lang", "de") or "de")
        return_to = _set_logical_back_url(request, fallback=_recipes_ui_route_path("/recipes"))
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
        prompt_preview = default_recipe_prompt_file(effective_id or "recipe-id")
        if not effective_id:
            prompt_preview = str(Path(prompt_preview).with_name("<recipe-id>.md"))
        prompt_file_value = str((loaded or {}).get("prompt_file", "")).strip() or (
            default_recipe_prompt_file(effective_id) if effective_id else ""
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
            name=_recipes_ui_template_name("recipes_wizard.html"),
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
        skill_connections: str = Form(""),
        skill_prompt_file: str = Form(""),
        skill_schema_version: str = Form("1.1"),
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
            return _redirect_with_return_to(
                f"{_recipes_ui_route_path('/recipes')}?error=readonly",
                request,
                fallback=_recipes_ui_route_path("/recipes"),
                return_to=return_to,
            )
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
                    skill_connections=skill_connections,
                    skill_prompt_file=skill_prompt_file,
                    skill_schema_version=skill_schema_version,
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
            return _redirect_with_return_to(
                f"{_recipes_ui_route_path('/recipes/wizard')}?skill_id={quote_plus(result.recipe_id)}&mode={quote_plus(result.wizard_mode)}&saved=1",
                request,
                fallback=_recipes_ui_route_path("/recipes"),
                return_to=return_to,
            )
        except (OSError, ValueError) as exc:
            clean_mode = _sanitize_wizard_mode(wizard_mode)
            return _redirect_with_return_to(
                f"{_recipes_ui_route_path('/recipes/wizard')}?mode={quote_plus(clean_mode)}&error={quote_plus(str(exc))}",
                request,
                fallback=_recipes_ui_route_path("/recipes"),
                return_to=return_to,
            )

    @app.post("/recipes/import")
    async def recipes_import(
        request: Request,
        csrf_token: str = Form(""),
        skill_file: UploadFile = File(...),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        surface_path = _recipe_surface_path(return_to, fallback=_recipes_ui_route_path("/recipes"))
        if not _is_admin_mode_request(request, get_auth_session_from_request, sanitize_role):
            return _redirect_with_return_to(
                f"{surface_path}?error=readonly",
                request,
                fallback=_chat_surface_route_path("/"),
                return_to=return_to,
            )
        expected_csrf = str(getattr(getattr(request, "state", object()), "csrf_token", "") or "")
        if not _is_valid_csrf_submission(csrf_token, expected_csrf):
            return _redirect_with_return_to(
                f"{surface_path}?error=csrf_failed",
                request,
                fallback=_chat_surface_route_path("/"),
                return_to=return_to,
            )
        try:
            payload = await skill_file.read()
            raw = json.loads(payload.decode("utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("Import erwartet ein JSON-Objekt.")
            clean = _save_stored_recipe_manifest(raw)
            return _redirect_with_return_to(
                f"{surface_path}?saved=1&info=imported:{quote_plus(clean['id'])}",
                request,
                fallback=_chat_surface_route_path("/"),
                return_to=return_to,
            )
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError, OSError) as exc:
            return _redirect_with_return_to(
                f"{surface_path}?error={quote_plus(str(exc))}",
                request,
                fallback=_chat_surface_route_path("/"),
                return_to=return_to,
            )

    @app.post("/recipes/import-sample")
    async def recipes_import_sample(
        request: Request,
        sample_file: str = Form(""),
        csrf_token: str = Form(""),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        surface_path = _recipe_surface_path(return_to, fallback=_recipes_ui_route_path("/recipes"))
        if not _is_admin_mode_request(request, get_auth_session_from_request, sanitize_role):
            return _redirect_with_return_to(
                f"{surface_path}?error=readonly",
                request,
                fallback=_chat_surface_route_path("/"),
                return_to=return_to,
            )
        expected_csrf = str(getattr(getattr(request, "state", object()), "csrf_token", "") or "")
        if not _is_valid_csrf_submission(csrf_token, expected_csrf):
            return _redirect_with_return_to(
                f"{surface_path}?error=csrf_failed",
                request,
                fallback=_chat_surface_route_path("/"),
                return_to=return_to,
            )
        try:
            lang = str(getattr(request.state, "lang", "de") or "de")
            url = import_sample_recipe_success_url(sample_file=sample_file, surface_path=surface_path, lang=lang)
            return _redirect_with_return_to(url, request, fallback=_chat_surface_route_path("/"), return_to=return_to)
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError, OSError) as exc:
            return _redirect_with_return_to(
                f"{surface_path}?error={quote_plus(str(exc))}",
                request,
                fallback=_chat_surface_route_path("/"),
                return_to=return_to,
            )

    @app.post("/recipes/duplicate")
    async def recipes_duplicate(
        request: Request,
        recipe_id: str = Form(""),
        csrf_token: str = Form(""),
    ) -> RedirectResponse:
        surface_path = _recipes_ui_route_path("/recipes/mine")
        if not _is_admin_mode_request(request, get_auth_session_from_request, sanitize_role):
            return _redirect_with_return_to(
                f"{surface_path}?error=readonly",
                request,
                fallback=_chat_surface_route_path("/"),
            )
        expected_csrf = str(getattr(getattr(request, "state", object()), "csrf_token", "") or "")
        if not _is_valid_csrf_submission(csrf_token, expected_csrf):
            return _redirect_with_return_to(
                f"{surface_path}?error=csrf_failed",
                request,
                fallback=_chat_surface_route_path("/"),
            )
        try:
            clean_source_id = _sanitize_recipe_id(recipe_id)
            manifests, _errors = _load_stored_recipe_manifests()
            source = next((row for row in manifests if str(row.get("id", "")) == clean_source_id), None)
            if source is None:
                raise ValueError(f"Recipe not found: {clean_source_id}")

            existing_ids = {str(row.get("id", "")) for row in manifests}
            base_id = _sanitize_recipe_id(f"{clean_source_id[:43]}-copy")
            copy_id = base_id
            suffix = 2
            while copy_id in existing_ids:
                suffix_text = f"-{suffix}"
                copy_id = f"{base_id[:48 - len(suffix_text)]}{suffix_text}"
                suffix += 1

            duplicate = copy.deepcopy(source)
            duplicate["id"] = copy_id
            duplicate["name"] = f"{str(source.get('name', clean_source_id)).strip()} (Kopie)"
            duplicate["enabled_default"] = False
            saved = _save_stored_recipe_manifest(duplicate)

            raw = migrate_custom_recipe_config(
                read_raw_config(),
                old_id="",
                new_id=saved["id"],
                enabled=False,
            )
            write_raw_config(raw)
            reload_runtime()
            return _redirect_with_return_to(
                f"{surface_path}?saved=1&info=duplicated:{quote_plus(saved['id'])}",
                request,
                fallback=surface_path,
            )
        except (OSError, ValueError) as exc:
            return _redirect_with_return_to(
                f"{surface_path}?error={quote_plus(str(exc))}",
                request,
                fallback=surface_path,
            )

    @app.post("/recipes/delete")
    async def recipes_delete(
        request: Request,
        skill_id: str = Form(""),
        csrf_token: str = Form(""),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        surface_path = _recipe_surface_path(return_to, fallback=_recipes_ui_route_path("/recipes"))
        if not _is_admin_mode_request(request, get_auth_session_from_request, sanitize_role):
            return _redirect_with_return_to(
                f"{surface_path}?error=readonly",
                request,
                fallback=_chat_surface_route_path("/"),
                return_to=return_to,
            )
        expected_csrf = str(getattr(getattr(request, "state", object()), "csrf_token", "") or "")
        if not _is_valid_csrf_submission(csrf_token, expected_csrf):
            return _redirect_with_return_to(
                f"{surface_path}?error=csrf_failed",
                request,
                fallback=_chat_surface_route_path("/"),
                return_to=return_to,
            )
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
                fallback=_chat_surface_route_path("/"),
                return_to=return_to,
            )
        except (OSError, ValueError) as exc:
            return _redirect_with_return_to(
                f"{surface_path}?error={quote_plus(str(exc))}",
                request,
                fallback=_chat_surface_route_path("/"),
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
