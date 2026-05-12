from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from aria.core.i18n import I18NStore
from aria.core.text_utils import is_english

_HTTP_API_I18N = I18NStore(Path(__file__).resolve().parents[2] / "i18n")


def _http_api_text(language: str | None, key: str, default: str = "", **values: object) -> str:
    template = _HTTP_API_I18N.t(language or "de", f"result_http_api.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template


def format_duration_compact(total_seconds: int) -> str:
    remaining = max(0, int(total_seconds))
    days, remaining = divmod(remaining, 86400)
    hours, remaining = divmod(remaining, 3600)
    minutes, _ = divmod(remaining, 60)
    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes and len(parts) < 2:
        parts.append(f"{minutes}m")
    if not parts:
        parts.append("<1m")
    return " ".join(parts[:2])


def looks_like_http_api_status_payload(payload: dict[str, Any], *, path: str = "") -> bool:
    lower_path = str(path or "").strip().lower().split("?", 1)[0]
    if lower_path in {"/", "/health", "/status", "/ready", "/live", "/ping", "/version", "/metrics"}:
        return True
    return any(key in payload for key in ("status", "state", "health", "ok", "healthy", "success", "services", "uptime_seconds", "version"))


def http_api_service_status_text(payload: dict[str, Any], *, language: str | None = None) -> str:
    services = payload.get("services")
    if not isinstance(services, dict) or not services:
        return ""
    items: list[str] = []
    for key, value in list(services.items())[:4]:
        key_text = str(key or "").strip()
        value_text = str(value or "").strip()
        if key_text and value_text:
            items.append(f"{key_text} {value_text}")
    if not items:
        return ""
    prefix = _http_api_text(language, "services_prefix", "Services")
    return f"{prefix}: {', '.join(items)}."


def http_api_uptime_text(payload: dict[str, Any], *, language: str | None = None) -> str:
    raw = payload.get("uptime_seconds")
    try:
        seconds = int(raw)
    except Exception:
        return ""
    if seconds < 60:
        return ""
    return _http_api_text(language, "uptime", "Uptime {duration}.", duration=format_duration_compact(seconds))


def summarize_http_api_result_for_chat(
    text: str,
    *,
    connection_ref: str,
    path: str = "",
    notes: list[str] | None = None,
    language: str | None = None,
    extract_json_object: Callable[[str], dict[str, Any]],
) -> str:
    clean_text = str(text or "").strip()
    if not clean_text:
        return ""
    note_set = {str(item or "").strip().lower() for item in list(notes or []) if str(item or "").strip()}
    effective_path = str(path or "").strip() or "/"
    payload = extract_json_object(clean_text)
    if not payload:
        return ""
    if (
        "api_agentic_request" not in note_set
        and "api_status_like" not in note_set
        and not looks_like_http_api_status_payload(payload, path=effective_path)
    ):
        return ""
    host_label = f"`{connection_ref}`"
    status_value = str(payload.get("status", "") or payload.get("state", "") or payload.get("health", "") or payload.get("result", "") or "").strip()
    message_value = str(payload.get("message", "") or payload.get("detail", "") or payload.get("summary", "") or "").strip()
    version_value = str(payload.get("version", "") or payload.get("build", "") or "").strip()
    ok_flag = payload.get("ok", payload.get("healthy", payload.get("success", None)))
    services_text = http_api_service_status_text(payload, language=language)
    uptime_value = http_api_uptime_text(payload, language=language)
    item_count = None
    for key in ("items", "results", "data", "entries"):
        value = payload.get(key)
        if isinstance(value, list):
            item_count = len(value)
            break
    parts: list[str]
    if is_english(language):
        parts = [_http_api_text(language, "api_check", "API check for {host}:", host=host_label)]
        if status_value:
            parts.append(f"Status {status_value}.")
        elif ok_flag is True:
            parts.append(_http_api_text(language, "status_ok", "Status ok."))
        elif ok_flag is False:
            parts.append(_http_api_text(language, "status_problem", "Status reports a problem."))
        else:
            parts.append(_http_api_text(language, "endpoint_responded", "Endpoint {path} responded.", path=effective_path))
        if message_value and len(message_value) <= 120:
            parts.append(message_value.rstrip(".") + ".")
        if version_value and len(version_value) <= 60:
            parts.append(f"Version {version_value}.")
        if services_text:
            parts.append(services_text)
        if uptime_value:
            parts.append(uptime_value)
        if item_count is not None:
            parts.append(_http_api_text(language, "response_entries", "Response contains {count} entries.", count=item_count))
    else:
        parts = [_http_api_text(language, "api_check", "API check for {host}:", host=host_label)]
        if status_value:
            parts.append(f"Status {status_value}.")
        elif ok_flag is True:
            parts.append(_http_api_text(language, "status_ok", "Status ok."))
        elif ok_flag is False:
            parts.append(_http_api_text(language, "status_problem", "Status reports a problem."))
        else:
            parts.append(_http_api_text(language, "endpoint_responded", "Endpoint {path} responded.", path=effective_path))
        if message_value and len(message_value) <= 120:
            parts.append(message_value.rstrip(".") + ".")
        if version_value and len(version_value) <= 60:
            parts.append(f"Version {version_value}.")
        if services_text:
            parts.append(services_text)
        if uptime_value:
            parts.append(uptime_value)
        if item_count is not None:
            parts.append(_http_api_text(language, "response_entries", "Response contains {count} entries.", count=item_count))
    return " ".join(parts).strip()
