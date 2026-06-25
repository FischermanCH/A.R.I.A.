from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aria.core.action_candidate_taxonomy import BUILT_IN_TEMPLATE_ORIGIN
from aria.core.action_candidate_taxonomy import LEGACY_SKILL_CANDIDATE_KIND
from aria.core.action_candidate_taxonomy import RECIPE_CANDIDATE_KIND
from aria.core.action_candidate_taxonomy import STORED_RECIPE_MANIFEST_ORIGIN
from aria.core.action_candidate_taxonomy import STORED_RECIPE_CANDIDATE_ROLE
from aria.core.action_candidate_taxonomy import TEMPLATE_CANDIDATE_ROLE
from aria.core.action_candidate_taxonomy import candidate_debug_label
from aria.core.action_candidate_taxonomy import candidate_origin_priority
from aria.core.action_candidate_taxonomy import candidate_role_priority
from aria.core.action_candidate_taxonomy import is_recipe_candidate_kind
from aria.core.action_candidate_taxonomy import normalize_action_candidate_kind
from aria.core.action_planner_candidate_details import apply_candidate_labels
from aria.core.action_planner_candidate_details import build_serialized_candidate
from aria.core.action_planner_candidate_details import candidate_kind_label as core_candidate_kind_label
from aria.core.action_planner_candidate_details import candidate_payload
from aria.core.action_planner_candidate_details import clarifying_question
from aria.core.action_planner_candidate_details import derive_candidate_preview
from aria.core.action_planner_candidate_details import input_key_label as core_input_key_label
from aria.core.action_planner_followups import suggested_follow_up_prompt as core_suggested_follow_up_prompt
from aria.core.action_planner_result_state import confidence_label as _confidence_label
from aria.core.action_planner_result_state import execution_state as _execution_state
from aria.core.action_planner_result_state import execution_state_label as _execution_state_label
from aria.core.action_planner_result_state import planner_source_label as _planner_source_label
from aria.core.action_planner_result_state import result_payload as _result_payload
from aria.core.action_planner_result_state import sort_serialized_candidates
from aria.core.action_planner_result_state import target_context as _target_context
from aria.core.action_planner_recipe_candidates import build_learned_recipe_action_candidates
from aria.core.action_planner_recipe_candidates import build_stored_recipe_action_candidates
from aria.core.action_planner_scoring import intent_score
from aria.core.action_planner_scoring import routing_preference_bonus
from aria.core.action_planner_scoring import template_router_keywords
from aria.core.action_planner_scoring import template_specific_score
from aria.core.action_planner_templates import ACTION_TEMPLATE_LIBRARY
from aria.core.action_planner_templates import action_template_base_preview
from aria.core.action_planner_templates import action_template_behavior_profile
from aria.core.capability_router import CapabilityRouter
from aria.core.capability_catalog import normalize_capability
from aria.core.connection_catalog import connection_routing_spec, normalize_connection_kind
from aria.core.i18n import I18NStore
from aria.core.recipe_manifests import load_stored_recipe_manifests
from aria.core.recipe_promotion_contract import learned_recipe_promotion_blockers
from aria.core.learned_recipe_store import load_learned_recipe_store_entries
from aria.core.learned_recipe_store_contract import normalize_learned_recipe_store_entry
from aria.core.planner_candidates import PlannerCandidate, PlannerInputSet, build_planner_input_set, planner_candidate_from_action
from aria.core.recipe_candidate_view import recipe_candidate_prompt_parts
from aria.core.text_utils import extract_json_object as core_extract_json_object
from aria.core.text_utils import is_german

_load_stored_recipe_manifests = load_stored_recipe_manifests
_ACTION_PLANNER_I18N = I18NStore(Path(__file__).resolve().parents[1] / "i18n")
_ACTION_PLANNER_EXTRACTOR_LEXICON_PATH = Path(__file__).resolve().parents[1] / "lexicons" / "action_planner_extractors.json"


