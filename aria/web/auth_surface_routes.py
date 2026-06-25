from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from logging import Logger
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus
from uuid import uuid4

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from aria.core.i18n import I18NStore


SettingsGetter = Callable[[], Any]
AuthManagerGetter = Callable[[], Any | None]
AuthSessionResolver = Callable[[Request], dict[str, Any] | None]
UsernameSanitizer = Callable[[str | None], str]
RoleSanitizer = Callable[[str | None], str]
CookieSetter = Callable[..., None]
CookieClearer = Callable[..., None]
CookieSecureResolver = Callable[..., bool]
RawConfigReader = Callable[[], dict[str, Any]]
RawConfigWriter = Callable[[dict[str, Any]], None]
BootstrapEnabler = Callable[[dict[str, Any]], dict[str, Any]]
RuntimeReloader = Callable[[], None]
DefaultCollectionResolver = Callable[[str], str]
AuthEncoder = Callable[[str, str], str]
LOGIN_RATE_LIMIT_MAX_FAILURES = 5
LOGIN_RATE_LIMIT_WINDOW_SECONDS = 5 * 60
LOGIN_RATE_LIMIT_BLOCK_SECONDS = 5 * 60
_AUTH_SURFACE_I18N = I18NStore(Path(__file__).resolve().parents[1] / "i18n")


