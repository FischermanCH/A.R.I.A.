from __future__ import annotations

import copy
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aria.core.i18n import I18NStore

_RECIPE_MANIFESTS_I18N = I18NStore(Path(__file__).resolve().parents[1] / "i18n")


def _recipe_manifest_text(key: str, default: str = "", **values: object) -> str:
    template = _RECIPE_MANIFESTS_I18N.t("de", f"recipe_manifests.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template


BASE_DIR = Path(__file__).resolve().parents[2]
RECIPES_STORE_DIR = BASE_DIR / "data" / "recipes"
RECIPE_TRIGGER_INDEX_FILE = RECIPES_STORE_DIR / "_trigger_index.json"
LEGACY_SKILLS_STORE_DIR = BASE_DIR / "data" / "skills"
LEGACY_SKILL_TRIGGER_INDEX_FILE = LEGACY_SKILLS_STORE_DIR / "_trigger_index.json"
SKILLS_STORE_DIR = RECIPES_STORE_DIR
SKILL_TRIGGER_INDEX_FILE = RECIPE_TRIGGER_INDEX_FILE
RECIPE_CATEGORY_DEFAULTS = [
    "automation",
    "infrastructure",
    "communication",
    "monitoring",
    "knowledge",
    "utility",
]
SKILL_CATEGORY_DEFAULTS = RECIPE_CATEGORY_DEFAULTS

_STORED_RECIPE_MANIFEST_CACHE: dict[str, Any] = {
    "sign": None,
    "rows": [],
    "errors": [],
}


def _sanitize_recipe_id(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    raw = re.sub(r"[^a-z0-9_-]", "-", raw)
    raw = re.sub(r"-+", "-", raw).strip("-")
    return raw[:48]


def _recipe_manifest_file(recipe_id: str) -> Path:
    clean_id = _sanitize_recipe_id(recipe_id)
    return SKILLS_STORE_DIR / f"{clean_id}.json"


def _default_recipe_prompt_file(recipe_id: str) -> str:
    clean_id = _sanitize_recipe_id(recipe_id)
    return f"prompts/recipes/{clean_id}.md" if clean_id else ""


def _legacy_recipe_manifest_file(recipe_id: str) -> Path:
    clean_id = _sanitize_recipe_id(recipe_id)
    return LEGACY_SKILLS_STORE_DIR / f"{clean_id}.json"


def _legacy_default_recipe_prompt_file(recipe_id: str) -> str:
    clean_id = _sanitize_recipe_id(recipe_id)
    return f"prompts/skills/{clean_id}.md" if clean_id else ""


def _normalize_recipe_steps_manifest(raw_steps: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_steps, list):
        return []
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(raw_steps):
        if not isinstance(item, dict):
            continue
        step_type = str(item.get("type", "")).strip().lower()
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
        step_id = str(item.get("id", "")).strip().lower() or f"s{index + 1}"
        step_name = str(item.get("name", "")).strip()[:80]
        params = item.get("params", {})
        if not isinstance(params, dict):
            params = {}
        clean_params: dict[str, str] = {}
        for key, val in params.items():
            clean_key = str(key).strip().lower()
            if not clean_key:
                continue
            clean_params[clean_key] = str(val).strip()[:1200]
        condition = item.get("condition", {})
        clean_condition: dict[str, Any] | None = None
        if isinstance(condition, dict):
            source = str(condition.get("source", "")).strip().lower()
            operator = str(condition.get("operator", "")).strip().lower()
            value = str(condition.get("value", "")).strip()[:1200]
            ignore_case = bool(condition.get("ignore_case", False))
            if operator in {"equals", "not_equals", "contains", "not_contains", "regex", "is_empty", "not_empty"}:
                clean_condition = {
                    "source": re.sub(r"[^a-z0-9_-]", "", source)[:40],
                    "operator": operator,
                    "value": value,
                    "ignore_case": ignore_case,
                }
        on_error = str(item.get("on_error", "stop")).strip().lower() or "stop"
        if on_error not in {"stop", "continue"}:
            on_error = "stop"
        row = {
            "id": re.sub(r"[^a-z0-9_-]", "", step_id)[:20] or f"s{index + 1}",
            "name": step_name,
            "type": step_type,
            "params": clean_params,
            "on_error": on_error,
        }
        if clean_condition:
            row["condition"] = clean_condition
        rows.append(row)
    return rows


def _normalize_recipe_schedule_manifest(raw_schedule: Any) -> dict[str, Any]:
    if not isinstance(raw_schedule, dict):
        raw_schedule = {}
    enabled = bool(raw_schedule.get("enabled", False))
    cron = str(raw_schedule.get("cron", "")).strip()[:80]
    timezone = str(raw_schedule.get("timezone", "")).strip()[:80] or "Europe/Zurich"
    run_on_startup = bool(raw_schedule.get("run_on_startup", False))
    if enabled and not cron:
        raise ValueError(_recipe_manifest_text("schedule_cron_missing", "Schedule is enabled, but cron is missing."))
    return {
        "enabled": enabled,
        "cron": cron,
        "timezone": timezone,
        "run_on_startup": run_on_startup,
    }


def _validate_stored_recipe_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    clean_id = _sanitize_recipe_id(manifest.get("id"))
    clean_name = str(manifest.get("name", "")).strip()
    if not clean_id:
        raise ValueError(_recipe_manifest_text("recipe_id_invalid", "Recipe ID is missing or invalid."))
    if not clean_name:
        raise ValueError(_recipe_manifest_text("recipe_name_missing", "Recipe name is missing."))
    version = str(manifest.get("version", "0.1.0")).strip() or "0.1.0"
    description = str(manifest.get("description", "")).strip()
    category = str(manifest.get("category", "custom")).strip() or "custom"
    prompt_file = str(manifest.get("prompt_file", "")).strip()
    router_keywords = manifest.get("router_keywords", [])
    if not isinstance(router_keywords, list):
        router_keywords = []
    clean_keywords = []
    for item in router_keywords:
        text = str(item).strip()
        if text:
            clean_keywords.append(text[:80])
    ui = manifest.get("ui", {})
    if not isinstance(ui, dict):
        ui = {}
    ui_config_path = str(ui.get("config_path", "")).strip()
    ui_hint = str(ui.get("hint", "")).strip()
    schedule = _normalize_recipe_schedule_manifest(manifest.get("schedule", {}))
    steps = _normalize_recipe_steps_manifest(manifest.get("steps", []))
    if not steps:
        raise ValueError(_recipe_manifest_text("step_required", "At least one step is required."))
    raw_connections = manifest.get("connections", [])
    explicit_connections: list[str] = []
    if isinstance(raw_connections, list):
        explicit_connections = [str(item).strip().lower() for item in raw_connections if str(item).strip()]
    elif isinstance(raw_connections, str):
        explicit_connections = [item.strip().lower() for item in raw_connections.split(",") if item.strip()]
    derived_connections: list[str] = []
    seen_connections: set[str] = set()
    for step in steps:
        step_type = str(step.get("type", "")).strip().lower()
        conn_name = ""
        if step_type == "ssh_run":
            conn_name = "ssh"
        elif step_type in {"sftp_read", "sftp_write"}:
            conn_name = "sftp"
        elif step_type in {"smb_read", "smb_write"}:
            conn_name = "smb"
        elif step_type == "rss_read":
            conn_name = "rss"
        elif step_type == "discord_send":
            conn_name = "discord"
        elif step_type == "llm_transform":
            conn_name = "llm"
        elif step_type == "chat_send":
            conn_name = "chat"
        if conn_name and conn_name not in seen_connections:
            seen_connections.add(conn_name)
            derived_connections.append(conn_name)
    merged_connections: list[str] = []
    for name in explicit_connections + derived_connections:
        connection_name = str(name).strip().lower()
        if not connection_name or connection_name in merged_connections:
            continue
        merged_connections.append(connection_name)
    enabled_default = bool(manifest.get("enabled_default", True))
    schema_version = str(manifest.get("schema_version", "1.1")).strip() or "1.1"
    return {
        "id": clean_id,
        "name": clean_name[:80],
        "version": version[:20],
        "description": description[:400],
        "category": category[:40],
        "prompt_file": prompt_file[:200],
        "router_keywords": clean_keywords[:30],
        "connections": merged_connections[:20],
        "enabled_default": enabled_default,
        "steps": steps,
        "schedule": schedule,
        "ui": {
            "config_path": ui_config_path[:200],
            "hint": ui_hint[:200],
        },
        "schema_version": schema_version[:16],
    }


def _load_stored_recipe_manifests() -> tuple[list[dict[str, Any]], list[str]]:
    snapshot = _stored_recipe_manifest_snapshot()
    if snapshot == _STORED_RECIPE_MANIFEST_CACHE.get("sign"):
        return (
            copy.deepcopy(_STORED_RECIPE_MANIFEST_CACHE.get("rows", [])),
            copy.deepcopy(_STORED_RECIPE_MANIFEST_CACHE.get("errors", [])),
        )

    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for path in _iter_stored_recipe_manifest_paths():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("Dateiinhalt ist kein Objekt.")
            rows.append(_validate_stored_recipe_manifest(raw))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{path.name}: {exc}")
    _STORED_RECIPE_MANIFEST_CACHE["sign"] = snapshot
    _STORED_RECIPE_MANIFEST_CACHE["rows"] = copy.deepcopy(rows)
    _STORED_RECIPE_MANIFEST_CACHE["errors"] = copy.deepcopy(errors)
    return rows, errors


def _invalidate_stored_recipe_manifest_cache() -> None:
    _STORED_RECIPE_MANIFEST_CACHE["sign"] = None
    _STORED_RECIPE_MANIFEST_CACHE["rows"] = []
    _STORED_RECIPE_MANIFEST_CACHE["errors"] = []


def _iter_stored_recipe_manifest_paths() -> list[Path]:
    SKILLS_STORE_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[Path] = []
    seen_names: set[str] = set()
    for root in (SKILLS_STORE_DIR, LEGACY_SKILLS_STORE_DIR):
        if root == SKILLS_STORE_DIR:
            paths = sorted(root.glob("*.json"))
        elif root.exists():
            paths = sorted(root.glob("*.json"))
        else:
            paths = []
        for path in paths:
            if path.name.startswith("_") or path.name in seen_names:
                continue
            seen_names.add(path.name)
            rows.append(path)
    return rows


def _stored_recipe_manifest_snapshot() -> tuple[tuple[str, int, int], ...]:
    rows: list[tuple[str, int, int]] = []
    for path in _iter_stored_recipe_manifest_paths():
        try:
            stat = path.stat()
        except OSError:
            continue
        rows.append((path.name, int(stat.st_mtime_ns), int(stat.st_size)))
    return tuple(rows)


def _build_recipe_trigger_index(rows: list[dict[str, Any]]) -> dict[str, Any]:
    triggers_map: dict[str, list[str]] = {}
    by_recipe: dict[str, list[str]] = {}
    for row in rows:
        recipe_id = str(row.get("id", "")).strip()
        if not recipe_id:
            continue
        keywords = row.get("router_keywords", [])
        if not isinstance(keywords, list):
            keywords = []
        normalized: list[str] = []
        for item in keywords:
            trigger = str(item).strip().lower()
            if not trigger:
                continue
            if trigger not in normalized:
                normalized.append(trigger)
            triggers_map.setdefault(trigger, [])
            if recipe_id not in triggers_map[trigger]:
                triggers_map[trigger].append(recipe_id)
        by_recipe[recipe_id] = normalized

    trigger_rows = [{"trigger": key, "skills": sorted(value)} for key, value in sorted(triggers_map.items())]
    collisions = [row for row in trigger_rows if len(row["skills"]) > 1]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "skills_count": len(by_recipe),
        "recipes_count": len(by_recipe),
        "triggers_count": len(trigger_rows),
        "collisions_count": len(collisions),
        "triggers": trigger_rows,
        "by_skill": by_recipe,
        "by_recipe": by_recipe,
    }


def _refresh_recipe_trigger_index() -> dict[str, Any]:
    manifests, _ = _load_stored_recipe_manifests()
    index = _build_recipe_trigger_index(manifests)
    SKILLS_STORE_DIR.mkdir(parents=True, exist_ok=True)
    SKILL_TRIGGER_INDEX_FILE.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return index


def _save_stored_recipe_manifest(manifest: dict[str, Any], previous_id: str | None = None) -> dict[str, Any]:
    clean = _validate_stored_recipe_manifest(manifest)
    SKILLS_STORE_DIR.mkdir(parents=True, exist_ok=True)
    previous_clean_id = _sanitize_recipe_id(previous_id)
    target = _recipe_manifest_file(clean["id"])
    previous_target = _recipe_manifest_file(previous_clean_id) if previous_clean_id else None
    legacy_target = _legacy_recipe_manifest_file(clean["id"])
    previous_legacy_target = _legacy_recipe_manifest_file(previous_clean_id) if previous_clean_id else None

    canonical_prompt_file = _default_recipe_prompt_file(clean["id"])
    legacy_prompt_file = _legacy_default_recipe_prompt_file(clean["id"])
    if clean.get("prompt_file") == legacy_prompt_file:
        clean["prompt_file"] = canonical_prompt_file
        old_prompt_path = BASE_DIR / legacy_prompt_file
        new_prompt_path = BASE_DIR / canonical_prompt_file
        if old_prompt_path.exists() and old_prompt_path != new_prompt_path and not new_prompt_path.exists():
            new_prompt_path.parent.mkdir(parents=True, exist_ok=True)
            old_prompt_path.rename(new_prompt_path)

    if previous_clean_id and previous_clean_id != clean["id"]:
        if target.exists() and target != previous_target:
            raise ValueError(_recipe_manifest_text("recipe_id_exists", "Recipe ID already exists: {recipe_id}", recipe_id=clean["id"]))
        old_prompt_file = _default_recipe_prompt_file(previous_clean_id)
        legacy_old_prompt_file = _legacy_default_recipe_prompt_file(previous_clean_id)
        if clean.get("prompt_file") in {old_prompt_file, legacy_old_prompt_file}:
            clean["prompt_file"] = canonical_prompt_file
            new_prompt_path = BASE_DIR / canonical_prompt_file
            for old_prompt_path in (BASE_DIR / old_prompt_file, BASE_DIR / legacy_old_prompt_file):
                if old_prompt_path.exists() and old_prompt_path != new_prompt_path and not new_prompt_path.exists():
                    new_prompt_path.parent.mkdir(parents=True, exist_ok=True)
                    old_prompt_path.rename(new_prompt_path)
                    break

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(clean, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if previous_target and previous_target.exists() and previous_target != target:
        previous_target.unlink()
    if previous_legacy_target and previous_legacy_target.exists() and previous_legacy_target != target:
        previous_legacy_target.unlink()
    if legacy_target.exists() and legacy_target != target:
        legacy_target.unlink()
    _invalidate_stored_recipe_manifest_cache()
    _refresh_recipe_trigger_index()
    return clean


def _delete_stored_recipe_manifest(recipe_id: str) -> dict[str, Any]:
    clean_id = _sanitize_recipe_id(recipe_id)
    if not clean_id:
        raise ValueError(_recipe_manifest_text("recipe_id_invalid", "Recipe ID is missing or invalid."))

    target = _recipe_manifest_file(clean_id)
    legacy_target = _legacy_recipe_manifest_file(clean_id)
    if not target.exists() and not legacy_target.exists():
        raise ValueError(_recipe_manifest_text("recipe_not_found", "Recipe not found: {recipe_id}", recipe_id=clean_id))

    prompt_file = ""
    try:
        source = target if target.exists() else legacy_target
        raw = json.loads(source.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            prompt_file = str(raw.get("prompt_file", "")).strip()
    except Exception:
        prompt_file = ""

    if target.exists():
        target.unlink()
    if legacy_target.exists() and legacy_target != target:
        legacy_target.unlink()

    default_prompt_file = _default_recipe_prompt_file(clean_id)
    legacy_default_recipe_prompt_file = _legacy_default_recipe_prompt_file(clean_id)
    prompt_candidates: list[Path] = []
    if prompt_file in {default_prompt_file, legacy_default_recipe_prompt_file} or not prompt_file:
        prompt_candidates.append(BASE_DIR / default_prompt_file)
        prompt_candidates.append(BASE_DIR / legacy_default_recipe_prompt_file)
    elif (
        prompt_file.startswith("prompts/skills/") or prompt_file.startswith("prompts/recipes/")
    ) and Path(prompt_file).name == f"{clean_id}.md":
        prompt_candidates.append(BASE_DIR / prompt_file)

    removed_prompt = False
    for candidate in prompt_candidates:
        if candidate.exists():
            candidate.unlink()
            removed_prompt = True

    _invalidate_stored_recipe_manifest_cache()
    _refresh_recipe_trigger_index()
    return {"id": clean_id, "prompt_removed": removed_prompt}


def _collect_recipe_categories(rows: list[dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for item in RECIPE_CATEGORY_DEFAULTS:
        key = str(item).strip().lower()
        if key and key not in seen:
            seen.add(key)
            merged.append(key)
    for row in rows:
        key = str(row.get("category", "")).strip().lower()
        if key and key not in seen:
            seen.add(key)
            merged.append(key)
    return merged


def sanitize_recipe_id(value: str | None) -> str:
    return _sanitize_recipe_id(value)


def recipe_manifest_file(recipe_id: str) -> Path:
    return _recipe_manifest_file(recipe_id)


def default_recipe_prompt_file(recipe_id: str) -> str:
    return _default_recipe_prompt_file(recipe_id)


def normalize_recipe_steps_manifest(raw_steps: Any) -> list[dict[str, Any]]:
    return _normalize_recipe_steps_manifest(raw_steps)


def normalize_recipe_schedule_manifest(raw_schedule: Any) -> dict[str, Any]:
    return _normalize_recipe_schedule_manifest(raw_schedule)


def validate_stored_recipe_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    return _validate_stored_recipe_manifest(manifest)


def load_stored_recipe_manifests() -> tuple[list[dict[str, Any]], list[str]]:
    return _load_stored_recipe_manifests()


def save_stored_recipe_manifest(manifest: dict[str, Any], previous_id: str | None = None) -> dict[str, Any]:
    return _save_stored_recipe_manifest(manifest, previous_id=previous_id)


def delete_stored_recipe_manifest(recipe_id: str) -> dict[str, Any]:
    return _delete_stored_recipe_manifest(recipe_id)


def collect_recipe_categories(rows: list[dict[str, Any]]) -> list[str]:
    return _collect_recipe_categories(rows)


def invalidate_stored_recipe_manifest_cache() -> None:
    _invalidate_stored_recipe_manifest_cache()


_sanitize_skill_id = _sanitize_recipe_id

# Legacy aliases for older imports/config tooling. New code should use the
# recipe/stored-recipe names above.
_custom_skill_file = _recipe_manifest_file
_default_prompt_file = _default_recipe_prompt_file
_legacy_custom_skill_file = _legacy_recipe_manifest_file
_legacy_default_prompt_file = _legacy_default_recipe_prompt_file
_normalize_skill_steps_manifest = _normalize_recipe_steps_manifest
_normalize_skill_schedule_manifest = _normalize_recipe_schedule_manifest
_validate_custom_skill_manifest = _validate_stored_recipe_manifest
_load_custom_skill_manifests = _load_stored_recipe_manifests
_invalidate_custom_skill_manifest_cache = _invalidate_stored_recipe_manifest_cache
_iter_custom_skill_manifest_paths = _iter_stored_recipe_manifest_paths
_custom_skill_manifest_snapshot = _stored_recipe_manifest_snapshot
_build_skill_trigger_index = _build_recipe_trigger_index
_refresh_skill_trigger_index = _refresh_recipe_trigger_index
_save_custom_skill_manifest = _save_stored_recipe_manifest
_delete_custom_skill_manifest = _delete_stored_recipe_manifest
_collect_skill_categories = _collect_recipe_categories
