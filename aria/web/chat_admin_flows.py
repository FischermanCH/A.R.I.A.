from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

import aria.web.chat_admin_actions as chat_admin_actions
from aria.core.connection_admin import ConnectionAdminError
from aria.core.connection_admin import friendly_connection_admin_error_text
from aria.core.connection_catalog import sanitize_connection_payload
from aria.core.connection_catalog import normalize_connection_kind
from aria.core.connection_admin import sanitize_connection_ref
from aria.core.i18n import I18NStore


@dataclass(frozen=True)
class ChatAdminRequests:
    connection_delete_confirm_token: str | None = None
    connection_delete_request: tuple[str, str] | None = None
    connection_create_confirm_token: str | None = None
    connection_create_request: dict[str, Any] | None = None
    connection_update_confirm_token: str | None = None
    connection_update_request: dict[str, Any] | None = None
    update_confirm_token: str | None = None
    update_run_request: bool = False
    update_status_request: bool = False
    backup_export_request: bool = False
    backup_import_request: bool = False
    stats_request: bool = False
    activities_request: bool = False


@dataclass(frozen=True)
class ChatAdminPendingState:
    connection_delete_pending: dict[str, Any] | None = None
    connection_create_pending: dict[str, Any] | None = None
    connection_update_pending: dict[str, Any] | None = None
    update_pending: dict[str, Any] | None = None


@dataclass(frozen=True)
class ChatAdminOutcome:
    handled: bool
    assistant_text: str = ""
    icon: str = "⚠"
    intent_label: str = "chat"
    set_cookies: dict[str, str] = field(default_factory=dict)
    clear_cookies: tuple[str, ...] = ()


COOKIE_CONNECTION_DELETE = "connection_delete"
COOKIE_CONNECTION_CREATE = "connection_create"
COOKIE_CONNECTION_UPDATE = "connection_update"
COOKIE_UPDATE = "update"
_CHAT_ADMIN_I18N = I18NStore(Path(__file__).resolve().parents[1] / "i18n")


ResolveUpdateHelperConfig = Callable[..., Any]
TriggerUpdateHelperRun = Callable[[Any], dict[str, Any]]
FetchUpdateHelperStatus = Callable[[Any], dict[str, Any]]
HelperStatusVisual = Callable[..., str]
ListConnectionRefs = Callable[[Path], Any]
ResolveConnectionTarget = Callable[..., tuple[str, str]]
DeleteConnectionProfile = Callable[[Path, str, str], dict[str, Any]]
CreateConnectionProfile = Callable[[Path, str, str, dict[str, Any]], dict[str, Any]]
UpdateConnectionProfile = Callable[[Path, str, str, dict[str, Any]], dict[str, Any]]
ReloadRuntime = Callable[[], Any]
ReadRawConfig = Callable[[], dict[str, Any]]
BuildConfigBackupPayload = Callable[..., dict[str, Any]]
SummarizeConfigBackupPayload = Callable[[dict[str, Any]], dict[str, Any]]
GetSecureStore = Callable[[dict[str, Any] | None], Any]
SanitizeUsername = Callable[[str | None], str]
SanitizeConnectionName = Callable[[str | None], str]


def _outcome(
    *,
    assistant_text: str,
    icon: str,
    intent_label: str,
    set_cookies: dict[str, str] | None = None,
    clear_cookies: tuple[str, ...] | None = None,
) -> ChatAdminOutcome:
    return ChatAdminOutcome(
        handled=True,
        assistant_text=assistant_text,
        icon=icon,
        intent_label=intent_label,
        set_cookies=dict(set_cookies or {}),
        clear_cookies=tuple(clear_cookies or ()),
    )


def _chat_admin_text(language: str | None, key: str, **values: Any) -> str:
    template = _CHAT_ADMIN_I18N.t(str(language or "de"), key, key)
    try:
        return template.format(**values)
    except (KeyError, IndexError, ValueError):
        return template


