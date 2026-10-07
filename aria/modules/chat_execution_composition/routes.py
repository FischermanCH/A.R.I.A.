from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
import hmac
import inspect
from pathlib import Path
import time
from typing import Any
from urllib.parse import urlencode

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from aria.modules.platform_primitives.i18n import I18NStore
from aria.modules.platform_primitives.recipe_progress import RECIPE_PROGRESS_STORE
from aria.modules.notes.context import notes_index_enabled
from aria.modules.notes.index import NotesIndex
from aria.modules.notes.store import NotesStore
from aria.modules.notes.store import NotesStoreError
from aria.modules.chat_execution_composition.flow import ChatExecutionDeps, execute_chat_flow
from aria.modules.chat_execution_composition.route_helpers import ChatResponseState
from aria.modules.chat_execution_composition.route_helpers import (
    apply_chat_response_cookies,
    prepare_chat_route_state,
    render_missing_username_response,
)
from aria.modules.notes.links import note_editor_path


SettingsGetter = Callable[[], Any]
UsernameResolver = Callable[[Request], str]
SessionIdResolver = Callable[[Request], str]
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
_CHAT_EXECUTION_ROUTES_I18N = I18NStore(Path(__file__).resolve().parents[2] / "i18n")


def _chat_route_text(lang: str | None, key: str, default: str = "", **values: object) -> str:
    template = _CHAT_EXECUTION_ROUTES_I18N.t(lang or "de", f"chat_execution_routes.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template


def _is_save_chat_as_note_command(message: str) -> bool:
    clean = str(message or "").strip().lower()
    return clean in {"/chat note", "/chat notes", "/chat als notiz", "/save chat note", "/save chat as note"}


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

    link = note_editor_path(note.note_id)
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
    connection_delete_pending_cookie: str
    connection_create_pending_cookie: str
    connection_update_pending_cookie: str
    update_pending_cookie: str
    routed_action_pending_cookie: str
    connection_pending_max_age_seconds: int
    forget_signing_secret: str
    pending_signing_secret: str


def register_chat_execution_routes(app: FastAPI, deps: ChatExecutionRouteDeps) -> None:
    def _job_request_wants_json(request: Request) -> bool:
        accept = str(request.headers.get("accept") or "").lower()
        requested_with = str(request.headers.get("x-requested-with") or "").lower()
        return "application/json" in accept or requested_with == "xmlhttprequest"

    def _job_control_response(
        request: Request, *, job_id: str, outcome: str, notice: str,
    ) -> Response:
        clean_job_id = "".join(
            character for character in str(job_id) if character.isalnum() or character in "_-"
        )[:64]
        if _job_request_wants_json(request):
            return JSONResponse({"job_id": clean_job_id, "notice": notice, "outcome": outcome})
        return RedirectResponse(
            url=f"/jobs/panel?{urlencode({'notice': notice})}#job-{clean_job_id}",
            status_code=303,
        )

    def _job_csrf_failure(request: Request) -> Response:
        message = _chat_route_text(
            getattr(request.state, "lang", "de"), "jobs_csrf_failed", "Security check failed.",
        )
        if _job_request_wants_json(request):
            return JSONResponse({"error": "csrf_failed", "detail": message}, status_code=403)
        return HTMLResponse(message, status_code=403)

    def _agent_jobs_for_user(username: str) -> list[dict[str, Any]]:
        list_jobs = getattr(deps.execution_deps.pipeline, "list_agent_jobs", None)
        if not callable(list_jobs):
            return []
        try:
            return [dict(row) for row in list_jobs(username, limit=20)]
        except Exception:
            return []

    def _agent_job_panel_rows(username: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for source in _agent_jobs_for_user(username):
            row = dict(source)
            status = str(row.get("status") or "error")
            result = str(row.get("result") or "")
            row["display_status"] = "interrupted" if status == "error" and result == "worker_restart" else status
            row["has_warning"] = status == "done" and bool(str(row.get("warning") or "").strip())
            row["is_partial"] = status == "done" and str(row.get("warning") or "") in {
                "native_agent_budget_incomplete", "native_agent_summary_unavailable",
            }
            row["goal"] = " ".join(str(row.get("goal") or "").split())[:240]
            usage = dict(row.get("usage") or {})
            total_tokens = max(0, int(usage.get("total_tokens", 0) or 0))
            cache_read = max(0, int(usage.get("cache_read_tokens", 0) or 0))
            input_tokens = max(0, int(usage.get("input_tokens", 0) or 0))
            usage_summary = f"≈ {total_tokens:,} Tokens".replace(",", " ") if total_tokens else ""
            if usage_summary and input_tokens:
                usage_summary += f" ({round(cache_read * 100 / input_tokens)} % aus Cache)"
            if usage.get("cost_usd") is not None:
                usage_summary += (" · " if usage_summary else "") + f"≈ ${float(usage['cost_usd']):.4f}"
            row["usage_summary"] = usage_summary
            for key in ("created_at", "updated_at"):
                try:
                    timestamp = datetime.fromtimestamp(float(row.get(key) or 0), tz=timezone.utc)
                    row[f"{key}_text"] = timestamp.isoformat(timespec="seconds").replace("+00:00", "Z")
                except (TypeError, ValueError, OSError, OverflowError):
                    row[f"{key}_text"] = "-"
            rows.append(row)
        return rows

    @app.get("/jobs")
    async def agent_jobs_status(request: Request) -> Response:
        username = deps.get_username_from_request(request)
        if not username:
            return JSONResponse({"error": "authentication_required"}, status_code=401)
        return JSONResponse({"jobs": _agent_jobs_for_user(username)})

    @app.get("/jobs/{job_id}/notice", response_class=HTMLResponse)
    async def agent_job_notice(request: Request, job_id: str) -> Response:
        username = deps.get_username_from_request(request)
        if not bool(getattr(request.state, "authenticated", False)) or not username:
            return JSONResponse({"error": "authentication_required"}, status_code=401)
        clean_job_id = "".join(
            character for character in str(job_id) if character.isalnum() or character in "_-"
        )[:64]
        job = next((
            dict(row)
            for row in _agent_jobs_for_user(username)
            if str(row.get("job_id") or "") == clean_job_id
        ), None)
        if not clean_job_id or job is None:
            return Response(status_code=404)
        desired_intent = (
            "agent_job_budget_reached"
            if str(job.get("status") or "") == "paused" and str(job.get("pause_reason") or "") == "budget_reached"
            else f"agent_job_{str(job.get('status') or '')}"
        )
        desired_event_key = str(job.get("event_key") or "")
        notice = next((
            dict(row)
            for row in reversed(deps.load_chat_history(username))
            if isinstance(row, dict)
            and str(row.get("role") or "") == "assistant"
            and str(row.get("agent_job_id") or "") == clean_job_id
            and bool(row.get("agent_job_notice"))
            and str(row.get("badge_intent") or "") == desired_intent
            and (
                not desired_event_key
                or str(row.get("agent_job_event_key") or "") == desired_event_key
            )
        ), None)
        if notice is None:
            return Response(status_code=204)
        return deps.templates.TemplateResponse(
            request=request,
            name="_chat_messages.html",
            context={
                "assistant_only": True,
                "assistant_message": str(notice.get("text") or ""),
                "badge_icon": str(notice.get("badge_icon") or ""),
                "badge_intent": str(notice.get("badge_intent") or ""),
                "badge_tokens": int(notice.get("badge_tokens") or 0),
                "badge_cost_usd": str(notice.get("badge_cost_usd") or "n/a"),
                "badge_duration": str(notice.get("badge_duration") or "0.0"),
                "badge_details": list(notice.get("badge_details") or []),
                "agent_job_id": clean_job_id,
                "agent_job_notice": True,
                "agent_job_event_key": str(notice.get("agent_job_event_key") or desired_event_key),
            },
        )

    @app.get("/jobs/panel", response_class=HTMLResponse)
    async def agent_jobs_panel(request: Request) -> Response:
        username = deps.get_username_from_request(request)
        if not bool(getattr(request.state, "authenticated", False)) or not username:
            return HTMLResponse(
                _chat_route_text(getattr(request.state, "lang", "de"), "jobs_auth_required", "Authentication required."),
                status_code=401,
            )
        rows = _agent_job_panel_rows(username)
        requested_job = "".join(
            character for character in str(request.query_params.get("job") or "")
            if character.isalnum() or character in "_-"
        )[:64]
        notice = str(request.query_params.get("notice") or "")
        if requested_job and not any(str(row.get("job_id") or "") == requested_job for row in rows):
            notice = "job_not_found"
        return deps.templates.TemplateResponse(
            request=request,
            name="agent_jobs.html",
            context={
                "jobs": rows,
                "jobs_notice": notice,
            },
        )

    @app.post("/jobs/{job_id}/cancel")
    async def agent_job_cancel(
        request: Request, job_id: str, csrf_token: str = Form(""), event_key: str = Form(""),
    ) -> Response:
        username = deps.get_username_from_request(request)
        if not bool(getattr(request.state, "authenticated", False)) or not username:
            return JSONResponse({"error": "authentication_required"}, status_code=401)
        expected_csrf = str(getattr(request.state, "csrf_token", "") or "")
        supplied_csrf = str(request.headers.get("x-csrf-token") or csrf_token or "")
        if not expected_csrf or not hmac.compare_digest(supplied_csrf, expected_csrf):
            return _job_csrf_failure(request)
        request_cancel = getattr(deps.execution_deps.pipeline, "request_agent_job_cancel", None)
        outcome = "not_found"
        if callable(request_cancel):
            try:
                try:
                    value = request_cancel(username, job_id, event_key=event_key)
                except TypeError:
                    value = request_cancel(username, job_id)
                outcome = str(value or "not_found")
            except Exception:
                outcome = "error"
        notice = outcome if outcome in {"requested", "already_handled", "not_running", "not_found"} else "error"
        return _job_control_response(
            request, job_id=job_id, outcome=outcome, notice=notice,
        )

    @app.post("/jobs/{job_id}/pause")
    async def agent_job_pause(
        request: Request, job_id: str, csrf_token: str = Form(""),
    ) -> Response:
        username = deps.get_username_from_request(request)
        if not bool(getattr(request.state, "authenticated", False)) or not username:
            return JSONResponse({"error": "authentication_required"}, status_code=401)
        expected_csrf = str(getattr(request.state, "csrf_token", "") or "")
        supplied_csrf = str(request.headers.get("x-csrf-token") or csrf_token or "")
        if not expected_csrf or not hmac.compare_digest(supplied_csrf, expected_csrf):
            return _job_csrf_failure(request)
        request_pause = getattr(deps.execution_deps.pipeline, "request_agent_job_pause", None)
        outcome = "not_found"
        if callable(request_pause):
            try:
                outcome = str(request_pause(username, job_id) or "not_found")
            except Exception:
                outcome = "error"
        notice = f"pause_{outcome}" if outcome in {"requested", "not_running", "not_found"} else "pause_error"
        return _job_control_response(
            request, job_id=job_id, outcome=outcome, notice=notice,
        )

    @app.post("/jobs/{job_id}/resume")
    async def agent_job_resume(
        request: Request, job_id: str, csrf_token: str = Form(""),
    ) -> Response:
        username = deps.get_username_from_request(request)
        if not bool(getattr(request.state, "authenticated", False)) or not username:
            return JSONResponse({"error": "authentication_required"}, status_code=401)
        expected_csrf = str(getattr(request.state, "csrf_token", "") or "")
        supplied_csrf = str(request.headers.get("x-csrf-token") or csrf_token or "")
        if not expected_csrf or not hmac.compare_digest(supplied_csrf, expected_csrf):
            return _job_csrf_failure(request)
        resume = getattr(deps.execution_deps.pipeline, "resume_agent_job", None)
        outcome = "not_found"
        if callable(resume):
            try:
                value = resume(username, job_id)
                outcome = str(await value if inspect.isawaitable(value) else value or "not_found")
            except Exception:
                outcome = "error"
        notice = f"resume_{outcome}" if outcome in {"started", "not_running", "not_found"} else "resume_error"
        return _job_control_response(
            request, job_id=job_id, outcome=outcome, notice=notice,
        )

    async def _budget_job_action(
        request: Request, job_id: str, *, action: str, csrf_token: str, event_key: str,
    ) -> Response:
        username = deps.get_username_from_request(request)
        if not bool(getattr(request.state, "authenticated", False)) or not username:
            return JSONResponse({"error": "authentication_required"}, status_code=401)
        expected_csrf = str(getattr(request.state, "csrf_token", "") or "")
        supplied_csrf = str(request.headers.get("x-csrf-token") or csrf_token or "")
        if not expected_csrf or not hmac.compare_digest(supplied_csrf, expected_csrf):
            return _job_csrf_failure(request)
        resume = getattr(deps.execution_deps.pipeline, "resume_agent_job", None)
        outcome = "not_found"
        if callable(resume):
            try:
                try:
                    value = resume(username, job_id, budget_action=action, event_key=event_key)
                except TypeError:
                    value = resume(username, job_id, budget_action=action)
                outcome = str(await value if inspect.isawaitable(value) else value or "not_found")
            except Exception:
                outcome = "error"
        return _job_control_response(
            request, job_id=job_id, outcome=outcome,
            notice=f"budget_{action}_{outcome}" if outcome in {"started", "already_handled", "not_running", "not_found"} else "resume_error",
        )

    @app.post("/jobs/{job_id}/extend")
    async def agent_job_extend(
        request: Request, job_id: str, csrf_token: str = Form(""), event_key: str = Form(""),
    ) -> Response:
        return await _budget_job_action(
            request, job_id, action="extend", csrf_token=csrf_token, event_key=event_key,
        )

    @app.post("/jobs/{job_id}/finish")
    async def agent_job_finish(
        request: Request, job_id: str, csrf_token: str = Form(""), event_key: str = Form(""),
    ) -> Response:
        return await _budget_job_action(
            request, job_id, action="finish", csrf_token=csrf_token, event_key=event_key,
        )

    @app.post("/jobs/{job_id}/delete")
    async def agent_job_delete(request: Request, job_id: str, csrf_token: str = Form("")) -> Response:
        username = deps.get_username_from_request(request)
        if not bool(getattr(request.state, "authenticated", False)) or not username:
            return JSONResponse({"error": "authentication_required"}, status_code=401)
        expected_csrf = str(getattr(request.state, "csrf_token", "") or "")
        supplied_csrf = str(request.headers.get("x-csrf-token") or csrf_token or "")
        if not expected_csrf or not hmac.compare_digest(supplied_csrf, expected_csrf):
            return _job_csrf_failure(request)
        delete = getattr(deps.execution_deps.pipeline, "delete_agent_job", None)
        outcome = str(delete(username, job_id) if callable(delete) else "not_found")
        return _job_control_response(request, job_id=job_id, outcome=outcome, notice=f"delete_{outcome}")

    @app.post("/jobs/clear-completed")
    async def agent_jobs_clear_completed(request: Request, csrf_token: str = Form("")) -> Response:
        username = deps.get_username_from_request(request)
        if not bool(getattr(request.state, "authenticated", False)) or not username:
            return JSONResponse({"error": "authentication_required"}, status_code=401)
        expected_csrf = str(getattr(request.state, "csrf_token", "") or "")
        supplied_csrf = str(request.headers.get("x-csrf-token") or csrf_token or "")
        if not expected_csrf or not hmac.compare_digest(supplied_csrf, expected_csrf):
            return _job_csrf_failure(request)
        clear = getattr(deps.execution_deps.pipeline, "clear_terminal_agent_jobs", None)
        count = int(clear(username) if callable(clear) else 0)
        if _job_request_wants_json(request):
            return JSONResponse({"outcome": "deleted", "count": count})
        return RedirectResponse(url=f"/jobs/panel?{urlencode({'notice': 'cleared', 'count': count})}", status_code=303)

    @app.post("/jobs/{job_id}/correct")
    async def agent_job_correct(
        request: Request, job_id: str, correction: str = Form(""), csrf_token: str = Form(""),
    ) -> Response:
        username = deps.get_username_from_request(request)
        if not bool(getattr(request.state, "authenticated", False)) or not username:
            return JSONResponse({"error": "authentication_required"}, status_code=401)
        expected_csrf = str(getattr(request.state, "csrf_token", "") or "")
        supplied_csrf = str(request.headers.get("x-csrf-token") or csrf_token or "")
        body_correction = correction
        if "application/json" in str(request.headers.get("content-type") or "").lower():
            try:
                payload = await request.json()
                body_correction = str(payload.get("correction") or "") if isinstance(payload, dict) else ""
            except Exception:
                body_correction = ""
        if not expected_csrf or not hmac.compare_digest(supplied_csrf, expected_csrf):
            return _job_csrf_failure(request)
        correct = getattr(deps.execution_deps.pipeline, "request_agent_job_correction", None)
        outcome = "not_found"
        if callable(correct):
            try:
                outcome = str(correct(username, job_id, body_correction) or "not_found")
            except Exception:
                outcome = "error"
        notice = {
            "queued": "correction_queued",
            "not_running": "correction_not_running",
            "not_found": "correction_not_found",
            "invalid": "correction_invalid",
        }.get(outcome, "correction_error")
        return _job_control_response(request, job_id=job_id, outcome=outcome, notice=notice)

    async def _resolve_job_confirmation(
        request: Request, job_id: str, *, approve: bool, csrf_token: str,
    ) -> Response:
        username = deps.get_username_from_request(request)
        if not bool(getattr(request.state, "authenticated", False)) or not username:
            return JSONResponse({"error": "authentication_required"}, status_code=401)
        expected_csrf = str(getattr(request.state, "csrf_token", "") or "")
        supplied_csrf = str(request.headers.get("x-csrf-token") or csrf_token or "")
        if not expected_csrf or not hmac.compare_digest(supplied_csrf, expected_csrf):
            return _job_csrf_failure(request)
        resolve = getattr(deps.execution_deps.pipeline, "resolve_agent_job_confirmation", None)
        outcome = "not_found"
        if callable(resolve):
            try:
                value = resolve(username, job_id, approve=approve)
                outcome = str(await value if inspect.isawaitable(value) else value or "not_found")
            except Exception:
                outcome = "error"
        prefix = "confirm" if approve else "decline"
        notice = f"{prefix}_{outcome}" if outcome in {"started", "not_running", "not_found"} else f"{prefix}_error"
        return _job_control_response(request, job_id=job_id, outcome=outcome, notice=notice)

    @app.post("/jobs/{job_id}/confirm")
    async def agent_job_confirm(
        request: Request, job_id: str, csrf_token: str = Form(""),
    ) -> Response:
        return await _resolve_job_confirmation(
            request, job_id, approve=True, csrf_token=csrf_token,
        )

    @app.post("/jobs/{job_id}/decline")
    async def agent_job_decline(
        request: Request, job_id: str, csrf_token: str = Form(""),
    ) -> Response:
        return await _resolve_job_confirmation(
            request, job_id, approve=False, csrf_token=csrf_token,
        )

    @app.get("/chat/progress")
    async def chat_progress(request: Request) -> Response:
        username = deps.get_username_from_request(request)
        if not username:
            return Response(status_code=204)
        progress = RECIPE_PROGRESS_STORE.get(username)
        if progress is None:
            return Response(status_code=204)
        return JSONResponse(progress)

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
                    "confirmation_button_label": None,
                    "agent_job_id": "",
                    "agent_job_notice": False,
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
                agent_job_id=response_state.agent_job_id,
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
            connection_delete_pending_cookie=deps.connection_delete_pending_cookie,
            connection_create_pending_cookie=deps.connection_create_pending_cookie,
            connection_update_pending_cookie=deps.connection_update_pending_cookie,
            update_pending_cookie=deps.update_pending_cookie,
            routed_action_pending_cookie=deps.routed_action_pending_cookie,
            routed_action_pending_override=routed_action_pending,
        )
        route_prepare_ms = int((time.perf_counter() - route_prepare_start) * 1000)

        history_load_start = time.perf_counter()
        chat_history = deps.load_chat_history(username)
        history_load_ms = int((time.perf_counter() - history_load_start) * 1000)
        feedback_ms = 0
        followup_rewrite_ms = 0
        execute_flow_start = time.perf_counter()
        response_state = await execute_chat_flow(
            clean_message=clean_message,
            username=username,
            lang=lang,
            is_english=is_english,
            route_state=route_state,
            memory_collection=memory_collection,
            session_collection=session_collection,
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
                agent_job_id=response_state.agent_job_id,
            )
            history_append_ms = int((time.perf_counter() - history_append_start) * 1000)
        route_pre_template_total_ms = int((time.perf_counter() - route_start) * 1000)
        route_timing_line = (
            "Routing Debug: web_route_timing "
            f"prepare_ms={route_prepare_ms} history_load_ms={history_load_ms} feedback_ms={feedback_ms} "
            f"followup_rewrite_ms={followup_rewrite_ms} execute_flow_ms={execute_flow_ms} "
            f"stamp_ms={stamp_ms} history_append_ms={history_append_ms} "
            f"pre_template_total_ms={route_pre_template_total_ms} "
            f"total_ms={route_pre_template_total_ms}"
        )
        response_state.badge_details.append(route_timing_line)
        if response_state.agent_job_id:
            append_agent_job_detail_line = getattr(
                deps.execution_deps.pipeline, "append_agent_job_detail_line", None,
            )
            if callable(append_agent_job_detail_line):
                try:
                    append_agent_job_detail_line(
                        username, response_state.agent_job_id, route_timing_line,
                    )
                except Exception:
                    pass
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
                "confirmation_button_label": response_state.confirmation_button_label,
                "suggestion_affordance": response_state.suggestion_affordance,
                "agent_job_id": response_state.agent_job_id,
                "agent_job_notice": False,
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
