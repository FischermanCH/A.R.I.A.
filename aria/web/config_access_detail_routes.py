from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import yaml
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from aria.core.i18n import I18NStore
from aria.core.guardrails import (
    GUARDRAIL_CATALOG,
    evaluate_guardrail,
    guardrail_is_compatible,
    guardrail_kind_label,
    guardrail_kind_options,
    normalize_guardrail_connection_kinds,
    normalize_guardrail_kind,
)
from aria.core.guardrail_drafts import (
    build_guardrail_draft_context,
    guardrail_connection_kind_options,
    suggest_guardrail_with_llm,
)
from aria.core.runtime_endpoint import cookie_should_be_secure


SettingsGetter = Callable[[], Any]
PipelineGetter = Callable[[], Any]
AuthManagerGetter = Callable[[], Any | None]
AuthSessionResolver = Callable[[Request], dict[str, Any] | None]
StringSanitizer = Callable[[str | None], str]
RoleSanitizer = Callable[[str | None], str]
ConfigPageContextBuilder = Callable[..., dict[str, Any]]
ConfigRedirector = Callable[..., RedirectResponse]
FriendlyRouteError = Callable[[str, Exception, str, str], str]
LocalizedMessage = Callable[[str, str, str], str]
RawConfigReader = Callable[[], dict[str, Any]]
RawConfigWriter = Callable[[dict[str, Any]], None]
RuntimeReloader = Callable[[], None]
ActiveAdminCounter = Callable[[list[dict[str, Any]]], int]
GuardrailReader = Callable[[], dict[str, dict[str, Any]]]
GuardrailOptionBuilder = Callable[[dict[str, dict[str, Any]]], list[dict[str, str]]]
SampleGuardrailRowsBuilder = Callable[[], list[dict[str, str]]]
SampleGuardrailImporter = Callable[[str], tuple[int, int]]
GuardrailTermSplitter = Callable[[str], list[str]]
SessionTimeoutLabelFormatter = Callable[[int, str], str]
DefaultCollectionResolver = Callable[[str], str]
AuthEncoder = Callable[[str, str], str]
IntGetter = Callable[[], int]
CookieNameResolver = Callable[[Request, str, str], str]
CookieScopeResolver = Callable[[Request], str]
_CONFIG_ACCESS_I18N = I18NStore(Path(__file__).resolve().parents[1] / "i18n")