def _connection_admin_denied(*, intent_label: str, clear_cookie_key: str, language: str | None) -> ChatAdminOutcome:
    return _outcome(
        assistant_text=_chat_admin_text(language, "chat_admin.connection_denied"),
        icon="⚠",
        intent_label=intent_label,
        clear_cookies=(clear_cookie_key,),
    )


def _handle_connection_delete_flow(
    *,
    request: ChatAdminRequests,
    pending: ChatAdminPendingState,
    username: str,
    auth_role: str,
    base_dir: Path,
    signing_secret: str,
    sanitize_username: SanitizeUsername,
    sanitize_connection_name: SanitizeConnectionName,
    list_connection_refs: ListConnectionRefs,
    resolve_connection_target: ResolveConnectionTarget,
    delete_connection_profile: DeleteConnectionProfile,
    reload_runtime: ReloadRuntime,
    language: str | None = None,
) -> ChatAdminOutcome | None:
    confirm_token = str(request.connection_delete_confirm_token or "").strip().lower()
    delete_request = request.connection_delete_request
    pending_payload = pending.connection_delete_pending or {}
    if confirm_token and pending_payload:
        pending_user = str(pending_payload.get("user_id", "")).strip()
        pending_token = str(pending_payload.get("token", "")).strip().lower()
        pending_kind = str(pending_payload.get("kind", "")).strip().lower()
        pending_ref = str(pending_payload.get("ref", "")).strip()
        if auth_role != "admin":
            return _connection_admin_denied(intent_label="connection_delete_denied", clear_cookie_key=COOKIE_CONNECTION_DELETE, language=language)
        if pending_user == username and pending_token and pending_token == confirm_token and pending_kind and pending_ref:
            try:
                delete_result = delete_connection_profile(base_dir, pending_kind, pending_ref)
                reload_runtime()
                assistant_text = str(delete_result.get("success_message", "") or "").strip()
                if not assistant_text:
                    assistant_text = _chat_admin_text(language, "chat_admin.connection_deleted_fallback", ref=pending_ref)
                assistant_text += "\n\n" + _chat_admin_text(
                    language,
                    "chat_admin.connection_deleted_detail",
                    kind=pending_kind,
                    ref=pending_ref,
                )
                return _outcome(
                    assistant_text=assistant_text,
                    icon="🗑",
                    intent_label="connection_delete",
                    clear_cookies=(COOKIE_CONNECTION_DELETE,),
                )
            except Exception as exc:
                detail = friendly_connection_admin_error_text(exc, kind=pending_kind, action="delete")
                return _outcome(
                    assistant_text=_chat_admin_text(language, "chat_admin.connection_delete_failed", detail=detail),
                    icon="⚠",
                    intent_label="connection_delete_error",
                )
        return _outcome(
            assistant_text=_chat_admin_text(language, "chat_admin.connection_delete_invalid_token"),
            icon="⚠",
            intent_label="connection_delete_invalid_token",
            clear_cookies=(COOKIE_CONNECTION_DELETE,),
        )

    if delete_request:
        if auth_role != "admin":
            return _connection_admin_denied(intent_label="connection_delete_denied", clear_cookie_key=COOKIE_CONNECTION_DELETE, language=language)
        kind_hint = ""
        try:
            kind_hint, ref_hint = delete_request
            catalog = list_connection_refs(base_dir)
            resolved_kind, resolved_ref = resolve_connection_target(catalog, ref_hint=ref_hint, kind_hint=kind_hint)
            token = uuid4().hex[:8].lower()
            pending_cookie = chat_admin_actions._encode_connection_delete_pending(
                {
                    "token": token,
                    "user_id": username,
                    "kind": resolved_kind,
                    "ref": resolved_ref,
                },
                signing_secret=signing_secret,
                sanitize_username=sanitize_username,
                sanitize_connection_name=sanitize_connection_name,
            )
            return _outcome(
                assistant_text=(
                    _chat_admin_text(
                        language,
                        "chat_admin.connection_delete_pending",
                        kind=resolved_kind,
                        ref=resolved_ref,
                        token=token,
                    )
                ),
                icon="🗑",
                intent_label="connection_delete_pending",
                set_cookies={COOKIE_CONNECTION_DELETE: pending_cookie},
            )
        except Exception as exc:
            detail = friendly_connection_admin_error_text(exc, kind=kind_hint, action="delete")
            return _outcome(
                assistant_text=_chat_admin_text(language, "chat_admin.connection_delete_not_prepared", detail=detail),
                icon="⚠",
                intent_label="connection_delete_error",
            )
    return None


