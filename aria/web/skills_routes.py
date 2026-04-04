from __future__ import annotations

import hmac
import json
import re
from pathlib import Path
from typing import Any, Awaitable, Callable
from urllib.parse import quote_plus

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from aria.core.custom_skills import (
    _collect_skill_categories,
    _custom_skill_file,
    _delete_custom_skill_manifest,
    _load_custom_skill_manifests,
    _normalize_skill_schedule_manifest,
    _normalize_skill_steps_manifest,
    _sanitize_skill_id,
    _save_custom_skill_manifest,
    _validate_custom_skill_manifest,
)


SettingsGetter = Callable[[], Any]
UsernameResolver = Callable[[Request], str]
AuthSessionResolver = Callable[[Request], dict[str, Any] | None]
RoleSanitizer = Callable[[str | None], str]
RawConfigReader = Callable[[], dict[str, Any]]
RawConfigWriter = Callable[[dict[str, Any]], None]
RuntimeReloader = Callable[[], None]
Translate = Callable[[str, str, str], str]
LocalizeSkillDescription = Callable[[dict[str, Any], str], str]
FormatInfoMessage = Callable[[str, str], str]
SuggestKeywords = Callable[..., Awaitable[list[str]]]
DailyTimeToCron = Callable[[str], str]
DailyTimeFromCron = Callable[[str], str]

BASE_DIR = Path(__file__).resolve().parents[2]
SAMPLE_SKILLS_DIR = BASE_DIR / "samples" / "skills"


def _sanitize_csrf_token_local(value: str | None) -> str:
    token = str(value or "").strip()
    token = re.sub(r"[^A-Za-z0-9_-]", "", token)
    return token[:256]


def _is_valid_csrf_submission(submitted_token: str | None, expected_token: str | None) -> bool:
    supplied = _sanitize_csrf_token_local(submitted_token)
    expected = _sanitize_csrf_token_local(expected_token)
    if not supplied or not expected:
        return False
    return hmac.compare_digest(supplied, expected)


def _is_admin_mode_request(
    request: Request,
    get_auth_session_from_request: AuthSessionResolver,
    sanitize_role: RoleSanitizer,
) -> bool:
    if bool(getattr(request.state, "can_access_advanced_config", False)):
        return True
    auth = get_auth_session_from_request(request) or {}
    role = sanitize_role(auth.get("role"))
    return role == "admin" and bool(getattr(request.state, "debug_mode", False))


def _build_connection_options(rows: dict[str, Any]) -> list[dict[str, str]]:
    options: list[dict[str, str]] = []
    for ref in sorted(rows.keys()):
        row = rows.get(ref)
        title = str(getattr(row, "title", "") or "").strip()
        label = f"{title} · {ref}" if title and title != ref else ref
        options.append({"ref": ref, "label": label})
    return options


def _build_skill_rows(lang: str, settings: Any, translate: Translate) -> list[dict[str, Any]]:
    return [
        {
            "key": "memory",
            "title": "Memory",
            "desc": translate(lang, "skills.core_memory_desc", "Speichern und Abrufen von Wissen via Qdrant."),
            "enabled": bool(settings.memory.enabled),
            "implemented": True,
        },
        {
            "key": "auto_memory",
            "title": "Auto-Memory",
            "desc": translate(lang, "skills.core_auto_memory_desc", "Automatische Fakten-Extraktion ohne Codewörter."),
            "enabled": bool(settings.auto_memory.enabled),
            "implemented": True,
        },
    ]


def _build_custom_rows(
    custom_manifests: list[dict[str, Any]],
    custom_cfg: dict[str, Any],
    lang: str,
    localize_custom_skill_description: LocalizeSkillDescription,
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
                "desc": localize_custom_skill_description(manifest, lang),
                "enabled": bool(custom_section.get("enabled", manifest.get("enabled_default", True))),
                "implemented": True,
                "category": manifest.get("category", "custom"),
                "prompt_file": manifest.get("prompt_file", ""),
                "router_keywords": manifest.get("router_keywords", []),
                "connections": manifest.get("connections", []),
                "steps": manifest.get("steps", []),
                "schedule": manifest.get("schedule", {}),
                "schedule_time_24h": daily_time_from_cron(str((manifest.get("schedule", {}) or {}).get("cron", ""))),
                "config_path": str((manifest.get("ui", {}) or {}).get("config_path", "")).strip(),
                "hint": str((manifest.get("ui", {}) or {}).get("hint", "")).strip(),
            }
        )
    return rows


