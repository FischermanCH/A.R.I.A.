from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import time
from typing import Any
from typing import Callable

from aria.modules.connections_profiles.admin import sanitize_connection_ref
from aria.modules.connections_catalog.catalog import connection_field_labels
from aria.modules.connections_catalog.catalog import connection_field_specs
from aria.modules.connections_catalog.catalog import connection_summary_fields
from aria.modules.connections_catalog.catalog import normalize_connection_kind
from aria.modules.connections_catalog.catalog import sanitize_connection_payload

_CONFIRM_TOKEN = r"([a-z0-9]{6,16})"
_CONFIRM_PREFIX = r"(?:bestätige|bestaetige|confirm)\s+"

SanitizeString = Callable[[str | None], str]
NowProvider = Callable[[], float]


def _parse_forget_confirm_token(message: str) -> str | None:
    text = message.strip().lower()
    match = re.search(rf"(?:bestätige|bestaetige|lösche|loesche|delete)\s+(?:jetzt\s+)?{_CONFIRM_TOKEN}", text)
    if not match:
        return None
    return match.group(1)


def _parse_connection_delete_confirm_token(message: str) -> str | None:
    text = message.strip().lower()
    match = re.search(rf"{_CONFIRM_PREFIX}(?:verbindung\s+)?(?:(?:löschen|loeschen|delete)\s+)?{_CONFIRM_TOKEN}", text)
    if not match:
        return None
    return match.group(1)


def _format_connection_payload_summary(kind: str, payload: dict[str, Any]) -> list[str]:
    labels = connection_field_labels(kind)
    lines: list[str] = []
    specs = connection_field_specs(kind)
    for key in connection_summary_fields(kind):
        spec = specs.get(key, {})
        value = payload.get(key)
        field_type = str(spec.get("type", "str")).strip().lower()
        if field_type == "list":
            if isinstance(value, list) and value:
                joined = ", ".join(str(item).strip() for item in value if str(item).strip())
                if joined:
                    lines.append(f"{labels.get(key, key)}: `{joined}`")
            continue
        if field_type == "bool":
            continue
        text = str(value or "").strip()
        if text:
            lines.append(f"{labels.get(key, key)}: `{text}`")
    return lines


def _parse_connection_create_confirm_token(message: str) -> str | None:
    match = re.search(
        rf"{_CONFIRM_PREFIX}(?:verbindung\s+)?(?:(?:erstellen|erfassen|create)\s+)?{_CONFIRM_TOKEN}",
        message.strip().lower(),
    )
    return match.group(1) if match else None


def _parse_connection_update_confirm_token(message: str) -> str | None:
    match = re.search(
        rf"{_CONFIRM_PREFIX}(?:verbindung\s+)?(?:(?:aktualisieren|update|aendern|ändern)\s+)?{_CONFIRM_TOKEN}",
        message.strip().lower(),
    )
    return match.group(1) if match else None


def _parse_update_confirm_token(message: str) -> str | None:
    match = re.search(
        rf"{_CONFIRM_PREFIX}(?:kontrolliertes\s+)?(?:update\s+)?{_CONFIRM_TOKEN}",
        re.sub(r"\s+", " ", str(message or "")).strip().lower(),
    )
    return match.group(1) if match else None


def _parse_routed_action_confirm_token(message: str) -> str | None:
    match = re.search(
        rf"{_CONFIRM_PREFIX}(?:aktion|ausfuehrung|ausführung|action|execute)\s+{_CONFIRM_TOKEN}",
        re.sub(r"\s+", " ", str(message or "")).strip().lower(),
    )
    return match.group(1) if match else None