def _handle_connection_create_flow(
    *,
    request: ChatAdminRequests,
    pending: ChatAdminPendingState,
    username: str,
    auth_role: str,
    signing_secret: str,
    sanitize_username: SanitizeUsername,
    create_connection_profile: CreateConnectionProfile,
    reload_runtime: ReloadRuntime,
    base_dir: Path,
    language: str | None = None,
) -> ChatAdminOutcome | None:
    confirm_token = str(request.connection_create_confirm_token or "").strip().lower()
    create_request = request.connection_create_request or {}
    pending_payload = pending.connection_create_pending or {}
    if confirm_token and pending_payload:
        pending_user = str(pending_payload.get("user_id", "")).strip()
        pending_token = str(pending_payload.get("token", "")).strip().lower()
        pending_kind = str(pending_payload.get("kind", "")).strip().lower()
        pending_ref = str(pending_payload.get("ref", "")).strip()
        pending_connection_payload = pending_payload.get("payload", {})
        if auth_role != "admin":
            return _connection_admin_denied(intent_label="connection_create_denied", clear_cookie_key=COOKIE_CONNECTION_CREATE, language=language)
        if (
            pending_user == username
            and pending_token
            and pending_token == confirm_token
            and pending_kind
            and pending_ref
            and isinstance(pending_connection_payload, dict)
        ):
            try:
                create_result = create_connection_profile(base_dir, pending_kind, pending_ref, pending_connection_payload)
                reload_runtime()
                assistant_text = str(create_result.get("success_message", "") or "").strip()
                if not assistant_text:
                    assistant_text = _chat_admin_text(language, "chat_admin.connection_created_fallback", ref=pending_ref)
                assistant_text += "\n\n" + _chat_admin_text(
                    language,
                    "chat_admin.connection_created_detail",
                    kind=pending_kind,
                    ref=pending_ref,
                )
                return _outcome(
                    assistant_text=assistant_text,
                    icon="🧩",
                    intent_label="connection_create",
                    clear_cookies=(COOKIE_CONNECTION_CREATE,),
                )
            except Exception as exc:
                detail = friendly_connection_admin_error_text(exc, kind=pending_kind, action="create")
                return _outcome(
                    assistant_text=_chat_admin_text(language, "chat_admin.connection_create_failed", detail=detail),
                    icon="⚠",
                    intent_label="connection_create_error",
                )
        return _outcome(
            assistant_text=_chat_admin_text(language, "chat_admin.connection_create_invalid_token"),
            icon="⚠",
            intent_label="connection_create_invalid_token",
            clear_cookies=(COOKIE_CONNECTION_CREATE,),
        )

    if create_request:
        if auth_role != "admin":
            return _connection_admin_denied(intent_label="connection_create_denied", clear_cookie_key=COOKIE_CONNECTION_CREATE, language=language)
        kind = ""
        try:
            kind = normalize_connection_kind(str(create_request.get("kind", "")).strip().lower().replace("-", "_"))
            ref = sanitize_connection_ref(str(create_request.get("ref", "")).strip())
            payload = sanitize_connection_payload(kind, create_request.get("payload", {}))
            if not kind or not ref or not isinstance(payload, dict):
                raise ConnectionAdminError("incomplete_data")
            token = uuid4().hex[:8].lower()
            pending_cookie = chat_admin_actions._encode_connection_create_pending(
                {
                    "token": token,
                    "user_id": username,
                    "kind": kind,
                    "ref": ref,
                    "payload": payload,
                },
                signing_secret=signing_secret,
                sanitize_username=sanitize_username,
            )
            summary_lines = [
                _chat_admin_text(language, "chat_admin.connection_summary_type", kind=kind),
                f"Ref: `{ref}`",
                *chat_admin_actions._format_connection_payload_summary(kind, payload),
            ]
            return _outcome(
                assistant_text=(
                    _chat_admin_text(language, "chat_admin.connection_create_pending_intro")
                    + "\n\n- "
                    + "\n- ".join(summary_lines)
                    + "\n\n"
                    + _chat_admin_text(language, "chat_admin.connection_create_confirm_instruction", token=token)
                ),
                icon="🧩",
                intent_label="connection_create_pending",
                set_cookies={COOKIE_CONNECTION_CREATE: pending_cookie},
            )
        except Exception as exc:
            detail = friendly_connection_admin_error_text(exc, kind=kind, action="create")
            return _outcome(
                assistant_text=_chat_admin_text(language, "chat_admin.connection_create_not_prepared", detail=detail),
                icon="⚠",
                intent_label="connection_create_error",
            )
    return None


