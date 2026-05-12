from __future__ import annotations

from pathlib import Path
from typing import Any

from aria.core.connection_action_contract import connection_action_contract
from aria.core.i18n import I18NStore
from aria.core.learned_recipe_store_contract import normalize_learned_recipe_store_entry
from aria.core.recipe_experience_promotion import is_stored_recipe_promotable_capability
from aria.core.recipe_promotion_contract import (
    PROMOTION_STATE_ELIGIBLE,
    PROMOTION_STATE_OBSERVED,
    PROMOTION_STATE_PROMOTED,
    PROMOTION_STATE_REVIEW_READY,
    promotion_state_rank,
)

_LEARNED_RECIPE_UI_I18N = I18NStore(Path(__file__).resolve().parents[1] / "i18n")


def _learned_recipe_ui_text(language: str | None, key: str, default: str = "", **values: object) -> str:
    template = _LEARNED_RECIPE_UI_I18N.t(language or "de", f"learned_recipe_ui.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template


LEARNED_RECIPE_FILTER_ALL = "all"
LEARNED_RECIPE_FILTER_VALUES = (
    LEARNED_RECIPE_FILTER_ALL,
    PROMOTION_STATE_OBSERVED,
    PROMOTION_STATE_REVIEW_READY,
    PROMOTION_STATE_ELIGIBLE,
    PROMOTION_STATE_PROMOTED,
)

LEARNED_RECIPE_KIND_FILTER_ALL = "all"
LEARNED_RECIPE_SORT_LAST_SUCCESS = "last_success"
LEARNED_RECIPE_SORT_EXPERIENCE = "experience"
LEARNED_RECIPE_SORT_TITLE = "title"
LEARNED_RECIPE_SORT_VALUES = (
    LEARNED_RECIPE_SORT_LAST_SUCCESS,
    LEARNED_RECIPE_SORT_EXPERIENCE,
    LEARNED_RECIPE_SORT_TITLE,
)


def normalize_learned_recipe_filter(value: str | None) -> str:
    clean = str(value or "").strip().lower()
    return clean if clean in LEARNED_RECIPE_FILTER_VALUES else LEARNED_RECIPE_FILTER_ALL


def normalize_learned_recipe_kind_filter(value: str | None, rows: list[dict[str, Any]] | None = None) -> str:
    clean = str(value or "").strip().lower()
    if clean == LEARNED_RECIPE_KIND_FILTER_ALL:
        return clean
    known = learned_recipe_kind_values(rows)
    return clean if clean and clean in known else LEARNED_RECIPE_KIND_FILTER_ALL


def normalize_learned_recipe_sort(value: str | None) -> str:
    clean = str(value or "").strip().lower()
    return clean if clean in LEARNED_RECIPE_SORT_VALUES else LEARNED_RECIPE_SORT_LAST_SUCCESS


def _promotion_state_label(state: str, *, language: str | None = None) -> str:
    clean = str(state or "").strip().lower()
    if clean == PROMOTION_STATE_OBSERVED:
        return _learned_recipe_ui_text(language, "state_observed", "Observed")
    if clean == PROMOTION_STATE_REVIEW_READY:
        return _learned_recipe_ui_text(language, "state_review_ready", "Review ready")
    if clean == PROMOTION_STATE_ELIGIBLE:
        return _learned_recipe_ui_text(language, "state_eligible", "Promotion due")
    if clean == PROMOTION_STATE_PROMOTED:
        return _learned_recipe_ui_text(language, "state_promoted", "Promoted")
    return _learned_recipe_ui_text(language, "state_unknown", "Unknown")


def _promotion_state_class(state: str) -> str:
    clean = str(state or "").strip().lower()
    if clean == PROMOTION_STATE_PROMOTED:
        return "is-on"
    if clean in {PROMOTION_STATE_REVIEW_READY, PROMOTION_STATE_ELIGIBLE}:
        return "is-warn"
    return "is-off"


def _scope_label(entry: dict[str, Any]) -> str:
    connection_kind = str(entry.get("connection_kind", "") or "").strip()
    connection_ref = str(entry.get("connection_ref", "") or "").strip()
    capability = str(entry.get("capability", "") or "").strip()

    parts: list[str] = []
    if connection_kind:
        parts.append(connection_kind)
    if connection_ref:
        parts.append(connection_ref)
    if capability:
        parts.append(capability)
    return " · ".join(parts)


def _target_label(entry: dict[str, Any]) -> str:
    connection_kind = str(entry.get("connection_kind", "") or "").strip()
    connection_ref = str(entry.get("connection_ref", "") or "").strip()
    if connection_kind and connection_ref:
        return f"{connection_kind}/{connection_ref}"
    return connection_ref or connection_kind


def _audit_action_label(entry: dict[str, Any]) -> str:
    chosen_action = str(entry.get("chosen_action", "") or "").strip()
    if chosen_action:
        return chosen_action
    inputs = entry.get("inputs", {})
    if isinstance(inputs, dict):
        for key in ("command", "remote_path", "path", "message", "search_query"):
            value = str(inputs.get(key, "") or "").strip()
            if value:
                return value
    return str(entry.get("preview", "") or "").strip()


def _review_safety_label(entry: dict[str, Any], promotion_state: str, *, language: str | None = None) -> str:
    if promotion_state == PROMOTION_STATE_PROMOTED:
        return _learned_recipe_ui_text(language, "review_safety_promoted", "Promoted: executable stored recipe")
    if str(entry.get("stored_recipe_id", "") or "").strip():
        return _learned_recipe_ui_text(language, "review_safety_stored_recipe", "Stored recipe exists")
    return _learned_recipe_ui_text(language, "review_safety_context_only", "Context only: not directly executable")


def _review_safety_class(promotion_state: str) -> str:
    if promotion_state == PROMOTION_STATE_PROMOTED:
        return "status-ok"
    if promotion_state in {PROMOTION_STATE_REVIEW_READY, PROMOTION_STATE_ELIGIBLE}:
        return "status-warn"
    return "status-muted"


def _review_next_action_label(
    entry: dict[str, Any],
    promotion_state: str,
    *,
    language: str | None = None,
) -> str:
    if promotion_state == PROMOTION_STATE_PROMOTED:
        return _learned_recipe_ui_text(language, "next_action_open_stored", "Open stored recipe for review")
    if is_stored_recipe_promotable_capability(entry.get("capability", "")):
        return _learned_recipe_ui_text(language, "next_action_promote", "Review and promote if still correct")
    return _learned_recipe_ui_text(language, "next_action_context_only", "Keep as planner context")


def _review_contract_label(entry: dict[str, Any], *, language: str | None = None) -> str:
    capability = str(entry.get("capability", "") or "").strip()
    contract = connection_action_contract(capability)
    if contract is None:
        return _learned_recipe_ui_text(language, "contract_missing", "No connection action contract found")
    side_effect = (
        _learned_recipe_ui_text(language, "contract_side_effect_confirm", "side effect: confirmation/policy required")
        if contract.side_effect
        else _learned_recipe_ui_text(language, "contract_side_effect_readonly", "read-only/bounded")
    )
    return _learned_recipe_ui_text(
        language,
        "contract_summary",
        "Contract: {family} · policy {policy} · runtime {operation} · {side_effect}",
        family=contract.family or "-",
        policy=contract.policy_family or "-",
        operation=contract.operation or "-",
        side_effect=side_effect,
    )


def build_learned_recipe_row(source: dict[str, Any] | None, *, language: str | None = None) -> dict[str, Any]:
    entry = normalize_learned_recipe_store_entry(source)
    promotion_state = str(entry.get("promotion_state", "") or "").strip().lower()
    last_success_at = str(entry.get("last_success_at", "") or "").strip()
    stored_recipe_id = str(entry.get("stored_recipe_id", "") or "").strip()
    scope = dict(entry.get("recipe_scope", {}) or {})
    return {
        **entry,
        "promotion_label": _promotion_state_label(promotion_state, language=language),
        "promotion_class": _promotion_state_class(promotion_state),
        "scope_label": _scope_label(entry),
        "last_success_label": last_success_at.replace("T", " ").replace("Z", " UTC") if last_success_at else "",
        "stored_recipe_id": stored_recipe_id,
        "user_message": str(entry.get("user_message", "") or "").strip(),
        "learning_origin": str(scope.get("learning_origin", "") or "").strip(),
        "review_target_label": _target_label(entry),
        "review_action_label": _audit_action_label(entry),
        "review_safety_label": _review_safety_label(entry, promotion_state, language=language),
        "review_safety_class": _review_safety_class(promotion_state),
        "review_next_action_label": _review_next_action_label(entry, promotion_state, language=language),
        "review_contract_label": _review_contract_label(entry, language=language),
        "can_promote_to_stored_recipe": is_stored_recipe_promotable_capability(entry.get("capability", "")) and promotion_state != PROMOTION_STATE_PROMOTED,
    }


def build_learned_recipe_rows(entries: list[dict[str, Any]] | None, *, language: str | None = None) -> list[dict[str, Any]]:
    rows = [build_learned_recipe_row(item, language=language) for item in list(entries or []) if isinstance(item, dict)]
    return rows


def sort_learned_recipe_rows(rows: list[dict[str, Any]] | None, sort_key: str | None) -> list[dict[str, Any]]:
    clean_sort = normalize_learned_recipe_sort(sort_key)
    all_rows = list(rows or [])
    if clean_sort == LEARNED_RECIPE_SORT_EXPERIENCE:
        all_rows.sort(
            key=lambda row: (
                int(row.get("experience_count", 0) or 0),
                promotion_state_rank(str(row.get("promotion_state", "") or "")),
                str(row.get("last_success_at", "") or ""),
                str(row.get("title", "") or ""),
            ),
            reverse=True,
        )
        return all_rows
    if clean_sort == LEARNED_RECIPE_SORT_TITLE:
        all_rows.sort(
            key=lambda row: (
                str(row.get("title", "") or "").lower(),
                -promotion_state_rank(str(row.get("promotion_state", "") or "")),
                -int(row.get("experience_count", 0) or 0),
            ),
        )
        return all_rows
    all_rows.sort(
        key=lambda row: (
            str(row.get("last_success_at", "") or ""),
            promotion_state_rank(str(row.get("promotion_state", "") or "")),
            int(row.get("experience_count", 0) or 0),
            str(row.get("title", "") or ""),
        ),
        reverse=True,
    )
    return all_rows


def filter_learned_recipe_rows(rows: list[dict[str, Any]] | None, promotion_filter: str | None) -> list[dict[str, Any]]:
    clean_filter = normalize_learned_recipe_filter(promotion_filter)
    all_rows = list(rows or [])
    if clean_filter == LEARNED_RECIPE_FILTER_ALL:
        return all_rows
    return [
        row
        for row in all_rows
        if str(row.get("promotion_state", "") or "").strip().lower() == clean_filter
    ]


def learned_recipe_kind_values(rows: list[dict[str, Any]] | None) -> list[str]:
    seen: set[str] = set()
    values: list[str] = []
    for row in list(rows or []):
        clean = str(row.get("connection_kind", "") or "").strip().lower()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        values.append(clean)
    return values


def filter_learned_recipe_rows_by_kind(rows: list[dict[str, Any]] | None, kind_filter: str | None) -> list[dict[str, Any]]:
    all_rows = list(rows or [])
    clean_filter = normalize_learned_recipe_kind_filter(kind_filter, all_rows)
    if clean_filter == LEARNED_RECIPE_KIND_FILTER_ALL:
        return all_rows
    return [row for row in all_rows if str(row.get("connection_kind", "") or "").strip().lower() == clean_filter]


def learned_recipe_kind_counts(rows: list[dict[str, Any]] | None) -> dict[str, int]:
    counts: dict[str, int] = {LEARNED_RECIPE_KIND_FILTER_ALL: len(list(rows or []))}
    for row in list(rows or []):
        clean = str(row.get("connection_kind", "") or "").strip().lower()
        if not clean:
            continue
        counts[clean] = counts.get(clean, 0) + 1
    return counts


def learned_recipe_filter_counts(rows: list[dict[str, Any]] | None) -> dict[str, int]:
    counts = {key: 0 for key in LEARNED_RECIPE_FILTER_VALUES}
    all_rows = list(rows or [])
    counts[LEARNED_RECIPE_FILTER_ALL] = len(all_rows)
    for row in all_rows:
        state = normalize_learned_recipe_filter(str(row.get("promotion_state", "") or ""))
        if state == LEARNED_RECIPE_FILTER_ALL:
            continue
        counts[state] = counts.get(state, 0) + 1
    return counts
