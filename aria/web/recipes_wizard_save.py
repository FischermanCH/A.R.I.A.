from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from aria.core.recipe_manifests import (
    _normalize_recipe_schedule_manifest,
    _sanitize_recipe_id,
    _save_stored_recipe_manifest,
)
from aria.web.recipes_wizard_catalog import _RECIPE_TYPE_PRESETS, _recipes_routes_text, _sanitize_recipe_type

DailyTimeToCron = Callable[[str], str]
SuggestKeywords = Callable[..., Awaitable[list[str]]]

_TRUE_VALUES = {"1", "true", "on", "yes"}
_STEP_TYPES = {
    "ssh_run",
    "llm_transform",
    "discord_send",
    "chat_send",
    "sftp_read",
    "sftp_write",
    "smb_read",
    "smb_write",
    "rss_read",
}


@dataclass(frozen=True)
class WizardSaveInput:
    original_skill_id: str = ""
    skill_id: str = ""
    skill_name: str = ""
    skill_version: str = "0.1.0"
    skill_description: str = ""
    skill_category: str = "custom"
    skill_type: str = "health_check"
    skill_router_keywords: str = ""
    skill_connections: str = ""
    skill_prompt_file: str = ""
    skill_schema_version: str = "1.1"
    auto_generate_keywords: str = "1"
    schedule_enabled: str = "0"
    schedule_time: str = ""
    schedule_timezone: str = "Europe/Zurich"
    schedule_run_on_startup: str = "0"
    skill_ui_config_path: str = ""
    skill_ui_hint: str = ""
    enabled_default: str = "0"
    wizard_mode: str = "simple"


@dataclass(frozen=True)
class WizardSaveResult:
    recipe_id: str
    original_recipe_id: str
    wizard_mode: str
    enabled_default: bool
    generated_keyword_count: int


def truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in _TRUE_VALUES


def sanitize_wizard_mode(value: str | None) -> str:
    mode = str(value or "").strip().lower()
    return "advanced" if mode == "advanced" else "simple"


def extract_steps_from_form(form: Any) -> list[dict[str, Any]]:
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
        if not truthy(str(form.get(f"step_{idx}_enabled", ""))):
            continue
        step_type = str(form.get(f"step_{idx}_type", "")).strip().lower()
        if step_type not in _STEP_TYPES:
            continue
        step_name = str(form.get(f"step_{idx}_name", "")).strip()
        step_id = _sanitize_recipe_id(str(form.get(f"step_{idx}_id", "")).strip()) or f"s{idx}"
        on_error = str(form.get(f"step_{idx}_on_error", "stop")).strip().lower() or "stop"
        if on_error not in {"stop", "continue"}:
            on_error = "stop"
        params = _step_params_from_form(form, idx=idx, step_type=step_type)
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


def _step_params_from_form(form: Any, *, idx: int, step_type: str) -> dict[str, str]:
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
    return params


def apply_recipe_type_defaults(
    *,
    recipe_type: str,
    wizard_mode: str,
    recipe_category: str,
    recipe_description: str,
    steps: list[dict[str, Any]],
) -> tuple[str, str, list[dict[str, Any]]]:
    clean_type = _sanitize_recipe_type(recipe_type)
    clean_mode = sanitize_wizard_mode(wizard_mode)
    if clean_mode != "simple" or clean_type == "custom":
        return recipe_category, recipe_description, steps

    preset = _RECIPE_TYPE_PRESETS.get(clean_type, _RECIPE_TYPE_PRESETS["custom"])
    effective_category = str(recipe_category or "").strip() or "custom"
    if effective_category == "custom":
        effective_category = str(preset.get("category", "custom")).strip() or "custom"
    effective_description = str(recipe_description or "").strip() or str(preset.get("description", "")).strip()

    if not steps:
        steps = [
            {
                "id": "s1",
                "name": str(preset.get("default_step_name", "")).strip(),
                "type": str(preset.get("default_step_type", "ssh_run")).strip() or "ssh_run",
                "params": dict(preset.get("default_params", {}) or {}),
                "on_error": "stop",
            }
        ]
        return effective_category, effective_description, steps

    first = dict(steps[0] or {})
    first["type"] = str(preset.get("default_step_type", first.get("type", "ssh_run"))).strip() or "ssh_run"
    if not str(first.get("name", "")).strip():
        first["name"] = str(preset.get("default_step_name", "")).strip()
    params = first.get("params", {})
    if not isinstance(params, dict):
        params = {}
    for key, value in dict(preset.get("default_params", {}) or {}).items():
        if not str(params.get(key, "")).strip():
            params[key] = str(value).strip()
    first["params"] = params
    return effective_category, effective_description, [first, *steps[1:]]


