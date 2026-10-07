from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates

import aria.modules.chat_admin_composition.actions as chat_admin_actions
import aria.modules.chat_admin_composition.flows as chat_admin_flows
import aria.modules.action_pending_chat_boundary.flows as chat_pending_flows


RequestCookieValue = Callable[[Request, str], str]
SetResponseCookie = Callable[..., None]
DeleteResponseCookie = Callable[..., None]
SanitizeUsername = Callable[[str | None], str]
SanitizeConnectionName = Callable[[str | None], str]
SanitizeRole = Callable[[str | None], str]


@dataclass(frozen=True)
class ChatPreparedState:
    auth_role: str
    advanced_mode: bool
    routed_action_confirm_token: str | None
    pending_state: chat_pending_flows.ChatPendingState
    admin_pending: chat_admin_flows.ChatAdminPendingState
    admin_requests: chat_admin_flows.ChatAdminRequests


@dataclass
class ChatResponseState:
    request_id: str = ""
    assistant_text: str = ""
    icon: str = "⚠"
    intent_label: str = "error"
    total_tokens: int = 0
    cost_usd: str = "n/a"
    duration_s: str = "0.0"
    badge_details: list[str] = field(default_factory=list)
    set_forget_cookie: str | None = None
    clear_forget_cookie: bool = False
    set_connection_delete_cookie: str | None = None
    clear_connection_delete_cookie: bool = False
    set_connection_create_cookie: str | None = None
    clear_connection_create_cookie: bool = False
    set_connection_update_cookie: str | None = None
    clear_connection_update_cookie: bool = False
    set_update_cookie: str | None = None
    clear_update_cookie: bool = False
    set_routed_action_cookie: str | None = None
    clear_routed_action_cookie: bool = False
    routed_action_confirm_command: str | None = None
    routed_action_confirm_payload: str | None = None
    confirmation_button_label: str | None = None
    suggestion_affordance: dict[str, str] | None = None
    agent_job_id: str = ""


def prepare_chat_route_state(
    *,
    request: Request,
    clean_message: str,
    username: str,
    lang: str,
    pipeline: Any,
    request_cookie_value: RequestCookieValue,
    sanitize_username: SanitizeUsername,
    sanitize_connection_name: SanitizeConnectionName,
    sanitize_role: SanitizeRole,
    forget_signing_secret: str,
    pending_signing_secret: str,
    connection_pending_max_age_seconds: int,
    forget_pending_cookie: str,
    connection_delete_pending_cookie: str,
    connection_create_pending_cookie: str,
    connection_update_pending_cookie: str,
    update_pending_cookie: str,
    routed_action_pending_cookie: str,
    routed_action_pending_override: str | None = None,
) -> ChatPreparedState:
    forget_pending = chat_admin_actions._decode_forget_pending(
        request_cookie_value(request, forget_pending_cookie),
        signing_secret=forget_signing_secret,
        sanitize_username=sanitize_username,
    )
    connection_delete_pending = chat_admin_actions._decode_connection_delete_pending(
        request_cookie_value(request, connection_delete_pending_cookie),
        signing_secret=pending_signing_secret,
        sanitize_username=sanitize_username,
        sanitize_connection_name=sanitize_connection_name,
        max_age_seconds=connection_pending_max_age_seconds,
    )
    connection_create_pending = chat_admin_actions._decode_connection_create_pending(
        request_cookie_value(request, connection_create_pending_cookie),
        signing_secret=pending_signing_secret,
        sanitize_username=sanitize_username,
        max_age_seconds=connection_pending_max_age_seconds,
    )
    connection_update_pending = chat_admin_actions._decode_connection_update_pending(
        request_cookie_value(request, connection_update_pending_cookie),
        signing_secret=pending_signing_secret,
        sanitize_username=sanitize_username,
        max_age_seconds=connection_pending_max_age_seconds,
    )
    update_pending = chat_admin_actions._decode_update_pending(
        request_cookie_value(request, update_pending_cookie),
        signing_secret=pending_signing_secret,
        sanitize_username=sanitize_username,
        max_age_seconds=connection_pending_max_age_seconds,
    )
    routed_action_pending_raw = request_cookie_value(request, routed_action_pending_cookie)
    routed_action_pending = chat_admin_actions._decode_routed_action_pending(
        routed_action_pending_raw,
        signing_secret=pending_signing_secret,
        sanitize_username=sanitize_username,
        max_age_seconds=connection_pending_max_age_seconds,
    )
    routed_action_confirmation_raw = str(routed_action_pending_override or "").strip()
    routed_action_confirmation_pending = (
        (
            chat_admin_actions._decode_routed_action_pending(
                routed_action_confirmation_raw,
                signing_secret=pending_signing_secret,
                sanitize_username=sanitize_username,
                max_age_seconds=connection_pending_max_age_seconds,
            )
            or {}
        )
        if routed_action_confirmation_raw
        else routed_action_pending
    )
    _ = pipeline, lang
    auth_role = sanitize_role(getattr(request.state, "auth_role", ""))
    advanced_mode = bool(getattr(request.state, "can_access_advanced_config", False))
    admin_requests = chat_admin_flows.ChatAdminRequests(
        connection_delete_confirm_token=chat_admin_actions._parse_connection_delete_confirm_token(clean_message),
        connection_create_confirm_token=chat_admin_actions._parse_connection_create_confirm_token(clean_message),
        connection_update_confirm_token=chat_admin_actions._parse_connection_update_confirm_token(clean_message),
        update_confirm_token=chat_admin_actions._parse_update_confirm_token(clean_message),
    )
    admin_pending = chat_admin_flows.ChatAdminPendingState(
        connection_delete_pending=connection_delete_pending,
        connection_create_pending=connection_create_pending,
        connection_update_pending=connection_update_pending,
        update_pending=update_pending,
    )
    pending_state = chat_pending_flows.ChatPendingState(
        forget_pending=forget_pending,
        routed_action_pending=routed_action_pending,
        routed_action_confirmation_pending=routed_action_confirmation_pending,
    )
    routed_action_confirm_token = chat_admin_actions._parse_routed_action_confirm_token(clean_message)
    return ChatPreparedState(
        auth_role=auth_role,
        advanced_mode=advanced_mode,
        routed_action_confirm_token=routed_action_confirm_token,
        pending_state=pending_state,
        admin_pending=admin_pending,
        admin_requests=admin_requests,
    )


