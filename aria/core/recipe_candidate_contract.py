from __future__ import annotations

from typing import Any

from aria.core.recipe_experience_contract import RECIPE_EXPERIENCE_METADATA_KEYS
from aria.core.recipe_experience_contract import normalize_recipe_experience

RECIPE_CANDIDATE_METADATA_KEYS = (
    "candidate_role",
    "recipe_scope",
    "recipe_origin",
    *RECIPE_EXPERIENCE_METADATA_KEYS,
)


def _source_value(source: Any, key: str) -> Any:
    if isinstance(source, dict):
        if key in source:
            return source.get(key)
        nested = source.get("metadata")
        if isinstance(nested, dict) and key in nested:
            return nested.get(key)
        return None
    return getattr(source, key, None)


def build_recipe_candidate_metadata(
    *,
    candidate_role: str = "",
    recipe_scope: dict[str, Any] | None = None,
    recipe_origin: str = "",
    experience: Any | None = None,
) -> dict[str, Any]:
    return {
        "candidate_role": str(candidate_role or "").strip(),
        "recipe_scope": dict(recipe_scope or {}),
        "recipe_origin": str(recipe_origin or "").strip(),
        **normalize_recipe_experience(experience),
    }
