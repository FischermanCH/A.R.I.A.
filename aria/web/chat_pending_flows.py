from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

import aria.web.chat_admin_actions as chat_admin_actions


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


@dataclass(frozen=True)
class ChatPipelinePendingOutcome:
    assistant_text: str
    icon: str
    intent_label: str
    set_cookies: dict[str, str] = field(default_factory=dict)
    clear_cookies: tuple[str, ...] = ()


COOKIE_FORGET = "forget"
COOKIE_SAFE_FIX = "safe_fix"
COOKIE_ROUTED_ACTION = "routed_action"

IntentBadge = Callable[[list[str], list[str] | None], tuple[str, str]]
FriendlyErrorText = Callable[[list[str] | None], str]
AlertSender = Callable[..., Any]
SanitizeUsername = Callable[[str | None], str]
SanitizeCollectionName = Callable[[str | None], str]
SanitizeConnectionName = Callable[[str | None], str]


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
            assistant_text = routed_result.text or ("Action executed." if is_english else "Aktion ausgeführt.")
            icon, intent_label = intent_badge(routed_result.intents, routed_result.skill_errors)
            warning = friendly_error_text(routed_result.skill_errors)
            if warning:
                assistant_text = f"{assistant_text}\n\nHinweis: {warning}"
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
                "The confirmation code for this action is invalid or expired."
                if is_english
                else "Der Bestätigungscode für diese Aktion ist ungültig oder abgelaufen."
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
            assistant_text = fix_result.content or "Safe-Fix abgeschlossen."
            icon = "🛠"
            intent_label = "safe_fix_apply"
            if not fix_result.success:
                icon = "⚠"
                warning = friendly_error_text([fix_result.error]) if fix_result.error else ""
                if warning:
                    assistant_text = f"{assistant_text}\n\nHinweis: {warning}"
            await asyncio.to_thread(
                alert_sender,
                settings,
                category="safe_fix",
                title="Safe-Fix ausgeführt",
                lines=[
                    f"User: {username}",
                    f"Ergebnis: {'ok' if fix_result.success else 'fehler'}",
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
            assistant_text="Der Safe-Fix Bestätigungscode ist ungültig oder abgelaufen.",
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
    if not missing_input:
        return None

    routed_result = await pipeline.continue_pending_routed_action_input(
        routed_pending,
        clean_message,
        user_id=username,
        source="web",
        language=language,
    )
    assistant_text = routed_result.text or (
        "Action updated." if is_english else "Aktion aktualisiert."
    )
    icon, intent_label = intent_badge(routed_result.intents, routed_result.skill_errors)
    warning = friendly_error_text(routed_result.skill_errors)
    if warning:
        assistant_text = f"{assistant_text}\n\nHinweis: {warning}"

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
            assistant_text = forget_result.content or "Löschen abgeschlossen."
            if forget_result.success:
                return _outcome(
                    assistant_text=assistant_text,
                    icon="🧹",
                    intent_label="memory_forget",
                    clear_cookies=(COOKIE_FORGET,),
                )
            friendly = friendly_error_text([forget_result.error])
            return _outcome(
                assistant_text=friendly or "Löschen fehlgeschlagen.",
                icon="⚠",
                intent_label="memory_error",
                clear_cookies=(COOKIE_FORGET,),
            )
        return _outcome(
            assistant_text="Der Bestätigungscode ist ungültig oder abgelaufen. Bitte 'Vergiss ...' erneut senden.",
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
            assistant_text=friendly_error_text([forget_preview.error]) or "Memory-Vorschau fehlgeschlagen.",
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
            assistant_text=f"{forget_preview.content}\n\nZum Löschen bestätige mit: 'bestätige {token}'",
            icon="🧹",
            intent_label="memory_forget_pending",
            set_cookies={COOKIE_FORGET: pending_cookie},
        )
    return _outcome(
        assistant_text=forget_preview.content or "Ich habe nichts Passendes zum Vergessen gefunden.",
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
        final_text = f"{final_text}\n\nSafe-Fix bereit. Bestätige mit: 'bestätige fix {token}'"
        await asyncio.to_thread(
            alert_sender,
            settings,
            category="safe_fix",
            title="Safe-Fix bereit",
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
        set_cookies[COOKIE_ROUTED_ACTION] = chat_admin_actions._encode_routed_action_pending(
            {
                "token": token,
                "user_id": username,
                **result.pending_action,
            },
            signing_secret=signing_secret,
            sanitize_username=sanitize_username,
        )
        action = dict(result.pending_action.get("action_decision", {}) or {})
        payload = dict(result.pending_action.get("payload", {}) or {})
        pending_missing_input = str(action.get("missing_input", "") or payload.get("missing_input", "") or "").strip()
        if not pending_missing_input:
            final_text = (
                f"{final_text}\n\n"
                + (
                    f"If that looks right, send: `confirm action {token}`"
                    if is_english
                    else f"Wenn das passt, sende: `bestätige aktion {token}`"
                )
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
    )
