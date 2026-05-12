from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote_plus

from aria.core.recipe_manifests import _sanitize_recipe_id, _save_stored_recipe_manifest
from aria.web.recipes_wizard_catalog import _recipes_routes_text

BASE_DIR = Path(__file__).resolve().parents[2]
SAMPLE_RECIPES_DIR = BASE_DIR / "samples" / "recipes"
LEGACY_SAMPLE_RECIPES_DIR = BASE_DIR / "samples" / "skills"


def sample_recipe_dir() -> Path:
    return SAMPLE_RECIPES_DIR if SAMPLE_RECIPES_DIR.exists() else LEGACY_SAMPLE_RECIPES_DIR


def build_sample_recipe_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
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
        rows.append(
            {
                "file_name": path.name,
                "id": recipe_id,
                "name": str(raw.get("name", "")).strip() or recipe_id,
                "description": str(raw.get("description", "")).strip(),
                "category": str(raw.get("category", "custom")).strip() or "custom",
            }
        )
    return rows


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