def _handle_connection_update_flow(
    *,
    request: ChatAdminRequests,
    pending: ChatAdminPendingState,
    username: str,
    auth_role: str,
    signing_secret: str,
    sanitize_username: SanitizeUsername,
    update_connection_profile: UpdateConnectionProfile,
    reload_runtime: ReloadRuntime,
    base_dir: Path,
    language: str | None = None,
) -> ChatAdminOutcome | None:
    confirm_token = str(request.connection_update_confirm_token or "").strip().lower()
    update_request = request.connection_update_request or {}
    pending_payload = pending.connection_update_pending or {}
    if confirm_token and pending_payload:
        pending_user = str(pending_payload.get("user_id", "")).strip()
        pending_token = str(pending_payload.get("token", "")).strip().lower()
        pending_kind = str(pending_payload.get("kind", "")).strip().lower()
        pending_ref = str(pending_payload.get("ref", "")).strip()
        pending_connection_payload = pending_payload.get("payload", {})
        if auth_role != "admin":
            return _connection_admin_denied(intent_label="connection_update_denied", clear_cookie_key=COOKIE_CONNECTION_UPDATE, language=language)
        if (
            pending_user == username
            and pending_token
            and pending_token == confirm_token
            and pending_kind
            and pending_ref
            and isinstance(pending_connection_payload, dict)
        ):
            try:
                update_result = update_connection_profile(base_dir, pending_kind, pending_ref, pending_connection_payload)
                reload_runtime()
                assistant_text = str(update_result.get("success_message", "") or "").strip()
                if not assistant_text:
                    assistant_text = _chat_admin_text(language, "chat_admin.connection_updated_fallback", ref=pending_ref)
                assistant_text += "\n\n" + _chat_admin_text(
                    language,
                    "chat_admin.connection_updated_detail",
                    kind=pending_kind,
                    ref=pending_ref,
                )
                return _outcome(
                    assistant_text=assistant_text,
                    icon="🛠",
                    intent_label="connection_update",
                    clear_cookies=(COOKIE_CONNECTION_UPDATE,),
                )
            except Exception as exc:
                detail = friendly_connection_admin_error_text(exc, kind=pending_kind, action="update")
                return _outcome(
                    assistant_text=_chat_admin_text(language, "chat_admin.connection_update_failed", detail=detail),
                    icon="⚠",
                    intent_label="connection_update_error",
                )
        return _outcome(
            assistant_text=_chat_admin_text(language, "chat_admin.connection_update_invalid_token"),
            icon="⚠",
            intent_label="connection_update_invalid_token",
            clear_cookies=(COOKIE_CONNECTION_UPDATE,),
        )

    if update_request:
        if auth_role != "admin":
            return _connection_admin_denied(intent_label="connection_update_denied", clear_cookie_key=COOKIE_CONNECTION_UPDATE, language=language)
        kind = ""
        try:
            kind = normalize_connection_kind(str(update_request.get("kind", "")).strip().lower().replace("-", "_"))
            ref = sanitize_connection_ref(str(update_request.get("ref", "")).strip())
            payload = sanitize_connection_payload(kind, update_request.get("payload", {}))
            if not kind or not ref or not isinstance(payload, dict) or not payload:
                raise ConnectionAdminError("incomplete_data")
            token = uuid4().hex[:8].lower()
            pending_cookie = chat_admin_actions._encode_connection_update_pending(
                {
                    "token": token,
                    "user_id": username,
                    "kind": kind,
                    "ref": ref,
                    "payload": payload,
                },
                signing_secret=signing_secret,
                sanitize_username=sanitize_username,
            )
            summary_lines = [
                _chat_admin_text(language, "chat_admin.connection_summary_type", kind=kind),
                f"Ref: `{ref}`",
                *chat_admin_actions._format_connection_payload_summary(kind, payload),
            ]
            return _outcome(
                assistant_text=(
                    _chat_admin_text(language, "chat_admin.connection_update_pending_intro")
                    + "\n\n- "
                    + "\n- ".join(summary_lines)
                    + "\n\n"
                    + _chat_admin_text(language, "chat_admin.connection_update_confirm_instruction", token=token)
                ),
                icon="🛠",
                intent_label="connection_update_pending",
                set_cookies={COOKIE_CONNECTION_UPDATE: pending_cookie},
            )
        except Exception as exc:
            detail = friendly_connection_admin_error_text(exc, kind=kind, action="update")
            return _outcome(
                assistant_text=_chat_admin_text(language, "chat_admin.connection_update_not_prepared", detail=detail),
                icon="⚠",
                intent_label="connection_update_error",
            )
    return None


