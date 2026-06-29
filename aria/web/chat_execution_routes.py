from __future__ import annotations

from collections.abc import Callable
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
import time
from typing import Any

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates

from aria.core.agentic_execution_learning import suppress_auto_learning
from aria.core.chat_learn_mode import append_chat_learn_observation
from aria.core.chat_learn_mode import chat_learn_mode_active
from aria.core.chat_learn_mode import cancel_chat_learn_mode
from aria.core.chat_learn_mode import finish_chat_learn_mode
from aria.core.chat_learn_mode import parse_chat_learn_command
from aria.core.chat_learn_mode import start_chat_learn_mode
from aria.core.chat_freshness import explicitly_requests_web_research
from aria.core.followup_resolution import FollowupResolver
from aria.core.i18n import I18NStore
from aria.core.notes_context import notes_index_enabled
from aria.core.notes_index import NotesIndex
from aria.core.notes_store import NotesStore
from aria.core.notes_store import NotesStoreError
from aria.core.user_feedback_learning import capture_user_feedback_learning
from aria.web.chat_execution_flow import ChatExecutionDeps, execute_chat_flow
from aria.web.chat_route_helpers import ChatResponseState
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
HistoryLoader = Callable[[str], list[dict[str, Any]]]
HistoryClearer = Callable[[str], None]
ContextClearer = Callable[[str], None]
SanitizeUsername = Callable[[str | None], str]
SanitizeConnectionName = Callable[[str | None], str]
SanitizeRole = Callable[[str | None], str]
IntentBadge = Callable[[list[str], list[str] | None], tuple[str, str]]
FriendlyErrorText = Callable[[list[str] | None], str]
_CHAT_EXECUTION_ROUTES_I18N = I18NStore(Path(__file__).resolve().parents[1] / "i18n")


