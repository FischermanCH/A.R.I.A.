from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aria.web.chat_admin_flows as chat_admin_flows
import aria.web.chat_notes_flows as chat_notes_flows
import aria.web.chat_pending_flows as chat_pending_flows
from aria.core.llm_client import LLMClientError
from aria.core.prompt_loader import PromptLoadError
from aria.web.chat_route_helpers import ChatPreparedState, ChatResponseState


IntentBadge = Callable[[list[str], list[str] | None], tuple[str, str]]
FriendlyErrorText = Callable[[list[str] | None], str]
AlertSender = Callable[..., Any]


@dataclass(frozen=True)
class ChatExecutionDeps:
    base_dir: Path
    pipeline: Any
    settings: Any
    intent_badge: IntentBadge
    friendly_error_text: FriendlyErrorText
    alert_sender: AlertSender
    signing_secret: str
    sanitize_username: Callable[[str | None], str]
    sanitize_connection_name: Callable[[str | None], str]
    sanitize_collection_name: Callable[[str | None], str]
    list_connection_refs: Callable[[Path], Any]
    resolve_connection_target: Callable[..., tuple[str, str]]
    delete_connection_profile: Callable[[Path, str, str], dict[str, Any]]
    create_connection_profile: Callable[[Path, str, str, dict[str, Any]], dict[str, Any]]
    update_connection_profile: Callable[[Path, str, str, dict[str, Any]], dict[str, Any]]
    reload_runtime: Callable[[], Any]
    resolve_update_helper_config: Callable[..., Any]
    trigger_update_helper_run: Callable[[Any], dict[str, Any]]
    fetch_update_helper_status: Callable[[Any], dict[str, Any]]
    helper_status_visual: Callable[..., str]
    get_secure_store: Callable[[dict[str, Any] | None], Any]
    build_config_backup_payload: Callable[..., dict[str, Any]]
    summarize_config_backup_payload: Callable[[dict[str, Any]], dict[str, Any]]
    read_raw_config: Callable[[], dict[str, Any]]


def _apply_pending_outcome(state: ChatResponseState, outcome: chat_pending_flows.ChatPendingOutcome) -> None:
    state.assistant_text = outcome.assistant_text
    state.icon = outcome.icon
    state.intent_label = outcome.intent_label
    if outcome.badge_tokens is not None:
        state.total_tokens = outcome.badge_tokens
    if outcome.badge_cost_usd is not None:
        state.cost_usd = outcome.badge_cost_usd
    if outcome.badge_duration is not None:
        state.duration_s = outcome.badge_duration
    if outcome.badge_details:
        state.badge_details = list(outcome.badge_details)
    state.set_safe_fix_cookie = outcome.set_cookies.get(chat_pending_flows.COOKIE_SAFE_FIX)
    state.set_routed_action_cookie = outcome.set_cookies.get(chat_pending_flows.COOKIE_ROUTED_ACTION)
    state.set_forget_cookie = outcome.set_cookies.get(chat_pending_flows.COOKIE_FORGET)
    state.clear_safe_fix_cookie = chat_pending_flows.COOKIE_SAFE_FIX in outcome.clear_cookies
    state.clear_routed_action_cookie = chat_pending_flows.COOKIE_ROUTED_ACTION in outcome.clear_cookies
    state.clear_forget_cookie = chat_pending_flows.COOKIE_FORGET in outcome.clear_cookies


def _apply_admin_outcome(state: ChatResponseState, outcome: chat_admin_flows.ChatAdminOutcome) -> None:
    state.assistant_text = outcome.assistant_text
    state.icon = outcome.icon
    state.intent_label = outcome.intent_label
    state.set_connection_delete_cookie = outcome.set_cookies.get(chat_admin_flows.COOKIE_CONNECTION_DELETE)
    state.set_connection_create_cookie = outcome.set_cookies.get(chat_admin_flows.COOKIE_CONNECTION_CREATE)
    state.set_connection_update_cookie = outcome.set_cookies.get(chat_admin_flows.COOKIE_CONNECTION_UPDATE)
    state.set_update_cookie = outcome.set_cookies.get(chat_admin_flows.COOKIE_UPDATE)
    state.clear_connection_delete_cookie = chat_admin_flows.COOKIE_CONNECTION_DELETE in outcome.clear_cookies
    state.clear_connection_create_cookie = chat_admin_flows.COOKIE_CONNECTION_CREATE in outcome.clear_cookies
    state.clear_connection_update_cookie = chat_admin_flows.COOKIE_CONNECTION_UPDATE in outcome.clear_cookies
    state.clear_update_cookie = chat_admin_flows.COOKIE_UPDATE in outcome.clear_cookies


