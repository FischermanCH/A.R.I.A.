from __future__ import annotations

from typing import Any

from aria.core.stored_recipe_manifest_view import stored_recipe_candidate_metadata
from aria.core.stored_recipe_manifest_view import stored_recipe_trigger_values


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
        "triggers": stored_recipe_trigger_values(manifest),
        "steps": step_names,
        **stored_recipe_candidate_metadata(manifest),
    }


def build_stored_recipe_toolbox_row(manifest: dict[str, Any], *, description: str = "") -> dict[str, Any] | None:
    recipe_id = str(manifest.get("id", "") or "").strip()
    recipe_name = str(manifest.get("name", "") or "").strip()
    trigger_values = [item for item in stored_recipe_trigger_values(manifest) if item]
    first_trigger = next((item for item in trigger_values if len(item.strip()) >= 3), "")
    if not recipe_name and not first_trigger and not recipe_id:
        return None
    label = recipe_name or first_trigger or recipe_id
    insert = first_trigger or recipe_name or recipe_id.replace("-", " ")
    hint = str(description or "").strip() or first_trigger or recipe_id
    keywords = list(
        dict.fromkeys(
            [
                *trigger_values,
                recipe_name.lower() if recipe_name else "",
                recipe_id.lower(),
                recipe_id.replace("-", " ").lower(),
                str(description or "").strip().lower(),
            ]
        )
    )
    return {
        "label": label,
        "insert": insert,
        "hint": hint,
        "keywords": [item for item in keywords if item],
        **stored_recipe_candidate_metadata(manifest),
    }