def _auth_text(language: str | None, key: str, default: str = "", **values: object) -> str:
    template = _AUTH_SURFACE_I18N.t(language or "de", f"auth_surface_routes.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template


@dataclass(frozen=True)
class AuthSurfaceRouteDeps:
    templates: Jinja2Templates
    get_settings: SettingsGetter
    get_auth_manager: AuthManagerGetter
    get_auth_session_from_request: AuthSessionResolver
    sanitize_username: UsernameSanitizer
    sanitize_role: RoleSanitizer
    set_response_cookie: CookieSetter
    clear_auth_related_cookies: CookieClearer
    cookie_should_be_secure: CookieSecureResolver
    read_raw_config: RawConfigReader
    write_raw_config: RawConfigWriter
    enable_bootstrap_admin_mode_in_raw_config: BootstrapEnabler
    reload_runtime: RuntimeReloader
    default_memory_collection_for_user: DefaultCollectionResolver
    encode_auth_session: AuthEncoder
    auth_cookie: str
    username_cookie: str
    memory_collection_cookie: str
    session_cookie: str
    auto_memory_cookie: str
    auth_session_max_age_seconds: int
    logger: Logger


def register_auth_surface_routes(app: FastAPI, deps: AuthSurfaceRouteDeps) -> None:
    login_failures: dict[str, list[float]] = {}
    login_blocked_until: dict[str, float] = {}

    def _login_rate_limit_key(request: Request, username: str) -> str:
        client_host = str(getattr(getattr(request, "client", None), "host", "") or "unknown").strip()
        return f"{client_host}:{deps.sanitize_username(username).lower() or '-'}"

    def _login_is_rate_limited(key: str, now: float) -> bool:
        blocked_until = float(login_blocked_until.get(key, 0.0) or 0.0)
        if blocked_until > now:
            return True
        if blocked_until:
            login_blocked_until.pop(key, None)
        return False

    def _record_failed_login(key: str, now: float) -> None:
        cutoff = now - LOGIN_RATE_LIMIT_WINDOW_SECONDS
        attempts = [item for item in login_failures.get(key, []) if item >= cutoff]
        attempts.append(now)
        login_failures[key] = attempts
        if len(attempts) >= LOGIN_RATE_LIMIT_MAX_FAILURES:
            login_blocked_until[key] = now + LOGIN_RATE_LIMIT_BLOCK_SECONDS

    def _clear_failed_logins(key: str) -> None:
        login_failures.pop(key, None)
        login_blocked_until.pop(key, None)

    @app.get("/login", response_class=HTMLResponse)
    async def login_page(request: Request, next: str = "/", error: str = "", info: str = "") -> HTMLResponse:  # noqa: A002
        auth = deps.get_auth_session_from_request(request)
        if auth:
            target = str(next or "/")
            if not target.startswith("/"):
                target = "/"
            return RedirectResponse(url=target, status_code=303)
        settings = deps.get_settings()
        bootstrap_mode = False
        login_users: list[str] = []
        bootstrap_locked = bool(settings.security.bootstrap_locked)
        manager = deps.get_auth_manager()
        if manager:
            try:
                rows = manager.store.list_users()
                bootstrap_mode = len(rows) == 0
                login_users = sorted(
                    [str(row.get("username", "")).strip() for row in rows if bool(row.get("active")) and str(row.get("username", "")).strip()]
                )
                lower_error = str(error or "").strip().lower()
                if lower_error and (
                    "security store" in lower_error
                    or "bootstrap gesperrt" in lower_error
                    or "bootstrap is currently locked" in lower_error
                ):
                    error = ""
            except Exception:
                bootstrap_mode = False
                login_users = []
        return deps.templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "title": settings.ui.title,
                "next_path": next if str(next).startswith("/") else "/",
                "error_message": error,
                "info_message": info,
                "username": "",
                "bootstrap_mode": bootstrap_mode,
                "bootstrap_locked": bootstrap_locked,
                "login_users": login_users,
            },
        )

    @app.post("/login")
    async def login_submit(
        request: Request,
        username: str = Form(...),
        password: str = Form(...),
        password_confirm: str = Form(""),
        next_path: str = Form("/"),
    ) -> RedirectResponse:
        settings = deps.get_settings()
        secure_cookie = deps.cookie_should_be_secure(request, public_url=str(settings.aria.public_url or ""))
        clean_username = deps.sanitize_username(username)
        target = str(next_path or "/")
        if not target.startswith("/"):
            target = "/"
        rate_limit_key = _login_rate_limit_key(request, clean_username)
        now = time.monotonic()
        lang = str(getattr(request.state, "lang", "de") or "de")
        if _login_is_rate_limited(rate_limit_key, now):
            msg = _auth_text(lang, "too_many_login_attempts", "Too many login attempts. Please wait briefly and try again.")
            return RedirectResponse(url=f"/login?error={quote_plus(msg)}", status_code=303)

        manager = deps.get_auth_manager()
        if not manager:
            msg = _auth_text(lang, "security_store_inactive", "Security store is not active. Please check secrets.env and security.")
            return RedirectResponse(
                url=f"/login?error={quote_plus(msg)}",
                status_code=303,
            )
        try:
            store = manager.store
            users = store.list_users()
            if not users:
                if bool(settings.security.bootstrap_locked):
                    msg = _auth_text(lang, "bootstrap_locked", "Bootstrap is locked. Please create an admin in the config store or disable bootstrap_locked.")
                    return RedirectResponse(
                        url=f"/login?error={quote_plus(msg)}",
                        status_code=303,
                    )
                if not clean_username:
                    msg = _auth_text(lang, "username_required", "Please enter a username.")
                    return RedirectResponse(url=f"/login?error={quote_plus(msg)}", status_code=303)
                if str(password or "") != str(password_confirm or ""):
                    msg = _auth_text(lang, "passwords_do_not_match", "Passwords do not match. Please enter the same password in both fields.")
                    return RedirectResponse(url=f"/login?error={quote_plus(msg)}", status_code=303)
                try:
                    manager.upsert_user(clean_username, password, role="admin")
                except ValueError as exc:
                    return RedirectResponse(url=f"/login?error={quote_plus(str(exc))}", status_code=303)
                try:
                    raw = deps.read_raw_config()
                    raw = deps.enable_bootstrap_admin_mode_in_raw_config(raw)
                    deps.write_raw_config(raw)
                    settings.ui.debug_mode = True
                except Exception:
                    deps.logger.exception("Failed to auto-enable admin mode for first bootstrap user")
                users = store.list_users()
            if not clean_username or not manager.verify(clean_username, password):
                if users:
                    _record_failed_login(rate_limit_key, now)
                return RedirectResponse(url=f"/login?error={quote_plus(_auth_text(lang, 'login_failed', 'Login failed'))}", status_code=303)
            _clear_failed_logins(rate_limit_key)
            user = store.get_user(clean_username)
            canonical_username = deps.sanitize_username((user or {}).get("username")) or clean_username
            role = deps.sanitize_role((user or {}).get("role"))
            response = RedirectResponse(url=target, status_code=303)
            deps.set_response_cookie(
                response,
                request,
                deps.auth_cookie,
                deps.encode_auth_session(
                    canonical_username,
                    role,
                    scope=str(getattr(request.state, "cookie_scope_source", "") or ""),
                ),
                max_age=deps.auth_session_max_age_seconds,
                secure=secure_cookie,
                httponly=True,
            )
            deps.set_response_cookie(
                response,
                request,
                deps.username_cookie,
                canonical_username,
                max_age=60 * 60 * 24 * 365,
                secure=secure_cookie,
                httponly=False,
            )
            deps.set_response_cookie(
                response,
                request,
                deps.memory_collection_cookie,
                deps.default_memory_collection_for_user(canonical_username),
                max_age=60 * 60 * 24 * 365,
                secure=secure_cookie,
                httponly=False,
            )
            deps.set_response_cookie(
                response,
                request,
                deps.session_cookie,
                uuid4().hex[:12],
                max_age=60 * 60 * 24 * 7,
                secure=secure_cookie,
                httponly=False,
            )
            return response
        except Exception:
            lang = str(getattr(request.state, "lang", "de") or "de")
            return RedirectResponse(url=f"/login?error={quote_plus(_auth_text(lang, 'login_failed', 'Login failed'))}", status_code=303)

    @app.post("/logout")
    async def logout(request: Request) -> RedirectResponse:
        response = RedirectResponse(url="/login", status_code=303)
        deps.clear_auth_related_cookies(response, request, clear_preferences=True)
        return response

    @app.get("/session-expired", response_class=HTMLResponse)
    async def session_expired_page(request: Request, next: str = "/") -> HTMLResponse:  # noqa: A002
        target = str(next or "/")
        if not target.startswith("/"):
            target = "/"
        settings = deps.get_settings()
        response = deps.templates.TemplateResponse(
            request=request,
            name="session_expired.html",
            context={
                "title": settings.ui.title,
                "next_path": target,
                "next_query": quote_plus(target),
            },
        )
        deps.clear_auth_related_cookies(response, request)
        return response

    @app.post("/set-username")
    async def set_username(request: Request, username: str = Form(...)) -> RedirectResponse:
        settings = deps.get_settings()
        secure_cookie = deps.cookie_should_be_secure(request, public_url=str(settings.aria.public_url or ""))
        auth = deps.get_auth_session_from_request(request)
        clean_username = deps.sanitize_username(username)
        if auth:
            clean_username = deps.sanitize_username(auth.get("username"))
        response = RedirectResponse(url="/", status_code=303)
        session_id = uuid4().hex[:12]
        if clean_username:
            deps.set_response_cookie(
                response,
                request,
                deps.username_cookie,
                clean_username,
                max_age=60 * 60 * 24 * 365,
                secure=secure_cookie,
                httponly=False,
            )
            deps.set_response_cookie(
                response,
                request,
                deps.memory_collection_cookie,
                deps.default_memory_collection_for_user(clean_username),
                max_age=60 * 60 * 24 * 365,
                secure=secure_cookie,
                httponly=False,
            )
            deps.set_response_cookie(
                response,
                request,
                deps.session_cookie,
                session_id,
                max_age=60 * 60 * 24 * 7,
                secure=secure_cookie,
                httponly=False,
            )
        return response

    @app.post("/set-auto-memory")
    async def set_auto_memory(request: Request, enabled: str = Form("0"), next_path: str = Form("/")) -> RedirectResponse:
        settings = deps.get_settings()
        secure_cookie = deps.cookie_should_be_secure(request, public_url=str(settings.aria.public_url or ""))
        target = "/" if not str(next_path).startswith("/") else str(next_path)
        try:
            active = str(enabled).strip().lower() in {"1", "true", "on", "yes"}
            raw = deps.read_raw_config()
            raw.setdefault("auto_memory", {})
            if not isinstance(raw["auto_memory"], dict):
                raw["auto_memory"] = {}
            raw["auto_memory"]["enabled"] = active
            raw["auto_memory"]["agentic_extraction_enabled"] = active
            deps.write_raw_config(raw)
            deps.reload_runtime()
            response = RedirectResponse(url=target, status_code=303)
            deps.set_response_cookie(
                response,
                request,
                deps.auto_memory_cookie,
                "1" if active else "0",
                max_age=60 * 60 * 24 * 365,
                secure=secure_cookie,
                httponly=False,
            )
            return response
        except (OSError, ValueError) as exc:
            return RedirectResponse(url=f"/memories/config?error={quote_plus(str(exc))}", status_code=303)