def _chat_route_text(lang: str | None, key: str, default: str = "", **values: object) -> str:
    template = _CHAT_EXECUTION_ROUTES_I18N.t(lang or "de", f"chat_execution_routes.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template


def _chat_learn_response(command: str, lang: str, *, event_count: int = 0, recipe_id: str = "", reason: str = "") -> ChatResponseState:
    state = ChatResponseState(icon="🧠", intent_label="recipe_learn_mode", total_tokens=0, cost_usd="$0.000000", duration_s="0.0")
    if command == "start":
        state.assistant_text = _chat_route_text(
            lang,
            "learn_start",
            "Recipe learn mode is active. I will record the following chat turns as review context. Use `/learn stop` to create a review-only recipe candidate or `/learn cancel` to discard it.",
        )
    elif command == "cancel":
        state.assistant_text = _chat_route_text(
            lang,
            "learn_cancel",
            "Recipe learn mode cancelled. Discarded {event_count} observed turn(s).",
            event_count=event_count,
        )
    elif command == "stop" and recipe_id:
        link = f"/recipes/learned?recipe_ref={recipe_id}"
        state.assistant_text = _chat_route_text(
            lang,
            "learn_stop_stored",
            "Recipe learn mode finished. Created review-only candidate `{recipe_id}` from {event_count} observed turn(s): {link}",
            recipe_id=recipe_id,
            event_count=event_count,
            link=link,
        )
    elif command == "stop":
        state.assistant_text = _chat_route_text(
            lang,
            "learn_stop_empty",
            "Recipe learn mode ended without a candidate ({reason}).",
            reason=reason or "no observed turns",
        )
    return state


def _is_save_chat_as_note_command(message: str) -> bool:
    clean = str(message or "").strip().lower()
    return clean in {"/chat note", "/chat notes", "/chat als notiz", "/save chat note", "/save chat as note"}


def _extract_recent_user_topic_for_web_search(history: list[dict[str, Any]]) -> str:
    for item in reversed(list(history or [])[-10:]):
        if not isinstance(item, dict):
            continue
        if str(item.get("role", "") or "").strip().lower() != "user":
            continue
        text = re.sub(r"\s+", " ", str(item.get("text", "") or "").strip())
        if not text:
            continue
        lower = text.lower()
        if any(marker in lower for marker in ("suche im internet", "search the web", "websuche", "internet suche")):
            continue
        if len(text.split()) > 18:
            continue
        version_match = re.search(r"\bwelche\s+version\s+(?:von|f(?:u|ue)r)\s+(.+?)(?:\s+(?:ist|sind)\b|$)", text, flags=re.IGNORECASE)
        if version_match:
            topic = re.sub(r"\s+", " ", str(version_match.group(1) or "").strip(" .,:;!?"))
            if topic:
                return f"{topic} version"
        text = re.sub(r"^(?:welche|was\s+ist|wie\s+lautet)\s+", "", text, flags=re.IGNORECASE).strip(" .,:;!?")
        text = re.sub(r"\b(?:ist|sind)\s+(?:momentan\s+)?aktuell\b", "", text, flags=re.IGNORECASE).strip(" .,:;!?")
        text = re.sub(r"\b(?:von|f(?:u|ue)r)\b\s+", "", text, count=1, flags=re.IGNORECASE).strip(" .,:;!?")
        text = re.sub(r"\s+", " ", text).strip(" .,:;!?")
        return text
    return ""


def _rewrite_vague_web_search_followup(message: str, history: list[dict[str, Any]]) -> str:
    clean = re.sub(r"\s+", " ", str(message or "").strip())
    if not clean:
        return clean
    lower = clean.lower()
    search_patterns = (
        r"^(?:suche|such)\s+(?:im|in dem|im)\s+internet\s+(?:nach\s+)?(.+)$",
        r"^(?:suche|such)\s+(?:online|web)\s+(?:nach\s+)?(.+)$",
        r"^search\s+(?:the\s+)?web\s+(?:for\s+)?(.+)$",
        r"^look\s+up\s+(.+)$",
    )
    query = ""
    for pattern in search_patterns:
        match = re.search(pattern, clean, flags=re.IGNORECASE)
        if match:
            query = str(match.group(1) or "").strip(" .,:;!?")
            break
    if not query:
        return clean

    query_lower = query.lower()
    vague_terms = (
        "neuste version",
        "neusten version",
        "neueste version",
        "neuesten version",
        "aktuelle version",
        "momentan aktuell",
        "latest version",
        "current version",
        "newest version",
        "davon",
        "dazu",
    )
    if not any(term in query_lower for term in vague_terms):
        return clean

    topic = _extract_recent_user_topic_for_web_search(history)
    if not topic:
        return clean
    if topic.lower() in query_lower:
        return clean
    return f"suche im internet nach {topic} {query}"


def _rewrite_vague_local_context_followup(message: str, history: list[dict[str, Any]]) -> str:
    clean = re.sub(r"\s+", " ", str(message or "").strip())
    if not clean:
        return clean
    lower = clean.lower()
    if not any(marker in lower for marker in ("meinen notizen", "meinen dokumenten", "meine notizen", "meine dokumente")):
        return clean
    vague_markers = ("dazu", f"dar{chr(117)}eber", f"dar{chr(252)}ber", "davon", "hierzu", "darin")
    if not any(marker in lower for marker in vague_markers):
        return clean
    topic = _extract_recent_user_topic_for_web_search(history)
    if not topic:
        return clean
    if topic.lower() in lower:
        return clean
    if "notiz" in lower:
        return f"was steht in meinen notizen zu {topic}"
    if "dokument" in lower:
        return f"was steht in meinen dokumenten zu {topic}"
    return clean


async def _resolve_pipeline_followup_message(
    message: str,
    history: list[dict[str, Any]],
    *,
    llm_client: Any | None,
    user_id: str = "",
    request_id: str = "",
) -> str:
    clean = re.sub(r"\s+", " ", str(message or "").strip())
    if not clean:
        return clean
    if explicitly_requests_web_research(clean):
        pipeline_message = _rewrite_vague_web_search_followup(clean, history)
        if pipeline_message == clean:
            return clean
    decision = await FollowupResolver(llm_client).resolve(
        clean,
        history=history,
        user_id=user_id,
        request_id=request_id,
    )
    if decision.source == "followup_resolution":
        if decision.action == "rewrite":
            return decision.rewritten_message or clean
        return clean
    pipeline_message = _rewrite_vague_web_search_followup(clean, history)
    return _rewrite_vague_local_context_followup(pipeline_message, history)


def _format_chat_history_markdown(history: list[dict[str, Any]], *, saved_at: str, language: str) -> str:
    if not history:
        return ""
    lines = [
        _chat_route_text(language, "chat_note_intro", "Saved from ARIA chat on {saved_at}.", saved_at=saved_at),
        "",
        _chat_route_text(language, "chat_note_conversation_heading", "## Conversation"),
        "",
    ]
    for item in history:
        role = str(item.get("role", "") or "").strip().lower()
        text = str(item.get("text", "") or "").strip()
        if role not in {"user", "assistant"} or not text:
            continue
        if role == "user":
            role_label = _chat_route_text(language, "chat_note_user", "User")
        else:
            role_label = _chat_route_text(language, "chat_note_assistant", "ARIA")
        timestamp = str(item.get("timestamp", "") or "").strip()
        suffix = f" · {timestamp}" if timestamp else ""
        lines.append(f"### {role_label}{suffix}")
        lines.append("")
        lines.append(text)
        lines.append("")
    body = "\n".join(lines).strip()
    if not body:
        return ""
    return body


async def _save_chat_history_as_note(
    *,
    base_dir: Path,
    settings: Any,
    username: str,
    history: list[dict[str, Any]],
    language: str,
) -> ChatResponseState:
    state = ChatResponseState(icon="📝", intent_label="notes", total_tokens=0, cost_usd="$0.000000", duration_s="0.0")
    relevant_history = [
        item
        for item in list(history or [])
        if isinstance(item, dict)
        and str(item.get("role", "") or "").strip().lower() in {"user", "assistant"}
        and str(item.get("text", "") or "").strip()
    ]
    if not relevant_history:
        state.assistant_text = _chat_route_text(language, "chat_note_empty", "There is no chat history to save yet.")
        return state
    now = datetime.now(timezone.utc)
    saved_at = now.isoformat(timespec="seconds").replace("+00:00", "Z")
    month = now.strftime("%Y-%m")
    title = _chat_route_text(language, "chat_note_title", "Chat {saved_at}", saved_at=saved_at)
    folder = _chat_route_text(language, "chat_note_folder", "Chats/{month}", month=month)
    body = _format_chat_history_markdown(relevant_history, saved_at=saved_at, language=language)
    if not body:
        state.assistant_text = _chat_route_text(language, "chat_note_empty", "There is no chat history to save yet.")
        return state
    store = NotesStore(Path(base_dir) / "data" / "notes")
    try:
        note = store.save_note(
            username,
            title=title,
            folder=folder,
            tags=["chat", "archive", "aria"],
            body=body,
        )
    except NotesStoreError as exc:
        state.assistant_text = _chat_route_text(language, "chat_note_failed", "The chat could not be saved as a note: {error}", error=exc)
        return state

    index_hint = _chat_route_text(language, "chat_note_index_inactive", "Qdrant index is not active; the Markdown note is saved.")
    if notes_index_enabled(settings):
        notes_index = NotesIndex(
            settings.memory,
            settings.embeddings,
            usage_meter=getattr(settings, "_aria_usage_meter", None),
        )
        try:
            result = await notes_index.reindex_note(note)
            index_hint = _chat_route_text(
                language,
                "chat_note_indexed",
                "Qdrant index updated ({chunk_count} chunks).",
                chunk_count=int(result.get("chunk_count", 0) or 0),
            )
        except Exception as exc:
            index_hint = _chat_route_text(
                language,
                "chat_note_index_failed",
                "Qdrant index could not be updated yet: {error}",
                error=exc,
            )
        finally:
            await notes_index.aclose()

    link = f"/notes?note={note.note_id}#note-editor"
    state.assistant_text = _chat_route_text(
        language,
        "chat_note_saved",
        "Chat saved as note: **{title}**\n\nFolder: {folder}\n\nOpen: `{link}`\n\n{index_hint}",
        title=note.title,
        folder=note.folder or "Inbox",
        link=link,
        index_hint=index_hint,
    )
    state.badge_details = [
        f"Chat note: messages={len(relevant_history)}",
        f"Chat note: note_id={note.note_id}",
    ]
    return state


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
    load_chat_history: HistoryLoader
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
    pending_signing_secret: str


def register_chat_execution_routes(app: FastAPI, deps: ChatExecutionRouteDeps) -> None:
    @app.post("/chat", response_class=HTMLResponse)
    async def chat(
        request: Request,
        message: str = Form(...),
        routed_action_pending: str = Form(""),
    ) -> HTMLResponse:
        route_start = time.perf_counter()
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

        def _stamp_route_wall_time(state: ChatResponseState) -> None:
            route_wall_ms = int((time.perf_counter() - route_start) * 1000)
            state.duration_s = f"{route_wall_ms / 1000:.1f}"
            details = list(state.badge_details or [])
            details.append(
                "Routing Debug: web_total_wall_time "
                f"total_ms={route_wall_ms} source=web_chat_route boundary=prompt_in_to_html_ready"
            )
            state.badge_details = details

        learn_command = parse_chat_learn_command(clean_message)
        if learn_command == "start":
            start_chat_learn_mode(deps.execution_deps.base_dir, username=username, session_id=session_id)
            response_state = _chat_learn_response("start", lang)
        elif learn_command == "cancel":
            discarded = cancel_chat_learn_mode(deps.execution_deps.base_dir, username=username, session_id=session_id)
            response_state = _chat_learn_response("cancel", lang, event_count=discarded)
        elif learn_command == "stop":
            learned_entry, event_count, reason = await finish_chat_learn_mode(
                deps.execution_deps.base_dir,
                username=username,
                session_id=session_id,
                llm_client=getattr(deps.execution_deps.pipeline, "llm_client", None),
                language=lang,
            )
            response_state = _chat_learn_response(
                "stop",
                lang,
                event_count=event_count,
                recipe_id=str((learned_entry or {}).get("recipe_id", "") or "").strip(),
                reason=reason,
            )
            response_state.badge_details = [
                f"Recipe learn mode: event_count={event_count}",
                f"Recipe learn mode: result={reason}",
            ]
            _stamp_route_wall_time(response_state)
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
                    "routed_action_confirm_command": None,
                    "routed_action_confirm_payload": None,
                },
            )
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
        else:
            response_state = None

        if response_state is None and _is_save_chat_as_note_command(clean_message):
            response_state = await _save_chat_history_as_note(
                base_dir=deps.execution_deps.base_dir,
                settings=settings,
                username=username,
                history=deps.load_chat_history(username),
                language=lang,
            )

        if response_state is not None:
            _stamp_route_wall_time(response_state)
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
                    "routed_action_confirm_command": None,
                    "routed_action_confirm_payload": None,
                },
            )
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

        route_prepare_start = time.perf_counter()
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
            forget_signing_secret=deps.forget_signing_secret,
            pending_signing_secret=deps.pending_signing_secret,
            connection_pending_max_age_seconds=deps.connection_pending_max_age_seconds,
            forget_pending_cookie=deps.forget_pending_cookie,
            safe_fix_pending_cookie=deps.safe_fix_pending_cookie,
            connection_delete_pending_cookie=deps.connection_delete_pending_cookie,
            connection_create_pending_cookie=deps.connection_create_pending_cookie,
            connection_update_pending_cookie=deps.connection_update_pending_cookie,
            update_pending_cookie=deps.update_pending_cookie,
            routed_action_pending_cookie=deps.routed_action_pending_cookie,
            routed_action_pending_override=routed_action_pending,
        )
        route_prepare_ms = int((time.perf_counter() - route_prepare_start) * 1000)

        learn_active = chat_learn_mode_active(deps.execution_deps.base_dir, username=username, session_id=session_id)
        history_load_start = time.perf_counter()
        chat_history = deps.load_chat_history(username)
        history_load_ms = int((time.perf_counter() - history_load_start) * 1000)
        feedback_ms = 0
        if not learn_active and auto_memory_enabled:
            feedback_start = time.perf_counter()
            try:
                await capture_user_feedback_learning(
                    message=clean_message,
                    user_id=username,
                    history=chat_history,
                    memory_skill=getattr(deps.execution_deps.pipeline, "memory_skill", None),
                    llm_client=getattr(deps.execution_deps.pipeline, "llm_client", None),
                )
                feedback_ms = int((time.perf_counter() - feedback_start) * 1000)
            except Exception:
                feedback_ms = int((time.perf_counter() - feedback_start) * 1000)
                pass
        followup_rewrite_start = time.perf_counter()
        pipeline_message = await _resolve_pipeline_followup_message(
            clean_message,
            chat_history,
            llm_client=getattr(deps.execution_deps.pipeline, "llm_client", None),
            user_id=username,
        )
        followup_rewrite_ms = int((time.perf_counter() - followup_rewrite_start) * 1000)
        learning_context = suppress_auto_learning() if learn_active else nullcontext()
        execute_flow_start = time.perf_counter()
        with learning_context:
            response_state = await execute_chat_flow(
                clean_message=clean_message,
                pipeline_message=pipeline_message,
                username=username,
                lang=lang,
                is_english=is_english,
                route_state=route_state,
                memory_collection=memory_collection,
                session_collection=session_collection,
                auto_memory_enabled=auto_memory_enabled,
                deps=deps.execution_deps,
                chat_history=chat_history,
            )
        execute_flow_ms = int((time.perf_counter() - execute_flow_start) * 1000)
        stamp_start = time.perf_counter()
        _stamp_route_wall_time(response_state)
        stamp_ms = int((time.perf_counter() - stamp_start) * 1000)

        history_append_ms = 0
        if username and response_state.assistant_text:
            history_append_start = time.perf_counter()
            append_chat_learn_observation(
                deps.execution_deps.base_dir,
                username=username,
                session_id=session_id,
                user_message=clean_message,
                assistant_text=response_state.assistant_text,
                intent_label=response_state.intent_label,
                badge_details=response_state.badge_details,
            )
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
            history_append_ms = int((time.perf_counter() - history_append_start) * 1000)
        response_state.badge_details.append(
            "Routing Debug: web_route_timing "
            f"prepare_ms={route_prepare_ms} history_load_ms={history_load_ms} feedback_ms={feedback_ms} "
            f"followup_rewrite_ms={followup_rewrite_ms} execute_flow_ms={execute_flow_ms} "
            f"stamp_ms={stamp_ms} history_append_ms={history_append_ms} "
            f"pre_template_total_ms={int((time.perf_counter() - route_start) * 1000)}"
        )
        template_start = time.perf_counter()
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
                "routed_action_confirm_command": response_state.routed_action_confirm_command,
                "routed_action_confirm_payload": response_state.routed_action_confirm_payload,
            },
        )
        template_ms = int((time.perf_counter() - template_start) * 1000)
        cookies_start = time.perf_counter()
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
        cookies_ms = int((time.perf_counter() - cookies_start) * 1000)
        response.headers["x-aria-web-template-ms"] = str(template_ms)
        response.headers["x-aria-web-cookies-ms"] = str(cookies_ms)
        return response

    @app.post("/chat/history/clear")
    async def clear_chat_history(request: Request) -> Response:
        username = deps.get_username_from_request(request)
        if username:
            deps.clear_chat_history(username)
            deps.clear_capability_context(username)
        return Response(status_code=204)
