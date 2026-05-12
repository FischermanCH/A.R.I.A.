from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from aria.core.stored_recipe_manifest_view import stored_recipe_candidate_metadata
from aria.core.stored_recipe_manifest_view import stored_recipe_trigger_values
from aria.web.stored_recipe_ui import build_stored_recipe_toolbox_row


SettingsGetter = Callable[[], Any]
UsernameResolver = Callable[[Request], str]
AuthSessionResolver = Callable[[Request], dict[str, Any] | None]
SessionIdResolver = Callable[[Request], str]
AutoMemoryResolver = Callable[[Request], bool]
MemoryCollectionResolver = Callable[[Request, str], str]
SessionCollectionResolver = Callable[[str, str], str]
StoredRecipeManifestLoader = Callable[[], tuple[list[dict[str, Any]], list[str]]]
StoredRecipeDescriptionLocalizer = Callable[[dict[str, Any], str], str]
RoleSanitizer = Callable[[str | None], str]
StoredRecipeProgressHintsBuilder = Callable[[list[dict[str, Any]]], list[dict[str, Any]]]
ConnectionCatalogGetter = Callable[[], dict[str, list[str]]]
ChatCatalogBuilder = Callable[..., tuple[list[dict[str, Any]], dict[str, str], list[dict[str, Any]]]]
ChatHistoryLoader = Callable[[str], list[dict[str, Any]]]
MemoryDayGetter = Callable[[], str]
CookieSecureResolver = Callable[..., bool]
CookieValueResolver = Callable[[Request, str], str]
CookieSetter = Callable[..., None]


@dataclass(frozen=True)
class ChatSurfaceRouteDeps:
    templates: Jinja2Templates
    get_settings: SettingsGetter
    get_username_from_request: UsernameResolver
    get_auth_session_from_request: AuthSessionResolver
    ensure_session_id: SessionIdResolver
    is_auto_memory_enabled: AutoMemoryResolver
    get_effective_memory_collection: MemoryCollectionResolver
    session_memory_collection_for_user: SessionCollectionResolver
    load_stored_recipe_manifests: StoredRecipeManifestLoader
    localize_stored_recipe_description: StoredRecipeDescriptionLocalizer
    sanitize_role: RoleSanitizer
    build_client_recipe_progress_hints: StoredRecipeProgressHintsBuilder
    get_connection_catalog: ConnectionCatalogGetter
    build_chat_command_catalog: ChatCatalogBuilder
    load_chat_history: ChatHistoryLoader
    current_memory_day: MemoryDayGetter
    cookie_should_be_secure: CookieSecureResolver
    request_cookie_value: CookieValueResolver
    set_response_cookie: CookieSetter
    session_cookie: str
    auto_memory_cookie: str


def register_chat_surface_routes(app: FastAPI, deps: ChatSurfaceRouteDeps) -> None:
    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        settings = deps.get_settings()
        secure_cookie = deps.cookie_should_be_secure(request, public_url=str(settings.aria.public_url or ""))
        username = deps.get_username_from_request(request)
        session_id = deps.ensure_session_id(request)
        auth = deps.get_auth_session_from_request(request) or {}
        auto_memory_enabled = deps.is_auto_memory_enabled(request)
        recall_templates = settings.routing.memory_recall_keywords
        store_templates = settings.routing.memory_store_prefixes
        stored_recipe_manifests, _ = deps.load_stored_recipe_manifests()
        recipe_trigger_hints: list[str] = []
        recipe_toolbox_rows: list[dict[str, Any]] = []
        seen_hints: set[str] = set()
        lang = str(getattr(request.state, "lang", "de") or "de")
        for manifest in stored_recipe_manifests:
            recipe_name = str(manifest.get("name", "") or "").strip()
            recipe_id = str(manifest.get("id", "") or "").strip()
            trigger_values = [item for item in stored_recipe_trigger_values(manifest) if item]
            names = [value for value in [recipe_name.lower(), recipe_id.replace("-", " ").lower()] if value]
            description = deps.localize_stored_recipe_description(manifest, lang).strip()
            for item in names + [value.lower() for value in trigger_values]:
                if not item or len(item) < 3 or item in seen_hints:
                    continue
                seen_hints.add(item)
                recipe_trigger_hints.append(item)
            toolbox_row = build_stored_recipe_toolbox_row(manifest, description=description)
            if toolbox_row:
                recipe_toolbox_rows.append(toolbox_row)
        active_collection = deps.get_effective_memory_collection(request, username or "web")
        session_collection = deps.session_memory_collection_for_user(username or "web", session_id)
        chat_history = deps.load_chat_history(username) if username else []
        auth_role = deps.sanitize_role(auth.get("role"))
        client_recipe_progress_hints = deps.build_client_recipe_progress_hints(stored_recipe_manifests)
        chat_command_entries, chat_command_group_titles, chat_toolbox_groups = deps.build_chat_command_catalog(
            lang=lang,
            auth_role=auth_role,
            advanced_mode=bool(getattr(request.state, "can_access_advanced_config", False)),
            recall_templates=list(recall_templates),
            store_templates=list(store_templates),
            recipe_trigger_hints=sorted(recipe_trigger_hints, key=len, reverse=True),
            recipe_toolbox_rows=sorted(
                recipe_toolbox_rows,
                key=lambda row: (
                    str(row.get("label", "") or "").lower(),
                    str(row.get("insert", "") or "").lower(),
                ),
            ),
            connection_catalog=deps.get_connection_catalog(),
            recent_messages=[
                str(item.get("text", "")).strip()
                for item in chat_history[-8:]
                if isinstance(item, dict) and str(item.get("text", "")).strip()
            ],
        )
        response = deps.templates.TemplateResponse(
            request=request,
            name="chat.html",
            context={
                "title": settings.ui.title,
                "username": username,
                "recall_templates": recall_templates,
                "store_templates": store_templates,
                "recipe_trigger_hints": sorted(recipe_trigger_hints, key=len, reverse=True),
                "recipe_progress_hints": client_recipe_progress_hints,
                "skill_trigger_hints": sorted(recipe_trigger_hints, key=len, reverse=True),
                "skill_progress_hints": client_recipe_progress_hints,
                "chat_command_entries": chat_command_entries,
                "chat_command_group_titles": chat_command_group_titles,
                "chat_toolbox_groups": chat_toolbox_groups,
                "active_memory_collection": active_collection,
                "active_session_collection": session_collection,
                "auto_memory_enabled": auto_memory_enabled,
                "active_memory_day": deps.current_memory_day(),
                "debug_mode": bool(settings.ui.debug_mode),
                "active_session_id": session_id,
                "auth_role": auth_role,
                "chat_history": chat_history,
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
        deps.set_response_cookie(
            response,
            request,
            deps.auto_memory_cookie,
            "1" if auto_memory_enabled else "0",
            max_age=60 * 60 * 24 * 365,
            secure=secure_cookie,
            httponly=False,
        )
        return response