def _build_sample_skill_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not SAMPLE_SKILLS_DIR.exists():
        return rows
    for path in sorted(SAMPLE_SKILLS_DIR.glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(raw, dict):
            continue
        skill_id = _sanitize_skill_id(str(raw.get("id", "")).strip())
        if not skill_id:
            continue
        rows.append(
            {
                "file_name": path.name,
                "id": skill_id,
                "name": str(raw.get("name", "")).strip() or skill_id,
                "description": str(raw.get("description", "")).strip(),
                "category": str(raw.get("category", "custom")).strip() or "custom",
            }
        )
    return rows


def _normalize_custom_cfg(raw: dict[str, Any]) -> dict[str, Any]:
    skills_cfg = raw.get("skills", {})
    if not isinstance(skills_cfg, dict):
        skills_cfg = {}
    custom_cfg = skills_cfg.get("custom", {})
    if not isinstance(custom_cfg, dict):
        custom_cfg = {}
    return custom_cfg


def _build_step_forms(loaded: dict[str, Any] | None) -> list[dict[str, Any]]:
    loaded_steps = _normalize_skill_steps_manifest((loaded or {}).get("steps", []))
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


def _migrate_custom_skill_config(raw: dict[str, Any], old_id: str, new_id: str, enabled: bool) -> dict[str, Any]:
    raw.setdefault("skills", {})
    if not isinstance(raw["skills"], dict):
        raw["skills"] = {}
    raw["skills"].setdefault("custom", {})
    if not isinstance(raw["skills"]["custom"], dict):
        raw["skills"]["custom"] = {}

    custom_section = raw["skills"]["custom"]
    clean_old = _sanitize_skill_id(old_id)
    clean_new = _sanitize_skill_id(new_id)

    previous = custom_section.get(clean_old, {}) if clean_old else {}
    current = custom_section.get(clean_new, {}) if clean_new else {}
    merged: dict[str, Any] = {}
    if isinstance(previous, dict):
        merged.update(previous)
    if isinstance(current, dict):
        merged.update(current)
    merged["enabled"] = bool(enabled)

    if clean_new:
        custom_section[clean_new] = merged
    if clean_old and clean_old != clean_new:
        custom_section.pop(clean_old, None)
    return raw


def _remove_custom_skill_config(raw: dict[str, Any], skill_id: str) -> dict[str, Any]:
    raw.setdefault("skills", {})
    if not isinstance(raw["skills"], dict):
        raw["skills"] = {}
    raw["skills"].setdefault("custom", {})
    if not isinstance(raw["skills"]["custom"], dict):
        raw["skills"]["custom"] = {}
    clean_id = _sanitize_skill_id(skill_id)
    if clean_id:
        raw["skills"]["custom"].pop(clean_id, None)
    return raw


def _extract_steps_from_form(form: Any) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    indices: list[int] = []
    seen_idx: set[int] = set()
    for key in form.keys():
        match = re.match(r"^step_(\d+)_", str(key))
        if not match:
            continue
        idx = int(match.group(1))
        if idx not in seen_idx:
            seen_idx.add(idx)
            indices.append(idx)
    indices.sort()

    for idx in indices:
        enabled = str(form.get(f"step_{idx}_enabled", "")).strip().lower() in {"1", "true", "on", "yes"}
        if not enabled:
            continue
        step_type = str(form.get(f"step_{idx}_type", "")).strip().lower()
        if step_type not in {
            "ssh_run",
            "llm_transform",
            "discord_send",
            "chat_send",
            "sftp_read",
            "sftp_write",
            "smb_read",
            "smb_write",
            "rss_read",
        }:
            continue
        step_name = str(form.get(f"step_{idx}_name", "")).strip()
        step_id = _sanitize_skill_id(str(form.get(f"step_{idx}_id", "")).strip()) or f"s{idx}"
        on_error = str(form.get(f"step_{idx}_on_error", "stop")).strip().lower() or "stop"
        if on_error not in {"stop", "continue"}:
            on_error = "stop"
        params: dict[str, str] = {}
        if step_type == "ssh_run":
            params["connection_ref"] = str(form.get(f"step_{idx}_connection_ref", "")).strip()
            params["command"] = str(form.get(f"step_{idx}_command", "")).strip()
        elif step_type in {"sftp_read", "sftp_write"}:
            params["connection_ref"] = str(form.get(f"step_{idx}_sftp_connection_ref", "")).strip()
            params["remote_path"] = str(form.get(f"step_{idx}_sftp_remote_path", "")).strip()
            if step_type == "sftp_write":
                params["content"] = str(form.get(f"step_{idx}_sftp_content", "")).strip()
        elif step_type in {"smb_read", "smb_write"}:
            params["connection_ref"] = str(form.get(f"step_{idx}_smb_connection_ref", "")).strip()
            params["remote_path"] = str(form.get(f"step_{idx}_smb_remote_path", "")).strip()
            if step_type == "smb_write":
                params["content"] = str(form.get(f"step_{idx}_smb_content", "")).strip()
        elif step_type == "rss_read":
            params["connection_ref"] = str(form.get(f"step_{idx}_rss_connection_ref", "")).strip()
        elif step_type == "llm_transform":
            params["prompt"] = str(form.get(f"step_{idx}_prompt", "")).strip()
        elif step_type == "discord_send":
            params["connection_ref"] = str(form.get(f"step_{idx}_discord_connection_ref", "")).strip()
            params["webhook_url"] = str(form.get(f"step_{idx}_webhook_url", "")).strip()
            params["message"] = str(form.get(f"step_{idx}_message", "")).strip()
        elif step_type == "chat_send":
            params["chat_message"] = str(form.get(f"step_{idx}_chat_message", "")).strip()
        steps.append(
            {
                "id": step_id,
                "name": step_name,
                "type": step_type,
                "params": params,
                "on_error": on_error,
            }
        )
    return steps


def register_skills_routes(
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
    localize_custom_skill_description: LocalizeSkillDescription,
    format_skill_routing_info: FormatInfoMessage,
    suggest_skill_keywords_with_llm: SuggestKeywords,
    daily_time_to_cron: DailyTimeToCron,
    daily_time_from_cron: DailyTimeFromCron,
) -> None:
    @app.get("/skills", response_class=HTMLResponse)
    async def skills_page(request: Request, saved: int = 0, error: str = "", info: str = "") -> HTMLResponse:
        settings = get_settings()
        username = get_username_from_request(request)
        lang = str(getattr(request.state, "lang", "de") or "de")
        custom_cfg = _normalize_custom_cfg(read_raw_config())
        custom_manifests, custom_errors = _load_custom_skill_manifests()
        advanced_mode = bool(getattr(request.state, "can_access_advanced_config", False))
        return templates.TemplateResponse(
            request=request,
            name="skills.html",
            context={
                "title": settings.ui.title,
                "username": username,
                "saved": bool(saved),
                "error_message": error,
                "info_message": format_skill_routing_info(lang, info),
                "skill_rows": _build_skill_rows(lang, settings, translate),
                "custom_rows": _build_custom_rows(
                    custom_manifests,
                    custom_cfg,
                    lang,
                    localize_custom_skill_description,
                    daily_time_from_cron,
                ),
                "sample_skill_rows": _build_sample_skill_rows(),
                "custom_errors": custom_errors,
                "skills_readonly": not advanced_mode,
            },
        )

    @app.post("/skills/save")
    async def skills_save(
        request: Request,
        memory_enabled: str = Form("0"),
        auto_memory_enabled: str = Form("0"),
    ) -> RedirectResponse:
        if not _is_admin_mode_request(request, get_auth_session_from_request, sanitize_role):
            return RedirectResponse(url="/skills?error=readonly", status_code=303)
        try:
            form = await request.form()
            raw = read_raw_config()
            raw.setdefault("memory", {})
            if not isinstance(raw["memory"], dict):
                raw["memory"] = {}
            raw["memory"]["enabled"] = str(memory_enabled).strip().lower() in {"1", "true", "on", "yes"}

            raw.setdefault("auto_memory", {})
            if not isinstance(raw["auto_memory"], dict):
                raw["auto_memory"] = {}
            raw["auto_memory"]["enabled"] = str(auto_memory_enabled).strip().lower() in {"1", "true", "on", "yes"}

            raw.setdefault("skills", {})
            if not isinstance(raw["skills"], dict):
                raw["skills"] = {}
            raw["skills"].setdefault("custom", {})
            if not isinstance(raw["skills"]["custom"], dict):
                raw["skills"]["custom"] = {}

            custom_manifest_rows, _ = _load_custom_skill_manifests()
            known_ids = {row["id"] for row in custom_manifest_rows}
            for skill_id in known_ids:
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
            return RedirectResponse(url="/skills?saved=1", status_code=303)
        except (OSError, ValueError) as exc:
            return RedirectResponse(url=f"/skills?error={quote_plus(str(exc))}", status_code=303)

    @app.get("/skills/wizard", response_class=HTMLResponse)
    async def skills_wizard_page(
        request: Request,
        skill_id: str = "",
        saved: int = 0,
        error: str = "",
        info: str = "",
    ) -> HTMLResponse:
        if not _is_admin_mode_request(request, get_auth_session_from_request, sanitize_role):
            return RedirectResponse(url="/skills?error=readonly", status_code=303)
        settings = get_settings()
        username = get_username_from_request(request)
        lang = str(getattr(request.state, "lang", "de") or "de")
        loaded: dict[str, Any] | None = None
        clean_id = _sanitize_skill_id(skill_id)
        if clean_id:
            path = _custom_skill_file(clean_id)
            if path.exists():
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    if isinstance(payload, dict):
                        loaded = _validate_custom_skill_manifest(payload)
                except Exception as exc:  # noqa: BLE001
                    error = error or str(exc)

        all_manifests, _ = _load_custom_skill_manifests()
        category_options = _collect_skill_categories(all_manifests)
        selected_category = str((loaded or {}).get("category", "")).strip().lower()
        if selected_category and selected_category not in category_options:
            category_options.append(selected_category)

        effective_id = _sanitize_skill_id((loaded or {}).get("id", "")) or _sanitize_skill_id((loaded or {}).get("name", ""))
        prompt_preview = f"prompts/skills/{effective_id or '<skill-id>'}.md"
        prompt_file_value = str((loaded or {}).get("prompt_file", "")).strip() or (
            f"prompts/skills/{effective_id}.md" if effective_id else ""
        )
        schema_version_value = str((loaded or {}).get("schema_version", "1.1")).strip() or "1.1"
        connections_value = (loaded or {}).get("connections", [])
        connections_text = ", ".join(connections_value) if isinstance(connections_value, list) else ""
        loaded_schedule = _normalize_skill_schedule_manifest((loaded or {}).get("schedule", {}))
        loaded_schedule["time_24h"] = daily_time_from_cron(str(loaded_schedule.get("cron", "")))

        return templates.TemplateResponse(
            request=request,
            name="skills_wizard.html",
            context={
                "title": settings.ui.title,
                "username": username,
                "saved": bool(saved),
                "error_message": error,
                "info_message": format_skill_routing_info(lang, info),
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
            },
        )

    @app.post("/skills/wizard/save")
    async def skills_wizard_save(
        request: Request,
        original_skill_id: str = Form(""),
        skill_id: str = Form(""),
        skill_name: str = Form(...),
        skill_version: str = Form("0.1.0"),
        skill_description: str = Form(""),
        skill_category: str = Form("custom"),
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
    ) -> RedirectResponse:
        if not _is_admin_mode_request(request, get_auth_session_from_request, sanitize_role):
            return RedirectResponse(url="/skills?error=readonly", status_code=303)
        try:
            form = await request.form()
            keywords = [item.strip() for item in str(skill_router_keywords).split(",") if item.strip()]
            connections = [item.strip().lower() for item in str(skill_connections).split(",") if item.strip()]
            original_clean_id = _sanitize_skill_id(original_skill_id)
            resolved_id = _sanitize_skill_id(skill_id) or _sanitize_skill_id(skill_name)
            if not resolved_id:
                raise ValueError("Skill-ID konnte nicht automatisch erzeugt werden. Bitte Namen anpassen.")
            prompt_file = str(skill_prompt_file).strip() or f"prompts/skills/{resolved_id}.md"
            auto_generate = str(auto_generate_keywords).strip().lower() in {"1", "true", "on", "yes"}
            steps = _extract_steps_from_form(form)
            if not steps:
                raise ValueError("Bitte mindestens einen aktiven Step konfigurieren.")
            schedule_enabled_bool = str(schedule_enabled).strip().lower() in {"1", "true", "on", "yes"}
            schedule_cron = daily_time_to_cron(schedule_time) if schedule_enabled_bool else ""
            schedule = _normalize_skill_schedule_manifest(
                {
                    "enabled": schedule_enabled_bool,
                    "cron": schedule_cron,
                    "timezone": schedule_timezone,
                    "run_on_startup": str(schedule_run_on_startup).strip().lower() in {"1", "true", "on", "yes"},
                }
            )

            language = str(getattr(request.state, "lang", "de") or "de")
            if auto_generate and not keywords:
                draft_manifest = {
                    "id": resolved_id,
                    "name": skill_name,
                    "version": skill_version,
                    "description": skill_description,
                    "category": skill_category,
                    "prompt_file": prompt_file,
                    "router_keywords": [],
                    "connections": connections,
                    "steps": steps,
                    "schedule": schedule,
                    "schema_version": str(skill_schema_version).strip() or "1.1",
                    "enabled_default": str(enabled_default).strip().lower() in {"1", "true", "on", "yes"},
                    "ui": {
                        "config_path": skill_ui_config_path,
                        "hint": skill_ui_hint,
                    },
                }
                keywords = await suggest_skill_keywords_with_llm(draft_manifest, language=language)

            clean = _save_custom_skill_manifest(
                {
                    "id": resolved_id,
                    "name": skill_name,
                    "version": skill_version,
                    "description": skill_description,
                    "category": skill_category,
                    "prompt_file": prompt_file,
                    "router_keywords": keywords,
                    "connections": connections,
                    "steps": steps,
                    "schedule": schedule,
                    "schema_version": str(skill_schema_version).strip() or "1.1",
                    "enabled_default": str(enabled_default).strip().lower() in {"1", "true", "on", "yes"},
                    "ui": {
                        "config_path": skill_ui_config_path,
                        "hint": skill_ui_hint,
                    },
                },
                previous_id=original_clean_id,
            )
            raw = read_raw_config()
            raw = _migrate_custom_skill_config(
                raw,
                old_id=original_clean_id,
                new_id=clean["id"],
                enabled=bool(clean.get("enabled_default", True)),
            )
            write_raw_config(raw)
            reload_runtime()
            info_suffix = ""
            if auto_generate and keywords:
                info_suffix = f"&info={quote_plus(f'keywords:auto:{len(keywords)}')}"
            return RedirectResponse(
                url=f"/skills/wizard?skill_id={quote_plus(clean['id'])}&saved=1{info_suffix}",
                status_code=303,
            )
        except (OSError, ValueError) as exc:
            return RedirectResponse(url=f"/skills/wizard?error={quote_plus(str(exc))}", status_code=303)

    @app.post("/skills/import")
    async def skills_import(
        request: Request,
        csrf_token: str = Form(""),
        skill_file: UploadFile = File(...),
    ) -> RedirectResponse:
        if not _is_admin_mode_request(request, get_auth_session_from_request, sanitize_role):
            return RedirectResponse(url="/skills?error=readonly", status_code=303)
        expected_csrf = str(getattr(getattr(request, "state", object()), "csrf_token", "") or "")
        if not _is_valid_csrf_submission(csrf_token, expected_csrf):
            return RedirectResponse(url="/skills?error=csrf_failed", status_code=303)
        try:
            payload = await skill_file.read()
            raw = json.loads(payload.decode("utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("Import erwartet ein JSON-Objekt.")
            clean = _save_custom_skill_manifest(raw)
            return RedirectResponse(url=f"/skills?saved=1&info=imported:{quote_plus(clean['id'])}", status_code=303)
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError, OSError) as exc:
            return RedirectResponse(url=f"/skills?error={quote_plus(str(exc))}", status_code=303)

    @app.post("/skills/import-sample")
    async def skills_import_sample(
        request: Request,
        sample_file: str = Form(""),
        csrf_token: str = Form(""),
    ) -> RedirectResponse:
        if not _is_admin_mode_request(request, get_auth_session_from_request, sanitize_role):
            return RedirectResponse(url="/skills?error=readonly", status_code=303)
        expected_csrf = str(getattr(getattr(request, "state", object()), "csrf_token", "") or "")
        if not _is_valid_csrf_submission(csrf_token, expected_csrf):
            return RedirectResponse(url="/skills?error=csrf_failed", status_code=303)
        try:
            clean_name = Path(str(sample_file or "").strip()).name
            if not clean_name or not clean_name.endswith(".json"):
                raise ValueError("Unbekanntes Sample-Skill-Manifest.")
            sample_path = SAMPLE_SKILLS_DIR / clean_name
            if not sample_path.exists() or not sample_path.is_file():
                raise ValueError("Sample-Skill nicht gefunden.")
            raw = json.loads(sample_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("Import erwartet ein JSON-Objekt.")
            clean = _save_custom_skill_manifest(raw)
            return RedirectResponse(url=f"/skills?saved=1&info=imported:{quote_plus(clean['id'])}", status_code=303)
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError, OSError) as exc:
            return RedirectResponse(url=f"/skills?error={quote_plus(str(exc))}", status_code=303)

    @app.post("/skills/delete")
    async def skills_delete(
        request: Request,
        skill_id: str = Form(""),
        csrf_token: str = Form(""),
    ) -> RedirectResponse:
        if not _is_admin_mode_request(request, get_auth_session_from_request, sanitize_role):
            return RedirectResponse(url="/skills?error=readonly", status_code=303)
        expected_csrf = str(getattr(getattr(request, "state", object()), "csrf_token", "") or "")
        if not _is_valid_csrf_submission(csrf_token, expected_csrf):
            return RedirectResponse(url="/skills?error=csrf_failed", status_code=303)
        try:
            result = _delete_custom_skill_manifest(skill_id)
            raw = read_raw_config()
            raw = _remove_custom_skill_config(raw, skill_id)
            write_raw_config(raw)
            reload_runtime()
            info_value = quote_plus(f"deleted:{result['id']}")
            return RedirectResponse(
                url=f"/skills?saved=1&info={info_value}",
                status_code=303,
            )
        except (OSError, ValueError) as exc:
            return RedirectResponse(url=f"/skills?error={quote_plus(str(exc))}", status_code=303)

    @app.get("/skills/export/{skill_id}")
    async def skills_export(request: Request, skill_id: str) -> Response:
        if not _is_admin_mode_request(request, get_auth_session_from_request, sanitize_role):
            return JSONResponse({"error": "readonly"}, status_code=403)
        clean_id = _sanitize_skill_id(skill_id)
        path = _custom_skill_file(clean_id)
        if not path.exists():
            return JSONResponse({"error": "not_found"}, status_code=404)
        content = path.read_text(encoding="utf-8")
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{clean_id}.json"'},
        )
