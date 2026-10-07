from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urlparse

import yaml
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from aria.modules.platform_primitives.i18n import I18NStore
from aria.modules.model_usage_observability.llm_audit import GLOBAL_LLM_AUDIT_LOG
from aria.modules import module_route_path, module_template_name
from aria.modules.native_web_llm.contracts import NativeWebRequest
from aria.modules.native_web_llm.gateway import NativeWebLLMError
from aria.modules.native_web_llm.source_policy import resolve_native_web_source_policy


BASE_DIR = Path(__file__).resolve().parents[3]
_CONFIG_WORKBENCH_I18N = I18NStore(BASE_DIR / "aria" / "i18n")


def _request_lang(request: Request) -> str:
    return str(getattr(request.state, "lang", "de") or "de")


def _workbench_text(lang: str | None, key: str, default: str = "", **values: Any) -> str:
    template = _CONFIG_WORKBENCH_I18N.t(lang or "de", f"config_workbench.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template


def _optional_temperature(value: object, *, default: float | None = 0.4) -> float | None:
    candidate = default if value is ... else value
    if candidate is None or not str(candidate).strip():
        return None
    return float(candidate)


def _config_ui_template(template_name: str) -> str:
    resolved = module_template_name("config_ui", template_name)
    if resolved is None:
        raise RuntimeError(f"config_ui template is not registered: {template_name}")
    return resolved


def _config_ui_path(route_path: str) -> str:
    resolved = module_route_path("config_ui", route_path)
    if resolved is None:
        raise RuntimeError(f"config_ui route is not registered: {route_path}")
    return resolved


SettingsGetter = Callable[[], Any]
PipelineGetter = Callable[[], Any]
UsernameResolver = Callable[[Request], str]
StringSanitizer = Callable[[str | None], str]
ModelChecker = Callable[[str], bool]
ConfigPageContextBuilder = Callable[..., dict[str, Any]]
ConfigRedirector = Callable[..., RedirectResponse]
FriendlyRouteError = Callable[[str, Exception, str, str], str]
LocalizedMessage = Callable[[str, str, str], str]
RawConfigReader = Callable[[], dict[str, Any]]
RawConfigWriter = Callable[[dict[str, Any]], None]
RuntimeReloader = Callable[[], None]
ProfilesGetter = Callable[[dict[str, Any], str], dict[str, dict[str, Any]]]
ActiveProfileGetter = Callable[[dict[str, Any], str], str]
ActiveProfileSetter = Callable[[dict[str, Any], str, str], None]
SecureStoreGetter = Callable[[dict[str, Any] | None], Any]
ModelLoader = Callable[[str, str], list[str]]
BackUrlSetter = Callable[[Request], str]
ConfigSurfacePath = Callable[[str | None, str], str]
ConfigInfoFormatter = Callable[[str, str], str]
ActiveProfileMetaBuilder = Callable[[dict[str, Any], str], dict[str, str]]
EmbeddingGuard = Callable[..., Awaitable[tuple[str, str]]]
ProfileTestRedirectBuilder = Callable[..., str]
ProfileTestMessageBuilder = Callable[[str, str, dict[str, Any], str], str]
ProbeRunner = Callable[..., Awaitable[dict[str, Any]]]
FileEditorEntryLister = Callable[[], list[dict[str, Any]]]
FileResolver = Callable[[str], Path]
EditorEntriesBuilder = Callable[[Path, list[str], FileResolver], list[dict[str, Any]]]
TextReader = Callable[[], str]
TextFileSaver = Callable[[Path, str], tuple[bool, str]]
EmbeddingGuardContextGetter = Callable[[str], Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class ConfigIntelligenceWorkbenchRouteDeps:
    templates: Jinja2Templates
    base_dir: Path
    error_interpreter_path: Path
    llm_provider_presets: dict[str, dict[str, str]]
    embedding_provider_presets: dict[str, dict[str, str]]
    get_settings: SettingsGetter
    get_pipeline: PipelineGetter
    get_username_from_request: UsernameResolver
    sanitize_profile_name: StringSanitizer
    is_ollama_model: ModelChecker
    build_config_page_context: ConfigPageContextBuilder
    redirect_with_return_to: ConfigRedirector
    friendly_route_error: FriendlyRouteError
    msg: LocalizedMessage
    read_raw_config: RawConfigReader
    write_raw_config: RawConfigWriter
    reload_runtime: RuntimeReloader
    get_profiles: ProfilesGetter
    get_active_profile_name: ActiveProfileGetter
    set_active_profile: ActiveProfileSetter
    get_secure_store: SecureStoreGetter
    load_models_from_api_base: ModelLoader
    set_logical_back_url: BackUrlSetter
    config_surface_path: ConfigSurfacePath
    format_config_info_message: ConfigInfoFormatter
    active_profile_runtime_meta: ActiveProfileMetaBuilder
    embedding_memory_guard_context: EmbeddingGuardContextGetter
    guard_embedding_switch: EmbeddingGuard
    profile_test_redirect_url: ProfileTestRedirectBuilder
    profile_test_result_message: ProfileTestMessageBuilder
    probe_llm: ProbeRunner
    probe_embeddings: ProbeRunner
    list_file_editor_entries: FileEditorEntryLister
    resolve_edit_file: FileResolver
    resolve_file_editor_file: FileResolver
    build_editor_entries_from_paths: EditorEntriesBuilder
    read_error_interpreter_raw: TextReader
    save_text_file_and_maybe_reload: TextFileSaver


def register_config_intelligence_workbench_routes(app: FastAPI, deps: ConfigIntelligenceWorkbenchRouteDeps) -> None:
    @app.get("/config/llm/debug", response_class=HTMLResponse)
    async def config_llm_debug_page(request: Request, limit: int = 30) -> HTMLResponse:
        settings = deps.get_settings()
        deps.set_logical_back_url(request)
        username = deps.get_username_from_request(request)
        lang = _request_lang(request)
        return deps.templates.TemplateResponse(
            request=request,
            name=_config_ui_template("config_llm_debug.html"),
            context={
                "title": settings.ui.title,
                "username": username,
                "config_nav": "admin",
                "config_page_heading": deps.msg(lang, "LLM Prompt Debug", "LLM Prompt Debug"),
                "page_return_to": deps.config_surface_path(
                    deps.set_logical_back_url(request),
                    fallback=_config_ui_path("/config"),
                ),
                "show_overview_checks": False,
                "entries": GLOBAL_LLM_AUDIT_LOG.entries(limit=limit),
                "limit": max(1, int(limit or 30)),
            },
        )

    @app.post("/config/llm/debug/clear")
    async def config_llm_debug_clear(request: Request) -> RedirectResponse:
        GLOBAL_LLM_AUDIT_LOG.clear()
        return deps.redirect_with_return_to(
            _config_ui_path("/config/llm/debug"),
            request,
            fallback=_config_ui_path("/config"),
        )

    @app.get("/config/llm", response_class=HTMLResponse)
    async def config_llm_page(
        request: Request,
        saved: int = 0,
        error: str = "",
        info: str = "",
        test_status: str = "",
        edit_profile: str = "",
    ) -> HTMLResponse:
        settings = deps.get_settings()
        deps.set_logical_back_url(request)
        username = deps.get_username_from_request(request)
        raw = deps.read_raw_config()
        llm_profiles = deps.get_profiles(raw, "llm")
        if not llm_profiles:
            llm_profiles = {
                "default": {
                    "model": settings.llm.model,
                    "api_base": settings.llm.api_base or "",
                    "api_key": settings.llm.api_key or "",
                    "temperature": settings.llm.temperature,
                    "max_tokens": settings.llm.max_tokens,
                    "timeout_seconds": settings.llm.timeout_seconds,
                }
            }
        active_llm_profile = deps.get_active_profile_name(raw, "llm") or "default"
        active_roles = raw.get("profiles", {}).get("active", {}) if isinstance(raw.get("profiles"), dict) else {}
        if not isinstance(active_roles, dict):
            active_roles = {}
        main_llm_profile = str(active_roles.get("main_llm") or active_llm_profile).strip() or active_llm_profile
        web_llm_profile = str(active_roles.get("web_llm") or getattr(settings.web_llm, "profile", "") or "").strip()
        requested_edit_profile = deps.sanitize_profile_name(edit_profile)
        edit_llm_profile = requested_edit_profile if requested_edit_profile in llm_profiles else active_llm_profile
        if edit_llm_profile not in llm_profiles:
            edit_llm_profile = sorted(llm_profiles.keys())[0]
        edit_row = dict(llm_profiles[edit_llm_profile])
        edit_api_key = str(edit_row.get("api_key", "") or "")
        store = deps.get_secure_store(raw)
        if store:
            edit_api_key = store.get_secret(f"profiles.llm.{edit_llm_profile}.api_key", default=edit_api_key)
        edit_llm = {
            "model": str(edit_row.get("model", "") or ""),
            "api_base": str(edit_row.get("api_base", "") or ""),
            "api_key": edit_api_key,
            "temperature": _optional_temperature(edit_row.get("temperature", ...)),
            "max_tokens": int(edit_row.get("max_tokens", 4096) or 4096),
            "timeout_seconds": int(edit_row.get("timeout_seconds", 60) or 60),
        }
        profile_rows = [
            {
                "name": name,
                "model": str(row.get("model", "") or ""),
                "api_base": str(row.get("api_base", "") or ""),
                "is_main": name == main_llm_profile,
                "is_web": name == web_llm_profile,
                "is_assigned": name in {main_llm_profile, web_llm_profile},
            }
            for name, row in sorted(llm_profiles.items())
        ]
        main_row = llm_profiles.get(main_llm_profile, {})
        providers = [
            {
                "key": key,
                "label": data["label"],
                "default_model": data["default_model"],
                "default_api_base": data["default_api_base"],
            }
            for key, data in deps.llm_provider_presets.items()
        ]
        lang = _request_lang(request)
        return deps.templates.TemplateResponse(
            request=request,
            name=_config_ui_template("config_llm.html"),
            context={
                "title": settings.ui.title,
                "username": username,
                "saved": bool(saved),
                "error_message": error,
                "info_message": deps.format_config_info_message(lang, info),
                "test_status": str(test_status or "").strip().lower(),
                "config_nav": "intelligence",
                "config_page_heading": deps.msg(lang, "KI-Modelle", "AI models"),
                "page_return_to": deps.config_surface_path(
                    deps.set_logical_back_url(request),
                    fallback=_config_ui_path("/config/intelligence"),
                ),
                "show_overview_checks": False,
                "llm": edit_llm,
                "providers": providers,
                "llm_profiles": sorted(llm_profiles.keys()),
                "active_llm_profile": active_llm_profile,
                "edit_llm_profile": edit_llm_profile,
                "profile_rows": profile_rows,
                "main_llm_profile": main_llm_profile,
                "web_llm_profile": web_llm_profile,
                "main_llm_runtime": {
                    "profile": main_llm_profile,
                    "model": str(getattr(settings.llm, "model", "") or main_row.get("model", "") or ""),
                    "api_base": str(getattr(settings.llm, "api_base", "") or main_row.get("api_base", "") or ""),
                },
                "web_llm_runtime": {
                    "profile": web_llm_profile,
                    "model": str(getattr(settings.web_llm, "model", "") or ""),
                    "api_base": str(getattr(settings.web_llm, "api_base", "") or ""),
                },
                "web_llm": settings.web_llm,
            },
        )

    @app.post("/config/llm/roles")
    async def config_llm_roles_save(
        request: Request,
        main_profile: str = Form(...),
        web_profile: str = Form(""),
        web_transport: str = Form("openai_responses"),
    ) -> RedirectResponse:
        lang = _request_lang(request)
        try:
            raw = deps.read_raw_config()
            profiles = deps.get_profiles(raw, "llm")
            main_name = deps.sanitize_profile_name(main_profile)
            web_name = deps.sanitize_profile_name(web_profile) if web_profile else ""
            if not main_name or main_name not in profiles:
                raise ValueError(_workbench_text(lang, "main_llm_profile_not_found", "Main-model profile not found."))
            if web_name and web_name not in profiles:
                raise ValueError(_workbench_text(lang, "web_llm_profile_not_found", "Web-model profile not found."))
            if web_transport not in {"openai_responses", "anthropic_native", "openai_web_search_options"}:
                raise ValueError(_workbench_text(lang, "web_llm_transport_unsupported", "Unsupported Web-model transport."))

            raw.setdefault("profiles", {})
            raw["profiles"].setdefault("active", {})
            raw["profiles"]["active"]["llm"] = main_name
            raw["profiles"]["active"]["main_llm"] = main_name
            raw["profiles"]["active"]["web_llm"] = web_name
            main_row = profiles[main_name]
            raw.setdefault("llm", {})
            for key in ("model", "api_base", "temperature", "max_tokens", "timeout_seconds"):
                if key in main_row:
                    raw["llm"][key] = main_row[key]
            raw["llm"]["api_key"] = ""

            previous_web = str(raw.get("web_llm", {}).get("profile", "") or "") if isinstance(raw.get("web_llm"), dict) else ""
            raw.setdefault("web_llm", {})
            raw["web_llm"].update(
                {
                    "profile": web_name,
                    "transport": web_transport,
                    "max_search_uses": 3,
                    "search_context_size": "low",
                    "enabled": bool(web_name and previous_web == web_name and raw["web_llm"].get("capability_verified_at")),
                }
            )
            if previous_web != web_name:
                raw["web_llm"]["capability_verified_at"] = ""
                raw["web_llm"].pop("capability_receipt", None)

            store = deps.get_secure_store(raw)
            if store:
                main_key = store.get_secret(f"profiles.llm.{main_name}.api_key", default="")
                if main_key:
                    store.set_secret("llm.api_key", main_key)
            deps.write_raw_config(raw)
            deps.reload_runtime()
            return deps.redirect_with_return_to(
                f"{_config_ui_path('/config/llm')}?saved=1",
                request,
                fallback=_config_ui_path("/config"),
            )
        except (OSError, ValueError) as exc:
            return deps.redirect_with_return_to(
                f"{_config_ui_path('/config/llm')}?error={quote_plus(str(exc))}",
                request,
                fallback=_config_ui_path("/config"),
            )

    @app.post("/config/llm/web/test")
    async def config_web_llm_test(request: Request, confirm_paid: str = Form("")) -> RedirectResponse:
        lang = _request_lang(request)
        if str(confirm_paid or "").strip().lower() not in {"1", "true", "yes", "on"}:
            message = _workbench_text(lang, "web_llm_test_unconfirmed", "Paid Web search test was not confirmed.")
            return deps.redirect_with_return_to(
                deps.profile_test_redirect_url(_config_ui_path("/config/llm"), ok=False, message=message),
                request,
                fallback=_config_ui_path("/config"),
            )
        settings = deps.get_settings()
        pipeline = deps.get_pipeline()
        gateway = getattr(pipeline, "web_llm_gateway", None)
        if gateway is None or not settings.web_llm.profile:
            message = _workbench_text(lang, "web_llm_profile_required", "Assign and save a Web-model profile first.")
            return deps.redirect_with_return_to(
                deps.profile_test_redirect_url(_config_ui_path("/config/llm"), ok=False, message=message),
                request,
                fallback=_config_ui_path("/config"),
            )
        question = "Welches ist die neueste stabile Version von n8n?"
        policy = resolve_native_web_source_policy(question)
        try:
            result = await gateway.answer(
                NativeWebRequest(
                    question=question,
                    language=_request_lang(request),
                    current_date=datetime.now(timezone.utc).date().isoformat(),
                    allowed_domains=policy.allowed_domains,
                    required_url_prefixes=policy.required_url_prefixes,
                    authority_mode=policy.authority_mode,
                    max_search_uses=3,
                ),
                source="config_web_llm_test",
                operation="native_web_capability_test",
                user_id=deps.get_username_from_request(request),
            )
        except NativeWebLLMError as exc:
            message = _workbench_text(
                lang,
                "web_llm_test_provider_failed",
                "Web search test failed: {error}.",
                error=str(exc).split(":", 1)[0],
            )
            return deps.redirect_with_return_to(
                deps.profile_test_redirect_url(_config_ui_path("/config/llm"), ok=False, message=message),
                request,
                fallback=_config_ui_path("/config"),
            )
        if result.passed:
            raw = deps.read_raw_config()
            raw.setdefault("web_llm", {})
            verified_at = datetime.now(timezone.utc).isoformat()
            raw["web_llm"]["enabled"] = True
            raw["web_llm"]["capability_verified_at"] = verified_at
            raw["web_llm"]["capability_receipt"] = {
                "model": result.model,
                "transport": settings.web_llm.transport,
                "verified_at": verified_at,
                "native_search_uses": result.native_search_uses,
                "citation_count": len(result.citations),
                "duration_ms": result.duration_ms,
            }
            deps.write_raw_config(raw)
            deps.reload_runtime()
        message = _workbench_text(
            lang,
            "web_llm_test_passed" if result.passed else "web_llm_test_failed",
            "Web search test passed: {searches} searches, {citations} citations, {duration_ms} ms."
            if result.passed
            else "Web search test failed: {searches} searches, {citations} citations, {duration_ms} ms.",
            searches=result.native_search_uses,
            citations=len(result.citations),
            duration_ms=result.duration_ms,
        )
        return deps.redirect_with_return_to(
            deps.profile_test_redirect_url(_config_ui_path("/config/llm"), ok=result.passed, message=message),
            request,
            fallback=_config_ui_path("/config"),
        )

    @app.post("/config/llm/profile/load")
    async def config_llm_profile_load(request: Request, profile_name: str = Form(...)) -> RedirectResponse:
        lang = _request_lang(request)
        try:
            raw = deps.read_raw_config()
            name = deps.sanitize_profile_name(profile_name)
            if not name:
                raise ValueError(_workbench_text(lang, "invalid_profile_name", "Invalid profile name."))
            llm_profiles = deps.get_profiles(raw, "llm")
            profile = llm_profiles.get(name)
            if not profile:
                raise ValueError(_workbench_text(lang, "llm_profile_not_found", "LLM profile not found."))

            raw.setdefault("llm", {})
            raw["llm"]["model"] = str(profile.get("model", "")).strip()
            raw["llm"]["api_base"] = str(profile.get("api_base", "")).strip() or None
            store = deps.get_secure_store(raw)
            profile_api_key = str(profile.get("api_key", "")).strip()
            if store:
                profile_api_key = store.get_secret(f"profiles.llm.{name}.api_key", default=profile_api_key)
            raw["llm"]["api_key"] = profile_api_key
            raw["llm"]["temperature"] = _optional_temperature(profile.get("temperature", ...))
            raw["llm"]["max_tokens"] = int(profile.get("max_tokens", 4096))
            raw["llm"]["timeout_seconds"] = int(profile.get("timeout_seconds", 60))
            if store and profile_api_key:
                store.set_secret("llm.api_key", profile_api_key)
                raw["llm"]["api_key"] = ""
            deps.set_active_profile(raw, "llm", name)
            deps.write_raw_config(raw)
            deps.reload_runtime()
            return deps.redirect_with_return_to(
                f"{_config_ui_path('/config/llm')}?saved=1",
                request,
                fallback=_config_ui_path("/config"),
            )
        except (OSError, ValueError) as exc:
            return deps.redirect_with_return_to(
                f"{_config_ui_path('/config/llm')}?error={quote_plus(str(exc))}",
                request,
                fallback=_config_ui_path("/config"),
            )

    @app.post("/config/llm/profile/save")
    async def config_llm_profile_save(
        request: Request,
        profile_name: str = Form(...),
        model: str = Form(...),
        api_base: str = Form(""),
        api_key: str = Form(""),
        temperature: str = Form(""),
        max_tokens: int = Form(...),
        timeout_seconds: int = Form(...),
        activate_main: str = Form("1"),
    ) -> RedirectResponse:
        lang = _request_lang(request)
        try:
            name = deps.sanitize_profile_name(profile_name)
            if not name:
                raise ValueError(_workbench_text(lang, "invalid_profile_name", "Invalid profile name."))

            cleaned_model = model.strip()
            cleaned_api_key = api_key.strip()
            if not cleaned_model:
                raise ValueError(_workbench_text(lang, "llm_model_required", "Model must not be empty."))
            if "<modellname>" in cleaned_model.lower():
                raise ValueError(_workbench_text(lang, "llm_model_placeholder", "Please enter a concrete model instead of the placeholder."))
            if not deps.is_ollama_model(cleaned_model) and not cleaned_api_key:
                raise ValueError(_workbench_text(lang, "llm_api_key_required", "API key is required for non-Ollama models."))
            parsed_temperature = _optional_temperature(temperature, default=None)
            if parsed_temperature is not None and (parsed_temperature < 0 or parsed_temperature > 2):
                raise ValueError(_workbench_text(lang, "temperature_range", "temperature must be between 0 and 2."))
            if max_tokens <= 0:
                raise ValueError(_workbench_text(lang, "max_tokens_positive", "max_tokens must be greater than 0."))
            if timeout_seconds <= 0:
                raise ValueError(_workbench_text(lang, "timeout_seconds_positive", "timeout_seconds must be greater than 0."))

            raw = deps.read_raw_config()
            existing_profiles = deps.get_profiles(raw, "llm")
            previous_row = dict(existing_profiles.get(name, {}))
            active_roles = raw.get("profiles", {}).get("active", {}) if isinstance(raw.get("profiles"), dict) else {}
            assigned_web = str(active_roles.get("web_llm", "") or "") if isinstance(active_roles, dict) else ""
            if not assigned_web and isinstance(raw.get("web_llm"), dict):
                assigned_web = str(raw["web_llm"].get("profile", "") or "")
            raw.setdefault("profiles", {})
            if not isinstance(raw["profiles"], dict):
                raw["profiles"] = {}
            raw["profiles"].setdefault("llm", {})
            if not isinstance(raw["profiles"]["llm"], dict):
                raw["profiles"]["llm"] = {}
            raw["profiles"]["llm"][name] = {
                "model": cleaned_model,
                "api_base": api_base.strip(),
                "api_key": "",
                "temperature": parsed_temperature,
                "max_tokens": int(max_tokens),
                "timeout_seconds": int(timeout_seconds),
            }
            should_activate_main = str(activate_main or "").strip().lower() in {"1", "true", "yes", "on"}
            if should_activate_main:
                deps.set_active_profile(raw, "llm", name)
                raw.setdefault("llm", {})
                raw["llm"].update(
                    {
                        "model": cleaned_model,
                        "api_base": api_base.strip() or None,
                        "api_key": "",
                        "temperature": parsed_temperature,
                        "max_tokens": int(max_tokens),
                        "timeout_seconds": int(timeout_seconds),
                    }
                )
            store = deps.get_secure_store(raw)
            previous_api_key = str(previous_row.get("api_key", "") or "")
            if store:
                previous_api_key = store.get_secret(f"profiles.llm.{name}.api_key", default=previous_api_key)
            if store and cleaned_api_key:
                store.set_secret(f"profiles.llm.{name}.api_key", cleaned_api_key)
                if should_activate_main:
                    store.set_secret("llm.api_key", cleaned_api_key)
            elif not store:
                raw["profiles"]["llm"][name]["api_key"] = cleaned_api_key
                if should_activate_main:
                    raw["llm"]["api_key"] = cleaned_api_key
            capability_changed = (
                str(previous_row.get("model", "") or "") != cleaned_model
                or str(previous_row.get("api_base", "") or "").strip() != api_base.strip()
                or (bool(cleaned_api_key) and cleaned_api_key != previous_api_key)
            )
            if name == assigned_web and capability_changed:
                raw.setdefault("web_llm", {})
                raw["web_llm"]["enabled"] = False
                raw["web_llm"]["capability_verified_at"] = ""
                raw["web_llm"].pop("capability_receipt", None)
            deps.write_raw_config(raw)
            deps.reload_runtime()
            return deps.redirect_with_return_to(
                f"{_config_ui_path('/config/llm')}?saved=1&edit_profile={quote_plus(name)}",
                request,
                fallback=_config_ui_path("/config"),
            )
        except (OSError, ValueError) as exc:
            return deps.redirect_with_return_to(
                f"{_config_ui_path('/config/llm')}?error={quote_plus(str(exc))}",
                request,
                fallback=_config_ui_path("/config"),
            )

    @app.post("/config/llm/profile/delete")
    async def config_llm_profile_delete(request: Request, profile_name: str = Form(...)) -> RedirectResponse:
        lang = _request_lang(request)
        try:
            raw = deps.read_raw_config()
            name = deps.sanitize_profile_name(profile_name)
            if not name:
                raise ValueError(_workbench_text(lang, "invalid_profile_name", "Invalid profile name."))
            active = deps.get_active_profile_name(raw, "llm")
            active_roles = raw.get("profiles", {}).get("active", {}) if isinstance(raw.get("profiles"), dict) else {}
            assigned_web = str(active_roles.get("web_llm", "") or "") if isinstance(active_roles, dict) else ""
            if name == active or name == assigned_web:
                raise ValueError(_workbench_text(lang, "active_llm_profile_delete_blocked", "The active LLM profile cannot be deleted."))
            llm_profiles = deps.get_profiles(raw, "llm")
            if name not in llm_profiles:
                raise ValueError(_workbench_text(lang, "llm_profile_not_found", "LLM profile not found."))

            del raw["profiles"]["llm"][name]
            deps.write_raw_config(raw)
            deps.reload_runtime()
            return deps.redirect_with_return_to(
                f"{_config_ui_path('/config/llm')}?saved=1",
                request,
                fallback=_config_ui_path("/config"),
            )
        except (OSError, ValueError) as exc:
            return deps.redirect_with_return_to(
                f"{_config_ui_path('/config/llm')}?error={quote_plus(str(exc))}",
                request,
                fallback=_config_ui_path("/config"),
            )

    @app.post("/config/llm/models")
    async def config_llm_models(request: Request, api_base: str = Form(...), api_key: str = Form("")) -> JSONResponse:
        lang = _request_lang(request)
        try:
            parsed = urlparse(api_base.strip())
            if parsed.scheme not in {"http", "https"}:
                raise ValueError(_workbench_text(lang, "api_base_scheme_required", "API base must start with http:// or https://."))
            models = deps.load_models_from_api_base(api_base=api_base, api_key=api_key)
            return JSONResponse(content={"models": models})
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.post("/config/embeddings/models")
    async def config_embeddings_models(request: Request, api_base: str = Form(...), api_key: str = Form("")) -> JSONResponse:
        lang = _request_lang(request)
        try:
            parsed = urlparse(api_base.strip())
            if parsed.scheme not in {"http", "https"}:
                raise ValueError(_workbench_text(lang, "api_base_scheme_required", "API base must start with http:// or https://."))
            models = deps.load_models_from_api_base(api_base=api_base, api_key=api_key)
            return JSONResponse(content={"models": models})
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.post("/config/llm/save")
    async def config_llm_save(
        request: Request,
        model: str = Form(...),
        api_base: str = Form(""),
        api_key: str = Form(""),
        temperature: str = Form(""),
        max_tokens: int = Form(...),
        timeout_seconds: int = Form(...),
        profile_name: str = Form(""),
    ) -> RedirectResponse:
        lang = _request_lang(request)
        try:
            cleaned_model = model.strip()
            cleaned_api_key = api_key.strip()
            if not cleaned_model:
                raise ValueError(_workbench_text(lang, "llm_model_required", "Model must not be empty."))
            if "<modellname>" in cleaned_model.lower():
                raise ValueError(_workbench_text(lang, "llm_model_placeholder", "Please enter a concrete model instead of the placeholder."))
            if not deps.is_ollama_model(cleaned_model) and not cleaned_api_key:
                raise ValueError(_workbench_text(lang, "llm_api_key_required", "API key is required for non-Ollama models."))
            parsed_temperature = _optional_temperature(temperature, default=None)
            if parsed_temperature is not None and (parsed_temperature < 0 or parsed_temperature > 2):
                raise ValueError(_workbench_text(lang, "temperature_range", "temperature must be between 0 and 2."))
            if max_tokens <= 0:
                raise ValueError(_workbench_text(lang, "max_tokens_positive", "max_tokens must be greater than 0."))
            if timeout_seconds <= 0:
                raise ValueError(_workbench_text(lang, "timeout_seconds_positive", "timeout_seconds must be greater than 0."))

            raw = deps.read_raw_config()
            raw.setdefault("llm", {})
            raw["llm"]["model"] = cleaned_model
            raw["llm"]["api_base"] = api_base.strip() or None
            raw["llm"]["api_key"] = ""
            raw["llm"]["temperature"] = parsed_temperature
            raw["llm"]["max_tokens"] = int(max_tokens)
            raw["llm"]["timeout_seconds"] = int(timeout_seconds)
            active_name = deps.get_active_profile_name(raw, "llm")
            requested_name = deps.sanitize_profile_name(profile_name)
            target_name = requested_name or active_name
            if target_name:
                deps.set_active_profile(raw, "llm", target_name)
                raw.setdefault("profiles", {})
                raw["profiles"].setdefault("llm", {})
                if isinstance(raw["profiles"]["llm"], dict):
                    raw["profiles"]["llm"][target_name] = {
                        "model": cleaned_model,
                        "api_base": api_base.strip(),
                        "api_key": "",
                        "temperature": parsed_temperature,
                        "max_tokens": int(max_tokens),
                        "timeout_seconds": int(timeout_seconds),
                    }
            store = deps.get_secure_store(raw)
            if store and cleaned_api_key:
                store.set_secret("llm.api_key", cleaned_api_key)
                if target_name:
                    store.set_secret(f"profiles.llm.{target_name}.api_key", cleaned_api_key)
            elif not store:
                raw["llm"]["api_key"] = cleaned_api_key
                if target_name and isinstance(raw.get("profiles", {}).get("llm"), dict):
                    raw["profiles"]["llm"][target_name]["api_key"] = cleaned_api_key
            deps.write_raw_config(raw)
            deps.reload_runtime()
            return deps.redirect_with_return_to(
                f"{_config_ui_path('/config/llm')}?saved=1",
                request,
                fallback=_config_ui_path("/config"),
            )
        except (OSError, ValueError) as exc:
            return deps.redirect_with_return_to(
                f"{_config_ui_path('/config/llm')}?error={quote_plus(str(exc))}",
                request,
                fallback=_config_ui_path("/config"),
            )

    @app.post("/config/llm/test")
    async def config_llm_test(request: Request, profile_name: str = Form("")) -> RedirectResponse:
        settings = deps.get_settings()
        pipeline = deps.get_pipeline()
        lang = _request_lang(request)
        raw = deps.read_raw_config()
        active_name = deps.get_active_profile_name(raw, "llm") or "default"
        requested_name = deps.sanitize_profile_name(profile_name)
        test_name = requested_name or active_name
        test_config = settings.llm
        profiles = deps.get_profiles(raw, "llm")
        if requested_name:
            row = profiles.get(requested_name)
            if row is None:
                result = {
                    "id": "llm",
                    "status": "error",
                    "detail": _workbench_text(lang, "llm_profile_not_found", "LLM profile not found."),
                }
            else:
                api_key = str(row.get("api_key", "") or "")
                store = deps.get_secure_store(raw)
                if store:
                    api_key = store.get_secret(f"profiles.llm.{requested_name}.api_key", default=api_key)
                test_config = settings.llm.model_copy(
                    update={
                        "model": str(row.get("model", "") or ""),
                        "api_base": str(row.get("api_base", "") or "") or None,
                        "api_key": api_key,
                        "temperature": _optional_temperature(row.get("temperature", ...)),
                        "max_tokens": int(row.get("max_tokens", 4096) or 4096),
                        "timeout_seconds": int(row.get("timeout_seconds", 60) or 60),
                    }
                )
                result = await deps.probe_llm(test_config, usage_meter=getattr(pipeline, "usage_meter", None))
        else:
            result = await deps.probe_llm(test_config, usage_meter=getattr(pipeline, "usage_meter", None))
        message = deps.profile_test_result_message("llm", test_name, result, lang)
        return deps.redirect_with_return_to(
            deps.profile_test_redirect_url(
                _config_ui_path("/config/llm"),
                ok=str(result.get("status", "")).strip().lower() == "ok",
                message=message,
            ),
            request,
            fallback=_config_ui_path("/config"),
        )

    @app.get("/config/embeddings", response_class=HTMLResponse)
    async def config_embeddings_page(
        request: Request,
        saved: int = 0,
        error: str = "",
        info: str = "",
        test_status: str = "",
    ) -> HTMLResponse:
        settings = deps.get_settings()
        deps.set_logical_back_url(request)
        username = deps.get_username_from_request(request)
        raw = deps.read_raw_config()
        embedding_profiles = deps.get_profiles(raw, "embeddings")
        if not embedding_profiles:
            embedding_profiles = {
                "default": {
                    "model": settings.embeddings.model,
                    "api_base": settings.embeddings.api_base or "",
                    "api_key": settings.embeddings.api_key or "",
                    "timeout_seconds": settings.embeddings.timeout_seconds,
                }
            }
        active_embedding_profile = deps.get_active_profile_name(raw, "embeddings") or "default"
        active_embedding_meta = deps.active_profile_runtime_meta(raw, "embeddings")
        providers = [
            {
                "key": key,
                "label": data["label"],
                "default_model": data["default_model"],
                "default_api_base": data["default_api_base"],
            }
            for key, data in deps.embedding_provider_presets.items()
        ]
        lang = _request_lang(request)
        guard_context = await deps.embedding_memory_guard_context(username)
        return deps.templates.TemplateResponse(
            request=request,
            name=_config_ui_template("config_embeddings.html"),
            context={
                "title": settings.ui.title,
                "username": username,
                "saved": bool(saved),
                "error_message": error,
                "info_message": deps.format_config_info_message(lang, info),
                "test_status": str(test_status or "").strip().lower(),
                "config_nav": "intelligence",
                "config_page_heading": deps.msg(lang, "Embedding Radar", "Embedding Radar"),
                "page_return_to": deps.config_surface_path(
                    deps.set_logical_back_url(request),
                    fallback=_config_ui_path("/config/intelligence"),
                ),
                "show_overview_checks": False,
                "embeddings": settings.embeddings,
                "providers": providers,
                "embedding_profiles": sorted(embedding_profiles.keys()),
                "active_embedding_profile": active_embedding_profile,
                "active_embedding_meta": active_embedding_meta,
                "embedding_guard": guard_context,
            },
        )

    @app.post("/config/embeddings/profile/load")
    async def config_embeddings_profile_load(
        request: Request,
        profile_name: str = Form(...),
        confirm_embedding_switch: str = Form(""),
        confirm_embedding_phrase: str = Form(""),
    ) -> RedirectResponse:
        lang = _request_lang(request)
        try:
            raw = deps.read_raw_config()
            name = deps.sanitize_profile_name(profile_name)
            if not name:
                raise ValueError(_workbench_text(lang, "invalid_profile_name", "Invalid profile name."))
            profiles = deps.get_profiles(raw, "embeddings")
            profile = profiles.get(name)
            if not profile:
                raise ValueError(_workbench_text(lang, "embedding_profile_not_found", "Embedding profile not found."))
            username = deps.get_username_from_request(request) or "web"
            fingerprint, resolved_model = await deps.guard_embedding_switch(
                username=username,
                new_model=str(profile.get("model", "")).strip(),
                new_api_base=str(profile.get("api_base", "")).strip(),
                confirm_switch=confirm_embedding_switch,
                confirm_phrase=confirm_embedding_phrase,
            )

            raw.setdefault("embeddings", {})
            raw["embeddings"]["model"] = str(profile.get("model", "")).strip()
            raw["embeddings"]["api_base"] = str(profile.get("api_base", "")).strip() or None
            store = deps.get_secure_store(raw)
            profile_api_key = str(profile.get("api_key", "")).strip()
            if store:
                profile_api_key = store.get_secret(f"profiles.embeddings.{name}.api_key", default=profile_api_key)
            raw["embeddings"]["api_key"] = profile_api_key
            raw["embeddings"]["timeout_seconds"] = int(profile.get("timeout_seconds", 60))
            if store and profile_api_key:
                store.set_secret("embeddings.api_key", profile_api_key)
                raw["embeddings"]["api_key"] = ""
            deps.set_active_profile(raw, "embeddings", name)
            raw.setdefault("memory", {})
            raw["memory"]["embedding_fingerprint"] = fingerprint
            raw["memory"]["embedding_model"] = resolved_model
            deps.write_raw_config(raw)
            deps.reload_runtime()
            return deps.redirect_with_return_to(
                f"{_config_ui_path('/config/embeddings')}?saved=1",
                request,
                fallback=_config_ui_path("/config"),
            )
        except (OSError, ValueError) as exc:
            return deps.redirect_with_return_to(
                f"{_config_ui_path('/config/embeddings')}?error={quote_plus(str(exc))}",
                request,
                fallback=_config_ui_path("/config"),
            )

    @app.post("/config/embeddings/profile/save")
    async def config_embeddings_profile_save(
        request: Request,
        profile_name: str = Form(...),
        model: str = Form(...),
        api_base: str = Form(""),
        api_key: str = Form(""),
        timeout_seconds: int = Form(...),
        confirm_embedding_switch: str = Form(""),
        confirm_embedding_phrase: str = Form(""),
    ) -> RedirectResponse:
        lang = _request_lang(request)
        try:
            name = deps.sanitize_profile_name(profile_name)
            if not name:
                raise ValueError(_workbench_text(lang, "invalid_profile_name", "Invalid profile name."))
            cleaned_model = model.strip()
            cleaned_api_key = api_key.strip()
            if not cleaned_model:
                raise ValueError(_workbench_text(lang, "embedding_model_required", "Embedding model must not be empty."))
            if "<modellname>" in cleaned_model.lower():
                raise ValueError(_workbench_text(lang, "embedding_model_placeholder", "Please enter a concrete embedding model instead of the placeholder."))
            if not deps.is_ollama_model(cleaned_model) and not cleaned_api_key:
                raise ValueError(_workbench_text(lang, "embedding_api_key_required", "API key is required for non-Ollama embedding models."))
            if timeout_seconds <= 0:
                raise ValueError(_workbench_text(lang, "timeout_seconds_positive", "timeout_seconds must be greater than 0."))
            username = deps.get_username_from_request(request) or "web"
            fingerprint, resolved_model = await deps.guard_embedding_switch(
                username=username,
                new_model=cleaned_model,
                new_api_base=api_base.strip(),
                confirm_switch=confirm_embedding_switch,
                confirm_phrase=confirm_embedding_phrase,
            )

            raw = deps.read_raw_config()
            raw.setdefault("profiles", {})
            if not isinstance(raw["profiles"], dict):
                raw["profiles"] = {}
            raw["profiles"].setdefault("embeddings", {})
            if not isinstance(raw["profiles"]["embeddings"], dict):
                raw["profiles"]["embeddings"] = {}
            raw["profiles"]["embeddings"][name] = {
                "model": cleaned_model,
                "api_base": api_base.strip(),
                "api_key": "",
                "timeout_seconds": int(timeout_seconds),
            }
            deps.set_active_profile(raw, "embeddings", name)
            raw.setdefault("embeddings", {})
            raw["embeddings"].update(
                {
                    "model": cleaned_model,
                    "api_base": api_base.strip() or None,
                    "api_key": "",
                    "timeout_seconds": int(timeout_seconds),
                }
            )
            raw.setdefault("memory", {})
            raw["memory"]["embedding_fingerprint"] = fingerprint
            raw["memory"]["embedding_model"] = resolved_model
            store = deps.get_secure_store(raw)
            if store and cleaned_api_key:
                store.set_secret("embeddings.api_key", cleaned_api_key)
                store.set_secret(f"profiles.embeddings.{name}.api_key", cleaned_api_key)
            elif not store:
                raw["profiles"]["embeddings"][name]["api_key"] = cleaned_api_key
                raw["embeddings"]["api_key"] = cleaned_api_key
            deps.write_raw_config(raw)
            deps.reload_runtime()
            return deps.redirect_with_return_to(
                f"{_config_ui_path('/config/embeddings')}?saved=1",
                request,
                fallback=_config_ui_path("/config"),
            )
        except (OSError, ValueError) as exc:
            return deps.redirect_with_return_to(
                f"{_config_ui_path('/config/embeddings')}?error={quote_plus(str(exc))}",
                request,
                fallback=_config_ui_path("/config"),
            )

    @app.post("/config/embeddings/profile/delete")
    async def config_embeddings_profile_delete(request: Request, profile_name: str = Form(...)) -> RedirectResponse:
        lang = _request_lang(request)
        try:
            raw = deps.read_raw_config()
            name = deps.sanitize_profile_name(profile_name)
            if not name:
                raise ValueError(_workbench_text(lang, "invalid_profile_name", "Invalid profile name."))
            active = deps.get_active_profile_name(raw, "embeddings")
            if name == active:
                raise ValueError(_workbench_text(lang, "active_embedding_profile_delete_blocked", "The active embedding profile cannot be deleted."))
            profiles = deps.get_profiles(raw, "embeddings")
            if name not in profiles:
                raise ValueError(_workbench_text(lang, "embedding_profile_not_found", "Embedding profile not found."))

            del raw["profiles"]["embeddings"][name]
            deps.write_raw_config(raw)
            deps.reload_runtime()
            return deps.redirect_with_return_to(
                f"{_config_ui_path('/config/embeddings')}?saved=1",
                request,
                fallback=_config_ui_path("/config"),
            )
        except (OSError, ValueError) as exc:
            return deps.redirect_with_return_to(
                f"{_config_ui_path('/config/embeddings')}?error={quote_plus(str(exc))}",
                request,
                fallback=_config_ui_path("/config"),
            )

    @app.post("/config/embeddings/save")
    async def config_embeddings_save(
        request: Request,
        model: str = Form(...),
        api_base: str = Form(""),
        api_key: str = Form(""),
        timeout_seconds: int = Form(...),
        profile_name: str = Form(""),
        confirm_embedding_switch: str = Form(""),
        confirm_embedding_phrase: str = Form(""),
    ) -> RedirectResponse:
        lang = _request_lang(request)
        try:
            cleaned_model = model.strip()
            cleaned_api_key = api_key.strip()
            if not cleaned_model:
                raise ValueError(_workbench_text(lang, "embedding_model_required", "Embedding model must not be empty."))
            if "<modellname>" in cleaned_model.lower():
                raise ValueError(_workbench_text(lang, "embedding_model_placeholder", "Please enter a concrete embedding model instead of the placeholder."))
            if not deps.is_ollama_model(cleaned_model) and not cleaned_api_key:
                raise ValueError(_workbench_text(lang, "embedding_api_key_required", "API key is required for non-Ollama embedding models."))
            if timeout_seconds <= 0:
                raise ValueError(_workbench_text(lang, "timeout_seconds_positive", "timeout_seconds must be greater than 0."))
            username = deps.get_username_from_request(request) or "web"
            fingerprint, resolved_model = await deps.guard_embedding_switch(
                username=username,
                new_model=cleaned_model,
                new_api_base=api_base.strip(),
                confirm_switch=confirm_embedding_switch,
                confirm_phrase=confirm_embedding_phrase,
            )

            raw = deps.read_raw_config()
            raw.setdefault("embeddings", {})
            raw["embeddings"]["model"] = cleaned_model
            raw["embeddings"]["api_base"] = api_base.strip() or None
            raw["embeddings"]["api_key"] = ""
            raw["embeddings"]["timeout_seconds"] = int(timeout_seconds)
            active_name = deps.get_active_profile_name(raw, "embeddings")
            requested_name = deps.sanitize_profile_name(profile_name)
            target_name = requested_name or active_name
            if target_name:
                deps.set_active_profile(raw, "embeddings", target_name)
                raw.setdefault("profiles", {})
                raw["profiles"].setdefault("embeddings", {})
                if isinstance(raw["profiles"]["embeddings"], dict):
                    raw["profiles"]["embeddings"][target_name] = {
                        "model": cleaned_model,
                        "api_base": api_base.strip(),
                        "api_key": "",
                        "timeout_seconds": int(timeout_seconds),
                    }
            raw.setdefault("memory", {})
            raw["memory"]["embedding_fingerprint"] = fingerprint
            raw["memory"]["embedding_model"] = resolved_model
            store = deps.get_secure_store(raw)
            if store and cleaned_api_key:
                store.set_secret("embeddings.api_key", cleaned_api_key)
                if target_name:
                    store.set_secret(f"profiles.embeddings.{target_name}.api_key", cleaned_api_key)
            elif not store:
                raw["embeddings"]["api_key"] = cleaned_api_key
                if target_name and isinstance(raw.get("profiles", {}).get("embeddings"), dict):
                    raw["profiles"]["embeddings"][target_name]["api_key"] = cleaned_api_key
            deps.write_raw_config(raw)
            deps.reload_runtime()
            return deps.redirect_with_return_to(
                f"{_config_ui_path('/config/embeddings')}?saved=1",
                request,
                fallback=_config_ui_path("/config"),
            )
        except (OSError, ValueError) as exc:
            return deps.redirect_with_return_to(
                f"{_config_ui_path('/config/embeddings')}?error={quote_plus(str(exc))}",
                request,
                fallback=_config_ui_path("/config"),
            )

    @app.post("/config/embeddings/test")
    async def config_embeddings_test(request: Request) -> RedirectResponse:
        settings = deps.get_settings()
        pipeline = deps.get_pipeline()
        lang = _request_lang(request)
        raw = deps.read_raw_config()
        active_name = deps.get_active_profile_name(raw, "embeddings") or "default"
        result = await deps.probe_embeddings(settings.embeddings, usage_meter=getattr(pipeline, "usage_meter", None))
        message = deps.profile_test_result_message("embeddings", active_name, result, lang)
        return deps.redirect_with_return_to(
            deps.profile_test_redirect_url(
                _config_ui_path("/config/embeddings"),
                ok=str(result.get("status", "")).strip().lower() == "ok",
                message=message,
            ),
            request,
            fallback=_config_ui_path("/config"),
        )

    @app.get("/config/files", response_class=HTMLResponse)
    async def config_files_page(request: Request, file: str | None = None, saved: int = 0, error: str = "") -> HTMLResponse:
        lang = _request_lang(request)
        entries = deps.list_file_editor_entries()
        rows = deps.build_editor_entries_from_paths(deps.base_dir, [row["path"] for row in entries], deps.resolve_file_editor_file)
        entry_map = {row["path"]: row for row in entries}
        for row in rows:
            meta = entry_map.get(row["path"], {})
            row["label"] = meta.get("label") or row["name"]
            row["group"] = meta.get("group") or "misc"
            row["mode"] = meta.get("mode") or "readonly"
        selected = file or (rows[0]["path"] if rows else "")
        content = ""

        if selected:
            try:
                selected_path = deps.resolve_file_editor_file(selected)
                if not selected_path.exists():
                    raise ValueError(_workbench_text(lang, "file_not_found", "File does not exist."))
                content = selected_path.read_text(encoding="utf-8")
            except (OSError, ValueError) as exc:
                error = str(exc)
                content = ""
        selected_row = next((row for row in rows if row.get("path") == selected), None)
        context = deps.build_config_page_context(
            request,
            saved=saved,
            error=error,
            logical_back_fallback=_config_ui_path("/config"),
            page_return_to=_config_ui_path("/config"),
            config_nav="admin",
            page_heading=_workbench_text(lang, "file_editor_heading", "File editor"),
        )
        context.update(
            {
                "rows": rows,
                "selected_file": selected,
                "selected_row": selected_row,
                "file_content": content,
            }
        )

        return deps.templates.TemplateResponse(
            request=request,
            name=_config_ui_template("config_files.html"),
            context=context,
        )

    @app.get("/config/error-interpreter", response_class=HTMLResponse)
    async def config_error_interpreter_page(request: Request, saved: int = 0, error: str = "") -> HTMLResponse:
        lang = _request_lang(request)
        content = ""
        category_count = 0
        try:
            content = deps.read_error_interpreter_raw()
            parsed = yaml.safe_load(content) or {}
            rules = parsed.get("rules", []) if isinstance(parsed, dict) else []
            if isinstance(rules, list):
                category_count = len([row for row in rules if isinstance(row, dict) and str(row.get("id", "")).strip()])
        except (OSError, yaml.YAMLError, ValueError) as exc:
            error = error or str(exc)
        context = deps.build_config_page_context(
            request,
            saved=saved,
            error=error,
            logical_back_fallback=_config_ui_path("/config"),
            page_return_to=_config_ui_path("/config"),
            config_nav="admin",
            page_heading=_workbench_text(lang, "error_interpreter_heading", "Error interpreter"),
        )
        context.update(
            {
                "file_content": content,
                "file_path": str(deps.error_interpreter_path.relative_to(deps.base_dir)),
                "category_count": category_count,
            }
        )
        return deps.templates.TemplateResponse(
            request=request,
            name=_config_ui_template("config_error_interpreter.html"),
            context=context,
        )

    @app.post("/config/error-interpreter/save")
    async def config_error_interpreter_save(
        request: Request,
        content: str = Form(...),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        lang = _request_lang(request)
        try:
            parsed = yaml.safe_load(content) or {}
            if not isinstance(parsed, dict):
                raise ValueError(_workbench_text(lang, "rules_yaml_object_required", "The rules file must contain a YAML object."))
            rules = parsed.get("rules", [])
            if not isinstance(rules, list):
                raise ValueError(_workbench_text(lang, "rules_list_required", "`rules` must be a list."))
            for idx, row in enumerate(rules, start=1):
                if not isinstance(row, dict):
                    raise ValueError(_workbench_text(lang, "rule_not_object", "Rule {idx} is not an object.", idx=idx))
                if not str(row.get("id", "")).strip():
                    raise ValueError(_workbench_text(lang, "rule_missing_id", "Rule {idx} has no ID.", idx=idx))
                patterns = row.get("patterns", [])
                messages = row.get("messages", {})
                if not isinstance(patterns, list):
                    raise ValueError(_workbench_text(lang, "rule_patterns_list_required", "Rule {idx}: `patterns` must be a list.", idx=idx))
                if not isinstance(messages, dict):
                    raise ValueError(_workbench_text(lang, "rule_messages_object_required", "Rule {idx}: `messages` must be an object.", idx=idx))
            deps.error_interpreter_path.write_text(content, encoding="utf-8")
            deps.reload_runtime()
            return deps.redirect_with_return_to(
                f"{_config_ui_path('/config/error-interpreter')}?saved=1",
                request,
                fallback=_config_ui_path("/config"),
                return_to=return_to,
            )
        except (OSError, ValueError, yaml.YAMLError) as exc:
            return deps.redirect_with_return_to(
                f"{_config_ui_path('/config/error-interpreter')}?error={quote_plus(str(exc))}",
                request,
                fallback=_config_ui_path("/config"),
                return_to=return_to,
            )

    @app.post("/config/files/save")
    async def config_files_save(
        request: Request,
        file: str = Form(...),
        content: str = Form(...),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        lang = _request_lang(request)
        try:
            target = deps.resolve_edit_file(file)
            if not target.exists():
                raise ValueError(_workbench_text(lang, "file_not_found", "File does not exist."))
            _saved, reload_message = deps.save_text_file_and_maybe_reload(target, content)
            target_url = f"{_config_ui_path('/config/files')}?file={quote_plus(file)}&saved=1"
            if reload_message:
                target_url += f"&error={quote_plus(reload_message)}"
            return deps.redirect_with_return_to(target_url, request, fallback=_config_ui_path("/config"), return_to=return_to)
        except (OSError, ValueError) as exc:
            lang = _request_lang(request)
            fallback = _workbench_text(lang, "file_save_failed", "Could not save file.")
            error = deps.friendly_route_error(lang, exc, fallback, fallback)
            return deps.redirect_with_return_to(
                f"{_config_ui_path('/config/files')}?file={quote_plus(file)}&error={quote_plus(error)}",
                request,
                fallback=_config_ui_path("/config"),
                return_to=return_to,
            )
