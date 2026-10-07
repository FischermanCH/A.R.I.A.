from __future__ import annotations

from typing import Any

from aria.modules.action_contracts.connection import connection_action_contract
from aria.modules.action_planner_templates.taxonomy import STORED_RECIPE_CANDIDATE_ROLE
from aria.modules.action_planner_templates.taxonomy import STORED_RECIPE_MANIFEST_ORIGIN


_PROMOTION_BLOCKER_MULTI_TARGET = "multi_target_scope"
_PROMOTION_BLOCKER_SIDE_EFFECT = "side_effect_requires_manual_recipe"


def _source_value(source: Any, key: str) -> Any:
    if isinstance(source, dict):
        if key in source:
            return source.get(key)
        nested = source.get("metadata")
        if isinstance(nested, dict) and key in nested:
            return nested.get(key)
        return None
    return getattr(source, key, None)


def _promotion_blockers(source: Any | None = None) -> set[str]:
    blockers: set[str] = set()
    scope = _source_value(source, "recipe_scope")
    scope = dict(scope) if isinstance(scope, dict) else {}
    target_scope = str(scope.get("target_scope", "") or scope.get("scope_kind", "") or "").strip().lower()
    learning_origin = str(scope.get("learning_origin", "") or "").strip().lower()
    if target_scope in {"multi_target", "plural_target_scope"} or learning_origin == "plural_target_scope":
        blockers.add(_PROMOTION_BLOCKER_MULTI_TARGET)
    capability = str(_source_value(source, "capability") or "").strip().lower()
    if bool(getattr(connection_action_contract(capability), "side_effect", False)):
        blockers.add(_PROMOTION_BLOCKER_SIDE_EFFECT)
    return blockers


def _promotion_hint(blockers: set[str]) -> str:
    if _PROMOTION_BLOCKER_MULTI_TARGET in blockers:
        return "Multi-target observations stay context-only; create an explicit reviewed recipe for the target set."
    if _PROMOTION_BLOCKER_SIDE_EFFECT in blockers:
        return "Side-effect learned actions stay review-only; create an explicit recipe so policy, confirmation and inputs are visible."
    return ""


def _normalized_promotion(source: Any | None = None) -> dict[str, str]:
    explicit_state = str(_source_value(source, "promotion_state") or "").strip().lower()
    explicit_hint = str(_source_value(source, "promotion_hint") or "").strip()
    if explicit_state or explicit_hint:
        return {"promotion_state": explicit_state, "promotion_hint": explicit_hint}

    blockers = _promotion_blockers(source)
    gate_hint = _promotion_hint(blockers)
    experience_count = int(_source_value(source, "experience_count") or 0)
    try:
        evidence = float(_source_value(source, "learning_evidence") or 0.0)
    except (TypeError, ValueError):
        evidence = 0.0
    maturity_score = evidence if evidence > 0 else float(experience_count)
    if _PROMOTION_BLOCKER_MULTI_TARGET in blockers:
        return {
            "promotion_state": "observed" if experience_count > 0 else "",
            "promotion_hint": gate_hint,
        }
    if _PROMOTION_BLOCKER_SIDE_EFFECT in blockers:
        if maturity_score >= 5:
            return {"promotion_state": "review_ready", "promotion_hint": gate_hint}
        if experience_count > 0:
            return {"promotion_state": "observed", "promotion_hint": gate_hint}
        return {"promotion_state": "", "promotion_hint": gate_hint}
    if maturity_score >= 5:
        return {
            "promotion_state": "eligible",
            "promotion_hint": "Repeated successful runs make this learned recipe eligible for promotion.",
        }
    if maturity_score >= 3:
        return {
            "promotion_state": "review_ready",
            "promotion_hint": "Multiple successful runs make this learned recipe ready for review.",
        }
    if experience_count > 0:
        return {
            "promotion_state": "observed",
            "promotion_hint": "Observed successful runs; collect more evidence before review.",
        }
    return {"promotion_state": "", "promotion_hint": ""}


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
    promotion = _normalized_promotion(experience)
    return {
        "candidate_role": STORED_RECIPE_CANDIDATE_ROLE,
        "recipe_scope": stored_recipe_scope(manifest, fallback_connection_kind=fallback_connection_kind),
        "recipe_origin": STORED_RECIPE_MANIFEST_ORIGIN,
        "experience_count": int(_source_value(experience, "experience_count") or 0),
        "last_success_at": str(_source_value(experience, "last_success_at") or "").strip(),
        **promotion,
    }


def stored_recipe_identity_values(manifest: dict[str, Any]) -> list[str]:
    skill_name = str(manifest.get("name", "") or "").strip()
    skill_id = str(manifest.get("id", "") or "").strip()
    rows: list[str] = []
    seen: set[str] = set()
    for raw in [
        skill_name.lower(),
        skill_id.lower(),
        skill_id.replace("-", " ").lower(),
    ]:
        if not raw or len(raw) < 3 or raw in seen:
            continue
        seen.add(raw)
        rows.append(raw)
    return rows
