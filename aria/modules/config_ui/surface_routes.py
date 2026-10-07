from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from aria.modules.platform_primitives.i18n import I18NStore
from aria.modules.read_model import (
    module_lifecycle_diagnostics,
    module_lifecycle_rows,
    module_registry_diagnostics,
    module_route_path,
    module_status_rows,
    module_template_name,
)
from aria.modules.config_ui.ui_audit import (
    UI_AUDIT_STATUSES,
    UIAuditDecisionStore,
    audit_template_rows,
    build_ui_route_inventory,
)


ConfigOverviewChecksBuilder = Callable[[Request], list[dict[str, str]]]
ConfigInfoMessageFormatter = Callable[[str, str], str]
UsernameResolver = Callable[[Request], str]
LogicalBackSetter = Callable[[Request], str]
SurfacePathResolver = Callable[[str | None], str]
LocalizedMessage = Callable[[str, str, str], str]
SettingsGetter = Callable[[], Any]
RawConfigReader = Callable[[], dict[str, Any]]
RawConfigWriter = Callable[[dict[str, Any]], None]
RuntimeReloader = Callable[[], None]
SecureStoreGetter = Callable[[dict[str, Any] | None], Any]
UpdateHelperConfigResolver = Callable[..., Any]
UpdateHelperStatusFetcher = Callable[..., dict[str, Any]]
ServiceRestartTrigger = Callable[..., dict[str, Any]]
ManagedServiceProbe = Callable[..., dict[str, Any]]
_CONFIG_SURFACE_I18N = I18NStore(Path(__file__).resolve().parents[2] / "i18n")