def _handle_update_flow(
    *,
    request: ChatAdminRequests,
    pending: ChatAdminPendingState,
    username: str,
    auth_role: str,
    signing_secret: str,
    sanitize_username: SanitizeUsername,
    resolve_update_helper_config: ResolveUpdateHelperConfig,
    trigger_update_helper_run: TriggerUpdateHelperRun,
    fetch_update_helper_status: FetchUpdateHelperStatus,
    helper_status_visual: HelperStatusVisual,
    get_secure_store: GetSecureStore,
    language: str | None = None,
) -> ChatAdminOutcome | None:
    confirm_token = str(request.update_confirm_token or "").strip().lower()
    pending_payload = pending.update_pending or {}
    if confirm_token and pending_payload:
        pending_user = str(pending_payload.get("user_id", "")).strip()
        pending_token = str(pending_payload.get("token", "")).strip().lower()
        if auth_role != "admin":
            return _outcome(
                assistant_text=_chat_admin_text(language, "chat_admin.update_denied"),
                icon="⚠",
                intent_label="update_denied",
                clear_cookies=(COOKIE_UPDATE,),
            )
        if pending_user == username and pending_token and pending_token == confirm_token:
            helper_config = resolve_update_helper_config(secure_store=get_secure_store(None))
            if not helper_config.enabled:
                return _outcome(
                    assistant_text=_chat_admin_text(language, "chat_admin.update_disabled"),
                    icon="⚠",
                    intent_label="update_disabled",
                    clear_cookies=(COOKIE_UPDATE,),
                )
            try:
                result = trigger_update_helper_run(helper_config)
                status = str(result.get("status", "")).strip().lower() or "accepted"
                return _outcome(
                    assistant_text=(
                        _chat_admin_text(language, "chat_admin.update_started", status=status)
                    ),
                    icon="🚀",
                    intent_label="update_started",
                    clear_cookies=(COOKIE_UPDATE,),
                )
            except RuntimeError as exc:
                return _outcome(
                    assistant_text=_chat_admin_text(language, "chat_admin.update_start_failed", error=exc),
                    icon="⚠",
                    intent_label="update_error",
                    clear_cookies=(COOKIE_UPDATE,),
                )
        return _outcome(
            assistant_text=_chat_admin_text(language, "chat_admin.update_invalid_token"),
            icon="⚠",
            intent_label="update_invalid_token",
            clear_cookies=(COOKIE_UPDATE,),
        )

    if request.update_run_request:
        if auth_role != "admin":
            return _outcome(
                assistant_text=_chat_admin_text(language, "chat_admin.update_denied"),
                icon="⚠",
                intent_label="update_denied",
                clear_cookies=(COOKIE_UPDATE,),
            )
        token = uuid4().hex[:8].lower()
        pending_cookie = chat_admin_actions._encode_update_pending(
            {"token": token, "user_id": username},
            signing_secret=signing_secret,
            sanitize_username=sanitize_username,
        )
        return _outcome(
            assistant_text=(
                _chat_admin_text(language, "chat_admin.update_pending", token=token)
            ),
            icon="🚀",
            intent_label="update_pending",
            set_cookies={COOKIE_UPDATE: pending_cookie},
        )

    if request.update_status_request:
        if auth_role != "admin":
            return _outcome(
                assistant_text=_chat_admin_text(language, "chat_admin.update_page_link"),
                icon="🩺",
                intent_label="update_page",
            )
        helper_config = resolve_update_helper_config(secure_store=get_secure_store(None))
        if not helper_config.enabled:
            return _outcome(
                assistant_text=_chat_admin_text(language, "chat_admin.update_disabled"),
                icon="⚠",
                intent_label="update_disabled",
            )
        try:
            helper_status = fetch_update_helper_status(helper_config)
            visual = helper_status_visual(
                str(helper_status.get("status", "") or ""),
                running=bool(helper_status.get("running", False)),
                configured=True,
                reachable=True,
                last_error=str(helper_status.get("last_error", "") or helper_status.get("helper_error", "") or ""),
            )
            lamp = {"ok": "🟢", "warn": "🟡", "error": "🔴"}.get(visual, "🟡")
            lines = [f"Update-Helper: {lamp} `{str(helper_status.get('status', 'unknown') or 'unknown')}`"]
            if str(helper_status.get("current_step", "")).strip():
                lines.append(_chat_admin_text(language, "chat_admin.update_current_step", step=helper_status["current_step"]))
            if str(helper_status.get("last_result", "")).strip():
                lines.append(_chat_admin_text(language, "chat_admin.update_last_result", result=helper_status["last_result"]))
            if str(helper_status.get("last_error", "")).strip():
                lines.append(_chat_admin_text(language, "chat_admin.update_last_error", error=helper_status["last_error"]))
            lines.append(_chat_admin_text(language, "chat_admin.update_page_link"))
            if bool(helper_status.get("running", False)):
                lines.append(_chat_admin_text(language, "chat_admin.update_live_link"))
            return _outcome(
                assistant_text="\n".join(lines),
                icon="🩺",
                intent_label="update_status",
            )
        except RuntimeError as exc:
            return _outcome(
                assistant_text=_chat_admin_text(language, "chat_admin.update_helper_unreachable", error=exc),
                icon="⚠",
                intent_label="update_error",
            )
    return None


