from __future__ import annotations

from typing import Any

from aria.modules.recipe_runtime.stored_manifest_view import stored_recipe_candidate_metadata
from aria.modules.recipe_runtime.stored_manifest_view import stored_recipe_identity_values


def build_stored_recipe_progress_hint(manifest: dict[str, Any]) -> dict[str, Any] | None:
    recipe_id = str(manifest.get("id", "") or "").strip()
    recipe_name = str(manifest.get("name", "") or "").strip() or recipe_id
    if not recipe_id:
        return None
    step_names: list[str] = []
    for item in list(manifest.get("steps", []) or [])[:8]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "") or "").strip()
        if name:
            step_names.append(name)
    return {
        "id": recipe_id,
        "name": recipe_name,
        "steps": step_names,
        **stored_recipe_candidate_metadata(manifest),
    }


def build_client_recipe_progress_hints(stored_recipe_manifests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for manifest in stored_recipe_manifests:
        row = build_stored_recipe_progress_hint(manifest)
        if row:
            rows.append(row)
    return rows


def build_client_skill_progress_hints(custom_manifests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return build_client_recipe_progress_hints(custom_manifests)


def build_stored_recipe_toolbox_row(manifest: dict[str, Any], *, description: str = "") -> dict[str, Any] | None:
    recipe_id = str(manifest.get("id", "") or "").strip()
    recipe_name = str(manifest.get("name", "") or "").strip()
    identity_values = [item for item in stored_recipe_identity_values(manifest) if item]
    first_identity = next((item for item in identity_values if len(item.strip()) >= 3), "")
    if not recipe_name and not first_identity and not recipe_id:
        return None
    label = recipe_name or first_identity or recipe_id
    insert = recipe_name or first_identity or recipe_id.replace("-", " ")
    hint = str(description or "").strip() or recipe_name or recipe_id
    return {
        "label": label,
        "insert": insert,
        "hint": hint,
        **stored_recipe_candidate_metadata(manifest),
    }