def _config_surface_text(language: str, key: str, default: str = "", **values: object) -> str:
    template = _CONFIG_SURFACE_I18N.t(language, f"config_surface.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template


def _ops_config_template(template_name: str) -> str:
    resolved = module_template_name("ops_config_backup", template_name)
    if resolved is None:
        raise RuntimeError(f"ops_config_backup template is not registered: {template_name}")
    return resolved


def _ops_config_route(route_path: str) -> str:
    resolved = module_route_path("ops_config_backup", route_path)
    if resolved is None:
        raise RuntimeError(f"ops_config_backup route is not registered: {route_path}")
    return resolved


def _config_ui_template(template_name: str) -> str:
    resolved = module_template_name("config_ui", template_name)
    if resolved is None:
        raise RuntimeError(f"config_ui template is not registered: {template_name}")
    return resolved


def _config_ui_path(route_path: str) -> str:
    resolved = module_route_path("config_ui", route_path)
    if resolved is None:
        raise RuntimeError(f"config_ui route is not registered: {route_path}")
    return resolved


def _chat_surface_path(route_path: str) -> str:
    resolved = module_route_path("chat_surface", route_path)
    if resolved is None:
        raise RuntimeError(f"chat_surface route is not registered: {route_path}")
    return resolved


def _config_ui_query(route_path: str, **params: str) -> str:
    base = _config_ui_path(route_path)
    clean = [(key, str(value or "").strip()) for key, value in params.items() if str(value or "").strip()]
    if not clean:
        return base
    return f"{base}?{'&'.join(f'{key}={value}' for key, value in clean)}"


def _ops_config_query(route_path: str, **params: str) -> str:
    base = _ops_config_route(route_path)
    clean = [(key, str(value or "").strip()) for key, value in params.items() if str(value or "").strip()]
    if not clean:
        return base
    return f"{base}?{'&'.join(f'{key}={value}' for key, value in clean)}"


@dataclass(frozen=True)
class ConfigSurfaceRouteDeps:
    templates: Jinja2Templates
    base_dir: Path
    get_settings: SettingsGetter
    read_raw_config: RawConfigReader
    write_raw_config: RawConfigWriter
    reload_runtime: RuntimeReloader
    get_username_from_request: UsernameResolver
    set_logical_back_url: LogicalBackSetter
    config_surface_path: SurfacePathResolver
    build_config_overview_checks: ConfigOverviewChecksBuilder
    format_config_info_message: ConfigInfoMessageFormatter
    msg: LocalizedMessage
    get_secure_store: SecureStoreGetter
    resolve_update_helper_config: UpdateHelperConfigResolver
    fetch_update_helper_status: UpdateHelperStatusFetcher
    trigger_update_helper_service_restart: ServiceRestartTrigger


class ConfigSurfaceRouter:
    def __init__(self, deps: ConfigSurfaceRouteDeps) -> None:
        self.deps = deps
        self.ui_audit_store = UIAuditDecisionStore(deps.base_dir / "data" / "runtime" / "ui_audit_decisions.json")

    def build_config_page_context(
        self,
        request: Request,
        *,
        saved: int = 0,
        error: str = "",
        info: str = "",
        logical_back_fallback: str | None = None,
        page_return_to: str | None = None,
        config_nav: str = "overview",
        page_heading: str,
        show_overview_checks: bool = False,
    ) -> dict[str, Any]:
        settings = self.deps.get_settings()
        username = self.deps.get_username_from_request(request) or "web"
        lang = str(getattr(request.state, "lang", "de") or "de")
        config_root = _config_ui_path("/config")
        logical_back_fallback = logical_back_fallback or config_root
        page_return_to = page_return_to or config_root
        logical_back_url = self.deps.set_logical_back_url(request, fallback=logical_back_fallback)
        if error == "admin_mode_required":
            error_message = _config_surface_text(lang, "admin_mode_required", "Enable Extended view to access this area.")
        elif error == "no_admin":
            error_message = _config_surface_text(lang, "no_admin", "Only admins can open this area.")
        else:
            error_message = str(error or "").strip()
        return {
            "title": settings.ui.title,
            "username": username,
            "saved": bool(saved),
            "info_message": self.deps.format_config_info_message(lang, info),
            "error_message": error_message,
            "overview_checks": self.deps.build_config_overview_checks(request),
            "config_nav": config_nav,
            "config_page_heading": page_heading,
            "return_to": logical_back_url,
            "page_return_to": self.deps.config_surface_path(page_return_to, fallback=config_root),
            "show_overview_checks": bool(show_overview_checks),
        }

    def build_operations_service_restart_context(self, request: Request) -> dict[str, Any]:
        lang = str(getattr(request.state, "lang", "de") or "de")
        service_meta = {
            "qdrant": {
                "title": _config_surface_text(lang, "restart_qdrant_title", "Restart Qdrant"),
                "desc": _config_surface_text(
                    lang,
                    "restart_qdrant_desc",
                    "Restart the vector store used for memory and routing.",
                ),
                "confirm": _config_surface_text(
                    lang,
                    "restart_qdrant_confirm",
                    "Restart Qdrant now? Memory and routing may be briefly unavailable.",
                ),
                "icon": "qdrant",
            },
        }
        payload = {
            "configured": False,
            "helper_error": "",
            "running": False,
            "status": "disabled",
            "status_visual": "warn",
            "current_step": "",
            "last_result": "",
            "last_error": "",
            "disabled": True,
            "services": [{"id": service_id, **meta} for service_id, meta in service_meta.items()],
            "native_web_llm": {
                "available": False,
                "status": "warn",
                "profile": "",
                "model": "",
                "transport": "",
                "verified_at": "",
                "search_budget": 3,
            },
        }
        settings = self.deps.get_settings()
        web_llm = getattr(settings, "web_llm", None)
        if web_llm is not None:
            verified_at = str(getattr(web_llm, "capability_verified_at", "") or "").strip()
            available = bool(
                getattr(web_llm, "enabled", False)
                and str(getattr(web_llm, "model", "") or "").strip()
                and verified_at
            )
            payload["native_web_llm"] = {
                "available": available,
                "status": "ok" if available else "warn",
                "profile": str(getattr(web_llm, "profile", "") or "").strip(),
                "model": str(getattr(web_llm, "model", "") or "").strip(),
                "transport": str(getattr(web_llm, "transport", "") or "").strip(),
                "verified_at": verified_at,
                "search_budget": int(getattr(web_llm, "max_search_uses", 3) or 3),
            }
        if not bool(getattr(request.state, "can_access_advanced_config", False)):
            return payload
        helper_config = self.deps.resolve_update_helper_config(secure_store=self.deps.get_secure_store(None))
        payload["configured"] = helper_config.enabled
        if helper_config.enabled:
            try:
                helper_status = self.deps.fetch_update_helper_status(helper_config, timeout=1.2)
                payload.update(
                    {
                        "running": bool(helper_status.get("running", False)),
                        "status": str(helper_status.get("status", "") or "idle"),
                        "status_visual": str(helper_status.get("visual_status", "") or "ok"),
                        "current_step": str(helper_status.get("current_step", "") or ""),
                        "last_result": str(helper_status.get("last_result", "") or ""),
                        "last_error": str(helper_status.get("last_error", "") or helper_status.get("error", "") or ""),
                    }
                )
            except RuntimeError as exc:
                payload["helper_error"] = str(exc)
                payload["status"] = "error"
                payload["status_visual"] = "error"
        payload["disabled"] = not bool(payload["configured"]) or bool(payload["helper_error"]) or bool(payload["running"])
        return payload

    def render_config_surface(
        self,
        request: Request,
        *,
        template_name: str,
        saved: int = 0,
        error: str = "",
        info: str = "",
        logical_back_fallback: str | None = None,
        page_return_to: str | None = None,
        config_nav: str = "overview",
        page_heading: str,
        show_overview_checks: bool = False,
        extra_context: dict[str, Any] | None = None,
    ) -> HTMLResponse:
        context = self.build_config_page_context(
            request,
            saved=saved,
            error=error,
            info=info,
            logical_back_fallback=logical_back_fallback,
            page_return_to=page_return_to,
            config_nav=config_nav,
            page_heading=page_heading,
            show_overview_checks=show_overview_checks,
        )
        if extra_context:
            context.update(extra_context)
        return self.deps.templates.TemplateResponse(
            request=request,
            name=_config_ui_template(template_name),
            context=context,
        )


def register_config_surface_routes(app: FastAPI, router: ConfigSurfaceRouter) -> None:
    @app.get("/config", response_class=HTMLResponse)
    async def config_page(
        request: Request,
        saved: int = 0,
        error: str = "",
        info: str = "",
    ) -> HTMLResponse:
        lang = str(getattr(request.state, "lang", "de") or "de")
        return router.render_config_surface(
            request,
            template_name="config_hub.html",
            saved=saved,
            error=error,
            info=info,
            logical_back_fallback=_chat_surface_path("/"),
            page_return_to=_config_ui_path("/config"),
            config_nav="overview",
            page_heading=_config_surface_text(lang, "heading_settings", "Settings"),
            show_overview_checks=False,
        )

    @app.get("/config/admin/modules", response_class=HTMLResponse)
    async def config_admin_modules_page(
        request: Request,
        saved: int = 0,
        error: str = "",
        info: str = "",
    ) -> HTMLResponse:
        if not bool(getattr(request.state, "can_access_advanced_config", False)):
            return RedirectResponse(url=_config_ui_query("/config", error="admin_mode_required"), status_code=303)
        lang = str(getattr(request.state, "lang", "de") or "de")
        module_rows = module_status_rows()
        module_diagnostics = module_registry_diagnostics()
        lifecycle_rows = module_lifecycle_rows()
        lifecycle_by_id = {row["id"]: row for row in lifecycle_rows}
        for module_row in module_rows:
            module_row["lifecycle"] = lifecycle_by_id[module_row["id"]]
        return router.render_config_surface(
            request,
            template_name="config_admin_modules.html",
            saved=saved,
            error=error,
            info=info,
            logical_back_fallback=_config_ui_path("/config"),
            page_return_to=_config_ui_path("/config/admin/modules"),
            config_nav="admin",
            page_heading=_config_surface_text(lang, "heading_modules", "Module Registry"),
            extra_context={
                "module_status_rows": module_rows,
                "module_status_total": len(module_rows),
                "module_status_build_allowed_count": sum(1 for row in module_rows if bool(row.get("build_allowed"))),
                "module_status_runtime_allowed_count": sum(1 for row in module_rows if bool(row.get("runtime_access_allowed"))),
                "module_registry_diagnostics": module_diagnostics,
                "module_lifecycle_diagnostics": module_lifecycle_diagnostics(),
            },
        )

    def _ui_audit_admin_allowed(request: Request) -> bool:
        return bool(getattr(request.state, "can_access_advanced_config", False)) and str(
            getattr(request.state, "auth_role", "") or ""
        ).strip().lower() == "admin"

    @app.get("/config/admin/ui-audit", response_class=HTMLResponse)
    async def config_admin_ui_audit_page(
        request: Request,
        saved: int = 0,
        error: str = "",
        info: str = "",
    ) -> HTMLResponse:
        if not _ui_audit_admin_allowed(request):
            return RedirectResponse(url=_config_ui_query("/config", error="no_admin"), status_code=303)
        lang = str(getattr(request.state, "lang", "de") or "de")
        routes = build_ui_route_inventory(app)
        rows = audit_template_rows(routes, router.ui_audit_store)
        return router.render_config_surface(
            request,
            template_name="config_admin_ui_audit.html",
            saved=saved,
            error=error,
            info=info,
            logical_back_fallback=_config_ui_path("/config/admin/modules"),
            page_return_to=_config_ui_path("/config/admin/ui-audit"),
            config_nav="admin",
            page_heading=router.deps.msg(lang, "UI-Routen-Audit", "UI route audit"),
            extra_context={
                "ui_audit_rows": rows,
                "ui_audit_statuses": UI_AUDIT_STATUSES,
            },
        )

    @app.post("/config/admin/ui-audit/save")
    async def config_admin_ui_audit_save(
        request: Request,
        route_key: str = Form(""),
        status: str = Form("verify"),
        note: str = Form(""),
        csrf_token: str = Form(""),  # noqa: ARG001
    ) -> Response:
        if not _ui_audit_admin_allowed(request):
            return JSONResponse({"error": "admin_required"}, status_code=403)
        valid_keys = {route.key for route in build_ui_route_inventory(app)}
        if route_key not in valid_keys:
            return JSONResponse({"error": "route_unknown"}, status_code=404)
        try:
            router.ui_audit_store.save(route_key, status=status, note=note)
        except ValueError:
            return JSONResponse({"error": "decision_invalid"}, status_code=422)
        return Response(status_code=204)

    @app.post("/config/admin/ui-audit/save-all")
    async def config_admin_ui_audit_save_all(request: Request) -> Response:
        if not _ui_audit_admin_allowed(request):
            return JSONResponse({"error": "admin_required"}, status_code=403)
        form = await request.form()
        route_keys = [str(value or "") for value in form.getlist("route_key")]
        statuses = [str(value or "") for value in form.getlist("status")]
        notes = [str(value or "") for value in form.getlist("note")]
        valid_keys = {route.key for route in build_ui_route_inventory(app)}
        for route_key, status, note in zip(route_keys, statuses, notes, strict=False):
            if route_key not in valid_keys:
                continue
            try:
                router.ui_audit_store.save(route_key, status=status, note=note)
            except ValueError:
                continue
        return RedirectResponse(url=_config_ui_query("/config/admin/ui-audit", saved=1), status_code=303)

    @app.get("/config/admin/ui-audit/export")
    async def config_admin_ui_audit_export(request: Request) -> JSONResponse:
        if not _ui_audit_admin_allowed(request):
            return JSONResponse({"error": "admin_required"}, status_code=403)
        payload = router.ui_audit_store.export(build_ui_route_inventory(app))
        return JSONResponse(
            payload,
            headers={"Content-Disposition": 'attachment; filename="aria-ui-route-audit.json"'},
        )

    @app.get("/config/intelligence", response_class=HTMLResponse)
    async def config_intelligence_page(
        request: Request,
        saved: int = 0,
        error: str = "",
        info: str = "",
    ) -> HTMLResponse:
        lang = str(getattr(request.state, "lang", "de") or "de")
        return router.render_config_surface(
            request,
            template_name="config_intelligence.html",
            saved=saved,
            error=error,
            info=info,
            logical_back_fallback=_config_ui_path("/config"),
            page_return_to=_config_ui_path("/config/intelligence"),
            config_nav="intelligence",
            page_heading=_config_surface_text(lang, "heading_intelligence", "Tune intelligence"),
        )

    @app.get("/config/persona", response_class=HTMLResponse)
    async def config_persona_page(
        request: Request,
        saved: int = 0,
        error: str = "",
        info: str = "",
    ) -> HTMLResponse:
        lang = str(getattr(request.state, "lang", "de") or "de")
        return router.render_config_surface(
            request,
            template_name="config_persona.html",
            saved=saved,
            error=error,
            info=info,
            logical_back_fallback=_config_ui_path("/config"),
            page_return_to=_config_ui_path("/config/persona"),
            config_nav="persona",
            page_heading=_config_surface_text(lang, "heading_persona", "Personality & style"),
        )

    @app.get("/config/access", response_class=HTMLResponse)
    async def config_access_page(
        request: Request,
        saved: int = 0,
        error: str = "",
        info: str = "",
    ) -> HTMLResponse:
        lang = str(getattr(request.state, "lang", "de") or "de")
        return router.render_config_surface(
            request,
            template_name="config_access.html",
            saved=saved,
            error=error,
            info=info,
            logical_back_fallback=_config_ui_path("/config"),
            page_return_to=_config_ui_path("/config/access"),
            config_nav="access",
            page_heading=_config_surface_text(lang, "heading_access", "Access & safety"),
        )

    @app.get("/config/operations", response_class=HTMLResponse)
    async def config_operations_page(
        request: Request,
        saved: int = 0,
        error: str = "",
        info: str = "",
    ) -> HTMLResponse:
        lang = str(getattr(request.state, "lang", "de") or "de")
        context = router.build_config_page_context(
            request,
            saved=saved,
            error=error,
            info=info,
            logical_back_fallback=_config_ui_path("/config"),
            page_return_to=_ops_config_route("/config/operations"),
            config_nav="operations",
            page_heading=_config_surface_text(lang, "heading_operations", "Operations & transfer"),
        )
        context["operations_service_restart"] = router.build_operations_service_restart_context(request)
        return router.deps.templates.TemplateResponse(
            request=request,
            name=_ops_config_template("config_operations.html"),
            context=context,
        )

    @app.post("/config/operations/service-restart")
    async def config_operations_service_restart(
        request: Request,
        service: str = Form(""),
        csrf_token: str = Form(""),  # noqa: ARG001
    ) -> RedirectResponse:
        if not bool(getattr(request.state, "can_access_advanced_config", False)):
            return RedirectResponse(url=_ops_config_query("/config/operations", error="no_admin"), status_code=303)
        lang = str(getattr(request.state, "lang", "de") or "de")
        target = str(service or "").strip().lower()
        service_labels = {"qdrant": "Qdrant"}
        label = service_labels.get(target, "")
        if not label:
            message = _config_surface_text(lang, "unknown_restart_target", "Unknown service restart target.")
            return RedirectResponse(url=_ops_config_query("/config/operations", error=quote_plus(message)), status_code=303)
        helper_config = router.deps.resolve_update_helper_config(secure_store=router.deps.get_secure_store(None))
        if not helper_config.enabled:
            message = _config_surface_text(lang, "restart_helper_disabled", "No GUI helper for service restarts is enabled.")
            return RedirectResponse(url=_ops_config_query("/config/operations", error=quote_plus(message)), status_code=303)
        try:
            result = router.deps.trigger_update_helper_service_restart(helper_config, target)
        except ValueError:
            message = _config_surface_text(lang, "unknown_restart_target", "Unknown service restart target.")
            return RedirectResponse(url=_ops_config_query("/config/operations", error=quote_plus(message)), status_code=303)
        except RuntimeError as exc:
            return RedirectResponse(url=_ops_config_query("/config/operations", error=quote_plus(str(exc))), status_code=303)
        status = str(result.get("status", "") or "").strip().lower()
        if status != "accepted":
            message = _config_surface_text(
                lang,
                "restart_request_failed",
                "{label} restart could not be requested.",
                label=label,
            )
            return RedirectResponse(url=_ops_config_query("/config/operations", error=quote_plus(message)), status_code=303)
        info_message = _config_surface_text(
            lang,
            "restart_requested",
            "{label} restart requested. The helper is restarting the service in the background.",
            label=label,
        )
        return RedirectResponse(url=_ops_config_query("/config/operations", saved="1", info=quote_plus(info_message)), status_code=303)
