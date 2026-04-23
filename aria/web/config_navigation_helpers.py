from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import Request
from fastapi.responses import RedirectResponse


@dataclass(frozen=True)
class ConfigNavigationHelpers:
    cookie_name_for_request: Callable[[Request, str, str], str]
    cookie_scope_for_request: Callable[[Request], str]
    sanitize_return_to: Callable[[str | None], str]
    resolve_return_to: Callable[[Request], str]
    redirect_with_return_to: Callable[..., RedirectResponse]
    set_logical_back_url: Callable[..., str]


def build_config_navigation_helpers() -> ConfigNavigationHelpers:
    def cookie_name_for_request(request: Request, key: str, fallback: str) -> str:
        cookie_names = getattr(request.state, "cookie_names", {}) or {}
        if isinstance(cookie_names, dict):
            candidate = str(cookie_names.get(key, "") or "").strip()
            if candidate:
                return candidate
        return fallback

    def cookie_scope_for_request(request: Request) -> str:
        return str(getattr(request.state, "cookie_scope_source", "") or "").strip()

    def sanitize_return_to(value: str | None) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        parsed = urlsplit(raw)
        path = str(parsed.path or "").strip()
        if not path.startswith("/") or path.startswith("//"):
            return ""
        cleaned = path
        if parsed.query:
            cleaned = f"{cleaned}?{parsed.query}"
        return cleaned

    def referer_return_to(request: Request) -> str:
        referer = str(request.headers.get("referer", "") or "").strip()
        if not referer:
            return ""
        parsed = urlsplit(referer)
        referer_query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        candidate = sanitize_return_to(referer_query.get("return_to"))
        if candidate:
            return candidate
        path = str(parsed.path or "").strip()
        if not path.startswith("/") or path.startswith("//"):
            return ""
        return sanitize_return_to(f"{path}?{parsed.query}" if parsed.query else path)

    def resolve_return_to(request: Request, *, fallback: str) -> str:
        current_path = str(request.url.path or "").strip()
        candidate = sanitize_return_to(request.query_params.get("return_to"))
        if candidate and urlsplit(candidate).path != current_path:
            return candidate
        referer_target = referer_return_to(request)
        if referer_target and urlsplit(referer_target).path != current_path:
            return referer_target
        return sanitize_return_to(fallback) or "/"

    def attach_return_to(url: str, return_to: str) -> str:
        target = sanitize_return_to(return_to)
        if not target:
            return url
        parsed = urlsplit(url)
        pairs = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True) if key != "return_to"]
        pairs.append(("return_to", target))
        query = urlencode(pairs)
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, parsed.fragment))

    def redirect_with_return_to(
        url: str,
        request: Request,
        *,
        fallback: str,
        return_to: str | None = None,
    ) -> RedirectResponse:
        target = sanitize_return_to(return_to) or resolve_return_to(request, fallback=fallback)
        return RedirectResponse(url=attach_return_to(url, target), status_code=303)

    def set_logical_back_url(request: Request, *, fallback: str) -> str:
        target = resolve_return_to(request, fallback=fallback)
        request.state.logical_back_url = target
        return target

    return ConfigNavigationHelpers(
        cookie_name_for_request=cookie_name_for_request,
        cookie_scope_for_request=cookie_scope_for_request,
        sanitize_return_to=sanitize_return_to,
        resolve_return_to=resolve_return_to,
        redirect_with_return_to=redirect_with_return_to,
        set_logical_back_url=set_logical_back_url,
    )
