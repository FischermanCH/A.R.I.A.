from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from aria.modules import module_route_path, module_template_name


SettingsGetter = Callable[[], Any]
UsernameResolver = Callable[[Request], str]
AuthSessionResolver = Callable[[Request], dict[str, Any] | None]
SecureStoreGetter = Callable[[], Any]
AuthCookieClearer = Callable[..., None]
RuntimePreflightGetter = Callable[[], Awaitable[dict[str, Any]]]
UpdateFinishedChecker = Callable[[Request, dict[str, Any]], bool]
ReleaseMetaReader = Callable[[Path], dict[str, Any]]
UpdateStatusGetter = Callable[[str], dict[str, Any]]
UpdateHelperConfigResolver = Callable[..., Any]
UpdateHelperStatusFetcher = Callable[..., dict[str, Any]]
UpdateHelperRunTrigger = Callable[[Any], dict[str, Any]]
HelperStatusVisualResolver = Callable[..., str]


@dataclass(frozen=True)
class SystemUpdateRouteDeps:
    templates: Jinja2Templates
    base_dir: Path
    get_settings: SettingsGetter
    get_username_from_request: UsernameResolver
    get_auth_session_from_request: AuthSessionResolver
    get_secure_store: SecureStoreGetter
    clear_auth_related_cookies: AuthCookieClearer
    get_runtime_preflight: RuntimePreflightGetter
    update_finished_after_session: UpdateFinishedChecker
    read_release_meta: ReleaseMetaReader
    get_update_status: UpdateStatusGetter
    resolve_update_helper_config: UpdateHelperConfigResolver
    fetch_update_helper_status: UpdateHelperStatusFetcher
    trigger_update_helper_run: UpdateHelperRunTrigger
    helper_status_visual: HelperStatusVisualResolver


