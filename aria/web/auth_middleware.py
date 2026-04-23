from __future__ import annotations

import hmac
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote_plus

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response


SettingsGetter = Callable[[], Any]
CookieSecureResolver = Callable[..., bool]
CookieScopeResolver = Callable[..., str]
CookieNamesResolver = Callable[..., dict[str, str]]
CookieValueResolver = Callable[[Request, str], str]
Translator = Callable[[Request, str, str], str]
ReleaseMetaReader = Callable[[Path], dict[str, Any]]
UpdateStatusGetter = Callable[[str], dict[str, Any]]
AuthSessionWithReasonResolver = Callable[[Request], tuple[dict[str, Any] | None, str]]
AuthManagerGetter = Callable[[], Any | None]
StringSanitizer = Callable[[str | None], str]
CsrfSanitizer = Callable[[str | None], str]
CsrfTokenFactory = Callable[[], str]
CookieSetter = Callable[..., None]
AuthCookieClearer = Callable[..., None]
LanguageRowsGetter = Callable[[], list[str]]
LanguageResolver = Callable[[str, str], str]
ThemeNormalizer = Callable[[str], str]
BackgroundNormalizer = Callable[[str], str]
BackgroundAssetResolver = Callable[[str], str]
RoleAccessCheck = Callable[[str], bool]
PathAccessCheck = Callable[[str], bool]
AuthSessionEncoder = Callable[[str, str, str], str]


@dataclass(frozen=True)
class AuthMiddlewareDeps:
    base_dir: Path
    get_settings: SettingsGetter
    cookie_should_be_secure: CookieSecureResolver
    cookie_scope_source: CookieScopeResolver
    cookie_names_for_request: CookieNamesResolver
    request_cookie_value: CookieValueResolver
    translate: Translator
    read_release_meta: ReleaseMetaReader
    get_update_status: UpdateStatusGetter
    get_auth_session_from_request_with_reason: AuthSessionWithReasonResolver
    get_auth_manager: AuthManagerGetter
    sanitize_username: StringSanitizer
    sanitize_role: StringSanitizer
    sanitize_csrf_token: CsrfSanitizer
    new_csrf_token: CsrfTokenFactory
    set_response_cookie: CookieSetter
    clear_auth_related_cookies: AuthCookieClearer
    available_languages: LanguageRowsGetter
    resolve_lang: LanguageResolver
    normalize_ui_theme: ThemeNormalizer
    normalize_ui_background: BackgroundNormalizer
    resolve_ui_background_asset_url: BackgroundAssetResolver
    can_access_settings: RoleAccessCheck
    can_access_users: RoleAccessCheck
    can_access_advanced_config: Callable[[str, bool], bool]
    is_admin_only_path: PathAccessCheck
    is_advanced_config_path: PathAccessCheck
    encode_auth_session: AuthSessionEncoder
    auth_cookie: str
    csrf_cookie: str
    username_cookie: str
    lang_cookie: str
    auth_session_max_age_seconds: int


