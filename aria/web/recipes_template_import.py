from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from aria.core.recipe_manifests import _sanitize_recipe_id, _save_stored_recipe_manifest
from aria.web.recipes_wizard_catalog import _recipes_routes_text

BASE_DIR = Path(__file__).resolve().parents[2]
SAMPLE_RECIPES_DIR = BASE_DIR / "samples" / "recipes"
LEGACY_SAMPLE_RECIPES_DIR = BASE_DIR / "samples" / "skills"


def sample_recipe_dir() -> Path:
    return SAMPLE_RECIPES_DIR if SAMPLE_RECIPES_DIR.exists() else LEGACY_SAMPLE_RECIPES_DIR


_SIDE_EFFECT_STEP_TYPES = {"discord_send", "webhook_send", "email_send", "mqtt_publish", "sftp_write", "smb_write"}


def _clean_string_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    rows: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = str(value or "").strip()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        rows.append(clean)
    return rows


def _sample_step_types(raw: dict[str, Any]) -> list[str]:
    rows: list[str] = []
    seen: set[str] = set()
    for step in list(raw.get("steps", []) or []):
        if not isinstance(step, dict):
            continue
        step_type = str(step.get("type", "") or "").strip()
        if not step_type or step_type in seen:
            continue
        seen.add(step_type)
        rows.append(step_type)
    return rows


def build_sample_recipe_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    sample_dir = sample_recipe_dir()
    if not sample_dir.exists():
        return rows
    for path in sorted(sample_dir.glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(raw, dict):
            continue
        recipe_id = _sanitize_recipe_id(str(raw.get("id", "")).strip())
        if not recipe_id:
            continue
        steps = list(raw.get("steps", []) or [])
        step_types = _sample_step_types(raw)
        connections = _clean_string_list(raw.get("connections", []))
        router_keywords = _clean_string_list(raw.get("router_keywords", []))
        schedule = raw.get("schedule", {})
        schedule_enabled = bool(isinstance(schedule, dict) and schedule.get("enabled"))
        schedule_cron = str(schedule.get("cron", "") or "").strip() if isinstance(schedule, dict) else ""
        rows.append(
            {
                "file_name": path.name,
                "id": recipe_id,
                "name": str(raw.get("name", "")).strip() or recipe_id,
                "description": str(raw.get("description", "")).strip(),
                "category": str(raw.get("category", "custom")).strip() or "custom",
                "step_count": len([step for step in steps if isinstance(step, dict)]),
                "step_types": step_types,
                "step_types_label": ", ".join(step_types),
                "connections": connections,
                "connections_label": ", ".join(connections),
                "trigger_count": len(router_keywords),
                "schedule_enabled": schedule_enabled,
                "schedule_cron": schedule_cron,
                "has_side_effect": any(step_type in _SIDE_EFFECT_STEP_TYPES for step_type in step_types),
            }
        )
    return sorted(rows, key=lambda row: (str(row.get("category", "")).lower(), str(row.get("name", "")).lower()))


def import_sample_recipe_success_url(*, sample_file: str, surface_path: str, lang: str) -> str:
    clean_name = Path(str(sample_file or "").strip()).name
    if not clean_name or not clean_name.endswith(".json"):
        raise ValueError(_recipes_routes_text(lang, "error.unknown_sample", "Unknown recipe template."))
    sample_path = sample_recipe_dir() / clean_name
    if not sample_path.exists() or not sample_path.is_file():
        raise ValueError(_recipes_routes_text(lang, "error.sample_not_found", "Recipe template not found."))
    raw = json.loads(sample_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(_recipes_routes_text(lang, "error.import_requires_object", "Import expects a JSON object."))
    clean = _save_stored_recipe_manifest(raw)
    target = str(surface_path or "").strip() or "/recipes"
    return f"{target}?saved=1&info=imported:{quote_plus(clean['id'])}"
