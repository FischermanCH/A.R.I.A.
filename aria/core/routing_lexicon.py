from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

ROUTING_LEXICON_FIELDS: tuple[str, ...] = (
    "memory_store_keywords",
    "memory_recall_keywords",
    "memory_store_prefixes",
    "memory_recall_cleanup_keywords",
    "memory_forget_keywords",
    "web_search_keywords",
    "web_search_prefixes",
    "web_search_cleanup_keywords",
    "skill_status_keywords",
    "skill_status_patterns",
    "skill_status_skill_terms",
    "skill_status_status_terms",
)

DEFAULT_ROUTING_LANGUAGE = "de"
_ROUTING_LEXICON_PATH = Path(__file__).resolve().parents[1] / "lexicons" / "routing.json"


@dataclass(frozen=True)
class CapabilityRoutingLexicon:
    write_terms: tuple[str, ...]
    read_terms: tuple[str, ...]
    feed_read_terms: tuple[str, ...]
    explicit_web_search_terms: tuple[str, ...]
    webhook_send_terms: tuple[str, ...]
    discord_send_terms: tuple[str, ...]
    api_terms: tuple[str, ...]
    api_action_terms: tuple[str, ...]
    email_send_terms: tuple[str, ...]
    email_send_action_terms: tuple[str, ...]
    mail_read_terms: tuple[str, ...]
    mail_search_terms: tuple[str, ...]
    mqtt_terms: tuple[str, ...]
    mqtt_action_terms: tuple[str, ...]
    ssh_command_terms: tuple[str, ...]
    webhook_action_terms: tuple[str, ...]
    discord_action_terms: tuple[str, ...]
    list_terms: tuple[str, ...]
    remote_terms: tuple[str, ...]
    ssh_hints: tuple[str, ...]
    sftp_hints: tuple[str, ...]
    smb_hints: tuple[str, ...]
    rss_hints: tuple[str, ...]
    webhook_hints: tuple[str, ...]
    discord_hints: tuple[str, ...]
    api_hints: tuple[str, ...]
    email_hints: tuple[str, ...]
    imap_hints: tuple[str, ...]
    mqtt_hints: tuple[str, ...]
    feed_subject_ignore_terms: tuple[str, ...]
    generic_connection_ref_tokens: tuple[str, ...]
    requested_connection_ref_ignore_terms: tuple[str, ...]
    discord_requested_ref_terms: tuple[str, ...]
    webhook_requested_ref_terms: tuple[str, ...]
    api_requested_ref_terms: tuple[str, ...]
    email_requested_ref_terms: tuple[str, ...]
    imap_requested_ref_terms: tuple[str, ...]
    mqtt_requested_ref_terms: tuple[str, ...]
    ssh_requested_ref_terms: tuple[str, ...]
    ssh_requested_ref_prepositions: tuple[str, ...]
    rss_requested_ref_terms: tuple[str, ...]
    ssh_natural_disk_terms: tuple[str, ...]
    ssh_natural_uptime_terms: tuple[str, ...]
    ssh_natural_online_terms: tuple[str, ...]
    mail_search_after_terms: tuple[str, ...]
    mqtt_topic_terms: tuple[str, ...]
    connection_kind_priority: tuple[str, ...]


def _dedupe_preserving_order(values: Iterable[str]) -> list[str]:
    rows: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value)
        if not text or text in seen:
            continue
        seen.add(text)
        rows.append(text)
    return rows


def _dedupe_tuple_preserving_order(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(_dedupe_preserving_order(values))


def _read_routing_lexicon_payload() -> dict[str, Any]:
    try:
        raw = json.loads(_ROUTING_LEXICON_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not load routing lexicon file: {_ROUTING_LEXICON_PATH}") from exc
    if not isinstance(raw, dict):
        raise RuntimeError(f"Routing lexicon file must contain a JSON object: {_ROUTING_LEXICON_PATH}")
    return raw


def _mapping_section(payload: Mapping[str, Any], section: str) -> dict[str, Any]:
    raw = payload.get(section, {})
    if not isinstance(raw, dict):
        return {}
    return {str(key).strip().lower(): value for key, value in raw.items() if str(key).strip()}


def _language_key(language: str | None, available: Mapping[str, Any]) -> str:
    fallback = str(_LEXICON_PAYLOAD.get("default_language") or DEFAULT_ROUTING_LANGUAGE).strip().lower()
    requested = str(language or fallback).strip().lower() or fallback
    if requested in available:
        return requested
    if fallback in available:
        return fallback
    return DEFAULT_ROUTING_LANGUAGE


_LEXICON_PAYLOAD = _read_routing_lexicon_payload()
_DEFAULT_ROUTING_LEXICONS = _mapping_section(_LEXICON_PAYLOAD, "routing_profiles")
_CAPABILITY_ROUTING_LEXICONS = _mapping_section(_LEXICON_PAYLOAD, "capability_lexicons")


def get_default_routing_profile(language: str | None = None) -> dict[str, list[str]]:
    lang_key = _language_key(language, _DEFAULT_ROUTING_LEXICONS)
    raw = _DEFAULT_ROUTING_LEXICONS.get(lang_key, {})
    if not isinstance(raw, dict):
        raw = {}
    return {
        field_name: _dedupe_preserving_order(raw.get(field_name, ()))
        for field_name in ROUTING_LEXICON_FIELDS
    }


def get_default_routing_languages() -> dict[str, dict[str, list[str]]]:
    return {
        language: get_default_routing_profile(language)
        for language in _DEFAULT_ROUTING_LEXICONS
        if language != DEFAULT_ROUTING_LANGUAGE
    }


def get_default_capability_lexicon(language: str | None = None) -> CapabilityRoutingLexicon:
    lang_key = _language_key(language, _CAPABILITY_ROUTING_LEXICONS)
    raw = _CAPABILITY_ROUTING_LEXICONS.get(lang_key, {})
    if not isinstance(raw, dict):
        raw = {}
    return CapabilityRoutingLexicon(
        **{
            field_name: _dedupe_tuple_preserving_order(raw.get(field_name, ()))
            for field_name in CapabilityRoutingLexicon.__dataclass_fields__
        }
    )