def register_auth_middleware(app: FastAPI, deps: AuthMiddlewareDeps) -> None:
    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        settings = deps.get_settings()
        path = request.url.path or "/"
        secure_cookie = deps.cookie_should_be_secure(request, public_url=str(settings.aria.public_url or ""))
        cookie_public_url = str(settings.aria.public_url or "")
        request.state.cookie_public_url = cookie_public_url
        request.state.cookie_scope_source = deps.cookie_scope_source(request, public_url=cookie_public_url)
        request.state.cookie_names = deps.cookie_names_for_request(request, public_url=cookie_public_url)
        accept_header = str(request.headers.get("accept", "") or "").lower()
        requested_with = str(request.headers.get("x-requested-with", "") or "").lower()
        expects_json = "application/json" in accept_header or requested_with in {"fetch", "xmlhttprequest"}
        requested_lang = (
            str(request.query_params.get("lang", "")).strip().lower()
            or str(deps.request_cookie_value(request, deps.lang_cookie)).strip().lower()
            or str(settings.ui.language or "de").strip().lower()
        )
        resolved_lang = deps.resolve_lang(requested_lang, default_lang=str(settings.ui.language or "de"))
        request.state.lang = resolved_lang
        request.state.supported_languages = deps.available_languages()
        request.state.agent_name = str(settings.ui.title or "ARIA").strip() or "ARIA"
        request.state.release_meta = deps.read_release_meta(deps.base_dir)
        request.state.update_status = deps.get_update_status(request.state.release_meta["label"])
        raw_auth_cookie = str(deps.request_cookie_value(request, deps.auth_cookie) or "").strip()
        auth, auth_reason = deps.get_auth_session_from_request_with_reason(request)
        auth_degraded = False
        csrf_cookie_token = deps.sanitize_csrf_token(deps.request_cookie_value(request, deps.csrf_cookie))
        if not csrf_cookie_token:
            csrf_cookie_token = deps.new_csrf_token()
        request.state.csrf_token = csrf_cookie_token
        if auth:
            manager = deps.get_auth_manager()
            if manager:
                try:
                    user = manager.store.get_user(auth["username"])
                except Exception:
                    auth_degraded = True
                    auth_reason = "store_error"
                else:
                    if not user:
                        auth = None
                        auth_reason = "user_missing"
                    elif not bool(user.get("active")):
                        auth = None
                        auth_reason = "user_inactive"
                    else:
                        auth["username"] = deps.sanitize_username(user.get("username"))
                        auth["role"] = deps.sanitize_role(user.get("role"))
            else:
                if bool(settings.security.enabled):
                    auth_degraded = True
                    auth_reason = "store_unavailable"
                else:
                    auth = None
                    auth_reason = "security_disabled"
        request.state.authenticated = bool(auth)
        request.state.auth_user = auth.get("username") if auth else ""
        request.state.auth_role = auth.get("role") if auth else ""
        request.state.auth_debug_reason = auth_reason
        request.state.auth_degraded = auth_degraded
        request.state.debug_mode = bool(settings.ui.debug_mode)
        request.state.ui_theme = deps.normalize_ui_theme(getattr(settings.ui, "theme", "matrix"))
        request.state.ui_background = deps.normalize_ui_background(getattr(settings.ui, "background", "grid"))
        request.state.ui_background_asset_url = deps.resolve_ui_background_asset_url(request.state.ui_background)
        request.state.can_access_settings = bool(auth) and deps.can_access_settings(request.state.auth_role)
        request.state.can_access_users = bool(auth) and deps.can_access_users(request.state.auth_role)
        request.state.can_access_advanced_config = bool(auth) and deps.can_access_advanced_config(
            request.state.auth_role,
            request.state.debug_mode,
        )

        public_paths = {"/health", "/login", "/session-expired"}
        is_public_or_api = (
            path in public_paths
            or path.startswith("/static/")
            or path.startswith("/v1/")
            or path.startswith("/api/")
        )

        needs_login = (
            path in {"/", "/chat", "/stats", "/activities", "/memories", "/skills", "/set-username", "/set-auto-memory"}
            or path.startswith("/memories/")
            or path.startswith("/skills/")
            or path.startswith("/stats/")
            or path.startswith("/activities/")
            or path.startswith("/config/")
            or path == "/config"
        )
        if not is_public_or_api and needs_login and not auth:
            target_path = path
            if request.url.query:
                target_path = f"{path}?{request.url.query}"
            next_path = quote_plus(target_path)
            login_url = f"/login?next={next_path}"
            if raw_auth_cookie:
                if expects_json:
                    response = JSONResponse(
                        status_code=401,
                        content={
                            "code": "session_expired",
                            "detail": deps.translate(request, "auth.session_expired", "Sitzung abgelaufen. Bitte erneut anmelden."),
                            "login_url": login_url,
                        },
                    )
                    if auth_reason not in {"store_unavailable", "store_error"}:
                        deps.clear_auth_related_cookies(response, request)
                    return response
                response = RedirectResponse(url=f"/session-expired?next={next_path}", status_code=303)
                if auth_reason not in {"store_unavailable", "store_error"}:
                    deps.clear_auth_related_cookies(response, request)
                return response
            if expects_json:
                return JSONResponse(
                    status_code=401,
                    content={
                        "code": "login_required",
                        "detail": deps.translate(request, "auth.login_required", "Bitte zuerst anmelden."),
                        "login_url": login_url,
                    },
                )
            return RedirectResponse(url=login_url, status_code=303)

        if not is_public_or_api and path == "/set-auto-memory" and auth:
            if deps.sanitize_role(auth.get("role")) != "admin":
                if expects_json:
                    return JSONResponse(
                        status_code=403,
                        content={
                            "code": "no_admin",
                            "detail": deps.translate(request, "auth.no_admin", "Admin-Rechte erforderlich."),
                        },
                    )
                return RedirectResponse(url="/?error=no_admin", status_code=303)

        if not is_public_or_api and path == "/config" and auth:
            if not request.state.can_access_settings:
                if expects_json:
                    return JSONResponse(
                        status_code=403,
                        content={
                            "code": "no_settings",
                            "detail": deps.translate(request, "auth.no_settings", "Keine Berechtigung für Einstellungen."),
                        },
                    )
                return RedirectResponse(url="/?error=no_settings", status_code=303)

        if not is_public_or_api and path.startswith("/config/") and auth:
            if not request.state.can_access_settings:
                if expects_json:
                    return JSONResponse(
                        status_code=403,
                        content={
                            "code": "no_settings",
                            "detail": deps.translate(request, "auth.no_settings", "Keine Berechtigung für Einstellungen."),
                        },
                    )
                return RedirectResponse(url="/?error=no_settings", status_code=303)
            if deps.is_admin_only_path(path) and not request.state.can_access_users:
                if expects_json:
                    return JSONResponse(
                        status_code=403,
                        content={
                            "code": "no_admin",
                            "detail": deps.translate(request, "auth.no_admin", "Admin-Rechte erforderlich."),
                        },
                    )
                return RedirectResponse(url="/config?error=no_admin", status_code=303)
            if deps.is_advanced_config_path(path) and not request.state.can_access_advanced_config:
                if expects_json:
                    return JSONResponse(
                        status_code=403,
                        content={
                            "code": "admin_mode_required",
                            "detail": deps.translate(
                                request,
                                "auth.admin_mode_required",
                                "Admin-Modus erforderlich. Bitte unter Benutzer aktivieren.",
                            ),
                        },
                    )
                return RedirectResponse(url="/config?error=admin_mode_required", status_code=303)

        protected_methods = {"POST", "PUT", "PATCH", "DELETE"}
        csrf_exempt_prefixes = ("/v1/", "/api/")
        csrf_exempt_paths = {"/health", "/skills/import", "/config/connections/rss/import-opml", "/memories/upload"}
        if (
            request.method.upper() in protected_methods
            and path not in csrf_exempt_paths
            and not path.startswith(csrf_exempt_prefixes)
        ):
            header_token = deps.sanitize_csrf_token(request.headers.get("x-csrf-token"))
            form_token = ""
            content_type = (request.headers.get("content-type") or "").lower()
            if not header_token and (
                "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type
            ):
                try:
                    if "multipart/form-data" in content_type:
                        form = await request.form()
                        raw_token = str(form.get("csrf_token", "") or "")
                    else:
                        body = await request.body()
                        parsed = parse_qs(body.decode("utf-8", errors="ignore"), keep_blank_values=False)
                        raw_token = parsed.get("csrf_token", [""])[0]
                    form_token = deps.sanitize_csrf_token(raw_token)
                except Exception:
                    form_token = ""
            supplied = header_token or form_token
            if not supplied or not hmac.compare_digest(supplied, csrf_cookie_token):
                if expects_json:
                    return JSONResponse(
                        status_code=403,
                        content={
                            "code": "csrf_failed",
                            "detail": deps.translate(
                                request,
                                "auth.csrf_failed",
                                "CSRF-Prüfung fehlgeschlagen. Bitte Seite neu laden.",
                            ),
                        },
                    )
                return HTMLResponse(
                    content="<h3>CSRF validation failed. Bitte Seite neu laden.</h3>",
                    status_code=403,
                )

        response = await call_next(request)
        if isinstance(response, Response):
            response_lang = deps.resolve_lang(
                str(getattr(request.state, "lang", resolved_lang) or resolved_lang),
                default_lang=str(settings.ui.language or "de"),
            )
            if bool(request.state.debug_mode):
                response.headers.setdefault("X-ARIA-Auth-Reason", str(auth_reason or "unknown"))
                response.headers.setdefault("X-ARIA-Auth-Degraded", "1" if auth_degraded else "0")
            response.headers.setdefault("X-Content-Type-Options", "nosniff")
            response.headers.setdefault("X-Frame-Options", "DENY")
            response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
            response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
            response.headers.setdefault(
                "Content-Security-Policy",
                (
                    "default-src 'self'; "
                    "img-src 'self' data:; "
                    "style-src 'self' 'unsafe-inline'; "
                    "script-src 'self' https://unpkg.com 'unsafe-inline'; "
                    "connect-src 'self'; "
                    "frame-ancestors 'none'; "
                    "base-uri 'self'; "
                    "form-action 'self'"
                ),
            )
            if auth and path != "/logout":
                refreshed = deps.encode_auth_session(
                    auth["username"],
                    auth["role"],
                    scope=str(getattr(request.state, "cookie_scope_source", "") or ""),
                )
                deps.set_response_cookie(
                    response,
                    request,
                    deps.auth_cookie,
                    refreshed,
                    max_age=deps.auth_session_max_age_seconds,
                    secure=secure_cookie,
                    httponly=True,
                )
                deps.set_response_cookie(
                    response,
                    request,
                    deps.username_cookie,
                    auth["username"],
                    max_age=60 * 60 * 24 * 365,
                    secure=secure_cookie,
                    httponly=False,
                )
            deps.set_response_cookie(
                response,
                request,
                deps.csrf_cookie,
                csrf_cookie_token,
                max_age=60 * 60 * 24 * 7,
                secure=secure_cookie,
                httponly=False,
            )
            deps.set_response_cookie(
                response,
                request,
                deps.lang_cookie,
                response_lang,
                max_age=60 * 60 * 24 * 365,
                secure=secure_cookie,
                httponly=False,
            )
        return response
