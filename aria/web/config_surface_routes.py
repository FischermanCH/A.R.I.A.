from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from aria.core.i18n import I18NStore


ConfigOverviewChecksBuilder = Callable[[Request], list[dict[str, str]]]
ConfigInfoMessageFormatter = Callable[[str, str], str]
UsernameResolver = Callable[[Request], str]
LogicalBackSetter = Callable[[Request], str]
SurfacePathResolver = Callable[[str | None], str]
LocalizedMessage = Callable[[str, str, str], str]
SettingsGetter = Callable[[], Any]
SecureStoreGetter = Callable[[dict[str, Any] | None], Any]
UpdateHelperConfigResolver = Callable[..., Any]
UpdateHelperStatusFetcher = Callable[..., dict[str, Any]]
ServiceRestartTrigger = Callable[..., dict[str, Any]]
_CONFIG_SURFACE_I18N = I18NStore(Path(__file__).resolve().parents[1] / "i18n")


def _config_surface_text(language: str, key: str, default: str = "", **values: object) -> str:
    template = _CONFIG_SURFACE_I18N.t(language, f"config_surface.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template


@dataclass(frozen=True)
class ConfigSurfaceRouteDeps:
    templates: Jinja2Templates
    get_settings: SettingsGetter
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

    def build_config_page_context(
        self,
        request: Request,
        *,
        saved: int = 0,
        error: str = "",
        info: str = "",
        logical_back_fallback: str = "/config",
        page_return_to: str = "/config",
        config_nav: str = "overview",
        page_heading: str,
        show_overview_checks: bool = False,
    ) -> dict[str, Any]:
        settings = self.deps.get_settings()
        username = self.deps.get_username_from_request(request) or "web"
        lang = str(getattr(request.state, "lang", "de") or "de")
        logical_back_url = self.deps.set_logical_back_url(request, fallback=logical_back_fallback)
        if error == "admin_mode_required":
            error_message = _config_surface_text(lang, "admin_mode_required", "Enable admin mode to access this area.")
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
            "page_return_to": self.deps.config_surface_path(page_return_to, fallback="/config"),
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
            "searxng": {
                "title": _config_surface_text(lang, "restart_searxng_title", "Restart SearXNG"),
                "desc": _config_surface_text(
                    lang,
                    "restart_searxng_desc",
                    "Restart the web-search and search-API service in the stack.",
                ),
                "confirm": _config_surface_text(
                    lang,
                    "restart_searxng_confirm",
                    "Restart SearXNG now? Web search and the search API may be briefly unavailable.",
                ),
                "icon": "searxng",
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
        logical_back_fallback: str = "/config",
        page_return_to: str = "/config",
        config_nav: str = "overview",
        page_heading: str,
        show_overview_checks: bool = False,
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
        return self.deps.templates.TemplateResponse(request=request, name=template_name, context=context)


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
            logical_back_fallback="/",
            page_return_to="/config",
            config_nav="overview",
            page_heading=_config_surface_text(lang, "heading_settings", "Settings"),
            show_overview_checks=True,
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
            logical_back_fallback="/config",
            page_return_to="/config/intelligence",
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
            logical_back_fallback="/config",
            page_return_to="/config/persona",
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
            logical_back_fallback="/config",
            page_return_to="/config/access",
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
            logical_back_fallback="/config",
            page_return_to="/config/operations",
            config_nav="operations",
            page_heading=_config_surface_text(lang, "heading_operations", "Operations & transfer"),
        )
        context["operations_service_restart"] = router.build_operations_service_restart_context(request)
        return router.deps.templates.TemplateResponse(
            request=request,
            name="config_operations.html",
            context=context,
        )

    @app.post("/config/operations/service-restart")
    async def config_operations_service_restart(
        request: Request,
        service: str = Form(""),
        csrf_token: str = Form(""),  # noqa: ARG001
    ) -> RedirectResponse:
        if not bool(getattr(request.state, "can_access_advanced_config", False)):
            return RedirectResponse(url="/config/operations?error=no_admin", status_code=303)
        lang = str(getattr(request.state, "lang", "de") or "de")
        target = str(service or "").strip().lower()
        service_labels = {"qdrant": "Qdrant", "searxng": "SearXNG"}
        label = service_labels.get(target, "")
        if not label:
            message = _config_surface_text(lang, "unknown_restart_target", "Unknown service restart target.")
            return RedirectResponse(url=f"/config/operations?error={quote_plus(message)}", status_code=303)
        helper_config = router.deps.resolve_update_helper_config(secure_store=router.deps.get_secure_store(None))
        if not helper_config.enabled:
            message = _config_surface_text(lang, "restart_helper_disabled", "No GUI helper for service restarts is enabled.")
            return RedirectResponse(url=f"/config/operations?error={quote_plus(message)}", status_code=303)
        try:
            result = router.deps.trigger_update_helper_service_restart(helper_config, target)
        except ValueError:
            message = _config_surface_text(lang, "unknown_restart_target", "Unknown service restart target.")
            return RedirectResponse(url=f"/config/operations?error={quote_plus(message)}", status_code=303)
        except RuntimeError as exc:
            return RedirectResponse(url=f"/config/operations?error={quote_plus(str(exc))}", status_code=303)
        status = str(result.get("status", "") or "").strip().lower()
        if status != "accepted":
            message = _config_surface_text(
                lang,
                "restart_request_failed",
                "{label} restart could not be requested.",
                label=label,
            )
            return RedirectResponse(url=f"/config/operations?error={quote_plus(message)}", status_code=303)
        info_message = _config_surface_text(
            lang,
            "restart_requested",
            "{label} restart requested. The helper is restarting the service in the background.",
            label=label,
        )
        return RedirectResponse(url=f"/config/operations?saved=1&info={quote_plus(info_message)}", status_code=303)

    @app.get("/config/workbench", response_class=HTMLResponse)
    async def config_workbench_page(
        request: Request,
        saved: int = 0,
        error: str = "",
        info: str = "",
    ) -> HTMLResponse:
        lang = str(getattr(request.state, "lang", "de") or "de")
        return router.render_config_surface(
            request,
            template_name="config_workbench.html",
            saved=saved,
            error=error,
            info=info,
            logical_back_fallback="/config",
            page_return_to="/config/workbench",
            config_nav="workbench",
            page_heading=_config_surface_text(lang, "heading_workbench", "Workbench"),
        )
