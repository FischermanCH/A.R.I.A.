from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import time
from typing import Any
from typing import Callable

from aria.core.connection_admin import CONNECTION_ADMIN_SPECS
from aria.core.connection_admin import sanitize_connection_ref
from aria.core.connection_catalog import connection_chat_aliases
from aria.core.connection_catalog import connection_chat_defaults
from aria.core.connection_catalog import connection_chat_field_specs
from aria.core.connection_catalog import connection_chat_primary_field
from aria.core.connection_catalog import connection_field_labels
from aria.core.connection_catalog import connection_field_specs
from aria.core.connection_catalog import connection_summary_fields
from aria.core.connection_catalog import normalize_connection_kind
from aria.core.connection_catalog import sanitize_connection_payload

_CONNECTION_ACTION_VERBS: dict[str, str] = {
    "create": r"(?:erstelle|erzeuge|lege an|erfasse|create)",
    "update": r"(?:aktualisiere|update|ändere|aendere|bearbeite)",
}

_CONNECTION_URL_FIELDS = {"webhook_url", "feed_url", "url", "base_url"}
_CONNECTION_LEADING_VALUE_KEYWORDS = {
    "host",
    "user",
    "key",
    "key_path",
    "schluesselpfad",
    "keypfad",
    "share",
    "pfad",
    "path",
    "root",
    "root_path",
    "from",
    "to",
    "mailbox",
    "topic",
    "port",
    "timeout",
    "passwort",
    "password",
    "token",
    "auth_token",
    "auth-token",
    "method",
    "methode",
    "strict",
    "checking",
    "host-key",
    "allow",
    "commands",
    "titel",
    "title",
    "beschreibung",
    "description",
    "tags",
    "tag",
    "aliase",
    "aliases",
    "alias",
}

SanitizeString = Callable[[str | None], str]
NowProvider = Callable[[], float]


def _parse_forget_query(message: str) -> str:
    text = re.sub(r"\s+", " ", message).strip()
    pattern = re.compile(r"^(vergiss|lösch|lösch|entfern|delete|remove)\s+", re.IGNORECASE)
    return pattern.sub("", text).strip(" .,:;!?") or text


def _parse_forget_confirm_token(message: str) -> str | None:
    text = message.strip().lower()
    match = re.search(
        r"(?:bestätige|bestätige|lösche|lösche|delete)\s+(?:jetzt\s+)?([a-z0-9]{6,16})",
        text,
    )
    if not match:
        return None
    return match.group(1)


def _parse_safe_fix_confirm_token(message: str) -> str | None:
    text = message.strip().lower()
    match = re.search(
        r"(?:bestätige|bestätige|confirm)\s+(?:safe-?fix\s+|fix\s+)?([a-z0-9]{6,16})",
        text,
    )
    if not match:
        return None
    return match.group(1)


