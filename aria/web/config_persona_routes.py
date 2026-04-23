from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from aria.core.config import UI_THEME_OPTIONS, discover_ui_background_files, normalize_ui_background, normalize_ui_theme
from aria.core.runtime_endpoint import cookie_should_be_secure


SettingsGetter = Callable[[], Any]
RawConfigReader = Callable[[], dict[str, Any]]
RawConfigWriter = Callable[[dict[str, Any]], None]
RuntimeReloader = Callable[[], None]
ConfigPageContextBuilder = Callable[..., dict[str, Any]]
ConfigRedirector = Callable[..., RedirectResponse]
FriendlyRouteError = Callable[[str, Exception, str, str], str]
LocalizedMessage = Callable[[str, str, str], str]
CookieNameResolver = Callable[[Request, str, str], str]
PromptLister = Callable[[], list[dict[str, Any]]]
PromptResolver = Callable[[str], Path]
TextFileSaver = Callable[[Path, str], tuple[bool, str]]
LanguageRowsGetter = Callable[[], list[str]]
LanguageFlag = Callable[[str], str]
LanguageLabel = Callable[[str], str]
LanguageResolver = Callable[[str, str], str]
CacheClearer = Callable[[], None]


@dataclass(frozen=True)
class ConfigPersonaRouteDeps:
    templates: Jinja2Templates
    base_dir: Path
    lang_cookie: str
    get_settings: SettingsGetter
    read_raw_config: RawConfigReader
    write_raw_config: RawConfigWriter
    reload_runtime: RuntimeReloader
    build_config_page_context: ConfigPageContextBuilder
    redirect_with_return_to: ConfigRedirector
    friendly_route_error: FriendlyRouteError
    msg: LocalizedMessage
    cookie_name_for_request: CookieNameResolver
    list_prompt_files: PromptLister
    resolve_prompt_file: PromptResolver
    save_text_file_and_maybe_reload: TextFileSaver
    lang_flag: LanguageFlag
    lang_label: LanguageLabel
    available_languages: LanguageRowsGetter
    resolve_lang: LanguageResolver
    clear_i18n_cache: CacheClearer


