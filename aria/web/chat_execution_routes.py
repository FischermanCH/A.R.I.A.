from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates

from aria.web.chat_execution_flow import ChatExecutionDeps, execute_chat_flow
from aria.web.chat_route_helpers import (
    apply_chat_response_cookies,
    prepare_chat_route_state,
    render_missing_username_response,
)


SettingsGetter = Callable[[], Any]
UsernameResolver = Callable[[Request], str]
SessionIdResolver = Callable[[Request], str]
AutoMemoryResolver = Callable[[Request], bool]
MemoryCollectionResolver = Callable[[Request, str], str]
SessionCollectionResolver = Callable[[str, str], str]
CookieSecureResolver = Callable[..., bool]
CookieValueResolver = Callable[[Request, str], str]
CookieSetter = Callable[..., None]
CookieDeleter = Callable[..., None]
HistoryAppender = Callable[..., None]
HistoryClearer = Callable[[str], None]
ContextClearer = Callable[[str], None]
SanitizeUsername = Callable[[str | None], str]
SanitizeConnectionName = Callable[[str | None], str]
SanitizeRole = Callable[[str | None], str]
IntentBadge = Callable[[list[str], list[str] | None], tuple[str, str]]
FriendlyErrorText = Callable[[list[str] | None], str]


@dataclass(frozen=True)
class ChatExecutionRouteDeps:
    templates: Jinja2Templates
    get_settings: SettingsGetter
    get_username_from_request: UsernameResolver
    ensure_session_id: SessionIdResolver
    is_auto_memory_enabled: AutoMemoryResolver
    get_effective_memory_collection: MemoryCollectionResolver
    session_memory_collection_for_user: SessionCollectionResolver
    cookie_should_be_secure: CookieSecureResolver
    request_cookie_value: CookieValueResolver
    set_response_cookie: CookieSetter
    delete_response_cookie: CookieDeleter
    sanitize_username: SanitizeUsername
    sanitize_connection_name: SanitizeConnectionName
    sanitize_role: SanitizeRole
    intent_badge: IntentBadge
    friendly_error_text: FriendlyErrorText
    execution_deps: ChatExecutionDeps
    append_chat_history: HistoryAppender
    clear_chat_history: HistoryClearer
    clear_capability_context: ContextClearer
    session_cookie: str
    forget_pending_cookie: str
    safe_fix_pending_cookie: str
    connection_delete_pending_cookie: str
    connection_create_pending_cookie: str
    connection_update_pending_cookie: str
    update_pending_cookie: str
    routed_action_pending_cookie: str
    connection_pending_max_age_seconds: int
    forget_signing_secret: str


def register_chat_execution_routes(app: FastAPI, deps: ChatExecutionRouteDeps) -> None:
    @app.post("/chat", response_class=HTMLResponse)
    async def chat(request: Request, message: str = Form(...)) -> HTMLResponse:
        settings = deps.get_settings()
        secure_cookie = deps.cookie_should_be_secure(request, public_url=str(settings.aria.public_url or ""))
        clean_message = message.strip()
        if not clean_message:
            return HTMLResponse("", status_code=204)
        username = deps.get_username_from_request(request)
        session_id = deps.ensure_session_id(request)
        lang = str(getattr(request.state, "lang", "de") or "de")
        is_english = lang.strip().lower().startswith("en")
        auto_memory_enabled = deps.is_auto_memory_enabled(request)
        memory_collection = deps.get_effective_memory_collection(request, username or "web")
        session_collection = deps.session_memory_collection_for_user(username or "web", session_id)
        if not username:
            return render_missing_username_response(
                templates=deps.templates,
                request=request,
                clean_message=clean_message,
                request_cookie_value=deps.request_cookie_value,
                set_response_cookie=deps.set_response_cookie,
                session_cookie=deps.session_cookie,
                session_id=session_id,
                secure_cookie=secure_cookie,
            )

        route_state = prepare_chat_route_state(
            request=request,
            clean_message=clean_message,
            username=username,
            lang=lang,
            pipeline=deps.execution_deps.pipeline,
            request_cookie_value=deps.request_cookie_value,
            sanitize_username=deps.sanitize_username,
            sanitize_connection_name=deps.sanitize_connection_name,
            sanitize_role=deps.sanitize_role,
            signing_secret=deps.forget_signing_secret,
            connection_pending_max_age_seconds=deps.connection_pending_max_age_seconds,
            forget_pending_cookie=deps.forget_pending_cookie,
            safe_fix_pending_cookie=deps.safe_fix_pending_cookie,
            connection_delete_pending_cookie=deps.connection_delete_pending_cookie,
            connection_create_pending_cookie=deps.connection_create_pending_cookie,
            connection_update_pending_cookie=deps.connection_update_pending_cookie,
            update_pending_cookie=deps.update_pending_cookie,
            routed_action_pending_cookie=deps.routed_action_pending_cookie,
        )

        response_state = await execute_chat_flow(
            clean_message=clean_message,
            username=username,
            lang=lang,
            is_english=is_english,
            route_state=route_state,
            memory_collection=memory_collection,
            session_collection=session_collection,
            auto_memory_enabled=auto_memory_enabled,
            deps=deps.execution_deps,
        )

        response = deps.templates.TemplateResponse(
            request=request,
            name="_chat_messages.html",
            context={
                "user_message": clean_message,
                "assistant_message": response_state.assistant_text,
                "badge_icon": response_state.icon,
                "badge_intent": response_state.intent_label,
                "badge_tokens": response_state.total_tokens,
                "badge_cost_usd": response_state.cost_usd,
                "badge_duration": response_state.duration_s,
                "badge_details": response_state.badge_details,
            },
        )
        if username and response_state.assistant_text:
            deps.append_chat_history(
                username,
                user_message=clean_message,
                assistant_message=response_state.assistant_text,
                badge_icon=response_state.icon,
                badge_intent=response_state.intent_label,
                badge_tokens=response_state.total_tokens,
                badge_cost_usd=response_state.cost_usd,
                badge_duration=response_state.duration_s,
                badge_details=response_state.badge_details,
            )
        apply_chat_response_cookies(
            response=response,
            request=request,
            state=response_state,
            request_cookie_value=deps.request_cookie_value,
            set_response_cookie=deps.set_response_cookie,
            delete_response_cookie=deps.delete_response_cookie,
            session_cookie=deps.session_cookie,
            session_id=session_id,
            forget_pending_cookie=deps.forget_pending_cookie,
            safe_fix_pending_cookie=deps.safe_fix_pending_cookie,
            connection_delete_pending_cookie=deps.connection_delete_pending_cookie,
            connection_create_pending_cookie=deps.connection_create_pending_cookie,
            connection_update_pending_cookie=deps.connection_update_pending_cookie,
            update_pending_cookie=deps.update_pending_cookie,
            routed_action_pending_cookie=deps.routed_action_pending_cookie,
            secure_cookie=secure_cookie,
        )
        return response

    @app.post("/chat/history/clear")
    async def clear_chat_history(request: Request) -> Response:
        username = deps.get_username_from_request(request)
        if username:
            deps.clear_chat_history(username)
            deps.clear_capability_context(username)
        return Response(status_code=204)
