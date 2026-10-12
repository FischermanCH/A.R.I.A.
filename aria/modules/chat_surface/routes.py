from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from aria.modules import module_template_name
from aria.modules.chat_surface.actions import build_chat_quick_actions
from aria.modules.platform_primitives.display_time import (
    format_display_timestamp,
    request_display_timezone_with_source,
)


SettingsGetter = Callable[[], Any]
UsernameResolver = Callable[[Request], str]
AuthSessionResolver = Callable[[Request], dict[str, Any] | None]
SessionIdResolver = Callable[[Request], str]
StoredRecipeManifestLoader = Callable[[], tuple[list[dict[str, Any]], list[str]]]
RoleSanitizer = Callable[[str | None], str]
StoredRecipeProgressHintsBuilder = Callable[[list[dict[str, Any]]], list[dict[str, Any]]]
ChatHistoryLoader = Callable[[str], list[dict[str, Any]]]
AgentJobNoticeReconciler = Callable[[str], Awaitable[int]]
MemoryDayGetter = Callable[[], str]
CookieSecureResolver = Callable[..., bool]
CookieValueResolver = Callable[[Request, str], str]
CookieSetter = Callable[..., None]


@dataclass(frozen=True)
class ChatSurfaceRouteDeps:
    base_dir: Path
    templates: Jinja2Templates
    get_settings: SettingsGetter
    get_username_from_request: UsernameResolver
    get_auth_session_from_request: AuthSessionResolver
    ensure_session_id: SessionIdResolver
    load_stored_recipe_manifests: StoredRecipeManifestLoader
    sanitize_role: RoleSanitizer
    build_client_recipe_progress_hints: StoredRecipeProgressHintsBuilder
    load_chat_history: ChatHistoryLoader
    reconcile_agent_job_notices: AgentJobNoticeReconciler
    current_memory_day: MemoryDayGetter
    cookie_should_be_secure: CookieSecureResolver
    request_cookie_value: CookieValueResolver
    set_response_cookie: CookieSetter
    session_cookie: str


def register_chat_surface_routes(app: FastAPI, deps: ChatSurfaceRouteDeps) -> None:
    def _chat_surface_template(template_name: str) -> str:
        resolved = module_template_name("chat_surface", template_name)
        if resolved is None:
            raise RuntimeError(f"chat_surface template is not registered: {template_name}")
        return resolved

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        settings = deps.get_settings()
        secure_cookie = deps.cookie_should_be_secure(request, public_url=str(settings.aria.public_url or ""))
        username = deps.get_username_from_request(request)
        session_id = deps.ensure_session_id(request)
        auth = deps.get_auth_session_from_request(request) or {}
        stored_recipe_manifests, _ = deps.load_stored_recipe_manifests()
        recipe_trigger_hints: list[str] = []
        seen_hints: set[str] = set()
        lang = str(getattr(request.state, "lang", "de") or "de")
        for manifest in stored_recipe_manifests:
            recipe_name = str(manifest.get("name", "") or "").strip()
            recipe_id = str(manifest.get("id", "") or "").strip()
            names = [value for value in [recipe_name.lower(), recipe_id.replace("-", " ").lower()] if value]
            for item in names:
                if not item or len(item) < 3 or item in seen_hints:
                    continue
                seen_hints.add(item)
                recipe_trigger_hints.append(item)
        if username:
            try:
                await deps.reconcile_agent_job_notices(username)
            except Exception:
                pass
        chat_history = deps.load_chat_history(username) if username else []
        terminal_agent_job_ids = {
            str(item.get("agent_job_id", "") or "")
            for item in chat_history
            if isinstance(item, dict)
            and str(item.get("badge_intent", "") or "") in {
                "agent_job_done", "agent_job_error", "agent_job_cancelled",
            }
        }
        display_timezone, display_timezone_source = request_display_timezone_with_source(
            request, settings
        )
        for item in chat_history:
            if not isinstance(item, dict):
                continue
            item["display_timestamp"] = format_display_timestamp(
                item.get("timestamp"),
                display_timezone,
                language=lang,
            )
        auth_role = deps.sanitize_role(auth.get("role"))
        client_recipe_progress_hints = deps.build_client_recipe_progress_hints(stored_recipe_manifests)
        chat_quick_actions = build_chat_quick_actions(lang)
        response = deps.templates.TemplateResponse(
            request=request,
            name=_chat_surface_template("chat.html"),
            context={
                "title": settings.ui.title,
                "username": username,
                "recipe_trigger_hints": sorted(recipe_trigger_hints, key=len, reverse=True),
                "recipe_progress_hints": client_recipe_progress_hints,
                "skill_trigger_hints": sorted(recipe_trigger_hints, key=len, reverse=True),
                "skill_progress_hints": client_recipe_progress_hints,
                "chat_quick_actions": chat_quick_actions,
                "terminal_agent_job_ids": terminal_agent_job_ids,
                "active_memory_day": deps.current_memory_day(),
                "debug_mode": bool(settings.ui.debug_mode),
                "active_session_id": session_id,
                "auth_role": auth_role,
                "chat_history": chat_history,
                "display_timezone": display_timezone,
                "display_timezone_source": display_timezone_source,
            },
        )
        if not deps.request_cookie_value(request, deps.session_cookie):
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