def render_missing_username_response(
    *,
    templates: Jinja2Templates,
    request: Request,
    clean_message: str,
    request_cookie_value: RequestCookieValue,
    set_response_cookie: SetResponseCookie,
    session_cookie: str,
    session_id: str,
    secure_cookie: bool,
) -> HTMLResponse:
    response = templates.TemplateResponse(
        request=request,
        name="_chat_messages.html",
        context={
            "user_message": clean_message,
            "assistant_message": "Bitte gib zuerst deinen Namen ein, damit ich dein Memory korrekt zuordnen kann.",
            "badge_icon": "⚠",
            "badge_intent": "missing_username",
            "badge_tokens": 0,
            "badge_cost_usd": "n/a",
            "badge_duration": "0.0",
            "badge_details": [],
        },
    )
    if not request_cookie_value(request, session_cookie):
        set_response_cookie(
            response,
            request,
            session_cookie,
            session_id,
            max_age=60 * 60 * 24 * 7,
            secure=secure_cookie,
            httponly=False,
        )
    return response


def apply_chat_response_cookies(
    *,
    response: Response,
    request: Request,
    state: ChatResponseState,
    request_cookie_value: RequestCookieValue,
    set_response_cookie: SetResponseCookie,
    delete_response_cookie: DeleteResponseCookie,
    session_cookie: str,
    session_id: str,
    forget_pending_cookie: str,
    connection_delete_pending_cookie: str,
    connection_create_pending_cookie: str,
    connection_update_pending_cookie: str,
    update_pending_cookie: str,
    routed_action_pending_cookie: str,
    secure_cookie: bool,
) -> None:
    if not request_cookie_value(request, session_cookie):
        set_response_cookie(
            response,
            request,
            session_cookie,
            session_id,
            max_age=60 * 60 * 24 * 7,
            secure=secure_cookie,
            httponly=False,
        )
    if state.clear_forget_cookie:
        delete_response_cookie(response, request, forget_pending_cookie)
    elif state.set_forget_cookie:
        set_response_cookie(response, request, forget_pending_cookie, state.set_forget_cookie, max_age=60 * 10, secure=secure_cookie, httponly=False)
    if state.clear_connection_delete_cookie:
        delete_response_cookie(response, request, connection_delete_pending_cookie)
    elif state.set_connection_delete_cookie:
        set_response_cookie(response, request, connection_delete_pending_cookie, state.set_connection_delete_cookie, max_age=60 * 10, secure=secure_cookie, httponly=False)
    if state.clear_connection_create_cookie:
        delete_response_cookie(response, request, connection_create_pending_cookie)
    elif state.set_connection_create_cookie:
        set_response_cookie(response, request, connection_create_pending_cookie, state.set_connection_create_cookie, max_age=60 * 10, secure=secure_cookie, httponly=False)
    if state.clear_connection_update_cookie:
        delete_response_cookie(response, request, connection_update_pending_cookie)
    elif state.set_connection_update_cookie:
        set_response_cookie(response, request, connection_update_pending_cookie, state.set_connection_update_cookie, max_age=60 * 10, secure=secure_cookie, httponly=False)
    if state.clear_update_cookie:
        delete_response_cookie(response, request, update_pending_cookie)
    elif state.set_update_cookie:
        set_response_cookie(response, request, update_pending_cookie, state.set_update_cookie, max_age=60 * 10, secure=secure_cookie, httponly=False)
    if state.clear_routed_action_cookie:
        delete_response_cookie(response, request, routed_action_pending_cookie)
    elif state.set_routed_action_cookie:
        set_response_cookie(response, request, routed_action_pending_cookie, state.set_routed_action_cookie, max_age=60 * 10, secure=secure_cookie, httponly=False)
