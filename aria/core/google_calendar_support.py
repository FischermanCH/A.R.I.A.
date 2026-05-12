from __future__ import annotations

import json
import socket
import ssl
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError

from aria.core.i18n import I18NStore

_GOOGLE_CALENDAR_I18N = I18NStore(Path(__file__).resolve().parents[1] / "i18n")


def _calendar_text(lang: str | None, key: str, default: str = "", **values: object) -> str:
    template = _GOOGLE_CALENDAR_I18N.t(lang or "de", f"google_calendar_support.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template


def _calendar_terms(key: str, fallback: tuple[str, ...]) -> tuple[str, ...]:
    raw = _calendar_text("de", key, ",".join(fallback))
    terms = tuple(item.strip().lower() for item in raw.split(",") if item.strip())
    return terms or fallback


def _looks_like_timeout_error(exc: Exception) -> bool:
    if isinstance(exc, TimeoutError):
        return True
    if isinstance(exc, socket.timeout):
        return True
    reason = getattr(exc, "reason", None) if isinstance(exc, URLError) else None
    if isinstance(reason, (TimeoutError, socket.timeout)):
        return True
    lower = str(exc).strip().lower()
    return any(term in lower for term in _calendar_terms("timeout_error_terms", ("timed out", "timeout")))


def _looks_like_ssl_error(exc: Exception) -> bool:
    if isinstance(exc, ssl.SSLError):
        return True
    if isinstance(exc, URLError) and isinstance(getattr(exc, "reason", None), ssl.SSLError):
        return True
    lower = str(exc).strip().lower()
    return "ssl" in lower or "tls" in lower or "certificate verify failed" in lower


def _read_http_error_payload(exc: HTTPError) -> dict[str, Any]:
    try:
        payload = exc.read()
    except Exception:
        payload = b""
    try:
        text = payload.decode("utf-8", errors="replace").strip()
    except Exception:
        text = ""
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except Exception:
        return {"raw": text}
    return parsed if isinstance(parsed, dict) else {"raw": text}


def _payload_strings(payload: dict[str, Any]) -> tuple[str, str, str]:
    if not isinstance(payload, dict):
        return "", "", ""
    top_error = str(payload.get("error", "") or "").strip()
    top_desc = str(payload.get("error_description", "") or "").strip()
    nested = payload.get("error")
    nested_message = ""
    nested_status = ""
    if isinstance(nested, dict):
        top_error = str(nested.get("status", "") or nested.get("code", "") or top_error).strip()
        nested_message = str(nested.get("message", "") or "").strip()
        nested_status = str(nested.get("status", "") or "").strip()
    return top_error, top_desc, f"{nested_status} {nested_message}".strip()


def _error_prefix(operation: str, lang: str) -> str:
    clean = str(operation or "").strip().lower()
    if clean == "sign_in":
        return _calendar_text(lang, "prefix_sign_in", "Google Calendar sign-in failed")
    if clean == "fetch":
        return _calendar_text(lang, "prefix_fetch", "Google Calendar fetch failed")
    return _calendar_text(lang, "prefix_test", "Google Calendar test failed")


def friendly_google_calendar_error_message(exc: Exception, *, lang: str = "de", operation: str = "test") -> str:
    prefix = _error_prefix(operation, lang)
    raw = str(exc).strip() or _calendar_text(lang, "unknown_error", "Unknown Google Calendar error.")

    payload: dict[str, Any] = {}
    code = 0
    if isinstance(exc, HTTPError):
        code = int(getattr(exc, "code", 0) or 0)
        payload = _read_http_error_payload(exc)
    err, desc, detail = _payload_strings(payload)
    haystack = " ".join(value.lower() for value in (err, desc, detail, raw) if value).strip()

    if _looks_like_timeout_error(exc):
        return _calendar_text(lang, "timeout_error", "{prefix}: Google did not respond in time. Please check the timeout or connectivity.", prefix=prefix)
    if _looks_like_ssl_error(exc):
        return _calendar_text(lang, "ssl_error", "{prefix}: TLS/SSL could not be established cleanly.", prefix=prefix)
    if code in {400, 401}:
        if any(token in haystack for token in ("invalid_grant", "expired or revoked", "token has been expired", "malformed auth code")):
            return _calendar_text(lang, "refresh_token_expired", "{prefix}: The refresh token is expired or revoked. Please reconnect the integration with Google in ARIA.", prefix=prefix)
        if any(token in haystack for token in ("invalid_client", "unauthorized_client", "client secret", "client authentication failed")):
            return _calendar_text(lang, "oauth_client_rejected", "{prefix}: Google rejected the OAuth client. Please verify the client ID and client secret from Google Cloud.", prefix=prefix)
        return _calendar_text(lang, "signin_incomplete", "{prefix}: The sign-in is expired or incomplete. Please check the client ID, client secret, and refresh token or reconnect the integration.", prefix=prefix)
    if code == 403:
        if any(token in haystack for token in ("accessnotconfigured", "api has not been used", "service disabled", "calendar api has not been used", "enable it")):
            return _calendar_text(lang, "api_not_enabled", "{prefix}: The Google Calendar API is not enabled for this project yet. Please enable the API in Google Cloud and wait a moment.", prefix=prefix)
        if any(token in haystack for token in ("insufficient", "scope", "permission", "forbidden")):
            return _calendar_text(lang, "access_refused_scope", "{prefix}: Google refused access. Please check the OAuth scopes, test users, and calendar permissions.", prefix=prefix)
        return _calendar_text(lang, "access_refused", "{prefix}: Google refused access. Please check the OAuth scopes, API enablement, and calendar permissions.", prefix=prefix)
    if code == 404:
        return _calendar_text(lang, "calendar_not_found", "{prefix}: The selected calendar could not be found. Please check the calendar ID.", prefix=prefix)
    if code == 429 or any(token in haystack for token in ("quota", "rate limit", "too many requests")):
        return _calendar_text(lang, "rate_limited", "{prefix}: Google is rate limiting requests right now. Please wait a moment and try again later.", prefix=prefix)
    if code:
        return _calendar_text(lang, "http_error", "{prefix}: HTTP {code}.", prefix=prefix, code=code)
    return _calendar_text(lang, "raw_error", "{prefix}: {raw}", prefix=prefix, raw=raw)