def _handle_info_pages_flow(
    *,
    request: ChatAdminRequests,
    advanced_mode: bool,
    base_dir: Path,
    read_raw_config: ReadRawConfig,
    build_config_backup_payload: BuildConfigBackupPayload,
    summarize_config_backup_payload: SummarizeConfigBackupPayload,
    get_secure_store: GetSecureStore,
    language: str | None = None,
) -> ChatAdminOutcome | None:
    if request.backup_export_request:
        if not advanced_mode:
            return _outcome(
                assistant_text=_chat_admin_text(language, "chat_admin.backup_export_denied"),
                icon="⚠",
                intent_label="backup_denied",
            )
        raw = read_raw_config()
        payload = build_config_backup_payload(
            base_dir=base_dir,
            raw_config=raw,
            secure_store=get_secure_store(raw),
            error_interpreter_path=base_dir / "config" / "error_interpreter.yaml",
        )
        summary = summarize_config_backup_payload(payload)
        return _outcome(
            assistant_text=(
                _chat_admin_text(
                    language,
                    "chat_admin.backup_export_ready",
                    secret_count=summary.get("secret_count", 0),
                    user_count=summary.get("user_count", 0),
                    recipe_count=summary.get("custom_skill_count", 0),
                    prompt_file_count=summary.get("prompt_file_count", 0),
                )
            ),
            icon="📦",
            intent_label="backup_export",
        )
    if request.backup_import_request:
        if not advanced_mode:
            return _outcome(
                assistant_text=_chat_admin_text(language, "chat_admin.backup_import_denied"),
                icon="⚠",
                intent_label="backup_denied",
            )
        return _outcome(
            assistant_text=(
                _chat_admin_text(language, "chat_admin.backup_import_page")
            ),
            icon="♻️",
            intent_label="backup_import",
        )
    if request.stats_request:
        return _outcome(
            assistant_text=_chat_admin_text(language, "chat_admin.stats_page"),
            icon="📊",
            intent_label="stats",
        )
    if request.activities_request:
        return _outcome(
            assistant_text=_chat_admin_text(language, "chat_admin.activities_page"),
            icon="🧾",
            intent_label="activities",
        )
    return None


