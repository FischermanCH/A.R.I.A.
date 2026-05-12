from __future__ import annotations

import copy
import json
import threading
from pathlib import Path
from typing import Any

from aria.core.learned_recipe_store_contract import normalize_learned_recipe_store_entry

_LEARNED_RECIPE_STORE_LOCK = threading.RLock()
_LEARNED_RECIPE_STORE_CACHE: dict[str, Any] = {
    "mtime_ns": -1,
    "size": -1,
    "payload": {"recipes": []},
}


def _learned_recipe_store_path() -> Path:
    path = Path(__file__).resolve().parents[2] / "data" / "runtime" / "learned_recipes.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _normalize_learned_recipe_store_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        payload = {}
    recipes = payload.get("recipes", [])
    if not isinstance(recipes, list):
        recipes = []
    return {
        "recipes": [
            normalize_learned_recipe_store_entry(item)
            for item in recipes
            if isinstance(item, dict)
        ]
    }


def _read_learned_recipe_store() -> dict[str, Any]:
    path = _learned_recipe_store_path()
    try:
        stat = path.stat()
    except FileNotFoundError:
        with _LEARNED_RECIPE_STORE_LOCK:
            _LEARNED_RECIPE_STORE_CACHE["mtime_ns"] = -1
            _LEARNED_RECIPE_STORE_CACHE["size"] = -1
            _LEARNED_RECIPE_STORE_CACHE["payload"] = {"recipes": []}
        return {"recipes": []}
    except OSError:
        return {"recipes": []}
    with _LEARNED_RECIPE_STORE_LOCK:
        if (
            int(_LEARNED_RECIPE_STORE_CACHE.get("mtime_ns", -1)) == int(stat.st_mtime_ns)
            and int(_LEARNED_RECIPE_STORE_CACHE.get("size", -1)) == int(stat.st_size)
        ):
            payload = _LEARNED_RECIPE_STORE_CACHE.get("payload", {"recipes": []})
            return copy.deepcopy(payload if isinstance(payload, dict) else {"recipes": []})
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"recipes": []}
    normalized = _normalize_learned_recipe_store_payload(data)
    with _LEARNED_RECIPE_STORE_LOCK:
        _LEARNED_RECIPE_STORE_CACHE["mtime_ns"] = int(stat.st_mtime_ns)
        _LEARNED_RECIPE_STORE_CACHE["size"] = int(stat.st_size)
        _LEARNED_RECIPE_STORE_CACHE["payload"] = copy.deepcopy(normalized)
    return copy.deepcopy(normalized)


def _write_learned_recipe_store(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_learned_recipe_store_payload(payload)
    path = _learned_recipe_store_path()
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)
    try:
        stat = path.stat()
    except OSError:
        stat = None
    if stat is not None:
        with _LEARNED_RECIPE_STORE_LOCK:
            _LEARNED_RECIPE_STORE_CACHE["mtime_ns"] = int(stat.st_mtime_ns)
            _LEARNED_RECIPE_STORE_CACHE["size"] = int(stat.st_size)
            _LEARNED_RECIPE_STORE_CACHE["payload"] = copy.deepcopy(normalized)
    return copy.deepcopy(normalized)


def invalidate_learned_recipe_store_cache() -> None:
    with _LEARNED_RECIPE_STORE_LOCK:
        _LEARNED_RECIPE_STORE_CACHE["mtime_ns"] = -1
        _LEARNED_RECIPE_STORE_CACHE["size"] = -1
        _LEARNED_RECIPE_STORE_CACHE["payload"] = {"recipes": []}


def load_learned_recipe_store_entries() -> list[dict[str, Any]]:
    payload = _read_learned_recipe_store()
    recipes = payload.get("recipes", [])
    if not isinstance(recipes, list):
        return []
    return [dict(item or {}) for item in recipes if isinstance(item, dict)]


def save_learned_recipe_store_entry(entry: dict[str, Any], previous_id: str | None = None) -> dict[str, Any]:
    normalized = normalize_learned_recipe_store_entry(entry)
    clean_id = str(normalized.get("recipe_id", "") or "").strip()
    previous_clean = str(previous_id or "").strip()
    payload = _read_learned_recipe_store()
    rows = [dict(item or {}) for item in list(payload.get("recipes", []) or []) if isinstance(item, dict)]
    next_rows: list[dict[str, Any]] = []
    replaced = False
    for row in rows:
        row_id = str(row.get("recipe_id", "") or "").strip()
        if row_id and row_id in {clean_id, previous_clean}:
            if not replaced:
                next_rows.append(normalized)
                replaced = True
            continue
        next_rows.append(row)
    if not replaced:
        next_rows.append(normalized)
    stored = _write_learned_recipe_store({"recipes": next_rows})
    for row in list(stored.get("recipes", []) or []):
        if str(row.get("recipe_id", "") or "").strip() == clean_id:
            return dict(row)
    return normalized


def delete_learned_recipe_store_entry(recipe_id: str) -> None:
    clean_id = str(recipe_id or "").strip()
    if not clean_id:
        return
    payload = _read_learned_recipe_store()
    rows = [dict(item or {}) for item in list(payload.get("recipes", []) or []) if isinstance(item, dict)]
    next_rows = [row for row in rows if str(row.get("recipe_id", "") or "").strip() != clean_id]
    if len(next_rows) == len(rows):
        return
    _write_learned_recipe_store({"recipes": next_rows})


def update_learned_recipe_store_entry(recipe_id: str, updates: dict[str, Any] | None = None) -> dict[str, Any]:
    clean_id = str(recipe_id or "").strip()
    if not clean_id:
        raise ValueError("recipe_id missing")
    payload = _read_learned_recipe_store()
    rows = [dict(item or {}) for item in list(payload.get("recipes", []) or []) if isinstance(item, dict)]
    patch = dict(updates or {})
    next_rows: list[dict[str, Any]] = []
    updated_row: dict[str, Any] | None = None
    for row in rows:
        row_id = str(row.get("recipe_id", "") or "").strip()
        if row_id != clean_id:
            next_rows.append(row)
            continue
        merged = dict(row)
        merged.update(patch)
        updated_row = normalize_learned_recipe_store_entry(merged)
        next_rows.append(updated_row)
    if updated_row is None:
        raise ValueError(f"Learned recipe not found: {clean_id}")
    _write_learned_recipe_store({"recipes": next_rows})
    return updated_row