def _sign_pending_payload(payload: dict[str, Any], *, signing_secret: str) -> str:
    raw = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    encoded = base64.urlsafe_b64encode(raw).decode("ascii")
    signature = hmac.new(signing_secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def _decode_signed_pending_payload(raw: str | None, *, signing_secret: str) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        encoded, signature = str(raw).split(".", 1)
        decoded = base64.urlsafe_b64decode(encoded.encode("ascii"))
        expected = hmac.new(signing_secret.encode("utf-8"), decoded, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        payload = json.loads(decoded.decode("utf-8"))
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def _encode_forget_pending(
    data: dict[str, Any],
    *,
    signing_secret: str,
    sanitize_username: SanitizeString,
    sanitize_collection_name: SanitizeString,
) -> str:
    candidates = data.get("candidates", [])
    if not isinstance(candidates, list):
        candidates = []
    cleaned_candidates: list[dict[str, Any]] = []
    for row in candidates[:10]:
        if not isinstance(row, dict):
            continue
        collection = sanitize_collection_name(str(row.get("collection", "")).strip())
        point_id = str(row.get("id", "")).strip()[:128]
        label = str(row.get("label", "")).strip()[:64]
        text = str(row.get("text", "")).strip()[:240]
        if not collection or not point_id:
            continue
        cleaned_candidates.append(
            {
                "collection": collection,
                "id": point_id,
                "label": label,
                "text": text,
            }
        )

    payload = {
        "token": str(data.get("token", "")).strip()[:24].lower(),
        "user_id": sanitize_username(str(data.get("user_id", ""))),
        "candidates": cleaned_candidates,
    }
    return _sign_pending_payload(payload, signing_secret=signing_secret)


def _decode_forget_pending(
    raw: str | None,
    *,
    signing_secret: str,
    sanitize_username: SanitizeString,
) -> dict[str, Any] | None:
    payload = _decode_signed_pending_payload(raw, signing_secret=signing_secret)
    if payload is None:
        return None
    token = str(payload.get("token", "")).strip().lower()
    user_id = sanitize_username(str(payload.get("user_id", "")))
    candidates = payload.get("candidates", [])
    if not token or not user_id or not isinstance(candidates, list):
        return None
    return {
        "token": token,
        "user_id": user_id,
        "candidates": candidates,
    }


def _encode_connection_delete_pending(
    data: dict[str, Any],
    *,
    signing_secret: str,
    sanitize_username: SanitizeString,
    sanitize_connection_name: SanitizeString,
    now_provider: NowProvider = time.time,
) -> str:
    payload = {
        "token": str(data.get("token", "")).strip()[:24].lower(),
        "user_id": sanitize_username(str(data.get("user_id", ""))),
        "kind": str(data.get("kind", "")).strip().lower().replace("-", "_")[:32],
        "ref": sanitize_connection_name(str(data.get("ref", "")))[:64],
        "issued_at": int(now_provider()),
    }
    return _sign_pending_payload(payload, signing_secret=signing_secret)


def _encode_routed_action_pending(
    data: dict[str, Any],
    *,
    signing_secret: str,
    sanitize_username: SanitizeString,
    now_provider: NowProvider = time.time,
) -> str:
    payload = {
        "token": str(data.get("token", "")).strip()[:24].lower(),
        "user_id": sanitize_username(str(data.get("user_id", ""))),
        "query": str(data.get("query", "")).strip()[:2000],
        "candidate_kind": str(data.get("candidate_kind", "")).strip().lower()[:24],
        "candidate_id": str(data.get("candidate_id", "")).strip()[:120],
        "routing_decision": dict(data.get("routing_decision", {}) or {}),
        "action_decision": dict(data.get("action_decision", {}) or {}),
        "payload": dict(data.get("payload", {}) or {}),
        "safety_decision": dict(data.get("safety_decision", {}) or {}),
        "execution_decision": dict(data.get("execution_decision", {}) or {}),
        "issued_at": int(now_provider()),
    }
    return _sign_pending_payload(payload, signing_secret=signing_secret)


def _decode_routed_action_pending(
    raw: str | None,
    *,
    signing_secret: str,
    sanitize_username: SanitizeString,
    max_age_seconds: int,
    now_provider: NowProvider = time.time,
) -> dict[str, Any] | None:
    payload = _decode_signed_pending_payload(raw, signing_secret=signing_secret)
    if payload is None:
        return None
    token = str(payload.get("token", "")).strip().lower()
    user_id = sanitize_username(str(payload.get("user_id", "")))
    query = str(payload.get("query", "")).strip()
    issued_at = int(payload.get("issued_at", 0) or 0)
    if not token or not user_id or not query or issued_at <= 0:
        return None
    if int(now_provider()) - issued_at > max_age_seconds:
        return None
    return {
        "token": token,
        "user_id": user_id,
        "query": query,
        "candidate_kind": str(payload.get("candidate_kind", "")).strip().lower(),
        "candidate_id": str(payload.get("candidate_id", "")).strip(),
        "routing_decision": dict(payload.get("routing_decision", {}) or {}),
        "action_decision": dict(payload.get("action_decision", {}) or {}),
        "payload": dict(payload.get("payload", {}) or {}),
        "safety_decision": dict(payload.get("safety_decision", {}) or {}),
        "execution_decision": dict(payload.get("execution_decision", {}) or {}),
        "issued_at": issued_at,
    }
    return _sign_pending_payload(payload, signing_secret=signing_secret)


def _decode_connection_delete_pending(
    raw: str | None,
    *,
    signing_secret: str,
    sanitize_username: SanitizeString,
    sanitize_connection_name: SanitizeString,
    max_age_seconds: int,
    now_provider: NowProvider = time.time,
) -> dict[str, Any] | None:
    payload = _decode_signed_pending_payload(raw, signing_secret=signing_secret)
    if payload is None:
        return None
    token = str(payload.get("token", "")).strip().lower()
    user_id = sanitize_username(str(payload.get("user_id", "")))
    kind = str(payload.get("kind", "")).strip().lower().replace("-", "_")
    ref = sanitize_connection_name(str(payload.get("ref", "")))
    issued_at = int(payload.get("issued_at", 0) or 0)
    if not token or not user_id or not kind or not ref or issued_at <= 0:
        return None
    if int(now_provider()) - issued_at > max_age_seconds:
        return None
    return {"token": token, "user_id": user_id, "kind": kind, "ref": ref, "issued_at": issued_at}


def _encode_connection_create_pending(
    data: dict[str, Any],
    *,
    signing_secret: str,
    sanitize_username: SanitizeString,
    now_provider: NowProvider = time.time,
) -> str:
    kind = normalize_connection_kind(str(data.get("kind", "")))
    payload = sanitize_connection_payload(kind, data.get("payload", {}))
    packed = {
        "token": str(data.get("token", "")).strip()[:24].lower(),
        "user_id": sanitize_username(str(data.get("user_id", ""))),
        "kind": kind[:32],
        "ref": sanitize_connection_ref(str(data.get("ref", "")))[:64],
        "issued_at": int(now_provider()),
        "payload": payload,
    }
    return _sign_pending_payload(packed, signing_secret=signing_secret)


def _decode_connection_create_pending(
    raw: str | None,
    *,
    signing_secret: str,
    sanitize_username: SanitizeString,
    max_age_seconds: int,
    now_provider: NowProvider = time.time,
) -> dict[str, Any] | None:
    payload = _decode_signed_pending_payload(raw, signing_secret=signing_secret)
    if payload is None:
        return None
    token = str(payload.get("token", "")).strip().lower()
    user_id = sanitize_username(str(payload.get("user_id", "")))
    kind = str(payload.get("kind", "")).strip().lower().replace("-", "_")
    ref = sanitize_connection_ref(str(payload.get("ref", "")))
    issued_at = int(payload.get("issued_at", 0) or 0)
    create_payload = sanitize_connection_payload(kind, payload.get("payload", {}))
    if not token or not user_id or not kind or not ref or issued_at <= 0:
        return None
    if int(now_provider()) - issued_at > max_age_seconds:
        return None
    return {"token": token, "user_id": user_id, "kind": kind, "ref": ref, "payload": create_payload, "issued_at": issued_at}


def _encode_connection_update_pending(
    data: dict[str, Any],
    *,
    signing_secret: str,
    sanitize_username: SanitizeString,
    now_provider: NowProvider = time.time,
) -> str:
    return _encode_connection_create_pending(
        data,
        signing_secret=signing_secret,
        sanitize_username=sanitize_username,
        now_provider=now_provider,
    )


def _decode_connection_update_pending(
    raw: str | None,
    *,
    signing_secret: str,
    sanitize_username: SanitizeString,
    max_age_seconds: int,
    now_provider: NowProvider = time.time,
) -> dict[str, Any] | None:
    return _decode_connection_create_pending(
        raw,
        signing_secret=signing_secret,
        sanitize_username=sanitize_username,
        max_age_seconds=max_age_seconds,
        now_provider=now_provider,
    )


def _encode_update_pending(
    data: dict[str, Any],
    *,
    signing_secret: str,
    sanitize_username: SanitizeString,
    now_provider: NowProvider = time.time,
) -> str:
    payload = {
        "token": str(data.get("token", "")).strip()[:24].lower(),
        "user_id": sanitize_username(str(data.get("user_id", ""))),
        "issued_at": int(now_provider()),
    }
    return _sign_pending_payload(payload, signing_secret=signing_secret)


def _decode_update_pending(
    raw: str | None,
    *,
    signing_secret: str,
    sanitize_username: SanitizeString,
    max_age_seconds: int,
    now_provider: NowProvider = time.time,
) -> dict[str, Any] | None:
    payload = _decode_signed_pending_payload(raw, signing_secret=signing_secret)
    if payload is None:
        return None
    token = str(payload.get("token", "")).strip().lower()
    user_id = sanitize_username(str(payload.get("user_id", "")))
    issued_at = int(payload.get("issued_at", 0) or 0)
    if not token or not user_id or issued_at <= 0:
        return None
    if int(now_provider()) - issued_at > max_age_seconds:
        return None
    return {"token": token, "user_id": user_id, "issued_at": issued_at}
