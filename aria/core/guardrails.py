from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any


GUARDRAIL_CATALOG: dict[str, dict[str, Any]] = {
    "ssh_command": {
        "label": "SSH Command",
        "connection_kinds": {"ssh"},
    },
    "http_request": {
        "label": "HTTP Request",
        "connection_kinds": {"http_api", "webhook"},
    },
    "file_access": {
        "label": "File Access",
        "connection_kinds": {"sftp", "smb"},
    },
    "mqtt_publish": {
        "label": "MQTT Publish",
        "connection_kinds": {"mqtt"},
    },
}


@dataclass
class GuardrailDecision:
    allowed: bool
    reason: str = ""
    profile_ref: str = ""
    kind: str = ""


def normalize_guardrail_kind(kind: str) -> str:
    return str(kind or "").strip().lower().replace("-", "_")


def guardrail_kind_label(kind: str) -> str:
    clean_kind = normalize_guardrail_kind(kind)
    spec = GUARDRAIL_CATALOG.get(clean_kind, {})
    return str(spec.get("label") or clean_kind or "Guardrail").strip()


def guardrail_kind_options() -> list[str]:
    return list(GUARDRAIL_CATALOG.keys())


def guardrail_is_compatible(kind: str, connection_kind: str) -> bool:
    clean_kind = normalize_guardrail_kind(kind)
    clean_connection_kind = str(connection_kind or "").strip().lower().replace("-", "_")
    spec = GUARDRAIL_CATALOG.get(clean_kind, {})
    allowed = spec.get("connection_kinds", set())
    return isinstance(allowed, set) and clean_connection_kind in allowed


def _clean_term_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    rows: list[str] = []
    for item in values:
        text = str(item).strip().lower()
        if text:
            rows.append(text)
    return rows


def _normalize_guardrail_text(value: str) -> str:
    return " ".join(str(value or "").split()).strip().lower()


def _guardrail_term_matches(text: str, term: str) -> bool:
    clean_text = _normalize_guardrail_text(text)
    clean_term = _normalize_guardrail_text(term)
    if not clean_text or not clean_term:
        return False
    if "/" in clean_term or "\\" in clean_term:
        return clean_term in clean_text
    pattern = re.escape(clean_term)
    pattern = re.sub(r"\\\s+", r"\\s+", pattern)
    if clean_term[0].isalnum() or clean_term[0] == "_":
        pattern = r"(?<![a-z0-9_])" + pattern
    if clean_term[-1].isalnum() or clean_term[-1] == "_":
        pattern = pattern + r"(?![a-z0-9_])"
    return re.search(pattern, clean_text, flags=re.IGNORECASE) is not None


def _any_guardrail_term_matches(text: str, terms: list[str]) -> bool:
    return any(_guardrail_term_matches(text, token) for token in terms)


def resolve_guardrail_profile(settings: Any, ref: str) -> dict[str, Any] | None:
    clean_ref = str(ref or "").strip()
    if not clean_ref:
        return None
    security_cfg = getattr(settings, "security", object())
    profiles = getattr(security_cfg, "guardrails", {}) or {}
    profile = profiles.get(clean_ref) if isinstance(profiles, dict) else None
    if profile is None:
        return None
    if isinstance(profile, dict):
        kind = normalize_guardrail_kind(str(profile.get("kind", "")).strip() or "ssh_command")
        return {
            "kind": kind,
            "title": str(profile.get("title", "")).strip(),
            "description": str(profile.get("description", "")).strip(),
            "allow_terms": _clean_term_list(profile.get("allow_terms", [])),
            "deny_terms": _clean_term_list(profile.get("deny_terms", [])),
        }
    return {
        "kind": normalize_guardrail_kind(str(getattr(profile, "kind", "")).strip() or "ssh_command"),
        "title": str(getattr(profile, "title", "")).strip(),
        "description": str(getattr(profile, "description", "")).strip(),
        "allow_terms": _clean_term_list(getattr(profile, "allow_terms", [])),
        "deny_terms": _clean_term_list(getattr(profile, "deny_terms", [])),
    }


def evaluate_guardrail(*, profile_ref: str, profile: dict[str, Any] | None, kind: str, text: str) -> GuardrailDecision:
    clean_kind = normalize_guardrail_kind(kind)
    if not profile:
        return GuardrailDecision(allowed=True, profile_ref=profile_ref, kind=clean_kind)
    profile_kind = normalize_guardrail_kind(str(profile.get("kind", "")).strip() or clean_kind)
    if profile_kind != clean_kind:
        return GuardrailDecision(
            allowed=False,
            reason=f"guardrail_kind_mismatch:{profile_kind}",
            profile_ref=profile_ref,
            kind=profile_kind,
        )

    lowered = _normalize_guardrail_text(text)
    deny_terms = _clean_term_list(profile.get("deny_terms", []))
    allow_terms = _clean_term_list(profile.get("allow_terms", []))

    if deny_terms and _any_guardrail_term_matches(lowered, deny_terms):
        return GuardrailDecision(
            allowed=False,
            reason="guardrail_denied",
            profile_ref=profile_ref,
            kind=profile_kind,
        )
    if allow_terms and not _any_guardrail_term_matches(lowered, allow_terms):
        return GuardrailDecision(
            allowed=False,
            reason="guardrail_not_allowed",
            profile_ref=profile_ref,
            kind=profile_kind,
        )
    return GuardrailDecision(allowed=True, profile_ref=profile_ref, kind=profile_kind)
