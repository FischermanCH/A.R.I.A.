from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from aria.core.behavior_families import behavior_family_id_for
from aria.core.behavior_families import file_operation_mode
from aria.core.behavior_families import mailbox_access_mode
from aria.core.behavior_families import request_target_mode
from aria.core.behavior_families import score_file_operation_query
from aria.core.behavior_families import score_mailbox_access_query
from aria.core.behavior_families import score_request_target_query
from aria.core.behavior_families import score_source_lookup_query
from aria.core.behavior_families import source_lookup_mode
from aria.core.connection_catalog import connection_routing_spec, normalize_connection_kind


_SCORING_LEXICON_PATH = Path(__file__).resolve().parents[1] / "lexicons" / "action_planner_scoring.json"


def _load_scoring_lexicon() -> dict[str, object]:
    try:
        raw = json.loads(_SCORING_LEXICON_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not load action planner scoring lexicon: {_SCORING_LEXICON_PATH}") from exc
    return raw if isinstance(raw, dict) else {}


def _tuple_map(section: str) -> dict[str, tuple[str, ...]]:
    raw_section = _SCORING_LEXICON.get(section, {})
    if not isinstance(raw_section, dict):
        return {}
    rows: dict[str, tuple[str, ...]] = {}
    for key, raw_values in raw_section.items():
        if not isinstance(raw_values, list):
            continue
        rows[str(key)] = tuple(str(value).strip().lower() for value in raw_values if str(value).strip())
    return rows


_SCORING_LEXICON = _load_scoring_lexicon()
INTENT_HINTS: dict[str, tuple[str, ...]] = _tuple_map("intent_hints")
ACTION_PREFERENCE_HINTS: dict[str, tuple[str, ...]] = _tuple_map("action_preference_hints")
_TEMPLATE_PROFILE_TERMS: dict[str, tuple[str, ...]] = _tuple_map("template_profile_terms")


def intent_score(query: str, intent: str, router_keywords: list[str]) -> float:
    lowered = str(query or "").strip().lower()
    if not lowered:
        return 0.0
    score = 0.0
    for token in INTENT_HINTS.get(intent, ()):
        if token in lowered:
            score += 2.0
    for keyword in router_keywords:
        clean = str(keyword or "").strip().lower()
        if clean and clean in lowered:
            score += 3.0
    return score


def template_specific_score(
    candidate_id: str,
    query: str,
    *,
    action_template_behavior_profile: Callable[[str], str],
    extract_quoted_text: Callable[[str], str],
    extract_remote_path: Callable[[str], str],
    extract_command_text: Callable[[str], str],
    extract_mqtt_topic_text: Callable[[str], str],
) -> float:
    lowered = str(query or "").strip().lower()
    if not lowered:
        return 0.0
    profile = action_template_behavior_profile(candidate_id)
    score = 0.0
    has_quoted_text = bool(extract_quoted_text(query))
    has_remote_path = bool(extract_remote_path(query))
    if profile == "ssh_run_command":
        if extract_command_text(query):
            score += 4.0
        elif any(token in lowered for token in _TEMPLATE_PROFILE_TERMS.get("ssh_status_like", ())):
            score += 3.0
    elif behavior_family_id_for(behavior_profile=profile) == "file_operation":
        score += score_file_operation_query(
            file_operation_mode(behavior_profile=profile),
            query,
            has_remote_path=has_remote_path,
            has_quoted_text=has_quoted_text,
        )
    elif behavior_family_id_for(behavior_profile=profile) == "source_lookup":
        score += score_source_lookup_query(source_lookup_mode(behavior_profile=profile), query)
    elif behavior_family_id_for(behavior_profile=profile) == "mailbox_access":
        score += score_mailbox_access_query(
            mailbox_access_mode(behavior_profile=profile),
            query,
            has_quoted_text=has_quoted_text,
        )
    elif behavior_family_id_for(behavior_profile=profile) == "request_target":
        score += score_request_target_query(request_target_mode(behavior_profile=profile), query)
    elif profile == "discord_send_message":
        if any(token in lowered for token in _TEMPLATE_PROFILE_TERMS.get("discord_send", ())):
            score += 4.0
        if has_quoted_text:
            score += 1.0
    elif profile == "webhook_send_message":
        if any(token in lowered for token in _TEMPLATE_PROFILE_TERMS.get("webhook_send", ())):
            score += 4.0
        if has_quoted_text:
            score += 1.0
    elif profile == "email_send_message":
        if any(token in lowered for token in _TEMPLATE_PROFILE_TERMS.get("email_send", ())):
            score += 4.0
        if has_quoted_text:
            score += 1.0
    elif profile == "mqtt_publish_message":
        if any(token in lowered for token in _TEMPLATE_PROFILE_TERMS.get("mqtt_publish", ())):
            score += 4.0
        if extract_mqtt_topic_text(query):
            score += 1.0
        if has_quoted_text:
            score += 1.0
    elif profile == "calendar_read_events":
        if any(token in lowered for token in _TEMPLATE_PROFILE_TERMS.get("calendar_read_topic", ())):
            score += 4.0
        if any(token in lowered for token in _TEMPLATE_PROFILE_TERMS.get("calendar_read", ())):
            score += 2.0
    return score


def routing_spec_keywords(connection_kind: str, *, safe_list: Callable[[object], list[str]]) -> list[str]:
    spec = connection_routing_spec(connection_kind)
    return safe_list(list(spec.supported_actions or []) + list(spec.language_hints or []), limit=24)


def template_router_keywords(raw: dict[str, object], connection_kind: str, *, safe_list: Callable[[object], list[str]]) -> list[str]:
    local_keywords = safe_list(raw.get("router_keywords", []), limit=16)
    spec_keywords = routing_spec_keywords(connection_kind, safe_list=safe_list)
    return [row for row in dict.fromkeys(local_keywords + spec_keywords) if row]


def routing_preference_profiles(query: str, connection_kind: str) -> list[str]:
    clean_kind = normalize_connection_kind(connection_kind)
    spec = connection_routing_spec(clean_kind)
    profiles: list[str] = []
    if spec.preferred_action_candidates.get("default"):
        profiles.append("default")
    lowered = str(query or "").strip().lower()
    if not lowered:
        return profiles
    for profile, hints in ACTION_PREFERENCE_HINTS.items():
        preferred_ids = spec.preferred_action_candidates.get(profile, [])
        if preferred_ids and any(token in lowered for token in hints):
            profiles.append(profile)
    return list(dict.fromkeys(profiles))


def routing_preference_bonus(candidate_id: str, query: str, connection_kind: str) -> float:
    spec = connection_routing_spec(connection_kind)
    profiles = routing_preference_profiles(query, connection_kind)
    clean_candidate_id = str(candidate_id or "").strip().lower()
    bonus = 0.0
    for profile_index, profile in enumerate(profiles):
        preferred_ids = [str(item or "").strip().lower() for item in spec.preferred_action_candidates.get(profile, []) if str(item or "").strip()]
        for candidate_index, preferred_id in enumerate(preferred_ids):
            if clean_candidate_id != preferred_id:
                continue
            bonus = max(bonus, 0.9 - (profile_index * 0.1) - (candidate_index * 0.05))
    return max(0.0, bonus)