def register_config_persona_routes(app: FastAPI, deps: ConfigPersonaRouteDeps) -> None:
    @app.get("/config/appearance", response_class=HTMLResponse)
    async def config_appearance_page(request: Request, saved: int = 0, error: str = "") -> HTMLResponse:
        lang = str(getattr(request.state, "lang", "de") or "de")
        settings = deps.get_settings()
        raw = deps.read_raw_config()
        ui_cfg = raw.get("ui", {})
        if not isinstance(ui_cfg, dict):
            ui_cfg = {}
        current_theme = normalize_ui_theme(ui_cfg.get("theme") or getattr(settings.ui, "theme", "matrix"))
        static_dir = deps.base_dir / "aria" / "static"
        current_background = normalize_ui_background(
            ui_cfg.get("background") or getattr(settings.ui, "background", "grid"),
            static_dir=static_dir,
        )
        theme_rows = [
            {"value": "matrix", "label_key": "config_appearance.theme_matrix", "fallback": "Matrix Green"},
            {"value": "sunset", "label_key": "config_appearance.theme_sunset", "fallback": "Sunset Amber"},
            {"value": "harbor", "label_key": "config_appearance.theme_harbor", "fallback": "Harbor Blue"},
            {"value": "paper", "label_key": "config_appearance.theme_paper", "fallback": "Paper Ink"},
            {"value": "cyberpunk", "label_key": "config_appearance.theme_cyberpunk", "fallback": "CyberPunk Classic"},
            {"value": "cyberpunk-neo", "label_key": "config_appearance.theme_cyberpunk_neo", "fallback": "CyberPunk Neo"},
            {"value": "nyan-cat", "label_key": "config_appearance.theme_nyan_cat", "fallback": "Nyan Cat"},
            {"value": "puke-unicorn", "label_key": "config_appearance.theme_puke_unicorn", "fallback": "Puke Unicorn"},
            {"value": "pixel", "label_key": "config_appearance.theme_pixel", "fallback": "8-Bit Arcade"},
            {"value": "crt-amber", "label_key": "config_appearance.theme_crt_amber", "fallback": "Amber CRT"},
            {"value": "deep-space", "label_key": "config_appearance.theme_deep_space", "fallback": "Deep Space"},
        ]
        background_rows = discover_ui_background_files(static_dir)
        context = deps.build_config_page_context(
            request,
            saved=saved,
            error=error,
            logical_back_fallback="/config/persona",
            page_return_to="/config/persona",
            config_nav="persona",
            page_heading=deps.msg(lang, "Erscheinungsbild & Theme", "Appearance & theme"),
        )
        context.update(
            {
                "theme_rows": [row for row in theme_rows if row["value"] in UI_THEME_OPTIONS],
                "background_rows": background_rows,
                "current_theme": current_theme,
                "current_background": current_background,
            }
        )
        return deps.templates.TemplateResponse(request=request, name="config_appearance.html", context=context)

    @app.post("/config/appearance/save")
    async def config_appearance_save(
        request: Request,
        theme: str = Form("matrix"),
        background: str = Form("grid"),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        try:
            raw = deps.read_raw_config()
            raw.setdefault("ui", {})
            if not isinstance(raw["ui"], dict):
                raw["ui"] = {}
            raw["ui"]["theme"] = normalize_ui_theme(theme)
            raw["ui"]["background"] = normalize_ui_background(background, static_dir=deps.base_dir / "aria" / "static")
            deps.write_raw_config(raw)
            deps.reload_runtime()
            return deps.redirect_with_return_to("/config/appearance?saved=1", request, fallback="/config", return_to=return_to)
        except (OSError, ValueError) as exc:
            return deps.redirect_with_return_to(
                f"/config/appearance?error={quote_plus(str(exc))}",
                request,
                fallback="/config",
                return_to=return_to,
            )

    @app.get("/config/language", response_class=HTMLResponse)
    async def config_language_page(request: Request, saved: int = 0, error: str = "", file: str = "") -> HTMLResponse:
        lang = str(getattr(request.state, "lang", "de") or "de")
        settings = deps.get_settings()
        raw = deps.read_raw_config()
        ui_cfg = raw.get("ui", {})
        if not isinstance(ui_cfg, dict):
            ui_cfg = {}
        default_language = str(ui_cfg.get("language", settings.ui.language or "de")).strip().lower() or "de"
        language_rows = [
            {"code": code, "flag": deps.lang_flag(code), "label": deps.lang_label(code)}
            for code in deps.available_languages()
        ]
        selected_file = str(file or "").strip().lower() or f"{default_language}.json"
        if not selected_file.endswith(".json"):
            selected_file += ".json"
        target = deps.base_dir / "aria" / "i18n" / selected_file
        editor_content = ""
        if target.exists():
            try:
                editor_content = target.read_text(encoding="utf-8")
            except OSError:
                editor_content = ""
        context = deps.build_config_page_context(
            request,
            saved=saved,
            error=error,
            logical_back_fallback="/config/persona",
            page_return_to="/config/persona",
            config_nav="persona",
            page_heading=deps.msg(lang, "Sprache", "Language"),
        )
        context.update(
            {
                "language_rows": language_rows,
                "default_language": default_language,
                "selected_file": selected_file,
                "editor_content": editor_content,
            }
        )
        return deps.templates.TemplateResponse(request=request, name="config_language.html", context=context)

    @app.post("/config/language/save")
    async def config_language_save(request: Request, default_language: str = Form(...), return_to: str = Form("")) -> RedirectResponse:
        try:
            settings = deps.get_settings()
            code = deps.resolve_lang(str(default_language).strip().lower(), settings.ui.language)
            raw = deps.read_raw_config()
            raw.setdefault("ui", {})
            if not isinstance(raw["ui"], dict):
                raw["ui"] = {}
            raw["ui"]["language"] = code
            deps.write_raw_config(raw)
            deps.reload_runtime()
            request.state.lang = code
            response = deps.redirect_with_return_to("/config/language?saved=1", request, fallback="/config", return_to=return_to)
            response.set_cookie(
                key=deps.cookie_name_for_request(request, "lang", deps.lang_cookie),
                value=code,
                max_age=60 * 60 * 24 * 365,
                samesite="lax",
                secure=cookie_should_be_secure(request, public_url=str(settings.aria.public_url or "")),
                httponly=False,
            )
            return response
        except (OSError, ValueError) as exc:
            return deps.redirect_with_return_to(
                f"/config/language?error={quote_plus(str(exc))}",
                request,
                fallback="/config",
                return_to=return_to,
            )

    @app.post("/config/language/file/save")
    async def config_language_file_save(
        request: Request,
        file_name: str = Form(...),
        content: str = Form(...),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        try:
            clean = str(file_name).strip().lower()
            if not re.fullmatch(r"[a-z0-9_-]+\.json", clean):
                raise ValueError("Ungültiger Dateiname.")
            target = deps.base_dir / "aria" / "i18n" / clean
            payload = json.loads(content)
            if not isinstance(payload, dict):
                raise ValueError("Sprachdatei muss ein JSON-Objekt sein.")
            target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            deps.clear_i18n_cache()
            return deps.redirect_with_return_to(
                f"/config/language?file={quote_plus(clean)}&saved=1",
                request,
                fallback="/config",
                return_to=return_to,
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return deps.redirect_with_return_to(
                f"/config/language?file={quote_plus(str(file_name))}&error={quote_plus(str(exc))}",
                request,
                fallback="/config",
                return_to=return_to,
            )

    @app.get("/config/prompts", response_class=HTMLResponse)
    async def config_prompts_page(
        request: Request,
        file: str | None = None,
        saved: int = 0,
        error: str = "",
    ) -> HTMLResponse:
        lang = str(getattr(request.state, "lang", "de") or "de")
        rows = deps.list_prompt_files()
        selected = file or (rows[0]["path"] if rows else "")
        content = ""
        if selected:
            try:
                selected_path = deps.resolve_prompt_file(selected)
                if not selected_path.exists():
                    raise ValueError("Datei existiert nicht.")
                content = selected_path.read_text(encoding="utf-8")
            except (OSError, ValueError) as exc:
                error = deps.friendly_route_error(
                    lang,
                    exc,
                    "Prompt-Datei konnte nicht geladen werden.",
                    "Could not load prompt file.",
                )
                content = ""
        selected_row = next((row for row in rows if row.get("path") == selected), None)
        context = deps.build_config_page_context(
            request,
            saved=saved,
            error=error,
            logical_back_fallback="/config/persona",
            page_return_to="/config/persona",
            config_nav="persona",
            page_heading=deps.msg(lang, "Prompt Studio", "Prompt studio"),
        )
        context.update(
            {
                "rows": rows,
                "selected_file": selected,
                "selected_row": selected_row,
                "file_content": content,
            }
        )
        return deps.templates.TemplateResponse(request=request, name="config_prompts.html", context=context)

    @app.post("/config/prompts/save")
    async def config_prompts_save(
        request: Request,
        file: str = Form(...),
        content: str = Form(...),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        try:
            target = deps.resolve_prompt_file(file)
            if not target.exists():
                raise ValueError("Datei existiert nicht.")
            _saved, reload_message = deps.save_text_file_and_maybe_reload(target, content)
            target_url = f"/config/prompts?file={quote_plus(file)}&saved=1"
            if reload_message:
                target_url += f"&error={quote_plus(reload_message)}"
            return deps.redirect_with_return_to(target_url, request, fallback="/config", return_to=return_to)
        except (OSError, ValueError) as exc:
            lang = str(getattr(request.state, "lang", "de") or "de")
            error = deps.friendly_route_error(
                lang,
                exc,
                "Prompt-Datei konnte nicht gespeichert werden.",
                "Could not save prompt file.",
            )
            return deps.redirect_with_return_to(
                f"/config/prompts?file={quote_plus(file)}&error={quote_plus(error)}",
                request,
                fallback="/config",
                return_to=return_to,
            )