def handle_chat_admin_flow(
    *,
    request: ChatAdminRequests,
    pending: ChatAdminPendingState,
    username: str,
    auth_role: str,
    advanced_mode: bool,
    base_dir: Path,
    signing_secret: str,
    sanitize_username: SanitizeUsername,
    sanitize_connection_name: SanitizeConnectionName,
    list_connection_refs: ListConnectionRefs,
    resolve_connection_target: ResolveConnectionTarget,
    delete_connection_profile: DeleteConnectionProfile,
    create_connection_profile: CreateConnectionProfile,
    update_connection_profile: UpdateConnectionProfile,
    reload_runtime: ReloadRuntime,
    resolve_update_helper_config: ResolveUpdateHelperConfig,
    trigger_update_helper_run: TriggerUpdateHelperRun,
    fetch_update_helper_status: FetchUpdateHelperStatus,
    helper_status_visual: HelperStatusVisual,
    get_secure_store: GetSecureStore,
    build_config_backup_payload: BuildConfigBackupPayload,
    summarize_config_backup_payload: SummarizeConfigBackupPayload,
    read_raw_config: ReadRawConfig,
    language: str | None = None,
) -> ChatAdminOutcome | None:
    handlers = (
        lambda: _handle_connection_delete_flow(
            request=request,
            pending=pending,
            username=username,
            auth_role=auth_role,
            base_dir=base_dir,
            signing_secret=signing_secret,
            sanitize_username=sanitize_username,
            sanitize_connection_name=sanitize_connection_name,
            list_connection_refs=list_connection_refs,
            resolve_connection_target=resolve_connection_target,
            delete_connection_profile=delete_connection_profile,
            reload_runtime=reload_runtime,
            language=language,
        ),
        lambda: _handle_connection_create_flow(
            request=request,
            pending=pending,
            username=username,
            auth_role=auth_role,
            signing_secret=signing_secret,
            sanitize_username=sanitize_username,
            create_connection_profile=create_connection_profile,
            reload_runtime=reload_runtime,
            base_dir=base_dir,
            language=language,
        ),
        lambda: _handle_connection_update_flow(
            request=request,
            pending=pending,
            username=username,
            auth_role=auth_role,
            signing_secret=signing_secret,
            sanitize_username=sanitize_username,
            update_connection_profile=update_connection_profile,
            reload_runtime=reload_runtime,
            base_dir=base_dir,
            language=language,
        ),
        lambda: _handle_update_flow(
            request=request,
            pending=pending,
            username=username,
            auth_role=auth_role,
            signing_secret=signing_secret,
            sanitize_username=sanitize_username,
            resolve_update_helper_config=resolve_update_helper_config,
            trigger_update_helper_run=trigger_update_helper_run,
            fetch_update_helper_status=fetch_update_helper_status,
            helper_status_visual=helper_status_visual,
            get_secure_store=get_secure_store,
            language=language,
        ),
        lambda: _handle_info_pages_flow(
            request=request,
            advanced_mode=advanced_mode,
            base_dir=base_dir,
            read_raw_config=read_raw_config,
            build_config_backup_payload=build_config_backup_payload,
            summarize_config_backup_payload=summarize_config_backup_payload,
            get_secure_store=get_secure_store,
            language=language,
        ),
    )
    for handler in handlers:
        outcome = handler()
        if outcome is not None and outcome.handled:
            return outcome
    return None
