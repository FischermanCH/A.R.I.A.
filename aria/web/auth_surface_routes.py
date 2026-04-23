from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from logging import Logger
from typing import Any
from urllib.parse import quote_plus
from uuid import uuid4

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates


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

        manager = deps.get_auth_manager()
        if not manager:
            return RedirectResponse(
                url="/login?error=Security+Store+nicht+aktiv.+Bitte+secrets.env+und+Security+prüfen.",
                status_code=303,
            )
        try:
            store = manager.store
            users = store.list_users()
            lang = str(getattr(request.state, "lang", "de") or "de")
            if not users:
                if bool(settings.security.bootstrap_locked):
                    return RedirectResponse(
                        url="/login?error=Bootstrap+gesperrt.+Bitte+Admin+im+Config+Store+anlegen+oder+bootstrap_locked+deaktivieren.",
                        status_code=303,
                    )
                if not clean_username:
                    return RedirectResponse(url="/login?error=Bitte+Benutzernamen+eingeben", status_code=303)
                if str(password or "") != str(password_confirm or ""):
                    msg = (
                        "Passwörter stimmen nicht überein. Bitte beide Felder identisch eingeben."
                        if lang.startswith("de")
                        else "Passwords do not match. Please enter the same password in both fields."
                    )
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
                return RedirectResponse(url=f"/login?error={quote_plus('Login fehlgeschlagen')}", status_code=303)
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
            return RedirectResponse(url=f"/login?error={quote_plus('Login fehlgeschlagen')}", status_code=303)

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