def register_system_update_routes(app: FastAPI, deps: SystemUpdateRouteDeps) -> None:
    def _release_update_template(template_name: str) -> str:
        resolved = module_template_name("release_update", template_name)
        if resolved is None:
            raise RuntimeError(f"release_update template is not registered: {template_name}")
        return resolved

    def _release_update_route(route_path: str) -> str:
        resolved = module_route_path("release_update", route_path)
        if resolved is None:
            raise RuntimeError(f"release_update route is not registered: {route_path}")
        return resolved

    def _config_ui_route(route_path: str) -> str:
        resolved = module_route_path("config_ui", route_path)
        if resolved is None:
            raise RuntimeError(f"config_ui route is not registered: {route_path}")
        return resolved

    def _auth_ui_route(route_path: str) -> str:
        resolved = module_route_path("auth_ui", route_path)
        if resolved is None:
            raise RuntimeError(f"auth_ui route is not registered: {route_path}")
        return resolved

    def _release_update_query(route_path: str, **params: str) -> str:
        base = _release_update_route(route_path)
        clean = [(key, str(value or "").strip()) for key, value in params.items() if str(value or "").strip()]
        if not clean:
            return base
        return f"{base}?{'&'.join(f'{key}={value}' for key, value in clean)}"

    def _auth_ui_query(route_path: str, **params: str) -> str:
        base = _auth_ui_route(route_path)
        clean = [(key, str(value or "").strip()) for key, value in params.items() if str(value or "").strip()]
        if not clean:
            return base
        return f"{base}?{'&'.join(f'{key}={value}' for key, value in clean)}"

    def _release_update_urls() -> dict[str, str]:
        updates_path = _release_update_route("/updates")
        relogin_path = _release_update_route("/updates/relogin")
        return {
            "health": _release_update_route("/health"),
            "updates": updates_path,
            "running": _release_update_route("/updates/running"),
            "run": _release_update_route("/updates/run"),
            "status": _release_update_route("/updates/status"),
            "relogin_updates": f"{relogin_path}?next={quote_plus(updates_path)}",
        }

    def _build_update_control_payload(request: Request) -> dict[str, Any]:
        update_notice = str(request.query_params.get("notice", "") or "").strip().lower()
        update_control = {
            "visible": str(getattr(request.state, "auth_role", "") or "").strip().lower() == "admin",
            "configured": False,
            "reachable": False,
            "running": False,
            "status": "disabled",
            "status_visual": "warn",
            "last_result": "",
            "last_error": "",
            "current_step": "",
            "log_tail": [],
            "helper_error": "",
        }
        if update_control["visible"]:
            helper_config = deps.resolve_update_helper_config(secure_store=deps.get_secure_store())
            update_control["configured"] = helper_config.enabled
            if helper_config.enabled:
                try:
                    helper_status = deps.fetch_update_helper_status(helper_config)
                    update_control.update(helper_status)
                except RuntimeError as exc:
                    update_control["helper_error"] = str(exc)
                    update_control["status"] = "error"
                    update_control["status_visual"] = "error"
            update_control["status_visual"] = deps.helper_status_visual(
                str(update_control.get("status", "") or ""),
                running=bool(update_control.get("running", False)),
                configured=bool(update_control.get("configured", False)),
                reachable=not bool(update_control.get("helper_error", "")),
                last_error=str(update_control.get("last_error", "") or update_control.get("helper_error", "") or ""),
            )
        if update_notice == "update_started" and not update_control["running"]:
            update_control["running"] = True
            update_control["status"] = "requested"
            update_control["status_visual"] = "warn"
        return update_control

    def _render_updates_running_page(
        request: Request,
        *,
        release_meta: dict[str, Any] | None = None,
        update_status: dict[str, Any] | None = None,
        update_control: dict[str, Any] | None = None,
    ) -> HTMLResponse:
        username = deps.get_username_from_request(request)
        settings = deps.get_settings()
        release_payload = dict(release_meta or getattr(request.state, "release_meta", {}) or deps.read_release_meta(deps.base_dir))
        update_payload = dict(update_status or deps.get_update_status(str(release_payload.get("label", "") or "")))
        control_payload = dict(update_control or _build_update_control_payload(request))
        return deps.templates.TemplateResponse(
            request=request,
            name=_release_update_template("updates_running.html"),
            context={
                "title": settings.ui.title,
                "username": username,
                "release_meta": release_payload,
                "update_status": update_payload,
                "update_control": control_payload,
                "release_update_urls": _release_update_urls(),
            },
        )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/system/preflight")
    async def system_preflight() -> dict[str, Any]:
        return await deps.get_runtime_preflight()

    @app.get("/updates", response_class=HTMLResponse)
    async def updates_page(request: Request) -> HTMLResponse:
        def _sanitize_updates_return_to(value: str | None) -> str:
            candidate = str(value or "").strip()
            if not candidate.startswith("/") or candidate.startswith("//"):
                return ""
            return candidate

        settings = deps.get_settings()
        username = deps.get_username_from_request(request)
        release_meta = dict(getattr(request.state, "release_meta", {}) or deps.read_release_meta(deps.base_dir))
        update_status = deps.get_update_status(str(release_meta.get("label", "") or ""))
        update_notice = str(request.query_params.get("notice", "") or "").strip().lower()
        update_error = str(request.query_params.get("error", "") or "").strip().lower()
        update_control = _build_update_control_payload(request)
        logical_back_url = _sanitize_updates_return_to(request.query_params.get("return_to")) or _config_ui_route("/config")
        request.state.logical_back_url = logical_back_url
        if deps.update_finished_after_session(request, update_control):
            return RedirectResponse(
                url=_release_update_query("/updates/relogin", next=quote_plus(_release_update_route("/updates"))),
                status_code=303,
            )
        return deps.templates.TemplateResponse(
            request=request,
            name=_release_update_template("updates.html"),
            context={
                "title": settings.ui.title,
                "username": username,
                "release_meta": release_meta,
                "update_status": update_status,
                "update_control": update_control,
                "update_notice": update_notice,
                "update_error": update_error,
                "config_nav": "updates",
                "config_page_heading": "Updates",
                "error_message": "",
                "saved": False,
                "info_message": "",
                "show_overview_checks": False,
                "overview_checks": [],
                "return_to": logical_back_url,
                "page_return_to": _release_update_route("/updates"),
                "release_update_urls": _release_update_urls(),
            },
        )

    @app.get("/updates/running", response_class=HTMLResponse)
    async def updates_running_page(request: Request) -> HTMLResponse:
        auth_role = str(getattr(request.state, "auth_role", "") or "").strip().lower()
        if auth_role != "admin":
            return RedirectResponse(url=_release_update_route("/updates"), status_code=303)
        return _render_updates_running_page(request)

    @app.get("/updates/relogin")
    async def updates_relogin(request: Request, next: str = "/updates") -> RedirectResponse:  # noqa: A002
        target = str(next or _release_update_route("/updates"))
        if not target.startswith("/"):
            target = _release_update_route("/updates")
        response = RedirectResponse(url=_auth_ui_query("/login", next=quote_plus(target)), status_code=303)
        deps.clear_auth_related_cookies(response, request)
        return response

    @app.post("/updates/run")
    async def run_updates_from_ui(request: Request, csrf_token: str = Form("")) -> Response:  # noqa: ARG001
        wants_json = str(request.headers.get("x-requested-with", "") or "").strip() == "ARIA-Update-UI"
        auth_role = str(getattr(request.state, "auth_role", "") or "").strip().lower()
        if auth_role != "admin":
            if wants_json:
                return JSONResponse(status_code=403, content={"detail": "Admin rights required."})
            return RedirectResponse(url=_release_update_query("/updates", error="no_admin"), status_code=303)
        helper_config = deps.resolve_update_helper_config(secure_store=deps.get_secure_store())
        if not helper_config.enabled:
            if wants_json:
                return JSONResponse(status_code=409, content={"detail": "GUI update helper is not enabled."})
            return RedirectResponse(url=_release_update_query("/updates", error="update_helper_disabled"), status_code=303)
        try:
            result = deps.trigger_update_helper_run(helper_config)
        except RuntimeError as exc:
            error_text = str(exc).strip().lower()
            if "already running" in error_text:
                if wants_json:
                    return JSONResponse(status_code=409, content={"detail": str(exc), "error": "already_running"})
                return RedirectResponse(url=_release_update_query("/updates", error="update_running"), status_code=303)
            if wants_json:
                return JSONResponse(status_code=502, content={"detail": str(exc)})
            return RedirectResponse(url=_release_update_query("/updates", error=quote_plus(str(exc))), status_code=303)
        status = str(result.get("status", "") or "").strip().lower()
        if wants_json:
            return JSONResponse(
                content={
                    "status": status or "accepted",
                    "message": "Update helper accepted the run." if status == "accepted" else "Update request forwarded.",
                    "reload_url": _release_update_urls()["relogin_updates"],
                    "status_url": _release_update_urls()["status"],
                    "running_url": _release_update_urls()["running"],
                }
            )
        if status == "accepted":
            release_meta = dict(getattr(request.state, "release_meta", {}) or deps.read_release_meta(deps.base_dir))
            update_status = deps.get_update_status(str(release_meta.get("label", "") or ""))
            update_control = _build_update_control_payload(request)
            update_control["running"] = True
            update_control["status"] = "requested"
            update_control["status_visual"] = "warn"
            return _render_updates_running_page(
                request,
                release_meta=release_meta,
                update_status=update_status,
                update_control=update_control,
            )
        return RedirectResponse(url=_release_update_query("/updates", notice="update_requested"), status_code=303)

    @app.get("/updates/status")
    async def updates_status_api(request: Request) -> JSONResponse:
        auth_role = str(getattr(request.state, "auth_role", "") or "").strip().lower()
        if auth_role != "admin":
            return JSONResponse(status_code=403, content={"detail": "Admin rights required."})
        helper_config = deps.resolve_update_helper_config(secure_store=deps.get_secure_store())
        if not helper_config.enabled:
            return JSONResponse(
                content={
                    "configured": False,
                    "reachable": False,
                    "running": False,
                    "status": "disabled",
                    "visual_status": "warn",
                    "current_step": "",
                    "last_started_at": "",
                    "last_finished_at": "",
                    "last_result": "",
                    "last_error": "",
                    "log_tail": [],
                }
            )
        try:
            payload = deps.fetch_update_helper_status(helper_config)
        except RuntimeError as exc:
            return JSONResponse(
                status_code=502,
                content={
                    "configured": True,
                    "reachable": False,
                    "running": False,
                    "status": "error",
                    "visual_status": "error",
                    "current_step": "",
                    "last_started_at": "",
                    "last_finished_at": "",
                    "last_result": "",
                    "last_error": str(exc),
                    "helper_error": str(exc),
                    "log_tail": [],
                },
            )
        payload["configured"] = True
        payload["visual_status"] = deps.helper_status_visual(
            str(payload.get("status", "") or ""),
            running=bool(payload.get("running", False)),
            configured=True,
            reachable=True,
            last_error=str(payload.get("last_error", "") or payload.get("helper_error", "") or ""),
        )
        return JSONResponse(content=payload)
