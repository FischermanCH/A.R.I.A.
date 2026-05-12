from __future__ import annotations

from typing import Any

from aria.core.recipe_candidate_contract import build_recipe_candidate_metadata
from aria.core.recipe_candidate_contract import RECIPE_CANDIDATE_METADATA_KEYS
from aria.core.recipe_experience_contract import recipe_experience_decision_fields
from aria.core.recipe_experience_contract import recipe_experience_prompt_parts


def _source_value(source: Any, key: str) -> Any:
    if isinstance(source, dict):
        if key in source:
            return source.get(key)
        nested = source.get("metadata")
        if isinstance(nested, dict) and key in nested:
            return nested.get(key)
    return getattr(source, key, None)


def recipe_candidate_metadata(source: Any) -> dict[str, Any]:
    return build_recipe_candidate_metadata(
        candidate_role=_source_value(source, "candidate_role") or "",
        recipe_scope=dict(_source_value(source, "recipe_scope") or {}),
        recipe_origin=_source_value(source, "recipe_origin") or "",
        experience=source,
    )


def recipe_candidate_prompt_parts(source: Any) -> list[str]:
    metadata = recipe_candidate_metadata(source)
    parts: list[str] = []
    if metadata["recipe_origin"]:
        parts.append(f"recipe_origin={metadata['recipe_origin']}")
    parts.extend(recipe_experience_prompt_parts(metadata))
    return parts


def recipe_candidate_decision_fields(source: Any, *, prefix: str = "") -> dict[str, Any]:
    metadata = recipe_candidate_metadata(source)
    return {
        f"{prefix}candidate_role": metadata["candidate_role"],
        f"{prefix}recipe_origin": metadata["recipe_origin"],
        f"{prefix}recipe_scope": dict(metadata["recipe_scope"] or {}),
        **recipe_experience_decision_fields(metadata, prefix=prefix),
    }
