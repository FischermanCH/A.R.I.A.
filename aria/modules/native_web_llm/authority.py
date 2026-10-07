from __future__ import annotations

import ipaddress
from dataclasses import replace
from urllib.parse import urlparse

from aria.modules.native_web_llm.contracts import NativeWebRequest, NativeWebResult


def _is_public_citation_url(url: str) -> bool:
    parsed = urlparse(str(url or "").strip())
    host = str(parsed.hostname or "").strip().lower().rstrip(".")
    if parsed.scheme not in {"http", "https"} or not host or parsed.username or parsed.password:
        return False
    if host == "localhost" or host.endswith((".localhost", ".local", ".lan", ".internal")):
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return True
    return bool(address.is_global)


def validate_native_web_result(result: NativeWebResult, request: NativeWebRequest) -> NativeWebResult:
    errors = list(result.errors)
    if result.provider_requests != 1:
        errors.append("provider_request_count_invalid")
    if result.main_llm_requests != 0:
        errors.append("main_llm_call_forbidden")
    if result.retries != 0:
        errors.append("automatic_retry_forbidden")
    if result.native_search_uses > max(1, min(int(request.max_search_uses or 3), 3)):
        errors.append("native_web_search_budget_exceeded")
    if any(not _is_public_citation_url(citation.url) for citation in result.citations):
        errors.append("private_or_invalid_citation")
    prefixes = tuple(prefix.lower() for prefix in request.required_url_prefixes if str(prefix).strip())
    if prefixes and not any(
        citation.url.lower().startswith(prefix)
        for citation in result.citations
        for prefix in prefixes
    ):
        errors.append("required_primary_source_missing")
    return replace(result, errors=tuple(dict.fromkeys(errors)))