def migrate_custom_recipe_config(raw: dict[str, Any], old_id: str, new_id: str, enabled: bool) -> dict[str, Any]:
    raw.setdefault("skills", {})
    if not isinstance(raw["skills"], dict):
        raw["skills"] = {}
    raw["skills"].setdefault("custom", {})
    if not isinstance(raw["skills"]["custom"], dict):
        raw["skills"]["custom"] = {}

    custom_section = raw["skills"]["custom"]
    clean_old = _sanitize_recipe_id(old_id)
    clean_new = _sanitize_recipe_id(new_id)

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


def remove_custom_recipe_config(raw: dict[str, Any], recipe_id: str) -> dict[str, Any]:
    raw.setdefault("skills", {})
    if not isinstance(raw["skills"], dict):
        raw["skills"] = {}
    raw["skills"].setdefault("custom", {})
    if not isinstance(raw["skills"]["custom"], dict):
        raw["skills"]["custom"] = {}
    clean_id = _sanitize_recipe_id(recipe_id)
    if clean_id:
        raw["skills"]["custom"].pop(clean_id, None)
    return raw


async def save_recipe_from_wizard_form(
    *,
    form: Any,
    values: WizardSaveInput,
    lang: str,
    daily_time_to_cron: DailyTimeToCron,
    suggest_keywords: SuggestKeywords,
) -> WizardSaveResult:
    keywords = [item.strip() for item in str(values.skill_router_keywords).split(",") if item.strip()]
    connections = [item.strip().lower() for item in str(values.skill_connections).split(",") if item.strip()]
    original_clean_id = _sanitize_recipe_id(values.original_skill_id)
    resolved_id = _sanitize_recipe_id(values.skill_id) or _sanitize_recipe_id(values.skill_name)
    if not resolved_id:
        raise ValueError(
            _recipes_routes_text(
                lang,
                "error.recipe_id_missing",
                "Recipe ID could not be generated automatically. Please adjust the name.",
            )
        )

    prompt_file = str(values.skill_prompt_file).strip() or f"prompts/recipes/{resolved_id}.md"
    auto_generate = truthy(values.auto_generate_keywords)
    clean_mode = sanitize_wizard_mode(values.wizard_mode)
    steps = extract_steps_from_form(form)
    recipe_category, recipe_description, steps = apply_recipe_type_defaults(
        recipe_type=values.skill_type,
        wizard_mode=clean_mode,
        recipe_category=values.skill_category,
        recipe_description=values.skill_description,
        steps=steps,
    )
    if not steps:
        raise ValueError(_recipes_routes_text(lang, "error.step_required", "Please configure at least one active step."))

    schedule_enabled = truthy(values.schedule_enabled)
    schedule = _normalize_recipe_schedule_manifest(
        {
            "enabled": schedule_enabled,
            "cron": daily_time_to_cron(values.schedule_time) if schedule_enabled else "",
            "timezone": values.schedule_timezone,
            "run_on_startup": truthy(values.schedule_run_on_startup),
        }
    )
    enabled_default = truthy(values.enabled_default)
    manifest = {
        "id": resolved_id,
        "name": values.skill_name,
        "version": values.skill_version,
        "description": recipe_description,
        "category": recipe_category,
        "prompt_file": prompt_file,
        "router_keywords": keywords,
        "connections": connections,
        "steps": steps,
        "schedule": schedule,
        "schema_version": str(values.skill_schema_version).strip() or "1.1",
        "enabled_default": enabled_default,
        "ui": {
            "config_path": values.skill_ui_config_path,
            "hint": values.skill_ui_hint,
        },
    }

    if auto_generate and not keywords:
        keywords = await suggest_keywords(manifest, language=lang)
        manifest["router_keywords"] = keywords

    clean = _save_stored_recipe_manifest(manifest, previous_id=original_clean_id)
    return WizardSaveResult(
        recipe_id=str(clean["id"]),
        original_recipe_id=original_clean_id,
        wizard_mode=clean_mode,
        enabled_default=bool(clean.get("enabled_default", True)),
        generated_keyword_count=len(keywords) if auto_generate and keywords else 0,
    )


def apply_skill_type_defaults(
    *,
    skill_type: str,
    wizard_mode: str,
    skill_category: str,
    skill_description: str,
    steps: list[dict[str, Any]],
) -> tuple[str, str, list[dict[str, Any]]]:
    return apply_recipe_type_defaults(
        recipe_type=skill_type,
        wizard_mode=wizard_mode,
        recipe_category=skill_category,
        recipe_description=skill_description,
        steps=steps,
    )
