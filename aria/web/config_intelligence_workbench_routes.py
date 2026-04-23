from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urlparse

import yaml
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates


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
    @app.get("/config/llm", response_class=HTMLResponse)
    async def config_llm_page(
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
        active_llm_meta = deps.active_profile_runtime_meta(raw, "llm")
        providers = [
            {
                "key": key,
                "label": data["label"],
                "default_model": data["default_model"],
                "default_api_base": data["default_api_base"],
            }
            for key, data in deps.llm_provider_presets.items()
        ]
        lang = str(getattr(request.state, "lang", "de") or "de")
        return deps.templates.TemplateResponse(
            request=request,
            name="config_llm.html",
            context={
                "title": settings.ui.title,
                "username": username,
                "saved": bool(saved),
                "error_message": error,
                "info_message": deps.format_config_info_message(lang, info),
                "test_status": str(test_status or "").strip().lower(),
                "config_nav": "intelligence",
                "config_page_heading": deps.msg(lang, "Chat Brain (LLM)", "Chat Brain (LLM)"),
                "page_return_to": deps.config_surface_path(
                    deps.set_logical_back_url(request),
                    fallback="/config/intelligence",
                ),
                "show_overview_checks": False,
                "llm": settings.llm,
                "providers": providers,
                "llm_profiles": sorted(llm_profiles.keys()),
                "active_llm_profile": active_llm_profile,
                "active_llm_meta": active_llm_meta,
            },
        )

    @app.post("/config/llm/profile/load")
    async def config_llm_profile_load(request: Request, profile_name: str = Form(...)) -> RedirectResponse:
        try:
            raw = deps.read_raw_config()
            name = deps.sanitize_profile_name(profile_name)
            if not name:
                raise ValueError("Ungültiger Profilname.")
            llm_profiles = deps.get_profiles(raw, "llm")
            profile = llm_profiles.get(name)
            if not profile:
                raise ValueError("LLM-Profil nicht gefunden.")

            raw.setdefault("llm", {})
            raw["llm"]["model"] = str(profile.get("model", "")).strip()
            raw["llm"]["api_base"] = str(profile.get("api_base", "")).strip() or None
            store = deps.get_secure_store(raw)
            profile_api_key = str(profile.get("api_key", "")).strip()
            if store:
                profile_api_key = store.get_secret(f"profiles.llm.{name}.api_key", default=profile_api_key)
            raw["llm"]["api_key"] = profile_api_key
            raw["llm"]["temperature"] = float(profile.get("temperature", 0.4))
            raw["llm"]["max_tokens"] = int(profile.get("max_tokens", 4096))
            raw["llm"]["timeout_seconds"] = int(profile.get("timeout_seconds", 60))
            if store and profile_api_key:
                store.set_secret("llm.api_key", profile_api_key)
                raw["llm"]["api_key"] = ""
            deps.set_active_profile(raw, "llm", name)
            deps.write_raw_config(raw)
            deps.reload_runtime()
            return deps.redirect_with_return_to("/config/llm?saved=1", request, fallback="/config")
        except (OSError, ValueError) as exc:
            return deps.redirect_with_return_to(f"/config/llm?error={quote_plus(str(exc))}", request, fallback="/config")

    @app.post("/config/llm/profile/save")
    async def config_llm_profile_save(
        request: Request,
        profile_name: str = Form(...),
        model: str = Form(...),
        api_base: str = Form(""),
        api_key: str = Form(""),
        temperature: float = Form(...),
        max_tokens: int = Form(...),
        timeout_seconds: int = Form(...),
    ) -> RedirectResponse:
        try:
            name = deps.sanitize_profile_name(profile_name)
            if not name:
                raise ValueError("Ungültiger Profilname.")

            cleaned_model = model.strip()
            cleaned_api_key = api_key.strip()
            if not cleaned_model:
                raise ValueError("Modell darf nicht leer sein.")
            if "<modellname>" in cleaned_model.lower():
                raise ValueError("Bitte ein konkretes Modell statt Placeholder eingeben.")
            if not deps.is_ollama_model(cleaned_model) and not cleaned_api_key:
                raise ValueError("API Key ist für Nicht-Ollama-Modelle erforderlich.")
            if temperature < 0 or temperature > 2:
                raise ValueError("temperature muss zwischen 0 und 2 liegen.")
            if max_tokens <= 0:
                raise ValueError("max_tokens muss > 0 sein.")
            if timeout_seconds <= 0:
                raise ValueError("timeout_seconds muss > 0 sein.")

            raw = deps.read_raw_config()
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
                "temperature": float(temperature),
                "max_tokens": int(max_tokens),
                "timeout_seconds": int(timeout_seconds),
            }
            deps.set_active_profile(raw, "llm", name)
            raw.setdefault("llm", {})
            raw["llm"].update(
                {
                    "model": cleaned_model,
                    "api_base": api_base.strip() or None,
                    "api_key": "",
                    "temperature": float(temperature),
                    "max_tokens": int(max_tokens),
                    "timeout_seconds": int(timeout_seconds),
                }
            )
            store = deps.get_secure_store(raw)
            if store and cleaned_api_key:
                store.set_secret("llm.api_key", cleaned_api_key)
                store.set_secret(f"profiles.llm.{name}.api_key", cleaned_api_key)
            elif not store:
                raw["profiles"]["llm"][name]["api_key"] = cleaned_api_key
                raw["llm"]["api_key"] = cleaned_api_key
            deps.write_raw_config(raw)
            deps.reload_runtime()
            return deps.redirect_with_return_to("/config/llm?saved=1", request, fallback="/config")
        except (OSError, ValueError) as exc:
            return deps.redirect_with_return_to(f"/config/llm?error={quote_plus(str(exc))}", request, fallback="/config")

    @app.post("/config/llm/profile/delete")
    async def config_llm_profile_delete(request: Request, profile_name: str = Form(...)) -> RedirectResponse:
        try:
            raw = deps.read_raw_config()
            name = deps.sanitize_profile_name(profile_name)
            if not name:
                raise ValueError("Ungültiger Profilname.")
            active = deps.get_active_profile_name(raw, "llm")
            if name == active:
                raise ValueError("Aktives LLM-Profil kann nicht gelöscht werden.")
            llm_profiles = deps.get_profiles(raw, "llm")
            if name not in llm_profiles:
                raise ValueError("LLM-Profil nicht gefunden.")

            del raw["profiles"]["llm"][name]
            deps.write_raw_config(raw)
            deps.reload_runtime()
            return deps.redirect_with_return_to("/config/llm?saved=1", request, fallback="/config")
        except (OSError, ValueError) as exc:
            return deps.redirect_with_return_to(f"/config/llm?error={quote_plus(str(exc))}", request, fallback="/config")

    @app.post("/config/llm/models")
    async def config_llm_models(api_base: str = Form(...), api_key: str = Form("")) -> JSONResponse:
        try:
            parsed = urlparse(api_base.strip())
            if parsed.scheme not in {"http", "https"}:
                raise ValueError("API Base muss mit http:// oder https:// beginnen.")
            models = deps.load_models_from_api_base(api_base=api_base, api_key=api_key)
            return JSONResponse(content={"models": models})
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.post("/config/embeddings/models")
    async def config_embeddings_models(api_base: str = Form(...), api_key: str = Form("")) -> JSONResponse:
        try:
            parsed = urlparse(api_base.strip())
            if parsed.scheme not in {"http", "https"}:
                raise ValueError("API Base muss mit http:// oder https:// beginnen.")
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
        temperature: float = Form(...),
        max_tokens: int = Form(...),
        timeout_seconds: int = Form(...),
        profile_name: str = Form(""),
    ) -> RedirectResponse:
        try:
            cleaned_model = model.strip()
            cleaned_api_key = api_key.strip()
            if not cleaned_model:
                raise ValueError("Modell darf nicht leer sein.")
            if "<modellname>" in cleaned_model.lower():
                raise ValueError("Bitte ein konkretes Modell statt Placeholder eingeben.")
            if not deps.is_ollama_model(cleaned_model) and not cleaned_api_key:
                raise ValueError("API Key ist für Nicht-Ollama-Modelle erforderlich.")
            if temperature < 0 or temperature > 2:
                raise ValueError("temperature muss zwischen 0 und 2 liegen.")
            if max_tokens <= 0:
                raise ValueError("max_tokens muss > 0 sein.")
            if timeout_seconds <= 0:
                raise ValueError("timeout_seconds muss > 0 sein.")

            raw = deps.read_raw_config()
            raw.setdefault("llm", {})
            raw["llm"]["model"] = cleaned_model
            raw["llm"]["api_base"] = api_base.strip() or None
            raw["llm"]["api_key"] = ""
            raw["llm"]["temperature"] = float(temperature)
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
                        "temperature": float(temperature),
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
            return deps.redirect_with_return_to("/config/llm?saved=1", request, fallback="/config")
        except (OSError, ValueError) as exc:
            return deps.redirect_with_return_to(f"/config/llm?error={quote_plus(str(exc))}", request, fallback="/config")

    @app.post("/config/llm/test")
    async def config_llm_test(request: Request) -> RedirectResponse:
        settings = deps.get_settings()
        pipeline = deps.get_pipeline()
        lang = str(getattr(request.state, "lang", "de") or "de")
        raw = deps.read_raw_config()
        active_name = deps.get_active_profile_name(raw, "llm") or "default"
        result = await deps.probe_llm(settings.llm, usage_meter=getattr(pipeline, "usage_meter", None))
        message = deps.profile_test_result_message("llm", active_name, result, lang)
        return deps.redirect_with_return_to(
            deps.profile_test_redirect_url(
                "/config/llm",
                ok=str(result.get("status", "")).strip().lower() == "ok",
                message=message,
            ),
            request,
            fallback="/config",
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
        lang = str(getattr(request.state, "lang", "de") or "de")
        guard_context = await deps.embedding_memory_guard_context(username)
        return deps.templates.TemplateResponse(
            request=request,
            name="config_embeddings.html",
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
                    fallback="/config/intelligence",
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
        try:
            raw = deps.read_raw_config()
            name = deps.sanitize_profile_name(profile_name)
            if not name:
                raise ValueError("Ungültiger Profilname.")
            profiles = deps.get_profiles(raw, "embeddings")
            profile = profiles.get(name)
            if not profile:
                raise ValueError("Embedding-Profil nicht gefunden.")
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
            return deps.redirect_with_return_to("/config/embeddings?saved=1", request, fallback="/config")
        except (OSError, ValueError) as exc:
            return deps.redirect_with_return_to(f"/config/embeddings?error={quote_plus(str(exc))}", request, fallback="/config")

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
        try:
            name = deps.sanitize_profile_name(profile_name)
            if not name:
                raise ValueError("Ungültiger Profilname.")
            cleaned_model = model.strip()
            cleaned_api_key = api_key.strip()
            if not cleaned_model:
                raise ValueError("Embedding-Modell darf nicht leer sein.")
            if "<modellname>" in cleaned_model.lower():
                raise ValueError("Bitte ein konkretes Embedding-Modell statt Placeholder eingeben.")
            if not deps.is_ollama_model(cleaned_model) and not cleaned_api_key:
                raise ValueError("API Key ist für Nicht-Ollama-Embedding-Modelle erforderlich.")
            if timeout_seconds <= 0:
                raise ValueError("timeout_seconds muss > 0 sein.")
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
            return deps.redirect_with_return_to("/config/embeddings?saved=1", request, fallback="/config")
        except (OSError, ValueError) as exc:
            return deps.redirect_with_return_to(f"/config/embeddings?error={quote_plus(str(exc))}", request, fallback="/config")

    @app.post("/config/embeddings/profile/delete")
    async def config_embeddings_profile_delete(request: Request, profile_name: str = Form(...)) -> RedirectResponse:
        try:
            raw = deps.read_raw_config()
            name = deps.sanitize_profile_name(profile_name)
            if not name:
                raise ValueError("Ungültiger Profilname.")
            active = deps.get_active_profile_name(raw, "embeddings")
            if name == active:
                raise ValueError("Aktives Embedding-Profil kann nicht gelöscht werden.")
            profiles = deps.get_profiles(raw, "embeddings")
            if name not in profiles:
                raise ValueError("Embedding-Profil nicht gefunden.")

            del raw["profiles"]["embeddings"][name]
            deps.write_raw_config(raw)
            deps.reload_runtime()
            return deps.redirect_with_return_to("/config/embeddings?saved=1", request, fallback="/config")
        except (OSError, ValueError) as exc:
            return deps.redirect_with_return_to(f"/config/embeddings?error={quote_plus(str(exc))}", request, fallback="/config")

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
        try:
            cleaned_model = model.strip()
            cleaned_api_key = api_key.strip()
            if not cleaned_model:
                raise ValueError("Embedding-Modell darf nicht leer sein.")
            if "<modellname>" in cleaned_model.lower():
                raise ValueError("Bitte ein konkretes Embedding-Modell statt Placeholder eingeben.")
            if not deps.is_ollama_model(cleaned_model) and not cleaned_api_key:
                raise ValueError("API Key ist für Nicht-Ollama-Embedding-Modelle erforderlich.")
            if timeout_seconds <= 0:
                raise ValueError("timeout_seconds muss > 0 sein.")
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
            return deps.redirect_with_return_to("/config/embeddings?saved=1", request, fallback="/config")
        except (OSError, ValueError) as exc:
            return deps.redirect_with_return_to(f"/config/embeddings?error={quote_plus(str(exc))}", request, fallback="/config")

    @app.post("/config/embeddings/test")
    async def config_embeddings_test(request: Request) -> RedirectResponse:
        settings = deps.get_settings()
        pipeline = deps.get_pipeline()
        lang = str(getattr(request.state, "lang", "de") or "de")
        raw = deps.read_raw_config()
        active_name = deps.get_active_profile_name(raw, "embeddings") or "default"
        result = await deps.probe_embeddings(settings.embeddings, usage_meter=getattr(pipeline, "usage_meter", None))
        message = deps.profile_test_result_message("embeddings", active_name, result, lang)
        return deps.redirect_with_return_to(
            deps.profile_test_redirect_url(
                "/config/embeddings",
                ok=str(result.get("status", "")).strip().lower() == "ok",
                message=message,
            ),
            request,
            fallback="/config",
        )

    @app.get("/config/files", response_class=HTMLResponse)
    async def config_files_page(request: Request, file: str | None = None, saved: int = 0, error: str = "") -> HTMLResponse:
        lang = str(getattr(request.state, "lang", "de") or "de")
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
                    raise ValueError("Datei existiert nicht.")
                content = selected_path.read_text(encoding="utf-8")
            except (OSError, ValueError) as exc:
                error = str(exc)
                content = ""
        selected_row = next((row for row in rows if row.get("path") == selected), None)
        context = deps.build_config_page_context(
            request,
            saved=saved,
            error=error,
            logical_back_fallback="/config/workbench",
            page_return_to="/config/workbench",
            config_nav="workbench",
            page_heading=deps.msg(lang, "Datei-Editor", "File editor"),
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
            name="config_files.html",
            context=context,
        )

    @app.get("/config/error-interpreter", response_class=HTMLResponse)
    async def config_error_interpreter_page(request: Request, saved: int = 0, error: str = "") -> HTMLResponse:
        lang = str(getattr(request.state, "lang", "de") or "de")
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
            logical_back_fallback="/config/workbench",
            page_return_to="/config/workbench",
            config_nav="workbench",
            page_heading=deps.msg(lang, "Error Interpreter", "Error interpreter"),
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
            name="config_error_interpreter.html",
            context=context,
        )

    @app.post("/config/error-interpreter/save")
    async def config_error_interpreter_save(
        request: Request,
        content: str = Form(...),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        try:
            parsed = yaml.safe_load(content) or {}
            if not isinstance(parsed, dict):
                raise ValueError("Die Regeldatei muss ein YAML-Objekt enthalten.")
            rules = parsed.get("rules", [])
            if not isinstance(rules, list):
                raise ValueError("`rules` muss eine Liste sein.")
            for idx, row in enumerate(rules, start=1):
                if not isinstance(row, dict):
                    raise ValueError(f"Regel {idx} ist kein Objekt.")
                if not str(row.get("id", "")).strip():
                    raise ValueError(f"Regel {idx} hat keine ID.")
                patterns = row.get("patterns", [])
                messages = row.get("messages", {})
                if not isinstance(patterns, list):
                    raise ValueError(f"Regel {idx}: `patterns` muss eine Liste sein.")
                if not isinstance(messages, dict):
                    raise ValueError(f"Regel {idx}: `messages` muss ein Objekt sein.")
            deps.error_interpreter_path.write_text(content, encoding="utf-8")
            deps.reload_runtime()
            return deps.redirect_with_return_to(
                "/config/error-interpreter?saved=1",
                request,
                fallback="/config",
                return_to=return_to,
            )
        except (OSError, ValueError, yaml.YAMLError) as exc:
            return deps.redirect_with_return_to(
                f"/config/error-interpreter?error={quote_plus(str(exc))}",
                request,
                fallback="/config",
                return_to=return_to,
            )

    @app.post("/config/files/save")
    async def config_files_save(
        request: Request,
        file: str = Form(...),
        content: str = Form(...),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        try:
            target = deps.resolve_edit_file(file)
            if not target.exists():
                raise ValueError("Datei existiert nicht.")
            _saved, reload_message = deps.save_text_file_and_maybe_reload(target, content)
            target_url = f"/config/files?file={quote_plus(file)}&saved=1"
            if reload_message:
                target_url += f"&error={quote_plus(reload_message)}"
            return deps.redirect_with_return_to(target_url, request, fallback="/config", return_to=return_to)
        except (OSError, ValueError) as exc:
            lang = str(getattr(request.state, "lang", "de") or "de")
            error = deps.friendly_route_error(lang, exc, "Datei konnte nicht gespeichert werden.", "Could not save file.")
            return deps.redirect_with_return_to(
                f"/config/files?file={quote_plus(file)}&error={quote_plus(error)}",
                request,
                fallback="/config",
                return_to=return_to,
            )
