from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

import aria.web.chat_admin_actions as chat_admin_actions
from aria.core.i18n import I18NStore
from aria.core.routing_resolver import infer_preferred_connection_kind


BASE_DIR = Path(__file__).resolve().parents[2]
_CHAT_PENDING_I18N = I18NStore(BASE_DIR / "aria" / "i18n")
_PENDING_ROUTE_KINDS = (
    "ssh",
    "sftp",
    "smb",
    "google_calendar",
    "discord",
    "rss",
    "http_api",
    "webhook",
    "email",
    "imap",
    "mqtt",
)


def _pending_text(language: str | None, key: str, default: str = "", **values: Any) -> str:
    template = _CHAT_PENDING_I18N.t(language or "de", f"chat_pending.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template


@dataclass(frozen=True)
class ChatPendingState:
    forget_pending: dict[str, Any] | None = None
    safe_fix_pending: dict[str, Any] | None = None
    routed_action_pending: dict[str, Any] | None = None


@dataclass(frozen=True)
class ChatPendingOutcome:
    handled: bool
    assistant_text: str = ""
    icon: str = "⚠"
    intent_label: str = "chat"
    badge_tokens: int | None = None
    badge_cost_usd: str | None = None
    badge_duration: str | None = None
    badge_details: tuple[str, ...] = ()
    set_cookies: dict[str, str] = field(default_factory=dict)
    clear_cookies: tuple[str, ...] = ()
    routed_action_confirm_command: str | None = None
    routed_action_confirm_payload: str | None = None


@dataclass(frozen=True)
class ChatPipelinePendingOutcome:
    assistant_text: str
    icon: str
    intent_label: str
    set_cookies: dict[str, str] = field(default_factory=dict)
    clear_cookies: tuple[str, ...] = ()
    routed_action_confirm_command: str | None = None
    routed_action_confirm_payload: str | None = None


COOKIE_FORGET = "forget"
COOKIE_SAFE_FIX = "safe_fix"
COOKIE_ROUTED_ACTION = "routed_action"

IntentBadge = Callable[[list[str], list[str] | None], tuple[str, str]]
FriendlyErrorText = Callable[[list[str] | None], str]
AlertSender = Callable[..., Any]
SanitizeUsername = Callable[[str | None], str]
SanitizeCollectionName = Callable[[str | None], str]
SanitizeConnectionName = Callable[[str | None], str]


def _looks_like_connection_ref_reply(
    pending_action: dict[str, Any],
    message: str,
    settings: Any,
) -> bool:
    payload = dict(pending_action.get("payload", {}) or {})
    connection_kind = str(payload.get("connection_kind", "") or "").strip().lower()
    clean_message = str(message or "").strip()
    if not connection_kind or not clean_message:
        return False
    rows = getattr(getattr(settings, "connections", object()), connection_kind, {})
    if not isinstance(rows, dict) or not rows:
        return False
    exact_refs = {str(ref or "").strip().lower() for ref in rows.keys() if str(ref or "").strip()}
    if clean_message.lower() in exact_refs:
        return True
    if any(token in clean_message for token in (" ", "?", "!", ":", "/", "\\")):
        return False
    return False


def _looks_like_pending_value_reply(
    pending_action: dict[str, Any],
    message: str,
    *,
    pipeline: Any,
    language: str,
) -> bool:
    payload = dict(pending_action.get("payload", {}) or {})
    pending_capability = str(payload.get("capability", "") or "").strip().lower()
    pending_kind = str(payload.get("connection_kind", "") or "").strip().lower()
    clean_message = str(message or "").strip()
    if not pending_capability or not clean_message:
        return True
    inferred_kind = infer_preferred_connection_kind(clean_message, available_kinds=_PENDING_ROUTE_KINDS)
    if inferred_kind and pending_kind and inferred_kind != pending_kind:
        return False
    classify = getattr(pipeline, "_classify_capability_draft", None)
    if not callable(classify):
        return True
    draft = classify(clean_message, language=language)
    if draft is None:
        return True
    draft_capability = str(getattr(draft, "capability", "") or "").strip().lower()
    draft_kind = str(getattr(draft, "connection_kind", "") or "").strip().lower()
    if not draft_capability:
        return True
    if draft_capability != pending_capability:
        return False
    if pending_kind and draft_kind and draft_kind != pending_kind:
        return False
    return True


def _should_continue_routed_pending_input(
    pending_action: dict[str, Any],
    message: str,
    *,
    pipeline: Any,
    settings: Any,
    language: str,
) -> bool:
    action = dict(pending_action.get("action_decision", {}) or {})
    payload = dict(pending_action.get("payload", {}) or {})
    missing_input = str(action.get("missing_input", "") or payload.get("missing_input", "") or "").strip()
    if not missing_input:
        return False
    if missing_input == "connection_ref":
        return _looks_like_connection_ref_reply(pending_action, message, settings)
    if missing_input in {"command", "content", "path"}:
        return _looks_like_pending_value_reply(
            pending_action,
            message,
            pipeline=pipeline,
            language=language,
        )
    return True


def _read_existing_connection_aliases(settings: Any, kind: str, ref: str) -> list[str]:
    connections = getattr(settings, "connections", object())
    rows = getattr(connections, kind, {}) if connections is not None else {}
    if not isinstance(rows, dict):
        return []
    row = rows.get(ref, {})
    if not isinstance(row, dict):
        return []
    aliases = row.get("aliases", [])
    if not isinstance(aliases, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for item in aliases:
        clean = str(item or "").strip()
        lower = clean.lower()
        if clean and lower not in seen:
            result.append(clean)
            seen.add(lower)
    return result


def _outcome(
    *,
    assistant_text: str,
    icon: str,
    intent_label: str,
    badge_tokens: int | None = None,
    badge_cost_usd: str | None = None,
    badge_duration: str | None = None,
    badge_details: tuple[str, ...] | None = None,
    set_cookies: dict[str, str] | None = None,
    clear_cookies: tuple[str, ...] | None = None,
) -> ChatPendingOutcome:
    return ChatPendingOutcome(
        handled=True,
        assistant_text=assistant_text,
        icon=icon,
        intent_label=intent_label,
        badge_tokens=badge_tokens,
        badge_cost_usd=badge_cost_usd,
        badge_duration=badge_duration,
        badge_details=tuple(badge_details or ()),
        set_cookies=dict(set_cookies or {}),
        clear_cookies=tuple(clear_cookies or ()),
    )


async def handle_chat_pending_confirm_flow(
    *,
    clean_message: str,
    state: ChatPendingState,
    username: str,
    pipeline: Any,
    settings: Any,
    routed_action_confirm_token: str | None,
    safe_fix_confirm_token: str | None,
    language: str,
    is_english: bool,
    intent_badge: IntentBadge,
    friendly_error_text: FriendlyErrorText,
    alert_sender: AlertSender,
) -> ChatPendingOutcome | None:
    routed_pending = state.routed_action_pending or {}
    routed_token = str(routed_action_confirm_token or "").strip().lower()
    if routed_token and routed_pending:
        pending_user = str(routed_pending.get("user_id", "")).strip()
        pending_token = str(routed_pending.get("token", "")).strip().lower()
        if pending_user == username and pending_token and pending_token == routed_token:
            routed_result = await pipeline.execute_pending_routed_action(
                routed_pending,
                user_id=username,
                source="web",
                language=language,
            )
            assistant_text = routed_result.text or _pending_text(language, "action_executed", "Action executed.")
            icon, intent_label = intent_badge(routed_result.intents, routed_result.skill_errors)
            warning = friendly_error_text(routed_result.skill_errors)
            if warning:
                assistant_text = f"{assistant_text}\n\n{_pending_text(language, 'warning_prefix', 'Note')}: {warning}"
            return _outcome(
                assistant_text=assistant_text,
                icon=icon,
                intent_label=intent_label,
                badge_tokens=int(routed_result.usage.get("total_tokens", 0) or 0),
                badge_cost_usd=(
                    f"${routed_result.total_cost_usd:.6f}"
                    if routed_result.total_cost_usd is not None
                    else None
                ),
                badge_duration=f"{routed_result.duration_ms / 1000:.1f}",
                badge_details=tuple(routed_result.detail_lines),
                clear_cookies=(COOKIE_ROUTED_ACTION,),
            )
        return _outcome(
            assistant_text=(
                _pending_text(
                    language,
                    "action_confirm_token_invalid",
                    "The confirmation code for this action is invalid or expired.",
                )
            ),
            icon="⚠",
            intent_label="routed_action_invalid_token",
            clear_cookies=(COOKIE_ROUTED_ACTION,),
        )
    if routed_token:
        return _outcome(
            assistant_text=(
                _pending_text(
                    language,
                    "action_confirm_token_invalid",
                    "The confirmation code for this action is invalid or expired.",
                )
            ),
            icon="⚠",
            intent_label="routed_action_invalid_token",
            clear_cookies=(COOKIE_ROUTED_ACTION,),
        )

    safe_fix_pending = state.safe_fix_pending or {}
    safe_fix_token = str(safe_fix_confirm_token or "").strip().lower()
    if safe_fix_token and safe_fix_pending:
        pending_user = str(safe_fix_pending.get("user_id", "")).strip()
        pending_token = str(safe_fix_pending.get("token", "")).strip().lower()
        pending_fixes = safe_fix_pending.get("fixes", [])
        if (
            pending_user == username
            and pending_token
            and pending_token == safe_fix_token
            and isinstance(pending_fixes, list)
            and pending_fixes
        ):
            fix_result = await pipeline.execute_safe_fix_plan(
                pending_fixes,
                language=language,
            )
            assistant_text = fix_result.content or _pending_text(language, "safe_fix_completed", "Safe fix completed.")
            icon = "🛠"
            intent_label = "safe_fix_apply"
            if not fix_result.success:
                icon = "⚠"
                warning = friendly_error_text([fix_result.error]) if fix_result.error else ""
                if warning:
                    assistant_text = f"{assistant_text}\n\n{_pending_text(language, 'warning_prefix', 'Note')}: {warning}"
            await asyncio.to_thread(
                alert_sender,
                settings,
                category="safe_fix",
                title=_pending_text(language, "safe_fix_alert_executed_title", "Safe fix executed"),
                lines=[
                    f"User: {username}",
                    f"{_pending_text(language, 'safe_fix_alert_result_label', 'Result')}: "
                    f"{_pending_text(language, 'result_ok' if fix_result.success else 'result_error', 'ok')}",
                    f"Text: {assistant_text[:300]}",
                ],
                level="info" if fix_result.success else "warn",
            )
            return _outcome(
                assistant_text=assistant_text,
                icon=icon,
                intent_label=intent_label,
                clear_cookies=(COOKIE_SAFE_FIX,),
            )
        return _outcome(
            assistant_text=_pending_text(
                language,
                "safe_fix_confirm_token_invalid",
                "The safe-fix confirmation code is invalid or expired.",
            ),
            icon="⚠",
            intent_label="safe_fix_invalid_token",
            clear_cookies=(COOKIE_SAFE_FIX,),
        )

    return None


async def handle_chat_pending_input_flow(
    *,
    clean_message: str,
    state: ChatPendingState,
    username: str,
    pipeline: Any,
    settings: Any,
    language: str,
    is_english: bool,
    intent_badge: IntentBadge,
    friendly_error_text: FriendlyErrorText,
    signing_secret: str,
    sanitize_username: SanitizeUsername,
    sanitize_connection_name: SanitizeConnectionName,
    auth_role: str,
    alert_sender: AlertSender,
) -> ChatPendingOutcome | None:
    routed_pending = state.routed_action_pending or {}
    if not routed_pending:
        return None
    pending_user = str(routed_pending.get("user_id", "")).strip()
    if pending_user != username:
        return None
    action = dict(routed_pending.get("action_decision", {}) or {})
    payload = dict(routed_pending.get("payload", {}) or {})
    missing_input = str(action.get("missing_input", "") or payload.get("missing_input", "") or "").strip()
    if not _should_continue_routed_pending_input(
        routed_pending,
        clean_message,
        pipeline=pipeline,
        settings=settings,
        language=language,
    ):
        return None

    routed_result = await pipeline.continue_pending_routed_action_input(
        routed_pending,
        clean_message,
        user_id=username,
        source="web",
        language=language,
    )
    assistant_text = routed_result.text or _pending_text(language, "action_updated", "Action updated.")
    icon, intent_label = intent_badge(routed_result.intents, routed_result.skill_errors)
    warning = friendly_error_text(routed_result.skill_errors)
    if warning:
        assistant_text = f"{assistant_text}\n\n{_pending_text(language, 'warning_prefix', 'Note')}: {warning}"

    requested_ref = str(payload.get("requested_connection_ref", "") or "").strip()
    selected_ref = str(clean_message or "").strip()
    connection_kind = str(payload.get("connection_kind", "") or "").strip().lower()
    if (
        missing_input == "connection_ref"
        and requested_ref
        and selected_ref
        and connection_kind
        and not routed_result.skill_errors
    ):
        existing_aliases = _read_existing_connection_aliases(settings, connection_kind, selected_ref)
        if requested_ref.lower() not in {alias.lower() for alias in existing_aliases}:
            if auth_role != "admin":
                assistant_text = (
                    f"{assistant_text}\n\n"
                    + _pending_text(
                        language,
                        "connection_alias_admin_suggestion",
                        "If this mapping should stick, an admin can later save `{requested_ref}` as an alias for `{selected_ref}`.",
                        requested_ref=requested_ref,
                        selected_ref=selected_ref,
                    )
                )
                return _outcome(
                    assistant_text=assistant_text,
                    icon=icon,
                    intent_label="connection_alias_suggestion",
                    badge_tokens=int(routed_result.usage.get("total_tokens", 0) or 0),
                    badge_cost_usd=(
                        f"${routed_result.total_cost_usd:.6f}"
                        if routed_result.total_cost_usd is not None
                        else None
                    ),
                    badge_duration=f"{routed_result.duration_ms / 1000:.1f}",
                    badge_details=tuple(routed_result.detail_lines),
                    clear_cookies=(COOKIE_ROUTED_ACTION,),
                )
            token = uuid4().hex[:8].lower()
            pending_cookie = chat_admin_actions._encode_connection_update_pending(
                {
                    "token": token,
                    "user_id": username,
                    "kind": connection_kind,
                    "ref": selected_ref,
                    "payload": {"aliases": [*existing_aliases, requested_ref]},
                },
                signing_secret=signing_secret,
                sanitize_username=sanitize_username,
            )
            assistant_text = (
                f"{assistant_text}\n\n"
                + _pending_text(
                    language,
                    "connection_alias_pending",
                    "If this should stay the default mapping, I can remember `{requested_ref}` as an alias for `{selected_ref}`. "
                    "Confirm with: `confirm update {token}`",
                    requested_ref=requested_ref,
                    selected_ref=selected_ref,
                    token=token,
                )
            )
            return _outcome(
                assistant_text=assistant_text,
                icon=icon,
                intent_label="connection_alias_pending",
                badge_tokens=int(routed_result.usage.get("total_tokens", 0) or 0),
                badge_cost_usd=(
                    f"${routed_result.total_cost_usd:.6f}"
                    if routed_result.total_cost_usd is not None
                    else None
                ),
                badge_duration=f"{routed_result.duration_ms / 1000:.1f}",
                badge_details=tuple(routed_result.detail_lines),
                set_cookies={"connection_update": pending_cookie},
                clear_cookies=(COOKIE_ROUTED_ACTION,),
            )

    followup = await apply_chat_result_pending_followups(
        result=routed_result,
        assistant_text=assistant_text,
        icon=icon,
        intent_label=intent_label,
        username=username,
        settings=settings,
        is_english=is_english,
        signing_secret=signing_secret,
        sanitize_username=sanitize_username,
        sanitize_connection_name=sanitize_connection_name,
        alert_sender=alert_sender,
        language=language,
    )
    return _outcome(
        assistant_text=followup.assistant_text,
        icon=followup.icon,
        intent_label=followup.intent_label,
        badge_tokens=int(routed_result.usage.get("total_tokens", 0) or 0),
        badge_cost_usd=(
            f"${routed_result.total_cost_usd:.6f}"
            if routed_result.total_cost_usd is not None
            else None
        ),
        badge_duration=f"{routed_result.duration_ms / 1000:.1f}",
        badge_details=tuple(routed_result.detail_lines),
        set_cookies=followup.set_cookies,
        clear_cookies=followup.clear_cookies,
    )


async def handle_memory_forget_flow(
    *,
    clean_message: str,
    state: ChatPendingState,
    username: str,
    pipeline: Any,
    memory_forget_requested: bool,
    language: str,
    signing_secret: str,
    sanitize_username: SanitizeUsername,
    sanitize_collection_name: SanitizeCollectionName,
    friendly_error_text: FriendlyErrorText,
) -> ChatPendingOutcome | None:
    if not memory_forget_requested or not getattr(pipeline, "memory_skill", None):
        return None

    forget_pending = state.forget_pending or {}
    confirm_token = chat_admin_actions._parse_forget_confirm_token(clean_message)
    if confirm_token and forget_pending:
        pending_user = str(forget_pending.get("user_id", "")).strip()
        pending_token = str(forget_pending.get("token", "")).strip().lower()
        pending_candidates = forget_pending.get("candidates", [])
        if (
            pending_user == username
            and pending_token
            and pending_token == confirm_token.lower()
            and isinstance(pending_candidates, list)
            and pending_candidates
        ):
            forget_result = await pipeline.memory_skill.execute(
                query="",
                params={
                    "action": "forget_apply",
                    "user_id": username,
                    "candidates": pending_candidates,
                },
            )
            assistant_text = forget_result.content or _pending_text(language, "memory_forget_completed", "Deletion completed.")
            if forget_result.success:
                return _outcome(
                    assistant_text=assistant_text,
                    icon="🧹",
                    intent_label="memory_forget",
                    clear_cookies=(COOKIE_FORGET,),
                )
            friendly = friendly_error_text([forget_result.error])
            return _outcome(
                assistant_text=friendly or _pending_text(language, "memory_forget_failed", "Deletion failed."),
                icon="⚠",
                intent_label="memory_error",
                clear_cookies=(COOKIE_FORGET,),
            )
        return _outcome(
            assistant_text=_pending_text(
                language,
                "memory_forget_token_invalid",
                "The confirmation code is invalid or expired. Please send 'Forget ...' again.",
            ),
            icon="⚠",
            intent_label="memory_forget",
            clear_cookies=(COOKIE_FORGET,),
        )

    forget_query = chat_admin_actions._parse_forget_query(clean_message)
    forget_preview = await pipeline.memory_skill.execute(
        query=forget_query,
        params={
            "action": "forget_preview",
            "user_id": username,
            "threshold": 0.75,
            "max_hits": 5,
        },
    )
    candidates = (forget_preview.metadata or {}).get("forget_candidates", [])
    if not forget_preview.success:
        return _outcome(
            assistant_text=friendly_error_text([forget_preview.error])
            or _pending_text(language, "memory_preview_failed", "Memory preview failed."),
            icon="⚠",
            intent_label="memory_error",
            clear_cookies=(COOKIE_FORGET,),
        )
    if isinstance(candidates, list) and candidates:
        token = uuid4().hex[:8].lower()
        pending_cookie = chat_admin_actions._encode_forget_pending(
            {
                "token": token,
                "user_id": username,
                "candidates": candidates,
            },
            signing_secret=signing_secret,
            sanitize_username=sanitize_username,
            sanitize_collection_name=sanitize_collection_name,
        )
        return _outcome(
            assistant_text=(
                f"{forget_preview.content}\n\n"
                + _pending_text(
                    language,
                    "memory_forget_confirm_prompt",
                    "To delete, confirm with: 'delete {token}'",
                    token=token,
                )
            ),
            icon="🧹",
            intent_label="memory_forget_pending",
            set_cookies={COOKIE_FORGET: pending_cookie},
        )
    return _outcome(
        assistant_text=forget_preview.content
        or _pending_text(language, "memory_forget_no_matches", "I did not find anything matching to forget."),
        icon="🧹",
        intent_label="memory_forget",
        clear_cookies=(COOKIE_FORGET,),
    )


async def apply_chat_result_pending_followups(
    *,
    result: Any,
    assistant_text: str,
    icon: str,
    intent_label: str,
    username: str,
    settings: Any,
    is_english: bool,
    language: str,
    signing_secret: str,
    sanitize_username: SanitizeUsername,
    sanitize_connection_name: SanitizeConnectionName,
    alert_sender: AlertSender,
) -> ChatPipelinePendingOutcome:
    final_text = assistant_text
    final_icon = icon
    final_intent_label = intent_label
    set_cookies: dict[str, str] = {}
    clear_cookies: list[str] = []
    routed_action_confirm_command: str | None = None
    routed_action_confirm_payload: str | None = None

    if isinstance(result.safe_fix_plan, list) and result.safe_fix_plan:
        token = uuid4().hex[:8].lower()
        set_cookies[COOKIE_SAFE_FIX] = chat_admin_actions._encode_safe_fix_pending(
            {
                "token": token,
                "user_id": username,
                "fixes": result.safe_fix_plan,
            },
            signing_secret=signing_secret,
            sanitize_username=sanitize_username,
            sanitize_connection_name=sanitize_connection_name,
        )
        final_text = (
            f"{final_text}\n\n"
            + _pending_text(
                language,
                "safe_fix_ready_confirm_prompt",
                "Safe fix ready. Confirm with: 'confirm fix {token}'",
                token=token,
            )
        )
        await asyncio.to_thread(
            alert_sender,
            settings,
            category="safe_fix",
            title=_pending_text(language, "safe_fix_alert_ready_title", "Safe fix ready"),
            lines=[
                f"User: {username}",
                f"Token: {token}",
                f"Intents: {', '.join(result.intents) or '-'}",
                f"Text: {final_text[:300]}",
            ],
            level="warn",
        )
        final_intent_label = "safe_fix_pending"
        final_icon = "🛠"

    if isinstance(result.pending_action, dict) and result.pending_action:
        token = uuid4().hex[:8].lower()
        routed_action_confirm_payload = chat_admin_actions._encode_routed_action_pending(
            {
                "token": token,
                "user_id": username,
                **result.pending_action,
            },
            signing_secret=signing_secret,
            sanitize_username=sanitize_username,
        )
        set_cookies[COOKIE_ROUTED_ACTION] = routed_action_confirm_payload
        action = dict(result.pending_action.get("action_decision", {}) or {})
        payload = dict(result.pending_action.get("payload", {}) or {})
        pending_missing_input = str(action.get("missing_input", "") or payload.get("missing_input", "") or "").strip()
        missing_fields = [
            str(item or "").strip()
            for item in list(payload.get("missing_fields", []) or [])
            if str(item or "").strip()
        ]
        if not pending_missing_input and not missing_fields:
            final_text = (
                f"{final_text}\n\n"
                + _pending_text(
                    language,
                    "routed_action_confirm_prompt",
                    "If that looks right, use the confirmation button.",
                    token=token,
                )
            )
            routed_action_confirm_command = _pending_text(
                language,
                "routed_action_confirm_command",
                "confirm action {token}",
                token=token,
            )
            final_icon = "🟡"
            final_intent_label = "routed_action_pending"
    else:
        clear_cookies.append(COOKIE_ROUTED_ACTION)

    return ChatPipelinePendingOutcome(
        assistant_text=final_text,
        icon=final_icon,
        intent_label=final_intent_label,
        set_cookies=set_cookies,
        clear_cookies=tuple(clear_cookies),
        routed_action_confirm_command=routed_action_confirm_command,
        routed_action_confirm_payload=routed_action_confirm_payload if routed_action_confirm_command else None,
    )
