from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit


_STATUS_PATH_HINTS = {
    "/",
    "/health",
    "/status",
    "/ready",
    "/live",
    "/ping",
    "/version",
    "/metrics",
}

_MUTATING_PATH_TERMS = (
    "/delete",
    "/remove",
    "/reset",
    "/restart",
    "/shutdown",
    "/stop",
    "/start",
    "/exec",
    "/run",
    "/write",
    "/create",
    "/update",
)

_SENSITIVE_PATH_TERMS = (
    "/admin",
    "/config",
    "/manage",
    "/internal",
)


@dataclass(frozen=True)
class HTTPAPIPolicyDecision:
    action: str
    reason: str
    normalized_path: str
    normalized_content: str


def normalize_http_api_path(path: str, *, health_path: str = "/") -> str:
    clean = str(path or "").strip()
    fallback = str(health_path or "/").strip() or "/"
    if not clean:
        return fallback
    if clean.startswith("http://") or clean.startswith("https://"):
        parts = urlsplit(clean)
        normalized = parts.path or "/"
        if parts.query:
            normalized += f"?{parts.query}"
        return normalized
    if clean.startswith("?"):
        return f"{fallback}{clean}"
    if not clean.startswith("/"):
        clean = "/" + clean.lstrip("/")
    return clean


def validate_http_api_request_policy(
    path: str,
    *,
    content: str = "",
    method: str = "GET",
    health_path: str = "/",
    status_like: bool = False,
) -> HTTPAPIPolicyDecision:
    normalized_path = normalize_http_api_path(path, health_path=health_path)
    normalized_content = str(content or "").strip()
    clean_method = str(method or "GET").strip().upper() or "GET"
    lower_path = normalized_path.lower()

    if any(token in normalized_path for token in ("`", "$(", "${", "\n", "\r", ";", "|")):
        return HTTPAPIPolicyDecision("block", "http_api_path_invalid", normalized_path, normalized_content)
    if normalized_path.startswith("http://") or normalized_path.startswith("https://"):
        return HTTPAPIPolicyDecision("block", "http_api_full_url_blocked", normalized_path, normalized_content)
    if ".." in normalized_path:
        return HTTPAPIPolicyDecision("block", "http_api_path_invalid", normalized_path, normalized_content)
    if clean_method == "DELETE":
        return HTTPAPIPolicyDecision("block", "http_api_mutating_method", normalized_path, normalized_content)
    if any(term in lower_path for term in _MUTATING_PATH_TERMS):
        return HTTPAPIPolicyDecision("block", "http_api_mutating_path", normalized_path, normalized_content)
    if clean_method in {"GET", "HEAD"} and normalized_content:
        return HTTPAPIPolicyDecision("block", "http_api_body_for_read_request", normalized_path, normalized_content)
    if clean_method in {"POST", "PUT", "PATCH"}:
        return HTTPAPIPolicyDecision("ask_user", "http_api_method_needs_confirmation", normalized_path, normalized_content)
    if clean_method not in {"GET", "HEAD"}:
        return HTTPAPIPolicyDecision("ask_user", "http_api_method_unknown", normalized_path, normalized_content)
    if len(normalized_path) > 160 or "?" in normalized_path:
        return HTTPAPIPolicyDecision("ask_user", "http_api_path_needs_confirmation", normalized_path, normalized_content)
    if any(term in lower_path for term in _SENSITIVE_PATH_TERMS):
        return HTTPAPIPolicyDecision("ask_user", "http_api_sensitive_path", normalized_path, normalized_content)
    if status_like and not _is_status_path(normalized_path, health_path=health_path):
        return HTTPAPIPolicyDecision("ask_user", "http_api_status_path_unclear", normalized_path, normalized_content)
    return HTTPAPIPolicyDecision("allow", "http_api_readonly_policy_allow", normalized_path, normalized_content)


def _is_status_path(path: str, *, health_path: str = "/") -> bool:
    clean = normalize_http_api_path(path, health_path=health_path).split("?", 1)[0].lower()
    health = normalize_http_api_path(health_path, health_path=health_path).split("?", 1)[0].lower()
    if clean == health:
        return True
    return clean in _STATUS_PATH_HINTS