async def execute_chat_flow(
    *,
    clean_message: str,
    username: str,
    lang: str,
    is_english: bool,
    route_state: ChatPreparedState,
    memory_collection: str,
    session_collection: str,
    auto_memory_enabled: bool,
    deps: ChatExecutionDeps,
) -> ChatResponseState:
    response_state = ChatResponseState()

    pending_confirm_outcome = await chat_pending_flows.handle_chat_pending_confirm_flow(
        clean_message=clean_message,
        state=route_state.pending_state,
        username=username,
        pipeline=deps.pipeline,
        settings=deps.settings,
        routed_action_confirm_token=route_state.routed_action_confirm_token,
        safe_fix_confirm_token=route_state.safe_fix_confirm_token,
        language=lang,
        is_english=is_english,
        intent_badge=deps.intent_badge,
        friendly_error_text=deps.friendly_error_text,
        alert_sender=deps.alert_sender,
    )
    if pending_confirm_outcome and pending_confirm_outcome.handled:
        _apply_pending_outcome(response_state, pending_confirm_outcome)
        return response_state

    pending_input_outcome = await chat_pending_flows.handle_chat_pending_input_flow(
        clean_message=clean_message,
        state=route_state.pending_state,
        username=username,
        pipeline=deps.pipeline,
        settings=deps.settings,
        language=lang,
        is_english=is_english,
        intent_badge=deps.intent_badge,
        friendly_error_text=deps.friendly_error_text,
        signing_secret=deps.signing_secret,
        sanitize_username=deps.sanitize_username,
        sanitize_connection_name=deps.sanitize_connection_name,
        alert_sender=deps.alert_sender,
    )
    if pending_input_outcome and pending_input_outcome.handled:
        _apply_pending_outcome(response_state, pending_input_outcome)
        return response_state

    admin_outcome = chat_admin_flows.handle_chat_admin_flow(
        request=route_state.admin_requests,
        pending=route_state.admin_pending,
        username=username,
        auth_role=route_state.auth_role,
        advanced_mode=route_state.advanced_mode,
        base_dir=deps.base_dir,
        signing_secret=deps.signing_secret,
        sanitize_username=deps.sanitize_username,
        sanitize_connection_name=deps.sanitize_connection_name,
        list_connection_refs=deps.list_connection_refs,
        resolve_connection_target=deps.resolve_connection_target,
        delete_connection_profile=deps.delete_connection_profile,
        create_connection_profile=deps.create_connection_profile,
        update_connection_profile=deps.update_connection_profile,
        reload_runtime=deps.reload_runtime,
        resolve_update_helper_config=deps.resolve_update_helper_config,
        trigger_update_helper_run=deps.trigger_update_helper_run,
        fetch_update_helper_status=deps.fetch_update_helper_status,
        helper_status_visual=deps.helper_status_visual,
        get_secure_store=deps.get_secure_store,
        build_config_backup_payload=deps.build_config_backup_payload,
        summarize_config_backup_payload=deps.summarize_config_backup_payload,
        read_raw_config=deps.read_raw_config,
    )
    if admin_outcome and admin_outcome.handled:
        _apply_admin_outcome(response_state, admin_outcome)
        return response_state

    if "memory_forget" in route_state.forget_decision.intents and deps.pipeline.memory_skill:
        forget_outcome = await chat_pending_flows.handle_memory_forget_flow(
            clean_message=clean_message,
            state=route_state.pending_state,
            username=username,
            pipeline=deps.pipeline,
            memory_forget_requested=True,
            signing_secret=deps.signing_secret,
            sanitize_username=deps.sanitize_username,
            sanitize_collection_name=deps.sanitize_collection_name,
            friendly_error_text=deps.friendly_error_text,
        )
        if forget_outcome and forget_outcome.handled:
            _apply_pending_outcome(response_state, forget_outcome)
            return response_state

    notes_outcome = await chat_notes_flows.handle_chat_notes_flow(
        clean_message=clean_message,
        username=username,
        base_dir=deps.base_dir,
        settings=deps.settings,
    )
    if notes_outcome and notes_outcome.handled:
        response_state.assistant_text = notes_outcome.assistant_text
        response_state.icon = notes_outcome.icon
        response_state.intent_label = notes_outcome.intent_label
        return response_state

    response_state.badge_details = []
    try:
        result = await deps.pipeline.process(
            clean_message,
            user_id=username,
            source="web",
            language=lang,
            memory_collection=memory_collection,
            session_collection=session_collection,
            auto_memory_enabled=auto_memory_enabled,
        )
        response_state.assistant_text = result.text or "Ich habe gerade keine Antwort erzeugt."
        response_state.icon, response_state.intent_label = deps.intent_badge(result.intents, result.skill_errors)
        response_state.total_tokens = int(result.usage.get("total_tokens", 0) or 0)
        if result.total_cost_usd is not None:
            response_state.cost_usd = f"${result.total_cost_usd:.6f}"
        response_state.duration_s = f"{result.duration_ms / 1000:.1f}"
        response_state.badge_details = list(result.detail_lines)
        warning = deps.friendly_error_text(result.skill_errors)
        if warning:
            response_state.assistant_text = f"{response_state.assistant_text}\n\nHinweis: {warning}"
        if result.skill_errors:
            discord_error_text = chat_pending_flows._discord_alert_error_lines(result.skill_errors)
            await asyncio.to_thread(
                deps.alert_sender,
                deps.settings,
                category="skill_errors",
                title="Skill-Fehler erkannt",
                lines=[
                    f"User: {username}",
                    f"Intents: {', '.join(result.intents) or '-'}",
                    f"Fehler: {discord_error_text or '-'}",
                ],
                level="warn",
            )
        followup = await chat_pending_flows.apply_chat_result_pending_followups(
            result=result,
            assistant_text=response_state.assistant_text,
            icon=response_state.icon,
            intent_label=response_state.intent_label,
            username=username,
            settings=deps.settings,
            is_english=is_english,
            signing_secret=deps.signing_secret,
            sanitize_username=deps.sanitize_username,
            sanitize_connection_name=deps.sanitize_connection_name,
            alert_sender=deps.alert_sender,
        )
        response_state.assistant_text = followup.assistant_text
        response_state.icon = followup.icon
        response_state.intent_label = followup.intent_label
        response_state.set_safe_fix_cookie = followup.set_cookies.get(chat_pending_flows.COOKIE_SAFE_FIX)
        response_state.set_routed_action_cookie = followup.set_cookies.get(chat_pending_flows.COOKIE_ROUTED_ACTION)
        response_state.clear_routed_action_cookie = chat_pending_flows.COOKIE_ROUTED_ACTION in followup.clear_cookies
        return response_state
    except (PromptLoadError, LLMClientError, ValueError) as exc:
        response_state.assistant_text = f"Fehler: {exc}"
        response_state.badge_details = []
        return response_state