def _config_access_text(lang: str | None, key: str, default: str = "", **values: object) -> str:
    template = _CONFIG_ACCESS_I18N.t(lang or "de", f"config_access_detail_routes.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template


@dataclass(frozen=True)
class ConfigAccessDetailRouteDeps:
    templates: Jinja2Templates
    auth_cookie: str
    username_cookie: str
    memory_collection_cookie: str
    get_settings: SettingsGetter
    get_pipeline: PipelineGetter
    get_auth_manager: AuthManagerGetter
    get_auth_session_from_request: AuthSessionResolver
    sanitize_username: StringSanitizer
    sanitize_role: RoleSanitizer
    sanitize_connection_name: StringSanitizer
    build_config_page_context: ConfigPageContextBuilder
    redirect_with_return_to: ConfigRedirector
    friendly_route_error: FriendlyRouteError
    msg: LocalizedMessage
    read_raw_config: RawConfigReader
    write_raw_config: RawConfigWriter
    reload_runtime: RuntimeReloader
    active_admin_count: ActiveAdminCounter
    read_guardrails: GuardrailReader
    build_guardrail_ref_options: GuardrailOptionBuilder
    build_sample_guardrail_rows: SampleGuardrailRowsBuilder
    import_sample_guardrail_manifest: SampleGuardrailImporter
    split_guardrail_terms: GuardrailTermSplitter
    format_session_timeout_label: SessionTimeoutLabelFormatter
    default_memory_collection_for_user: DefaultCollectionResolver
    encode_auth_session: AuthEncoder
    get_auth_session_max_age_seconds: IntGetter
    cookie_name_for_request: CookieNameResolver
    cookie_scope_for_request: CookieScopeResolver


def register_config_access_detail_routes(app: FastAPI, deps: ConfigAccessDetailRouteDeps) -> None:
    def _security_page_context(
        request: Request,
        *,
        saved: int = 0,
        error: str = "",
        info: str = "",
        guardrail_ref: str = "",
        guardrail_draft: dict[str, Any] | None = None,
        guardrail_draft_instruction: str = "",
        guardrail_draft_kind: str = "ssh_command",
        guardrail_draft_connection_kind: str = "",
        guardrail_test_result: dict[str, Any] | None = None,
        guardrail_test_ref: str = "",
        guardrail_test_kind: str = "ssh_command",
        guardrail_test_text: str = "",
    ) -> dict[str, Any]:
        lang = str(getattr(request.state, "lang", "de") or "de")
        settings = deps.get_settings()
        guardrail_rows = deps.read_guardrails()
        guardrail_refs = sorted(guardrail_rows.keys())
        selected_guardrail_ref = deps.sanitize_connection_name(guardrail_ref) or (guardrail_refs[0] if guardrail_refs else "")
        selected_guardrail = guardrail_rows.get(selected_guardrail_ref, {})
        timeout_minutes = max(5, int(getattr(settings.security, "session_max_age_seconds", 60 * 60 * 12) or 0) // 60)
        context = deps.build_config_page_context(
            request,
            saved=saved,
            error=error,
            logical_back_fallback="/config/access",
            page_return_to="/config/access",
            config_nav="access",
            page_heading=deps.msg(lang, "Security Guardrails", "Security guardrails"),
            info=info,
        )
        context.update(
            {
                "security_cfg": settings.security,
                "security_session_timeout_minutes": timeout_minutes,
                "security_session_timeout_display": deps.format_session_timeout_label(timeout_minutes, lang=lang),
                "guardrail_refs": guardrail_refs,
                "guardrail_ref_options": deps.build_guardrail_ref_options(guardrail_rows)[1:],
                "selected_guardrail_ref": selected_guardrail_ref,
                "selected_guardrail": selected_guardrail,
                "guardrail_kind_options": [{"value": kind, "label": guardrail_kind_label(kind)} for kind in guardrail_kind_options()],
                "guardrail_connection_kind_options": guardrail_connection_kind_options(),
                "guardrail_compatibility_rows": [
                    {
                        "kind": kind,
                        "label": guardrail_kind_label(kind),
                        "connections": ", ".join(sorted(GUARDRAIL_CATALOG.get(kind, {}).get("connection_kinds", set()))),
                    }
                    for kind in guardrail_kind_options()
                ],
                "guardrail_draft": guardrail_draft or {},
                "guardrail_draft_instruction": guardrail_draft_instruction,
                "guardrail_draft_kind": normalize_guardrail_kind(guardrail_draft_kind or "ssh_command"),
                "guardrail_draft_connection_kind": str(guardrail_draft_connection_kind or "").strip().lower().replace("-", "_"),
                "guardrail_test_result": guardrail_test_result or {},
                "guardrail_test_ref": deps.sanitize_connection_name(guardrail_test_ref) or selected_guardrail_ref,
                "guardrail_test_kind": normalize_guardrail_kind(guardrail_test_kind or (selected_guardrail.get("kind") if isinstance(selected_guardrail, dict) else "") or "ssh_command"),
                "guardrail_test_text": str(guardrail_test_text or ""),
                "sample_guardrail_rows": deps.build_sample_guardrail_rows(),
            }
        )
        return context

    def _guardrail_test_reason_label(reason: str, *, lang: str | None = None) -> str:
        clean = str(reason or "").strip()
        if clean == "guardrail_denied":
            return _config_access_text(lang, "guardrail_test_reason_denied", "Deny wording matched. The request would be blocked.")
        if clean == "guardrail_not_allowed":
            return _config_access_text(lang, "guardrail_test_reason_not_allowed", "Allow wording is set, but no allow term matched. The request would be blocked.")
        if clean.startswith("guardrail_kind_mismatch"):
            expected = clean.split(":", 1)[1] if ":" in clean else ""
            return _config_access_text(
                lang,
                "guardrail_test_reason_kind_mismatch",
                "Guardrail type mismatch. The selected profile is {expected}.",
                expected=expected or "unknown",
            )
        return _config_access_text(lang, "guardrail_test_reason_allowed", "No deny wording matched and allow wording permits this request.")

    async def _save_user_security_settings(
        request: Request,
        bootstrap_locked: str,
        session_timeout_minutes: int,
        return_to: str = "",
        *,
        target_path: str = "/config/users",
        error_de: str = "Benutzer- und Login-Einstellungen konnten nicht gespeichert werden.",
        error_en: str = "Could not save user and login settings.",
    ) -> RedirectResponse:
        try:
            active = str(bootstrap_locked).strip().lower() in {"1", "true", "on", "yes"}
            timeout_minutes = max(5, min(int(session_timeout_minutes or 0), 60 * 24 * 30))
            raw = deps.read_raw_config()
            raw.setdefault("security", {})
            if not isinstance(raw["security"], dict):
                raw["security"] = {}
            raw["security"]["bootstrap_locked"] = active
            raw["security"]["session_max_age_seconds"] = int(timeout_minutes * 60)
            deps.write_raw_config(raw)
            deps.reload_runtime()
            return deps.redirect_with_return_to(f"{target_path}?saved=1", request, fallback="/config", return_to=return_to)
        except (OSError, ValueError) as exc:
            lang = str(getattr(request.state, "lang", "de") or "de")
            error_msg = deps.friendly_route_error(lang, exc, error_de, error_en)
            return deps.redirect_with_return_to(
                f"{target_path}?error={quote_plus(error_msg)}",
                request,
                fallback="/config",
                return_to=return_to,
            )

    @app.get("/config/debug", response_class=HTMLResponse)
    async def config_debug_page(request: Request, saved: int = 0, error: str = "") -> HTMLResponse:
        _ = request, saved, error
        return deps.redirect_with_return_to("/config/users", request, fallback="/config")

    async def _config_debug_save(request: Request, debug_mode: str = Form("0"), return_to: str = Form("")) -> RedirectResponse:
        try:
            lang = str(getattr(request.state, "lang", "de") or "de")
            active = str(debug_mode).strip().lower() in {"1", "true", "on", "yes"}
            raw = deps.read_raw_config()
            raw.setdefault("ui", {})
            if not isinstance(raw["ui"], dict):
                raw["ui"] = {}
            raw["ui"]["debug_mode"] = active
            deps.write_raw_config(raw)
            deps.reload_runtime()
            info = (
                "Admin-Modus aktiviert. Erweiterte Systembereiche sind jetzt sichtbar."
                if active and lang.startswith("de")
                else "Admin mode enabled. Advanced system areas are now visible."
                if active
                else "Admin-Modus deaktiviert. Erweiterte Systembereiche sind jetzt ausgeblendet."
                if lang.startswith("de")
                else "Admin mode disabled. Advanced system areas are now hidden."
            )
            return deps.redirect_with_return_to(
                f"/config/users?saved=1&info={quote_plus(info)}",
                request,
                fallback="/config",
                return_to=return_to,
            )
        except (OSError, ValueError) as exc:
            return deps.redirect_with_return_to(
                f"/config/users?error={quote_plus(str(exc))}",
                request,
                fallback="/config",
                return_to=return_to,
            )

    @app.post("/config/debug/save")
    async def config_debug_save(request: Request, debug_mode: str = Form("0"), return_to: str = Form("")) -> RedirectResponse:
        return await _config_debug_save(request, debug_mode=debug_mode, return_to=return_to)

    @app.post("/config/users/debug-save")
    async def config_users_debug_save(request: Request, debug_mode: str = Form("0"), return_to: str = Form("")) -> RedirectResponse:
        return await _config_debug_save(request, debug_mode=debug_mode, return_to=return_to)

    @app.get("/config/security", response_class=HTMLResponse)
    async def config_security_page(
        request: Request,
        saved: int = 0,
        error: str = "",
        info: str = "",
        guardrail_ref: str = "",
    ) -> HTMLResponse:
        context = _security_page_context(request, saved=saved, error=error, info=info, guardrail_ref=guardrail_ref)
        return deps.templates.TemplateResponse(request=request, name="config_security.html", context=context)

    @app.post("/config/security/guardrails/draft", response_class=HTMLResponse)
    async def config_security_guardrail_draft(
        request: Request,
        draft_instruction: str = Form(""),
        draft_kind: str = Form("ssh_command"),
        draft_connection_kind: str = Form(""),
        return_to: str = Form(""),
    ) -> HTMLResponse:
        _ = return_to
        lang = str(getattr(request.state, "lang", "de") or "de")
        clean_kind = normalize_guardrail_kind(draft_kind or "ssh_command")
        if clean_kind not in guardrail_kind_options():
            clean_kind = "ssh_command"
        clean_connection_kind = str(draft_connection_kind or "").strip().lower().replace("-", "_")
        try:
            raw = deps.read_raw_config()
            draft_context = build_guardrail_draft_context(raw, guardrail_kind=clean_kind, connection_kind=clean_connection_kind)
            session = deps.get_auth_session_from_request(request) or {}
            user_id = str(session.get("username", "") or "system")
            pipeline = deps.get_pipeline()
            draft = await suggest_guardrail_with_llm(
                llm_client=getattr(pipeline, "llm_client", None),
                instruction=draft_instruction,
                draft_context=draft_context,
                language=lang,
                user_id=user_id,
                request_id=str(getattr(request.state, "request_id", "") or ""),
            )
            if clean_connection_kind and not draft.get("connection_kinds"):
                draft["connection_kinds"] = [clean_connection_kind]
            context = _security_page_context(
                request,
                info=_config_access_text(lang, "guardrail_draft_ready", "Guardrail draft ready for review."),
                guardrail_draft=draft,
                guardrail_draft_instruction=draft_instruction,
                guardrail_draft_kind=clean_kind,
                guardrail_draft_connection_kind=clean_connection_kind,
            )
        except (OSError, ValueError) as exc:
            context = _security_page_context(
                request,
                error=deps.friendly_route_error(
                    lang,
                    exc,
                    _config_access_text(lang, "guardrail_draft_failed", "Could not create guardrail draft."),
                    "Could not create guardrail draft.",
                ),
                guardrail_draft_instruction=draft_instruction,
                guardrail_draft_kind=clean_kind,
                guardrail_draft_connection_kind=clean_connection_kind,
            )
        return deps.templates.TemplateResponse(request=request, name="config_security.html", context=context)

    @app.post("/config/security/guardrails/test", response_class=HTMLResponse)
    async def config_security_guardrail_test(
        request: Request,
        guardrail_ref: str = Form(""),
        kind: str = Form("ssh_command"),
        test_text: str = Form(""),
        return_to: str = Form(""),
    ) -> HTMLResponse:
        _ = return_to
        lang = str(getattr(request.state, "lang", "de") or "de")
        clean_ref = deps.sanitize_connection_name(guardrail_ref)
        clean_kind = normalize_guardrail_kind(kind or "ssh_command")
        if clean_kind not in guardrail_kind_options():
            clean_kind = "ssh_command"
        clean_text = str(test_text or "").strip()
        try:
            if not clean_ref:
                raise ValueError(_config_access_text(lang, "guardrail_test_missing_ref", "Choose a guardrail profile first."))
            if not clean_text:
                raise ValueError(_config_access_text(lang, "guardrail_test_missing_text", "Enter a request to test first."))
            rows = deps.read_guardrails()
            profile = rows.get(clean_ref)
            if not profile:
                raise ValueError(_config_access_text(lang, "guardrail_test_missing_profile", "Guardrail profile not found."))
            decision = evaluate_guardrail(profile_ref=clean_ref, profile=profile, kind=clean_kind, text=clean_text)
            action = "allow" if decision.allowed else "block"
            context = _security_page_context(
                request,
                guardrail_ref=clean_ref,
                guardrail_test_ref=clean_ref,
                guardrail_test_kind=clean_kind,
                guardrail_test_text=clean_text,
                guardrail_test_result={
                    "action": action,
                    "action_label": _config_access_text(lang, "guardrail_test_allow", "allow") if action == "allow" else _config_access_text(lang, "guardrail_test_block", "block"),
                    "reason": decision.reason or "guardrail_allowed",
                    "reason_label": _guardrail_test_reason_label(decision.reason, lang=lang),
                    "profile_ref": clean_ref,
                    "kind": decision.kind or clean_kind,
                },
            )
        except (OSError, ValueError) as exc:
            context = _security_page_context(
                request,
                error=deps.friendly_route_error(
                    lang,
                    exc,
                    _config_access_text(lang, "guardrail_test_failed", "Could not test guardrail."),
                    "Could not test guardrail.",
                ),
                guardrail_ref=clean_ref,
                guardrail_test_ref=clean_ref,
                guardrail_test_kind=clean_kind,
                guardrail_test_text=clean_text,
            )
        return deps.templates.TemplateResponse(request=request, name="config_security.html", context=context)

    @app.post("/config/security/save")
    async def config_security_save(
        request: Request,
        bootstrap_locked: str = Form("0"),
        session_timeout_minutes: int = Form(60 * 12 // 60),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        return await _save_user_security_settings(
            request,
            bootstrap_locked,
            session_timeout_minutes,
            return_to=return_to,
            target_path="/config/security",
            error_de="Security-Einstellungen konnten nicht gespeichert werden.",
            error_en="Could not save security settings.",
        )

    @app.post("/config/security/guardrails/save")
    async def config_security_guardrail_save(
        request: Request,
        guardrail_ref: str = Form(...),
        original_ref: str = Form(""),
        kind: str = Form("ssh_command"),
        connection_kinds: str = Form(""),
        title: str = Form(""),
        description: str = Form(""),
        allow_terms: str = Form(""),
        deny_terms: str = Form(""),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        try:
            raw = deps.read_raw_config()
            raw.setdefault("security", {})
            if not isinstance(raw["security"], dict):
                raw["security"] = {}
            raw["security"].setdefault("guardrails", {})
            if not isinstance(raw["security"]["guardrails"], dict):
                raw["security"]["guardrails"] = {}
            rows = raw["security"]["guardrails"]
            ref = deps.sanitize_connection_name(guardrail_ref)
            original_ref_clean = deps.sanitize_connection_name(original_ref)
            clean_kind = normalize_guardrail_kind(kind)
            if clean_kind not in guardrail_kind_options():
                raise ValueError("Unbekannter Guardrail-Typ.")
            if not ref:
                raise ValueError("Guardrail-Ref fehlt.")
            if ref != original_ref_clean and ref in rows:
                raise ValueError(f"Guardrail-Profil '{ref}' existiert bereits.")
            rows[ref] = {
                "kind": clean_kind,
                "connection_kinds": normalize_guardrail_connection_kinds(connection_kinds, guardrail_kind=clean_kind),
                "title": str(title).strip(),
                "description": str(description).strip(),
                "allow_terms": deps.split_guardrail_terms(allow_terms),
                "deny_terms": deps.split_guardrail_terms(deny_terms),
            }
            if original_ref_clean and original_ref_clean != ref:
                rows.pop(original_ref_clean, None)
            deps.write_raw_config(raw)
            deps.reload_runtime()
            return deps.redirect_with_return_to(
                f"/config/security?saved=1&guardrail_ref={quote_plus(ref)}",
                request,
                fallback="/config",
                return_to=return_to,
            )
        except (OSError, ValueError) as exc:
            lang = str(getattr(request.state, "lang", "de") or "de")
            error = deps.friendly_route_error(
                lang,
                exc,
                _config_access_text(lang, "guardrail_save_failed", "Could not save guardrail."),
                "Could not save guardrail.",
            )
            suffix = f"&guardrail_ref={quote_plus(deps.sanitize_connection_name(original_ref) or deps.sanitize_connection_name(guardrail_ref))}" if (original_ref or guardrail_ref) else ""
            return deps.redirect_with_return_to(
                f"/config/security?error={quote_plus(error)}{suffix}",
                request,
                fallback="/config",
                return_to=return_to,
            )

    @app.post("/config/security/guardrails/delete")
    async def config_security_guardrail_delete(
        request: Request,
        guardrail_ref: str = Form(...),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        try:
            ref = deps.sanitize_connection_name(guardrail_ref)
            if not ref:
                raise ValueError("Guardrail-Ref fehlt.")
            raw = deps.read_raw_config()
            raw.setdefault("security", {})
            if not isinstance(raw["security"], dict):
                raw["security"] = {}
            rows = raw["security"].get("guardrails", {})
            if not isinstance(rows, dict) or ref not in rows:
                raise ValueError("Guardrail-Profil nicht gefunden.")
            rows.pop(ref, None)
            connections = raw.get("connections", {})
            if isinstance(connections, dict):
                for connection_rows in connections.values():
                    if not isinstance(connection_rows, dict):
                        continue
                    for value in connection_rows.values():
                        if isinstance(value, dict) and str(value.get("guardrail_ref", "")).strip() == ref:
                            value["guardrail_ref"] = ""
            deps.write_raw_config(raw)
            deps.reload_runtime()
            return deps.redirect_with_return_to("/config/security?saved=1", request, fallback="/config", return_to=return_to)
        except (OSError, ValueError) as exc:
            lang = str(getattr(request.state, "lang", "de") or "de")
            error = deps.friendly_route_error(
                lang,
                exc,
                _config_access_text(lang, "guardrail_delete_failed", "Could not delete guardrail."),
                "Could not delete guardrail.",
            )
            return deps.redirect_with_return_to(
                f"/config/security?error={quote_plus(error)}",
                request,
                fallback="/config",
                return_to=return_to,
            )

    @app.post("/config/security/guardrails/import-sample")
    async def config_security_guardrail_import_sample(
        request: Request,
        sample_file: str = Form(""),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        if not bool(getattr(request.state, "can_access_advanced_config", False)):
            return RedirectResponse(url="/config?error=admin_mode_required", status_code=303)
        try:
            imported_count, skipped_count = deps.import_sample_guardrail_manifest(sample_file)
            info = quote_plus(f"guardrail_sample_imported:{imported_count}:{skipped_count}")
            return deps.redirect_with_return_to(
                f"/config/security?saved=1&info={info}",
                request,
                fallback="/config",
                return_to=return_to,
            )
        except (OSError, ValueError, yaml.YAMLError) as exc:
            return deps.redirect_with_return_to(
                f"/config/security?error={quote_plus(str(exc))}",
                request,
                fallback="/config",
                return_to=return_to,
            )

    @app.get("/config/users", response_class=HTMLResponse)
    async def config_users_page(
        request: Request,
        saved: int = 0,
        error: str = "",
        info: str = "",
    ) -> HTMLResponse:
        lang = str(getattr(request.state, "lang", "de") or "de")
        settings = deps.get_settings()
        manager = deps.get_auth_manager()
        users: list[dict[str, Any]] = []
        if manager:
            try:
                users = manager.store.list_users()
            except Exception as exc:
                error = error or str(exc)
        else:
            error = error or "Security Store nicht aktiv."
        timeout_minutes = max(5, int(getattr(settings.security, "session_max_age_seconds", 60 * 60 * 12) or 0) // 60)
        context = deps.build_config_page_context(
            request,
            saved=saved,
            error=error,
            info=info,
            logical_back_fallback="/config/access",
            page_return_to="/config/access",
            config_nav="access",
            page_heading=deps.msg(lang, "Team & Access", "Team & access"),
        )
        context.update(
            {
                "users": users,
                "debug_mode": bool(settings.ui.debug_mode),
                "security_cfg": settings.security,
                "security_session_timeout_minutes": timeout_minutes,
                "security_session_timeout_display": deps.format_session_timeout_label(timeout_minutes, lang=lang),
            }
        )
        return deps.templates.TemplateResponse(request=request, name="config_users.html", context=context)

    @app.post("/config/users/security-save")
    async def config_users_security_save(
        request: Request,
        bootstrap_locked: str = Form("0"),
        session_timeout_minutes: int = Form(60 * 60 * 12 // 60),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        return await _save_user_security_settings(request, bootstrap_locked, session_timeout_minutes, return_to=return_to)

    @app.post("/config/users/create")
    async def config_users_create(
        request: Request,
        create_username: str = Form(...),
        create_password: str = Form(...),
        create_role: str = Form("user"),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        manager = deps.get_auth_manager()
        if not manager:
            return deps.redirect_with_return_to("/config/users?error=Security+Store+nicht+aktiv", request, fallback="/config", return_to=return_to)
        try:
            clean_username = deps.sanitize_username(create_username)
            clean_role = deps.sanitize_role(create_role)
            if not clean_username:
                raise ValueError("Username darf nicht leer sein.")
            if manager.store.get_user(clean_username):
                raise ValueError("User existiert bereits.")
            manager.upsert_user(clean_username, create_password, role=clean_role)
            return deps.redirect_with_return_to("/config/users?saved=1&info=User+erstellt", request, fallback="/config", return_to=return_to)
        except ValueError as exc:
            return deps.redirect_with_return_to(
                f"/config/users?error={quote_plus(str(exc))}",
                request,
                fallback="/config",
                return_to=return_to,
            )

    @app.post("/config/users/update")
    async def config_users_update(
        request: Request,
        username_value: str = Form(...),
        new_username_value: str = Form(""),
        role_value: str = Form("user"),
        active_value: str = Form("0"),
        password_value: str = Form(""),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        manager = deps.get_auth_manager()
        if not manager:
            return deps.redirect_with_return_to("/config/users?error=Security+Store+nicht+aktiv", request, fallback="/config", return_to=return_to)
        try:
            settings = deps.get_settings()
            auth = deps.get_auth_session_from_request(request) or {}
            current_username = deps.sanitize_username(auth.get("username"))
            old_username = deps.sanitize_username(username_value)
            clean_username = deps.sanitize_username(new_username_value) or old_username
            clean_role = deps.sanitize_role(role_value)
            target_active = str(active_value).strip().lower() in {"1", "true", "on", "yes"}
            new_password = str(password_value).strip()

            if not old_username or not clean_username:
                raise ValueError("Username darf nicht leer sein.")

            before = manager.store.get_user(old_username)
            if not before:
                raise ValueError("User nicht gefunden.")
            if clean_username != old_username and manager.store.get_user(clean_username):
                raise ValueError("Ziel-Username existiert bereits.")

            before_role = deps.sanitize_role(before.get("role"))
            before_active = bool(before.get("active"))
            if old_username == current_username and (clean_role != "admin" or not target_active):
                raise ValueError("Aktueller Admin darf sich nicht selbst deaktivieren oder degradieren.")

            users = manager.store.list_users()
            active_admins = deps.active_admin_count(users)
            removing_last_admin = (
                before_role == "admin"
                and before_active
                and active_admins <= 1
                and (clean_role != "admin" or not target_active)
            )
            if removing_last_admin:
                raise ValueError("Mindestens ein aktiver Admin muss erhalten bleiben.")

            if clean_username != old_username:
                manager.store.rename_user(old_username=old_username, new_username=clean_username)

            if new_password:
                manager.upsert_user(clean_username, new_password, role=clean_role)
            else:
                manager.store.set_user_role(clean_username, clean_role)

            manager.store.set_user_active(clean_username, target_active)
            response = deps.redirect_with_return_to("/config/users?saved=1&info=User+aktualisiert", request, fallback="/config", return_to=return_to)
            if old_username == current_username:
                secure_cookie = cookie_should_be_secure(request, public_url=str(settings.aria.public_url or ""))
                response.set_cookie(
                    key=deps.cookie_name_for_request(request, "auth", deps.auth_cookie),
                    value=deps.encode_auth_session(clean_username, clean_role, scope=deps.cookie_scope_for_request(request)),
                    max_age=deps.get_auth_session_max_age_seconds(),
                    samesite="lax",
                    secure=secure_cookie,
                    httponly=True,
                )
                response.set_cookie(
                    key=deps.cookie_name_for_request(request, "username", deps.username_cookie),
                    value=clean_username,
                    max_age=60 * 60 * 24 * 365,
                    samesite="lax",
                    secure=secure_cookie,
                    httponly=False,
                )
                response.set_cookie(
                    key=deps.cookie_name_for_request(request, "memory_collection", deps.memory_collection_cookie),
                    value=deps.default_memory_collection_for_user(clean_username),
                    max_age=60 * 60 * 24 * 365,
                    samesite="lax",
                    secure=secure_cookie,
                    httponly=False,
                )
            return response
        except ValueError as exc:
            return deps.redirect_with_return_to(
                f"/config/users?error={quote_plus(str(exc))}",
                request,
                fallback="/config",
                return_to=return_to,
            )