def _load_extractor_lexicon() -> dict[str, Any]:
    try:
        raw = json.loads(_ACTION_PLANNER_EXTRACTOR_LEXICON_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not load action planner extractor lexicon: {_ACTION_PLANNER_EXTRACTOR_LEXICON_PATH}") from exc
    return raw if isinstance(raw, dict) else {}


_ACTION_PLANNER_EXTRACTOR_LEXICON = _load_extractor_lexicon()


@dataclass(slots=True)
class ActionPlanCandidate:
    candidate_kind: str
    candidate_id: str
    plan_class: str = ""
    title: str = ""
    summary: str = ""
    intent: str = ""
    connection_kind: str = ""
    capability: str = ""
    preview: str = ""
    inputs: dict[str, str] = field(default_factory=dict)
    router_keywords: list[str] = field(default_factory=list)
    source: str = ""
    candidate_role: str = ""
    recipe_scope: dict[str, Any] = field(default_factory=dict)
    recipe_origin: str = ""
    experience_count: int = 0
    last_success_at: str = ""
    promotion_state: str = ""
    promotion_hint: str = ""
    score: float = 0.0

    @property
    def key(self) -> tuple[str, str]:
        return (normalize_action_candidate_kind(str(self.candidate_kind or "").strip().lower()), str(self.candidate_id or "").strip())


def _planner_text(language: str | None, key: str, default: str = "", **values: Any) -> str:
    template = _ACTION_PLANNER_I18N.t(language or "de", f"action_planner.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template


def _localized_text(language: str, *, de: str, en: str) -> str:
    return de if is_german(language) else en


def _candidate_kind_priority(value: str) -> int:
    clean = normalize_action_candidate_kind(value)
    if clean == "template":
        return 0
    if clean == RECIPE_CANDIDATE_KIND:
        return 1
    return 9


def _candidate_role_priority(candidate: ActionPlanCandidate) -> int:
    priority = candidate_role_priority(candidate.candidate_role)
    if priority != 9:
        return priority
    return _candidate_kind_priority(candidate.candidate_kind)


def _candidate_origin_priority(candidate: ActionPlanCandidate) -> int:
    return candidate_origin_priority(candidate.recipe_origin)


def _candidate_selection_sort_key(candidate: ActionPlanCandidate) -> tuple[float, int, int, int, str]:
    return (
        -float(candidate.score or 0.0),
        _candidate_role_priority(candidate),
        _candidate_origin_priority(candidate),
        _candidate_kind_priority(candidate.candidate_kind),
        candidate.candidate_id,
    )


def _extract_quoted_text(query: str) -> str:
    text = str(query or "")
    for pattern in (r'"([^"]+)"', r"'([^']+)'", r"“([^”]+)”"):
        match = re.search(pattern, text)
        if match:
            return str(match.group(1) or "").strip()
    return ""


def _extract_remote_path(query: str) -> str:
    text = str(query or "").strip()
    explicit = re.search(r"(?P<path>/(?:[\w.\-]+/?)+)", text)
    if explicit:
        return str(explicit.group("path") or "").strip()
    lowered = text.lower()
    known = _ACTION_PLANNER_EXTRACTOR_LEXICON.get("known_remote_paths", {})
    known = known if isinstance(known, dict) else {}
    for needle, path in known.items():
        if needle in lowered:
            return path
    return ""


def _extract_command_text(query: str) -> str:
    quoted = _extract_quoted_text(query)
    if quoted:
        return quoted
    lowered = str(query or "").strip().lower()
    known_commands = _ACTION_PLANNER_EXTRACTOR_LEXICON.get("known_commands", [])
    known_commands = known_commands if isinstance(known_commands, list) else []
    for command in known_commands:
        if command in lowered:
            return command
    command_pattern = str(_ACTION_PLANNER_EXTRACTOR_LEXICON.get("command_pattern") or "")
    match = re.search(command_pattern, lowered) if command_pattern else None
    if match:
        return str(match.group(1) or "").strip()
    return CapabilityRouter._extract_natural_ssh_command(query)


def _extract_message_text(query: str) -> str:
    quoted = _extract_quoted_text(query)
    if quoted:
        return quoted
    lowered = str(query or "").strip().lower()
    if "testnachricht" in lowered or "test message" in lowered:
        return "ARIA test message"
    return ""


def _extract_mail_search_text(query: str, connection_ref: str = "") -> str:
    return CapabilityRouter._extract_mail_search_query(query, connection_ref)


def _extract_mqtt_topic_text(query: str) -> str:
    return CapabilityRouter._extract_mqtt_topic(query)


def _extract_website_group_text(query: str) -> str:
    text = str(query or "").strip()
    match = re.search(r"(?:\b(?:in|aus|from)\b)\s+(.+)$", text, re.IGNORECASE)
    if not match:
        return ""
    return str(match.group(1) or "").strip(" \t\r\n.,;:!?")


def _extract_calendar_range_text(query: str) -> str:
    return CapabilityRouter._extract_calendar_range(query)


def _extract_calendar_search_text(query: str) -> str:
    return CapabilityRouter._extract_calendar_search(query)


def _extract_json_object(raw: str) -> dict[str, Any] | None:
    return core_extract_json_object(raw)


def _normalize_candidate_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").strip().lower())


def _safe_list(values: Any, *, limit: int = 8) -> list[str]:
    if not isinstance(values, list):
        return []
    rows: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = " ".join(str(value or "").strip().split())
        if not clean:
            continue
        key = clean.lower()
        if key in seen:
            continue
        seen.add(key)
        rows.append(clean)
        if len(rows) >= max(1, int(limit)):
            break
    return rows


def _base_candidate_preview(candidate: ActionPlanCandidate, language: str = "") -> str:
    if is_recipe_candidate_kind(candidate.candidate_kind):
        return candidate.preview
    return action_template_base_preview(candidate.candidate_id, language, candidate.preview)


def _missing_required_reason(missing_input: str, language: str = "") -> str:
    label = _input_key_label(missing_input, language) or missing_input
    return _planner_text(language, "missing_required", "Missing required {label}.", label=label)


def _routing_target_confirmation_reason(language: str = "") -> str:
    return _planner_text(
        language,
        "target_confirmation_required",
        "The target is not fully confirmed yet; ARIA should ask before execution.",
    )


def _heuristic_reason_text(reason: str, language: str = "") -> str:
    mapping = {
        "single_candidate": _planner_text(language, "reason_single_candidate", "Only one suitable action candidate is available."),
        "no_signal": _planner_text(language, "reason_no_signal", "The request is still too vague for action selection."),
        "same_intent_role_priority": _planner_text(language, "reason_same_intent_role_priority", "For the same intent, the better-bounded candidate was preferred."),
        "ambiguous": _planner_text(language, "reason_ambiguous", "The request remains ambiguous for action selection."),
        "ranking_hint_needs_llm": _planner_text(language, "reason_ranking_hint_needs_llm", "Candidate scores are ranking hints only; ARIA should ask before selecting an action without an LLM decision."),
    }
    return mapping.get(str(reason or "").strip(), str(reason or "").strip())


def _template_candidates(query: str, *, connection_kind: str, language: str = "") -> list[ActionPlanCandidate]:
    clean_kind = normalize_connection_kind(connection_kind)
    rows: list[ActionPlanCandidate] = []
    for raw in ACTION_TEMPLATE_LIBRARY.get(clean_kind, []):
        keywords = template_router_keywords(raw, clean_kind, safe_list=_safe_list)
        candidate = ActionPlanCandidate(
            candidate_kind="template",
            candidate_id=str(raw.get("candidate_id", "") or "").strip(),
            plan_class=str(raw.get("plan_class", "") or "").strip().lower(),
            title=str(raw.get("title", "") or "").strip(),
            summary=str(raw.get("summary", "") or "").strip(),
            intent=str(raw.get("intent", "") or "").strip(),
            connection_kind=clean_kind,
            capability=normalize_capability(str(raw.get("capability", "") or "").strip()),
            preview=str(raw.get("preview", "") or "").strip(),
            router_keywords=keywords,
            source="built_in_template",
            candidate_role=TEMPLATE_CANDIDATE_ROLE,
            recipe_scope={"connection_kind": clean_kind},
            recipe_origin=BUILT_IN_TEMPLATE_ORIGIN,
            score=intent_score(query, str(raw.get("intent", "") or ""), keywords),
        )
        candidate.score += template_specific_score(
            candidate.candidate_id,
            query,
            action_template_behavior_profile=action_template_behavior_profile,
            extract_quoted_text=_extract_quoted_text,
            extract_remote_path=_extract_remote_path,
            extract_command_text=_extract_command_text,
            extract_mqtt_topic_text=_extract_mqtt_topic_text,
        )
        candidate.score += routing_preference_bonus(candidate.candidate_id, query, clean_kind)
        candidate.preview = _base_candidate_preview(candidate, language)
        rows.append(candidate)
    return rows


def _recipe_candidates(query: str, *, connection_kind: str, language: str = "") -> list[ActionPlanCandidate]:
    clean_kind = normalize_connection_kind(connection_kind)
    manifests, _ = _load_stored_recipe_manifests()
    rows = build_stored_recipe_action_candidates(
        manifests,
        query=query,
        connection_kind=clean_kind,
        language=language,
        candidate_factory=ActionPlanCandidate,
        normalize_capability=normalize_capability,
        intent_score=intent_score,
        safe_list=_safe_list,
        localized_text=_localized_text,
    )
    rows.sort(key=_candidate_selection_sort_key)
    return rows[:8]


def _load_learned_recipe_records() -> list[dict[str, Any]]:
    if str(os.getenv("ARIA_ENABLE_LEARNED_RECIPE_CANDIDATES", "") or "").strip().lower() not in {"1", "true", "yes", "on"}:
        return []
    rows: list[dict[str, Any]] = []
    for row in load_learned_recipe_store_entries():
        if not isinstance(row, dict):
            continue
        normalized = normalize_learned_recipe_store_entry(dict(row or {}))
        promotion_state = str(normalized.get("promotion_state", "") or "").strip().lower()
        stored_recipe_id = str(normalized.get("stored_recipe_id", "") or "").strip()
        if promotion_state != "promoted" or not stored_recipe_id:
            continue
        if learned_recipe_promotion_blockers(normalized):
            continue
        rows.append(normalized)
    return rows


def _learned_recipe_candidates(query: str, *, connection_kind: str, language: str = "") -> list[ActionPlanCandidate]:
    clean_kind = normalize_connection_kind(connection_kind)
    records = [
        normalize_learned_recipe_store_entry(dict(item or {}), fallback_connection_kind=clean_kind)
        for item in list(_load_learned_recipe_records() or [])
        if isinstance(item, dict)
    ]
    rows = build_learned_recipe_action_candidates(
        records,
        query=query,
        connection_kind=clean_kind,
        language=language,
        candidate_factory=ActionPlanCandidate,
        normalize_capability=normalize_capability,
        intent_score=intent_score,
        safe_list=_safe_list,
        localized_text=_localized_text,
    )
    rows.sort(key=_candidate_selection_sort_key)
    return rows[:8]


def bounded_action_candidates_for_target(
    query: str,
    *,
    connection_kind: str,
    language: str = "",
) -> list[ActionPlanCandidate]:
    clean_kind = normalize_connection_kind(connection_kind)
    if not clean_kind:
        return []
    rows = (
        _template_candidates(query, connection_kind=clean_kind, language=language)
        + _recipe_candidates(query, connection_kind=clean_kind, language=language)
        + _learned_recipe_candidates(query, connection_kind=clean_kind, language=language)
    )
    rows.sort(key=_candidate_selection_sort_key)
    seen: set[tuple[str, str]] = set()
    result: list[ActionPlanCandidate] = []
    for row in rows:
        if row.key in seen:
            continue
        seen.add(row.key)
        result.append(row)
    return result[:10]


def build_action_planner_input_set(
    query: str,
    *,
    connection_kind: str,
    connection_ref: str = "",
    language: str = "",
    notes: list[str] | None = None,
) -> PlannerInputSet:
    candidates = bounded_action_candidates_for_target(query, connection_kind=connection_kind, language=language)
    planner_candidates: list[PlannerCandidate] = [planner_candidate_from_action(candidate) for candidate in candidates]
    return build_planner_input_set(
        query=query,
        language=language,
        preferred_connection_kind=connection_kind,
        connection_ref=connection_ref,
        action_candidates=planner_candidates,
        notes=notes,
    )


def _heuristic_action_decision(query: str, candidates: list[ActionPlanCandidate]) -> tuple[ActionPlanCandidate | None, str, bool, str]:
    if not candidates:
        return None, "", False, ""
    if len(candidates) == 1:
        return candidates[0], "high", False, "single_candidate"

    ordered = sorted(candidates, key=_candidate_selection_sort_key)
    top = ordered[0]
    second = ordered[1]
    top_score = float(top.score or 0.0)
    second_score = float(second.score or 0.0)

    if top_score <= 0 and second_score <= 0:
        return top, "low", True, "no_signal"
    return top, "low", True, "ranking_hint_needs_llm"


def _recover_llm_candidate_selection(
    *,
    candidate_kind: str,
    candidate_id: str,
    intent: str,
    candidates: list[ActionPlanCandidate],
    heuristic_candidate: ActionPlanCandidate | None = None,
    heuristic_ask_user: bool = False,
) -> tuple[ActionPlanCandidate | None, str]:
    clean_kind = normalize_action_candidate_kind(candidate_kind)
    clean_id = str(candidate_id or "").strip()
    clean_intent = str(intent or "").strip().lower()
    normalized_id = _normalize_candidate_token(clean_id)

    if clean_kind and normalized_id:
        same_kind = [candidate for candidate in candidates if normalize_action_candidate_kind(candidate.candidate_kind) == clean_kind]
        exact_normalized = [
            candidate
            for candidate in same_kind
            if _normalize_candidate_token(candidate.candidate_id) == normalized_id
        ]
        if len(exact_normalized) == 1:
            return exact_normalized[0], "normalized_candidate_id"
        fuzzy = [
            candidate
            for candidate in same_kind
            if normalized_id in _normalize_candidate_token(candidate.candidate_id)
            or _normalize_candidate_token(candidate.candidate_id) in normalized_id
        ]
        if len(fuzzy) == 1:
            return fuzzy[0], "fuzzy_candidate_id"

    if clean_intent:
        intent_matches = [
            candidate
            for candidate in candidates
            if (not clean_kind or normalize_action_candidate_kind(candidate.candidate_kind) == clean_kind) and candidate.intent == clean_intent
        ]
        if len(intent_matches) == 1:
            return intent_matches[0], "intent_match"
        if len(intent_matches) > 1:
            ordered = sorted(intent_matches, key=_candidate_selection_sort_key)
            top = ordered[0]
            second = ordered[1]
            if float(top.score or 0.0) - float(second.score or 0.0) >= 1.0:
                return top, "intent_clear_lead"

    if heuristic_candidate is not None and not heuristic_ask_user:
        if (not clean_kind or normalize_action_candidate_kind(heuristic_candidate.candidate_kind) == clean_kind) and (
            not clean_intent or heuristic_candidate.intent == clean_intent
        ):
            return heuristic_candidate, "heuristic_clear_fallback"

    return None, ""


def _candidate_rows_for_prompt(candidates: list[ActionPlanCandidate], language: str = "") -> list[str]:
    rows: list[str] = []
    for index, candidate in enumerate(candidates, start=1):
        role = str(candidate.candidate_role or "").strip()
        label = f"{candidate.candidate_kind}/{candidate.candidate_id}"
        if role:
            label = f"{label} [{role}]"
        parts = [f"{index}. {label}", f"title={candidate.title or '-'}", f"intent={candidate.intent or '-'}", f"connection_kind={candidate.connection_kind or '-'}"]
        if candidate.capability:
            parts.append(f"capability={candidate.capability}")
        if candidate.summary:
            parts.append(f"summary={candidate.summary}")
        preview = _derive_candidate_preview(candidate, "", language)
        if preview:
            parts.append(f"preview={preview}")
        if candidate.router_keywords:
            parts.append("router_keywords=" + ", ".join(candidate.router_keywords))
        parts.extend(recipe_candidate_prompt_parts(candidate))
        rows.append(" | ".join(parts))
    return rows


def _candidate_debug_label(candidate: ActionPlanCandidate, language: str = "") -> str:
    role = str(candidate.candidate_role or "").strip()
    if role:
        return candidate_debug_label(role, language)
    return _candidate_kind_label(candidate.candidate_kind, language) or str(candidate.candidate_kind or "").strip()


def _derive_candidate_preview(candidate: ActionPlanCandidate, query: str, language: str = "") -> str:
    return derive_candidate_preview(
        candidate,
        query,
        language=language,
        extract_command_text=_extract_command_text,
        extract_remote_path=_extract_remote_path,
        extract_mail_search_text=_extract_mail_search_text,
        extract_message_text=_extract_message_text,
        extract_mqtt_topic_text=_extract_mqtt_topic_text,
        extract_website_group_text=_extract_website_group_text,
        extract_calendar_range_text=_extract_calendar_range_text,
        extract_calendar_search_text=_extract_calendar_search_text,
        base_candidate_preview=_base_candidate_preview,
    )


def _apply_candidate_labels(
    payload: dict[str, Any],
    candidate: ActionPlanCandidate,
    query: str,
    *,
    language: str = "",
    connection_ref: str = "",
    target_context: str = "",
) -> str:
    return apply_candidate_labels(
        payload,
        candidate,
        query,
        language=language,
        connection_ref=connection_ref,
        target_context=target_context,
        extract_command_text=_extract_command_text,
        extract_remote_path=_extract_remote_path,
        extract_mail_search_text=_extract_mail_search_text,
        extract_message_text=_extract_message_text,
        extract_mqtt_topic_text=_extract_mqtt_topic_text,
        extract_website_group_text=_extract_website_group_text,
        extract_calendar_range_text=_extract_calendar_range_text,
        extract_calendar_search_text=_extract_calendar_search_text,
        base_candidate_preview=_base_candidate_preview,
    )


def _build_serialized_candidate(
    candidate: ActionPlanCandidate,
    query: str,
    *,
    language: str = "",
    connection_ref: str = "",
    target_context: str = "",
) -> dict[str, Any]:
    return build_serialized_candidate(
        candidate,
        query,
        language=language,
        connection_ref=connection_ref,
        target_context=target_context,
        execution_state=_execution_state,
        execution_state_label=_execution_state_label,
        extract_command_text=_extract_command_text,
        extract_remote_path=_extract_remote_path,
        extract_mail_search_text=_extract_mail_search_text,
        extract_message_text=_extract_message_text,
        extract_mqtt_topic_text=_extract_mqtt_topic_text,
        extract_website_group_text=_extract_website_group_text,
        extract_calendar_range_text=_extract_calendar_range_text,
        extract_calendar_search_text=_extract_calendar_search_text,
        base_candidate_preview=_base_candidate_preview,
    )


def _sort_serialized_candidates(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sort_serialized_candidates(rows, candidate_kind_priority=_candidate_kind_priority)


def _candidate_payload(candidate: ActionPlanCandidate) -> dict[str, Any]:
    return candidate_payload(candidate)


def _candidate_kind_label(kind: str, language: str = "") -> str:
    return core_candidate_kind_label(kind, language)


def _input_key_label(key: str, language: str = "") -> str:
    return core_input_key_label(key, language)


def _clarifying_question(candidate: ActionPlanCandidate, missing_input: str, language: str = "") -> str:
    return clarifying_question(candidate, missing_input, language)


def _suggested_follow_up_prompt(
    query: str,
    candidate: ActionPlanCandidate,
    *,
    connection_ref: str,
    missing_input: str = "",
    language: str = "",
) -> str:
    follow_up_candidate = ActionPlanCandidate(
        candidate_kind=candidate.candidate_kind,
        candidate_id=candidate.candidate_id,
        plan_class=candidate.plan_class,
        title=candidate.title,
        summary=candidate.summary,
        intent=candidate.intent,
        connection_kind=candidate.connection_kind,
        capability=candidate.capability,
        preview=candidate.preview,
        inputs=dict(candidate.inputs or {}),
        router_keywords=list(candidate.router_keywords or []),
        source=candidate.source,
        candidate_role=candidate.candidate_role,
        recipe_scope=dict(candidate.recipe_scope or {}),
        recipe_origin=candidate.recipe_origin,
        experience_count=int(candidate.experience_count or 0),
        last_success_at=candidate.last_success_at,
        promotion_state=candidate.promotion_state,
        promotion_hint=candidate.promotion_hint,
        score=float(candidate.score or 0.0),
    )
    follow_up_candidate.inputs.setdefault("behavior_profile", action_template_behavior_profile(candidate.candidate_id))
    return core_suggested_follow_up_prompt(
        query,
        candidate=follow_up_candidate,
        connection_ref=connection_ref,
        missing_input=missing_input,
        language=language,
        localized_text=_localized_text,
        extract_remote_path=_extract_remote_path,
        extract_message_text=_extract_message_text,
        extract_mail_search_text=_extract_mail_search_text,
        extract_mqtt_topic_text=_extract_mqtt_topic_text,
        extract_calendar_range_text=_extract_calendar_range_text,
        extract_website_group_text=_extract_website_group_text,
    )


async def debug_bounded_action_plan_decision(
    query: str,
    *,
    llm_client: Any | None,
    routing_decision: dict[str, Any] | None = None,
    language: str = "",
) -> dict[str, Any]:
    clean_query = str(query or "").strip()
    decision = dict(routing_decision or {})
    if not bool(decision.get("found")):
        return _result_payload(
            available=True,
            used=False,
            status="warn",
            message=_planner_text(language, "dry_run_no_routing_target", "Action dry-run skipped: no routing target was resolved first."),
        )

    connection_kind = normalize_connection_kind(str(decision.get("kind", "") or ""))
    connection_ref = str(decision.get("ref", "") or "").strip()
    target_context = _target_context(connection_kind, connection_ref)
    target_reason = str(decision.get("reason", "") or "").strip()
    routing_requires_confirmation = bool(
        decision.get("routing_ask_user")
        or decision.get("llm_ask_user")
        or decision.get("target_ask_user")
    )
    candidates = bounded_action_candidates_for_target(clean_query, connection_kind=connection_kind, language=language)
    serialized_candidates = _sort_serialized_candidates(
        [
            _build_serialized_candidate(
                candidate,
                clean_query,
                language=language,
                connection_ref=connection_ref,
            )
            for candidate in candidates
        ]
    )
    if not candidates:
        return _result_payload(
            available=True,
            used=False,
            status="warn",
            message=_planner_text(
                language,
                "dry_run_no_candidates",
                "Action dry-run skipped: no compatible templates or recipes were found for {target}.",
                target=f"{connection_kind}/{connection_ref}",
            ),
            planner_source="catalog",
            planner_source_label=_planner_source_label("catalog", language),
            candidate_count=0,
            candidates=serialized_candidates,
            target_context=target_context,
            target_reason=target_reason,
        )

    valid_by_key = {candidate.key: candidate for candidate in candidates}
    heuristic_candidate, heuristic_confidence, heuristic_ask_user, heuristic_reason = _heuristic_action_decision(clean_query, candidates)
    if llm_client is None:
        if heuristic_candidate is not None and not heuristic_ask_user:
            payload = _candidate_payload(heuristic_candidate)
            missing_input = _apply_candidate_labels(
                payload,
                heuristic_candidate,
                clean_query,
                language=language,
                target_context=target_context,
            )
            payload["execution_state"] = _execution_state(ask_user=bool(missing_input), missing_input=missing_input)
            payload["execution_state_label"] = _execution_state_label(payload["execution_state"], language)
            if missing_input:
                payload["reason"] = _missing_required_reason(missing_input, language)
                return _result_payload(
                    available=False,
                    used=False,
                    status="warn",
                    message=_planner_text(language, "dry_run_recommends_followup", "Action dry-run recommends asking the user before execution."),
                    decision=payload,
                    confidence="low",
                    confidence_label=_confidence_label("low", language),
                    ask_user=True,
                    execution_state=_execution_state(ask_user=True, missing_input=missing_input),
                    execution_state_label=_execution_state_label(_execution_state(ask_user=True, missing_input=missing_input), language),
                    planner_source="heuristic",
                    planner_source_label=_planner_source_label("heuristic", language),
                    candidate_count=len(candidates),
                    candidates=serialized_candidates,
                    target_context=target_context,
                    target_reason=target_reason,
                    missing_input=missing_input,
                    missing_input_label=_input_key_label(missing_input, language),
                    clarifying_question=_clarifying_question(heuristic_candidate, missing_input, language),
                    example_prompt=_suggested_follow_up_prompt(clean_query, heuristic_candidate, connection_ref=connection_ref, missing_input=missing_input, language=language),
                )
            effective_ask_user = routing_requires_confirmation
            payload["reason"] = (
                _routing_target_confirmation_reason(language)
                if routing_requires_confirmation
                else payload["preview"] or heuristic_candidate.title or _heuristic_reason_text(heuristic_reason, language)
            )
            return _result_payload(
                available=False,
                used=False,
                status="warn" if effective_ask_user else "ok",
                message=(
                    _planner_text(
                        language,
                        "heuristic_target_confirmation_required",
                        "A heuristic action candidate was inferred, but the target should be confirmed before execution.",
                    )
                    if effective_ask_user
                    else _planner_text(
                        language,
                        "heuristic_candidate_inferred",
                        "Heuristic {candidate_label} inferred: {candidate_id}.",
                        candidate_label=_candidate_debug_label(heuristic_candidate, language),
                        candidate_id=heuristic_candidate.candidate_id,
                    )
                ),
                decision=payload,
                confidence=heuristic_confidence or "medium",
                confidence_label=_confidence_label(heuristic_confidence or "medium", language),
                ask_user=effective_ask_user,
                execution_state=_execution_state(ask_user=effective_ask_user),
                execution_state_label=_execution_state_label(_execution_state(ask_user=effective_ask_user), language),
                planner_source="heuristic",
                planner_source_label=_planner_source_label("heuristic", language),
                candidate_count=len(candidates),
                candidates=serialized_candidates,
                target_context=target_context,
                target_reason=target_reason,
            )
        if heuristic_candidate is not None and heuristic_ask_user:
            payload = _candidate_payload(heuristic_candidate)
            missing_input = _apply_candidate_labels(
                payload,
                heuristic_candidate,
                clean_query,
                language=language,
                target_context=target_context,
            )
            payload["reason"] = (
                _missing_required_reason(missing_input, language)
                if missing_input
                else _routing_target_confirmation_reason(language)
                if routing_requires_confirmation
                else _heuristic_reason_text(heuristic_reason, language) or payload["preview"] or heuristic_candidate.title
            )
            payload["execution_state"] = _execution_state(ask_user=True, missing_input=missing_input)
            payload["execution_state_label"] = _execution_state_label(payload["execution_state"], language)
            return _result_payload(
                available=False,
                used=False,
                status="warn",
                message=_planner_text(language, "dry_run_recommends_followup", "Action dry-run recommends asking the user before execution."),
                decision=payload,
                confidence=heuristic_confidence or "low",
                confidence_label=_confidence_label(heuristic_confidence or "low", language),
                ask_user=True,
                execution_state=_execution_state(ask_user=True, missing_input=missing_input),
                execution_state_label=_execution_state_label(_execution_state(ask_user=True, missing_input=missing_input), language),
                planner_source="heuristic",
                planner_source_label=_planner_source_label("heuristic", language),
                candidate_count=len(candidates),
                candidates=serialized_candidates,
                target_context=target_context,
                target_reason=target_reason,
                missing_input=missing_input,
                missing_input_label=_input_key_label(missing_input, language),
                clarifying_question=_clarifying_question(heuristic_candidate, missing_input, language),
                example_prompt=_suggested_follow_up_prompt(clean_query, heuristic_candidate, connection_ref=connection_ref, missing_input=missing_input, language=language),
            )
        return _result_payload(
            available=False,
            used=False,
            status="warn",
            message=_planner_text(language, "dry_run_no_llm_client", "Action dry-run unavailable: no LLM client is configured."),
            execution_state="",
            execution_state_label="",
            planner_source="heuristic",
            planner_source_label=_planner_source_label("heuristic", language),
            candidate_count=len(candidates),
            candidates=serialized_candidates,
            target_context=target_context,
            target_reason=target_reason,
        )

    system_prompt = (
        "You are ARIA's bounded action planner for admin/debug dry-runs. "
        "A routing target is already resolved. Choose only from the provided action candidates. "
        "Prefer safe built-in templates for generic requests like health checks, file reads, or sending messages. "
        "Prefer an existing stored recipe candidate when it clearly matches the request and target. "
        "Stored and learned recipe candidates use candidate_kind='recipe' in the JSON contract. "
        f"Legacy payloads may still send candidate_kind='{LEGACY_SKILL_CANDIDATE_KIND}', which should be treated as 'recipe'. "
        "If the request is ambiguous or the action still needs clarification, set ask_user to true. "
        "Respond only as JSON in this format: "
        '{"candidate_kind":"template|recipe","candidate_id":"<id or empty>","intent":"<intent or empty>",'
        '"confidence":"high|medium|low","ask_user":true|false,"reason":"short explanation"}.'
    )
    user_prompt = "\n".join(
        [
            f"User request: {str(query or '').strip()}",
            f"Language: {str(language or '').strip().lower() or '-'}",
            f"Resolved target: {connection_kind}/{connection_ref}",
            f"Routing reason: {str(decision.get('reason', '') or '-').strip()}",
            "",
            "Bounded action candidates:",
            *_candidate_rows_for_prompt(candidates, language),
        ]
    )
    try:
        response = await llm_client.chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            source="action_plan_debug",
            operation="action_plan_debug",
        )
    except Exception as exc:
        return _result_payload(
            available=True,
            used=True,
            status="error",
            message=_planner_text(language, "llm_planner_failed", "LLM action planner failed: {error}", error=exc),
            execution_state="",
            execution_state_label="",
            planner_source="llm",
            planner_source_label=_planner_source_label("llm", language),
            candidate_count=len(candidates),
            candidates=serialized_candidates,
            target_context=target_context,
            target_reason=target_reason,
        )

    raw_response = str(getattr(response, "content", "") or "").strip()
    payload = _extract_json_object(raw_response) or {}
    candidate_kind = normalize_action_candidate_kind(str(payload.get("candidate_kind", "") or "").strip().lower())
    candidate_id = str(payload.get("candidate_id", "") or "").strip()
    intent = str(payload.get("intent", "") or "").strip()
    confidence = str(payload.get("confidence", "") or "").strip().lower()
    ask_user = bool(payload.get("ask_user", False))
    reason = str(payload.get("reason", "") or "").strip()
    if confidence not in {"high", "medium", "low"}:
        return _result_payload(
            available=True,
            used=True,
            status="warn",
            message=_planner_text(language, "llm_invalid_confidence", "LLM action planner returned invalid confidence."),
            execution_state="",
            execution_state_label="",
            planner_source="llm",
            planner_source_label=_planner_source_label("llm", language),
            candidate_count=len(candidates),
            candidates=serialized_candidates,
            target_context=target_context,
            target_reason=target_reason,
            raw_response=raw_response[:500],
        )

    candidate = valid_by_key.get((candidate_kind, candidate_id))
    if not candidate:
        candidate, recovery_reason = _recover_llm_candidate_selection(
            candidate_kind=candidate_kind,
            candidate_id=candidate_id,
            intent=intent,
            candidates=candidates,
            heuristic_candidate=heuristic_candidate,
            heuristic_ask_user=heuristic_ask_user,
        )
        if not candidate:
            return _result_payload(
                available=True,
                used=True,
                status="warn",
                message=_planner_text(language, "llm_out_of_bounds_candidate", "LLM action planner chose a candidate outside the bounded set."),
                confidence=confidence,
                confidence_label=_confidence_label(confidence, language),
                ask_user=ask_user,
                execution_state=_execution_state(ask_user=ask_user),
                execution_state_label=_execution_state_label(_execution_state(ask_user=ask_user), language),
                planner_source="llm",
                planner_source_label=_planner_source_label("llm", language),
                candidate_count=len(candidates),
                candidates=serialized_candidates,
                target_context=target_context,
                target_reason=target_reason,
                raw_response=raw_response[:500],
            )
        payload = _candidate_payload(candidate)
        payload["intent"] = intent or candidate.intent
        missing_input = _apply_candidate_labels(
            payload,
            candidate,
            clean_query,
            language=language,
            target_context=target_context,
        )
        if missing_input:
            ask_user = True
            confidence = "low" if confidence == "high" else confidence or "low"
        elif routing_requires_confirmation:
            ask_user = True
        payload["execution_state"] = _execution_state(ask_user=ask_user or confidence == "low", missing_input=missing_input)
        payload["execution_state_label"] = _execution_state_label(payload["execution_state"], language)
        payload["reason"] = (
            _missing_required_reason(missing_input, language)
            if missing_input
            else _routing_target_confirmation_reason(language)
            if routing_requires_confirmation
            else reason
            or _planner_text(
                language,
                "llm_recovery_reason",
                "LLM selection was recovered via bounded recovery ({recovery_reason}).",
                recovery_reason=recovery_reason,
            )
        )
        return _result_payload(
            available=True,
            used=True,
            status="ok" if not ask_user and confidence in {"high", "medium"} else "warn",
            message=(
                _planner_text(
                    language,
                    "llm_normalized_target_confirmation_required",
                    "The LLM action planner was normalized, but the target should be confirmed before execution.",
                )
                if routing_requires_confirmation
                else _planner_text(
                    language,
                    "llm_normalized_via_recovery",
                    "LLM action planner was normalized to {candidate_label} {candidate_id} via bounded recovery.",
                    candidate_label=_candidate_debug_label(candidate, language),
                    candidate_id=candidate.candidate_id,
                )
            ),
            decision=payload,
            confidence=confidence,
            confidence_label=_confidence_label(confidence, language),
            ask_user=ask_user,
            execution_state=_execution_state(ask_user=ask_user or confidence == "low", missing_input=missing_input),
            execution_state_label=_execution_state_label(_execution_state(ask_user=ask_user or confidence == "low", missing_input=missing_input), language),
            planner_source="llm",
            planner_source_label=_planner_source_label("llm", language),
            candidate_count=len(candidates),
            candidates=serialized_candidates,
            target_context=target_context,
            target_reason=target_reason,
            missing_input=missing_input,
            missing_input_label=_input_key_label(missing_input, language),
            clarifying_question=_clarifying_question(candidate, missing_input, language) if ask_user else "",
            example_prompt=_suggested_follow_up_prompt(clean_query, candidate, connection_ref=connection_ref, missing_input=missing_input, language=language) if ask_user else "",
            raw_response=raw_response[:500],
        )

    payload = _candidate_payload(candidate)
    payload["intent"] = intent or candidate.intent
    missing_input = _apply_candidate_labels(
        payload,
        candidate,
        clean_query,
        language=language,
        target_context=target_context,
    )
    if missing_input:
        ask_user = True
        confidence = "low" if confidence == "high" else confidence or "low"
    elif routing_requires_confirmation:
        ask_user = True
    payload["execution_state"] = _execution_state(ask_user=ask_user or confidence == "low", missing_input=missing_input)
    payload["execution_state_label"] = _execution_state_label(payload["execution_state"], language)
    payload["reason"] = (
        _missing_required_reason(missing_input, language)
        if missing_input
        else _routing_target_confirmation_reason(language)
        if routing_requires_confirmation
        else reason or payload["preview"] or candidate.title
    )
    message = _planner_text(
        language,
        "llm_selected_candidate",
        "LLM action planner selected {candidate_label} {candidate_id}.",
        candidate_label=_candidate_debug_label(candidate, language),
        candidate_id=candidate.candidate_id,
    )
    if routing_requires_confirmation:
        message = _planner_text(
            language,
            "llm_found_action_target_confirmation_required",
            "The LLM action planner found a suitable action, but the target should be confirmed before execution.",
        )
    elif ask_user or confidence == "low":
        message = _planner_text(language, "llm_recommends_followup", "LLM action planner recommends asking the user before execution.")
    return _result_payload(
        available=True,
        used=True,
        status="ok" if not ask_user and confidence in {"high", "medium"} else "warn",
        message=message,
        decision=payload,
        confidence=confidence,
        confidence_label=_confidence_label(confidence, language),
        ask_user=ask_user,
        execution_state=_execution_state(ask_user=ask_user or confidence == "low", missing_input=missing_input),
        execution_state_label=_execution_state_label(_execution_state(ask_user=ask_user or confidence == "low", missing_input=missing_input), language),
        planner_source="llm",
        planner_source_label=_planner_source_label("llm", language),
        candidate_count=len(candidates),
        candidates=serialized_candidates,
        target_context=target_context,
        target_reason=target_reason,
        missing_input=missing_input,
        missing_input_label=_input_key_label(missing_input, language),
        clarifying_question=_clarifying_question(candidate, missing_input, language) if ask_user else "",
        example_prompt=_suggested_follow_up_prompt(clean_query, candidate, connection_ref=connection_ref, missing_input=missing_input, language=language) if ask_user else "",
        raw_response=raw_response[:500],
    )