def _parse_connection_delete_request(message: str) -> tuple[str, str] | None:
    text = re.sub(r"\s+", " ", str(message or "")).strip()
    match = re.search(
        r"(?:lösche|loesche|entferne|delete|remove)\s+(?:die\s+|das\s+|den\s+)?(?:(ssh|discord|sftp|smb|webhook|smtp|email|imap|http api|http-api|rss|mqtt)\s+)?(?:verbindung|profil)?\s*([a-z0-9._-]+)",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    kind = str(match.group(1) or "").strip().lower()
    ref = str(match.group(2) or "").strip()
    return kind, ref


def _parse_connection_delete_confirm_token(message: str) -> str | None:
    text = message.strip().lower()
    match = re.search(
        r"(?:bestätige|bestaetige|confirm)\s+(?:verbindung\s+)?(?:(?:löschen|loeschen|delete)\s+)?([a-z0-9]{6,16})",
        text,
    )
    if not match:
        return None
    return match.group(1)


def _extract_connection_create_metadata(text: str) -> dict[str, Any]:
    def _extract(pattern: str) -> str:
        match = re.search(pattern, text, re.IGNORECASE)
        return str(match.group(1)).strip() if match else ""

    title = _extract(r'(?:titel|title)\s+"([^"]+)"')
    description = _extract(r'(?:beschreibung|description)\s+"([^"]+)"')
    tags_raw = _extract(r'(?:tags|tag)\s+"([^"]+)"')
    aliases_raw = _extract(r'(?:aliase|aliases|alias)\s+"([^"]+)"')

    payload: dict[str, Any] = {}
    if title:
        payload["title"] = title[:120]
    if description:
        payload["description"] = description[:280]
    if tags_raw:
        payload["tags"] = [item.strip() for item in re.split(r"[;,]", tags_raw) if item.strip()][:12]
    if aliases_raw:
        payload["aliases"] = [item.strip() for item in re.split(r"[;,]", aliases_raw) if item.strip()][:12]
    return payload


def _extract_connection_field(text: str, pattern: str) -> str:
    match = re.search(pattern, text, re.IGNORECASE)
    return str(match.group(1)).strip() if match else ""


def _build_connection_chat_alias_map() -> dict[str, str]:
    alias_map: dict[str, str] = {}
    for kind in CONNECTION_ADMIN_SPECS:
        clean_kind = normalize_connection_kind(kind)
        for alias in connection_chat_aliases(clean_kind):
            token = str(alias).strip().lower()
            if token:
                alias_map[token] = clean_kind
    return alias_map


def _match_connection_request_header(text: str, action: str) -> tuple[str, str, str] | None:
    alias_map = _build_connection_chat_alias_map()
    alias_pattern = "|".join(sorted((re.escape(alias) for alias in alias_map), key=len, reverse=True))
    if not alias_pattern:
        return None
    verbs = _CONNECTION_ACTION_VERBS.get(action, "")
    if not verbs:
        return None
    match = re.search(
        rf"^{verbs}\s+(?:eine\s+|ein\s+)?(?P<alias>{alias_pattern})(?:\s+verbindung|\s+profil)?\s+(?P<ref>[a-z0-9._-]+)(?P<rest>.*)$",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    alias = str(match.group("alias") or "").strip().lower()
    ref = str(match.group("ref") or "").strip()
    rest = str(match.group("rest") or "").strip()
    kind = alias_map.get(alias, "")
    if not kind or not ref:
        return None
    return kind, ref, rest


def _extract_connection_primary_value(kind: str, rest: str) -> tuple[str, str]:
    primary_field = connection_chat_primary_field(kind)
    clean_rest = str(rest or "").strip()
    if not primary_field or not clean_rest:
        return "", clean_rest
    if primary_field in _CONNECTION_URL_FIELDS:
        match = re.match(r"(https?://\S+)(?:\s+(.*))?$", clean_rest, re.IGNORECASE)
        if not match:
            return "", clean_rest
        primary_value = str(match.group(1) or "").strip()
        remaining = str(match.group(2) or "").strip()
        if primary_field == "base_url":
            primary_value = primary_value.rstrip("/")
        return primary_value, remaining
    token, _, remaining = clean_rest.partition(" ")
    lowered = token.strip().lower()
    if not token or lowered in _CONNECTION_LEADING_VALUE_KEYWORDS or token.startswith('"'):
        return "", clean_rest
    return token.strip(), remaining.strip()


def _extract_connection_field_value(text: str, kind: str, field: str) -> Any:
    chat_spec = connection_chat_field_specs(kind).get(field, {})
    patterns = chat_spec.get("patterns", [])
    if not isinstance(patterns, list) or not patterns:
        return None
    value = ""
    for pattern in patterns:
        value = _extract_connection_field(text, str(pattern))
        if value:
            break
    if not value:
        return None
    field_spec = connection_field_specs(kind).get(field, {})
    field_type = str(field_spec.get("type", "str")).strip().lower()
    if field_type == "list":
        split_pattern = str(chat_spec.get("split_pattern") or r"[;,]")
        return [item.strip() for item in re.split(split_pattern, value) if item.strip()]
    if field_type == "int":
        try:
            return int(value)
        except ValueError:
            return None
    if field == "base_url":
        return value.rstrip("/")
    return value


def _parse_catalog_connection_request(message: str, action: str) -> dict[str, Any] | None:
    text = re.sub(r"\s+", " ", str(message or "")).strip()
    if not text:
        return None
    header = _match_connection_request_header(text, action)
    if not header:
        return None
    kind, ref, rest = header
    payload: dict[str, Any] = connection_chat_defaults(kind) if action == "create" else {}
    payload.update(_extract_connection_create_metadata(text))

    primary_field = connection_chat_primary_field(kind)
    primary_value, remaining = _extract_connection_primary_value(kind, rest)
    if primary_field and primary_value:
        payload[primary_field] = primary_value

    if kind == "http_api" and remaining.startswith("/"):
        inline_path, _, remaining = remaining.partition(" ")
        if inline_path.strip():
            payload["health_path"] = inline_path.strip()

    for field in connection_field_specs(kind):
        if field in {"title", "description", "tags", "aliases"}:
            continue
        if field == primary_field and field in payload:
            continue
        extracted = _extract_connection_field_value(text, kind, field)
        if extracted in (None, "", []):
            continue
        payload[field] = extracted

    clean_payload = sanitize_connection_payload(kind, payload)
    if action == "create" and primary_field and primary_field not in clean_payload:
        return None
    if action == "update" and not clean_payload:
        return None
    return {"kind": kind, "ref": ref, "payload": clean_payload}


def _parse_connection_create_request(message: str) -> dict[str, Any] | None:
    return _parse_catalog_connection_request(message, "create")


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
    text = message.strip().lower()
    match = re.search(
        r"(?:bestätige|bestaetige|confirm)\s+(?:verbindung\s+)?(?:(?:erstellen|erfassen|create)\s+)?([a-z0-9]{6,16})",
        text,
    )
    if not match:
        return None
    return match.group(1)


def _parse_connection_update_request(message: str) -> dict[str, Any] | None:
    return _parse_catalog_connection_request(message, "update")


def _parse_connection_update_confirm_token(message: str) -> str | None:
    text = message.strip().lower()
    match = re.search(
        r"(?:bestätige|bestaetige|confirm)\s+(?:verbindung\s+)?(?:(?:aktualisieren|update|aendern|ändern)\s+)?([a-z0-9]{6,16})",
        text,
    )
    if not match:
        return None
    return match.group(1)


def _normalize_chat_command_text(message: str) -> str:
    return re.sub(r"\s+", " ", str(message or "")).strip().lower()


def _matches_chat_phrase(message: str, phrases: tuple[str, ...]) -> bool:
    text = _normalize_chat_command_text(message)
    if not text:
        return False
    return any(phrase in text for phrase in phrases)


def _parse_update_run_request(message: str) -> bool:
    return _matches_chat_phrase(
        message,
        (
            "starte update",
            "start update",
            "führe update aus",
            "fuehre update aus",
            "run update",
            "installiere update",
            "update jetzt",
            "jetzt updaten",
            "kontrolliertes update starten",
        ),
    )


def _parse_update_status_request(message: str) -> bool:
    return _matches_chat_phrase(
        message,
        (
            "zeige update status",
            "show update status",
            "update status",
            "status vom update",
            "status des updates",
            "läuft ein update",
            "laeuft ein update",
            "läuft gerade ein update",
            "laeuft gerade ein update",
            "update helper status",
            "öffne update seite",
            "oeffne update seite",
            "open update page",
        ),
    )


def _parse_update_confirm_token(message: str) -> str | None:
    text = _normalize_chat_command_text(message)
    match = re.search(
        r"(?:bestätige|bestaetige|confirm)\s+(?:kontrolliertes\s+)?(?:update\s+)?([a-z0-9]{6,16})",
        text,
    )
    if not match:
        return None
    return match.group(1)


def _parse_routed_action_confirm_token(message: str) -> str | None:
    text = _normalize_chat_command_text(message)
    match = re.search(
        r"(?:bestätige|bestaetige|confirm)\s+(?:aktion|ausfuehrung|ausführung|action|execute)\s+([a-z0-9]{6,16})",
        text,
    )
    if not match:
        return None
    return match.group(1)


def _parse_backup_export_request(message: str) -> bool:
    return _matches_chat_phrase(
        message,
        (
            "exportiere config backup",
            "export config backup",
            "erstelle config backup",
            "create config backup",
            "download config backup",
            "sichere aria config",
            "backup der config",
            "backup der konfig",
        ),
    )


def _parse_backup_import_request(message: str) -> bool:
    return _matches_chat_phrase(
        message,
        (
            "importiere config backup",
            "import config backup",
            "restore config backup",
            "spiele config backup ein",
            "backup wiederherstellen",
            "restore backup",
        ),
    )


def _parse_stats_request(message: str) -> bool:
    return _matches_chat_phrase(
        message,
        (
            "zeige stats",
            "show stats",
            "zeige statistiken",
            "show statistics",
            "öffne stats",
            "oeffne stats",
        ),
    )


def _parse_activities_request(message: str) -> bool:
    return _matches_chat_phrase(
        message,
        (
            "zeige aktivitäten",
            "zeige aktivitaeten",
            "show activities",
            "zeige runs",
            "show runs",
            "öffne aktivitäten",
            "oeffne aktivitaeten",
        ),
    )


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


def _encode_safe_fix_pending(
    data: dict[str, Any],
    *,
    signing_secret: str,
    sanitize_username: SanitizeString,
    sanitize_connection_name: SanitizeString,
) -> str:
    fixes = data.get("fixes", [])
    if not isinstance(fixes, list):
        fixes = []
    clean_fixes: list[dict[str, Any]] = []
    for row in fixes[:20]:
        if not isinstance(row, dict):
            continue
        conn_ref = sanitize_connection_name(str(row.get("connection_ref", "")))
        packages = row.get("packages", [])
        if not conn_ref or not isinstance(packages, list):
            continue
        clean_packages: list[str] = []
        for pkg in packages:
            name = str(pkg).strip().lower()
            if re.fullmatch(r"[a-z0-9][a-z0-9+_.-]*", name):
                clean_packages.append(name)
        clean_packages = sorted(set(clean_packages))[:30]
        if not clean_packages:
            continue
        clean_fixes.append({"connection_ref": conn_ref, "packages": clean_packages})

    payload = {
        "token": str(data.get("token", "")).strip()[:24].lower(),
        "user_id": sanitize_username(str(data.get("user_id", ""))),
        "fixes": clean_fixes,
    }
    return _sign_pending_payload(payload, signing_secret=signing_secret)


def _decode_safe_fix_pending(
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
    fixes = payload.get("fixes", [])
    if not token or not user_id or not isinstance(fixes, list):
        return None
    return {"token": token, "user_id": user_id, "fixes": fixes}


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
