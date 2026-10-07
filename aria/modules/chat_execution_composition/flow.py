from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

import aria.modules.chat_admin_composition.flows as chat_admin_flows
import aria.modules.action_pending_chat_boundary.flows as chat_pending_flows
from aria.modules.platform_primitives.i18n import I18NStore
from aria.modules.model_gateway_clients.llm import LLMClientError
from aria.modules.platform_primitives.prompt_loader import PromptLoadError
from aria.modules.chat_execution_composition.route_helpers import ChatPreparedState, ChatResponseState
from aria.modules.navigation_shell.ui_helpers import discord_alert_error_lines
from aria.modules.navigation_shell.ui_helpers import is_web_source_no_reliable_error
from aria.modules.navigation_shell.ui_helpers import should_alert_recipe_errors


IntentBadge = Callable[[list[str], list[str] | None], tuple[str, str]]
FriendlyErrorText = Callable[[list[str] | None], str]
AlertSender = Callable[..., Any]
_CHAT_EXECUTION_I18N = I18NStore(Path(__file__).resolve().parents[2] / "i18n")


def _chat_execution_text(lang: str | None, key: str, default: str = "", **values: object) -> str:
    template = _CHAT_EXECUTION_I18N.t(lang or "de", f"chat_execution_flow.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template


def _web_source_alert_diagnostics(detail_lines: list[str] | None) -> list[str]:
    markers = (
        "web_source_acquisition_plan",
        "web_source_queries",
        "web_source_contract",
        "web_source_curation_retry",
        "web_source_curation ",
    )
    rows: list[str] = []
    seen: set[str] = set()
    for line in list(detail_lines or []):
        clean = " ".join(str(line or "").split())
        if not clean or not any(marker in clean for marker in markers):
            continue
        clean = clean[:360]
        if clean in seen:
            continue
        seen.add(clean)
        rows.append(clean)
        if len(rows) >= 6:
            break
    if not rows:
        return []
    return ["Web-Source-Diagnose:", *[f"- {row}" for row in rows]]


@dataclass(frozen=True)
class ChatExecutionDeps:
    base_dir: Path
    pipeline: Any
    settings: Any
    intent_badge: IntentBadge
    friendly_error_text: FriendlyErrorText
    alert_sender: AlertSender
    claim_action_confirmation: Callable[..., str]
    pending_signing_secret: str
    forget_signing_secret: str
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
    state.set_routed_action_cookie = outcome.set_cookies.get(chat_pending_flows.COOKIE_ROUTED_ACTION)
    state.set_forget_cookie = outcome.set_cookies.get(chat_pending_flows.COOKIE_FORGET)
    state.set_connection_update_cookie = outcome.set_cookies.get(chat_admin_flows.COOKIE_CONNECTION_UPDATE)
    state.clear_routed_action_cookie = chat_pending_flows.COOKIE_ROUTED_ACTION in outcome.clear_cookies
    state.clear_forget_cookie = chat_pending_flows.COOKIE_FORGET in outcome.clear_cookies
    state.clear_connection_update_cookie = chat_admin_flows.COOKIE_CONNECTION_UPDATE in outcome.clear_cookies
    state.routed_action_confirm_command = outcome.routed_action_confirm_command
    state.routed_action_confirm_payload = outcome.routed_action_confirm_payload
    state.confirmation_button_label = outcome.confirmation_button_label


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












async def _execute_chat_flow(
    *,
    clean_message: str,
    username: str,
    lang: str,
    is_english: bool,
    route_state: ChatPreparedState,
    memory_collection: str,
    session_collection: str,
    deps: ChatExecutionDeps,
    chat_history: list[dict[str, Any]] | None = None,
) -> ChatResponseState:
    web_start = time.perf_counter()
    response_state = ChatResponseState()
    parsed_confirmation_token = str(route_state.routed_action_confirm_token or "").strip().lower()
    native_confirmation_token = parsed_confirmation_token if parsed_confirmation_token.startswith("na") else ""

    if not native_confirmation_token:
        pending_confirm_outcome = await chat_pending_flows.handle_chat_pending_confirm_flow(
            clean_message=clean_message,
            state=route_state.pending_state,
            username=username,
            pipeline=deps.pipeline,
            settings=deps.settings,
            routed_action_confirm_token=route_state.routed_action_confirm_token,
            language=lang,
            is_english=is_english,
            intent_badge=deps.intent_badge,
            friendly_error_text=deps.friendly_error_text,
            alert_sender=deps.alert_sender,
            claim_action_confirmation=deps.claim_action_confirmation,
        )
        if pending_confirm_outcome and pending_confirm_outcome.handled:
            _apply_pending_outcome(response_state, pending_confirm_outcome)
            return response_state

    admin_outcome = chat_admin_flows.handle_chat_admin_flow(
        request=route_state.admin_requests,
        pending=route_state.admin_pending,
        username=username,
        auth_role=route_state.auth_role,
        advanced_mode=route_state.advanced_mode,
        base_dir=deps.base_dir,
        signing_secret=deps.pending_signing_secret,
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
        language=lang,
    )
    if admin_outcome and admin_outcome.handled:
        _apply_admin_outcome(response_state, admin_outcome)
        return response_state

    forget_outcome = await chat_pending_flows.handle_memory_forget_flow(
        clean_message=clean_message,
        state=route_state.pending_state,
        username=username,
        pipeline=deps.pipeline,
        memory_forget_requested=False,
        language=lang,
        signing_secret=deps.forget_signing_secret,
        sanitize_username=deps.sanitize_username,
        sanitize_collection_name=deps.sanitize_collection_name,
        friendly_error_text=deps.friendly_error_text,
    )
    if forget_outcome and forget_outcome.handled:
        _apply_pending_outcome(response_state, forget_outcome)
        return response_state

    response_state.badge_details = []
    try:
        pipeline_call_start = time.perf_counter()
        result = await deps.pipeline.process(
            str(clean_message or "").strip(),
            user_id=username,
            source="web",
            language=lang,
            memory_collection=memory_collection,
            session_collection=session_collection,
            recent_history=chat_history,
            auth_role=route_state.auth_role,
            confirmation_token=native_confirmation_token,
        )
        response_state.request_id = str(result.request_id or "")
        response_state.agent_job_id = str(result.agent_job_id or "")
        pipeline_call_ms = int((time.perf_counter() - pipeline_call_start) * 1000)
        post_pipeline_start = time.perf_counter()
        result_mapping_start = time.perf_counter()
        response_state.assistant_text = result.text or _chat_execution_text(lang, "empty_answer", "I did not produce an answer right now.")
        response_state.icon, response_state.intent_label = deps.intent_badge(result.intents, result.skill_errors)
        response_state.total_tokens = int(result.usage.get("total_tokens", 0) or 0)
        if result.total_cost_usd is not None:
            response_state.cost_usd = f"${result.total_cost_usd:.6f}"
        result_mapping_ms = int((time.perf_counter() - result_mapping_start) * 1000)
        web_total_ms = int((time.perf_counter() - web_start) * 1000)
        response_state.duration_s = f"{web_total_ms / 1000:.1f}"
        response_state.badge_details = [
            *list(result.detail_lines),
            "Routing Debug: web_outer_timing "
            f"pre_pipeline_ms=0 pipeline_call_ms={pipeline_call_ms} post_pipeline_ms=0",
            f"Routing Debug: web_request_timing total_ms={web_total_ms} pipeline_ms={int(result.duration_ms or 0)} source=web_chat",
        ]
        warning_start = time.perf_counter()
        warning = deps.friendly_error_text(result.skill_errors)
        if warning:
            response_state.assistant_text = f"{response_state.assistant_text}\n\n{_chat_execution_text(lang, 'warning_prefix', 'Note')}: {warning}"
        warning_ms = int((time.perf_counter() - warning_start) * 1000)
        alert_ms = 0
        if is_web_source_no_reliable_error(result.skill_errors):
            alert_start = time.perf_counter()
            discord_error_text = discord_alert_error_lines(result.skill_errors)
            web_source_diagnostics = _web_source_alert_diagnostics(result.detail_lines)
            await asyncio.to_thread(
                deps.alert_sender,
                deps.settings,
                category="skill_errors",
                title=_chat_execution_text(lang, "web_search_source_error_title", "Web search found no reliable sources"),
                lines=[
                    f"User: {username}",
                    f"Intents: {', '.join(result.intents) or '-'}",
                    f"{_chat_execution_text(lang, 'error_prefix', 'Error')}: {discord_error_text or '-'}",
                    *web_source_diagnostics,
                ],
                level="warn",
            )
            alert_ms = int((time.perf_counter() - alert_start) * 1000)
        elif "native_agent" in result.intents and result.skill_errors:
            alert_start = time.perf_counter()
            discord_error_text = discord_alert_error_lines(result.skill_errors)
            await asyncio.to_thread(
                deps.alert_sender,
                deps.settings,
                category="native_agent_errors",
                title=_chat_execution_text(lang, "native_agent_error_title", "Native agent error detected"),
                lines=[
                    f"User: {username}",
                    f"Intents: {', '.join(result.intents) or '-'}",
                    f"{_chat_execution_text(lang, 'error_prefix', 'Error')}: {discord_error_text or '-'}",
                ],
                level="warn",
            )
            alert_ms = int((time.perf_counter() - alert_start) * 1000)
        elif should_alert_recipe_errors(result.skill_errors):
            alert_start = time.perf_counter()
            discord_error_text = discord_alert_error_lines(result.skill_errors)
            await asyncio.to_thread(
                deps.alert_sender,
                deps.settings,
                category="recipe_errors",
                title=_chat_execution_text(lang, "recipe_error_title", "Recipe error detected"),
                lines=[
                    f"User: {username}",
                    f"Intents: {', '.join(result.intents) or '-'}",
                    f"{_chat_execution_text(lang, 'error_prefix', 'Error')}: {discord_error_text or '-'}",
                ],
                level="warn",
            )
            alert_ms = int((time.perf_counter() - alert_start) * 1000)
        pending_followup_start = time.perf_counter()
        followup = await chat_pending_flows.apply_chat_result_pending_followups(
            result=result,
            assistant_text=response_state.assistant_text,
            icon=response_state.icon,
            intent_label=response_state.intent_label,
            username=username,
            settings=deps.settings,
            is_english=is_english,
            language=lang,
            signing_secret=deps.pending_signing_secret,
            sanitize_username=deps.sanitize_username,
            sanitize_connection_name=deps.sanitize_connection_name,
            alert_sender=deps.alert_sender,
        )
        pending_followup_ms = int((time.perf_counter() - pending_followup_start) * 1000)
        response_state.assistant_text = followup.assistant_text
        response_state.icon = followup.icon
        response_state.intent_label = followup.intent_label
        response_state.duration_s = f"{(time.perf_counter() - web_start):.1f}"
        response_state.set_routed_action_cookie = followup.set_cookies.get(chat_pending_flows.COOKIE_ROUTED_ACTION)
        response_state.clear_routed_action_cookie = chat_pending_flows.COOKIE_ROUTED_ACTION in followup.clear_cookies
        response_state.routed_action_confirm_command = followup.routed_action_confirm_command
        response_state.routed_action_confirm_payload = followup.routed_action_confirm_payload
        if result.routed_action_confirm_command:
            response_state.routed_action_confirm_command = result.routed_action_confirm_command
            response_state.routed_action_confirm_payload = None
            response_state.confirmation_button_label = _chat_execution_text(
                lang, "confirm_native_action_button", "Run action",
            )
        if result.suggestion_affordance:
            suggestion = dict(result.suggestion_affordance)
            host = str(suggestion.get("new_host") or "").strip()
            if suggestion.get("kind") == "cross_host":
                suggestion["label"] = _chat_execution_text(
                    lang, "learning_suggestion_copy_button", "Create copy for {host}", host=host,
                )
                suggestion["caption"] = _chat_execution_text(
                    lang, "learning_suggestion_copy_caption",
                    "Create an inactive copy of this Recipe for {host}.", host=host,
                )
            elif suggestion.get("kind") == "memory":
                suggestion["label"] = _chat_execution_text(
                    lang, "learning_suggestion_memory_button", "Save as memory",
                )
                suggestion["caption"] = _chat_execution_text(
                    lang, "learning_suggestion_memory_caption",
                    "Save this preference as a personal memory.",
                )
            else:
                suggestion["label"] = _chat_execution_text(
                    lang, "learning_suggestion_save_button", "Save as Recipe",
                )
                suggestion["caption"] = _chat_execution_text(
                    lang, "learning_suggestion_save_caption",
                    "Save this repeated action as an inactive Recipe draft.",
                )
            response_state.suggestion_affordance = suggestion
        else:
            response_state.suggestion_affordance = None
        if result.clear_routed_action_affordance:
            response_state.clear_routed_action_cookie = True
        post_pipeline_ms = int((time.perf_counter() - post_pipeline_start) * 1000)
        for index, line in enumerate(response_state.badge_details):
            if line.startswith("Routing Debug: web_outer_timing "):
                response_state.badge_details[index] = (
                    "Routing Debug: web_outer_timing "
                    f"pre_pipeline_ms=0 pipeline_call_ms={pipeline_call_ms} "
                    f"post_pipeline_ms={post_pipeline_ms}"
                )
                break
        response_state.badge_details.append(
            "Routing Debug: web_post_pipeline_timing "
            f"result_mapping_ms={result_mapping_ms} warning_ms={warning_ms} alert_ms={alert_ms} "
            f"pending_followup_ms={pending_followup_ms} total_ms={post_pipeline_ms}"
        )
        return response_state
    except (PromptLoadError, LLMClientError, ValueError) as exc:
        response_state.assistant_text = f"{_chat_execution_text(lang, 'error_prefix', 'Error')}: {exc}"
        response_state.badge_details = []
        return response_state


async def execute_chat_flow(
    *,
    clean_message: str,
    username: str,
    lang: str,
    is_english: bool,
    route_state: ChatPreparedState,
    memory_collection: str,
    session_collection: str,
    deps: ChatExecutionDeps,
    chat_history: list[dict[str, Any]] | None = None,
) -> ChatResponseState:
    usage_meter = getattr(deps.pipeline, "usage_meter", None)
    scope_factory = getattr(usage_meter, "scope", None)
    current_scope = getattr(usage_meter, "current_scope", None)
    if not callable(scope_factory) or (callable(current_scope) and current_scope() is not None):
        return await _execute_chat_flow(
            clean_message=clean_message,
            username=username,
            lang=lang,
            is_english=is_english,
            route_state=route_state,
            memory_collection=memory_collection,
            session_collection=session_collection,
            deps=deps,
            chat_history=chat_history,
        )
    with scope_factory(
        request_id=str(uuid4()),
        user_id=username,
        source="web_chat",
        router_level=0,
    ):
        return await _execute_chat_flow(
            clean_message=clean_message,
            username=username,
            lang=lang,
            is_english=is_english,
            route_state=route_state,
            memory_collection=memory_collection,
            session_collection=session_collection,
            deps=deps,
            chat_history=chat_history,
        )
