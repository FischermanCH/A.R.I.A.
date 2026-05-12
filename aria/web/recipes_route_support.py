from __future__ import annotations

import hmac
import re
from typing import Callable
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from fastapi import Request
from fastapi.responses import RedirectResponse

AuthSessionResolver = Callable[[Request], dict[str, object] | None]
RoleSanitizer = Callable[[str | None], str]

RECIPE_SURFACE_PATHS = {
    "/recipes",
    "/recipes/start",
    "/recipes/learned",
    "/recipes/mine",
    "/recipes/system",
    "/recipes/templates",
}


def sanitize_return_to(value: str | None) -> str:
    candidate = str(value or "").strip()
    if not candidate or not candidate.startswith("/"):
        return ""
    if candidate.startswith("//"):
        return ""
    parsed = urlparse(candidate)
    if parsed.scheme or parsed.netloc:
        return ""
    path = parsed.path or "/"
    return f"{path}?{parsed.query}" if parsed.query else path


def canonical_recipe_surface_path(path: str | None) -> str:
    clean = str(path or "").strip()
    if clean == "/skills":
        return "/recipes"
    if clean.startswith("/skills/"):
        return "/recipes/" + clean[len("/skills/") :]
    return clean


def canonical_recipe_surface_return_to(candidate: str | None) -> str:
    clean = sanitize_return_to(candidate)
    if not clean:
        return ""
    parsed = urlparse(clean)
    path = canonical_recipe_surface_path(parsed.path or "")
    query = f"?{parsed.query}" if parsed.query else ""
    return f"{path}{query}" if path else ""


def referer_return_to(request: Request) -> str:
    referer = str(request.headers.get("referer", "") or "").strip()
    if not referer:
        return ""
    parsed = urlparse(referer)
    if parsed.scheme or parsed.netloc:
        current = urlparse(str(request.url))
        if parsed.netloc and parsed.netloc != current.netloc:
            return ""
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    candidate = sanitize_return_to(query.get("return_to"))
    if candidate:
        return candidate
    path = parsed.path or "/"
    current_path = request.url.path or "/"
    if path == current_path:
        return ""
    return sanitize_return_to(f"{path}?{parsed.query}" if parsed.query else path)


def resolve_return_to(request: Request, *, fallback: str) -> str:
    candidate = sanitize_return_to(request.query_params.get("return_to"))
    current_path = request.url.path or "/"
    if candidate and urlparse(candidate).path != current_path:
        return candidate
    referer_target = referer_return_to(request)
    if referer_target and urlparse(referer_target).path != current_path:
        return referer_target
    return sanitize_return_to(fallback) or "/"


def attach_return_to(url: str, return_to: str) -> str:
    target = canonical_recipe_surface_return_to(return_to)
    if not target:
        return url
    parsed = urlparse(url)
    pairs = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True) if key != "return_to"]
    pairs.append(("return_to", target))
    return urlunparse(parsed._replace(query=urlencode(pairs)))


def redirect_with_return_to(
    url: str,
    request: Request,
    *,
    fallback: str,
    return_to: str | None = None,
) -> RedirectResponse:
    target = canonical_recipe_surface_return_to(return_to) or canonical_recipe_surface_return_to(
        resolve_return_to(request, fallback=fallback)
    )
    return RedirectResponse(url=attach_return_to(url, target), status_code=303)


def set_logical_back_url(request: Request, *, fallback: str) -> str:
    target = canonical_recipe_surface_return_to(resolve_return_to(request, fallback=fallback))
    request.state.logical_back_url = target
    return target


def sanitize_csrf_token(value: str | None) -> str:
    token = str(value or "").strip()
    token = re.sub(r"[^A-Za-z0-9_-]", "", token)
    return token[:256]


def is_valid_csrf_submission(submitted_token: str | None, expected_token: str | None) -> bool:
    supplied = sanitize_csrf_token(submitted_token)
    expected = sanitize_csrf_token(expected_token)
    if not supplied or not expected:
        return False
    return hmac.compare_digest(supplied, expected)


def is_admin_mode_request(
    request: Request,
    get_auth_session_from_request: AuthSessionResolver,
    sanitize_role: RoleSanitizer,
) -> bool:
    if bool(getattr(request.state, "can_access_advanced_config", False)):
        return True
    auth = get_auth_session_from_request(request) or {}
    role = sanitize_role(auth.get("role"))
    return role == "admin" and bool(getattr(request.state, "debug_mode", False))


def recipe_surface_path(candidate: str | None, *, fallback: str = "/recipes") -> str:
    clean = sanitize_return_to(candidate)
    if clean:
        parsed = urlparse(clean)
        path = canonical_recipe_surface_path(parsed.path or "")
        if path in RECIPE_SURFACE_PATHS:
            return path
    return fallback


def recipe_surface_return_to(candidate: str | None, *, fallback: str = "/recipes") -> str:
    clean = sanitize_return_to(candidate)
    if clean:
        parsed = urlparse(clean)
        path = canonical_recipe_surface_path(parsed.path or "")
        if path in RECIPE_SURFACE_PATHS:
            query = f"?{parsed.query}" if parsed.query else ""
            return f"{path}{query}"
    return fallback
