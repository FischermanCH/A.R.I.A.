from __future__ import annotations

from typing import Any

from aria.core.action_candidate_taxonomy import STORED_RECIPE_MANIFEST_ORIGIN
from aria.core.action_candidate_taxonomy import STORED_RECIPE_CANDIDATE_ROLE
from aria.core.recipe_candidate_contract import build_recipe_candidate_metadata


def stored_recipe_step_types(manifest: dict[str, Any]) -> list[str]:
    rows: list[str] = []
    seen: set[str] = set()
    for step in list(manifest.get("steps", []) or []):
        step_type = str((step or {}).get("type", "") or "").strip().lower()
        if not step_type or step_type in seen:
            continue
        seen.add(step_type)
        rows.append(step_type)
    return rows


def stored_recipe_connection_kinds(manifest: dict[str, Any]) -> list[str]:
    rows: list[str] = []
    seen: set[str] = set()
    for item in list(manifest.get("connections", []) or []):
        clean = str(item or "").strip().lower()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        rows.append(clean)
    return rows


def stored_recipe_scope(manifest: dict[str, Any], *, fallback_connection_kind: str = "") -> dict[str, Any]:
    connection_kinds = stored_recipe_connection_kinds(manifest)
    clean_fallback = str(fallback_connection_kind or "").strip().lower()
    if clean_fallback and clean_fallback not in connection_kinds:
        connection_kinds = [*connection_kinds, clean_fallback] if connection_kinds else [clean_fallback]
    return {
        "connection_kinds": connection_kinds,
        "step_types": stored_recipe_step_types(manifest),
    }


def stored_recipe_candidate_metadata(
    manifest: dict[str, Any],
    *,
    fallback_connection_kind: str = "",
    experience: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata = build_recipe_candidate_metadata(
        candidate_role=STORED_RECIPE_CANDIDATE_ROLE,
        recipe_scope=stored_recipe_scope(manifest, fallback_connection_kind=fallback_connection_kind),
        recipe_origin=STORED_RECIPE_MANIFEST_ORIGIN,
        experience=experience,
    )
    return metadata


def stored_recipe_trigger_values(manifest: dict[str, Any]) -> list[str]:
    skill_name = str(manifest.get("name", "") or "").strip()
    skill_id = str(manifest.get("id", "") or "").strip()
    keywords = manifest.get("router_keywords", [])
    if not isinstance(keywords, list):
        keywords = []
    rows: list[str] = []
    seen: set[str] = set()
    for raw in [
        skill_name.lower(),
        skill_id.lower(),
        skill_id.replace("-", " ").lower(),
        *[str(item or "").strip().lower() for item in keywords],
    ]:
        if not raw or len(raw) < 3 or raw in seen:
            continue
        seen.add(raw)
        rows.append(raw)
    return rows
