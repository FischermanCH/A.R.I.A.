from __future__ import annotations

import html
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from markupsafe import Markup

from aria.core.capability_catalog import capability_badge
from aria.core.i18n import I18NStore
from aria.web.recipe_ui_contract import RECIPE_STATUS_BADGE_LABEL
from aria.web.recipe_ui_contract import STORED_RECIPE_BADGE_LABEL
from aria.web.stored_recipe_ui import build_stored_recipe_progress_hint

try:
    import markdown as markdown_lib
except ModuleNotFoundError:  # pragma: no cover - runtime dependency fallback
    markdown_lib = None

LANGUAGE_LABELS = {
    "de": "Deutsch",
    "en": "English",
}
_MAIN_UI_I18N = I18NStore(Path(__file__).resolve().parents[1] / "i18n")

_MARKDOWN_LINK_RE = re.compile(r"\[(.+?)\]\(((?:https?://|/)[^\s)]+)\)")


def _main_ui_text(language: str | None, key: str, default: str = "", **values: Any) -> str:
    template = _MAIN_UI_I18N.t(language or "de", f"main_ui.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template


def replace_agent_name(text: str, agent_name: str) -> str:
    raw = str(text or "")
    clean_name = str(agent_name or "").strip() or "ARIA"
    return re.sub(r"\b(?:ARIA|Aria)\b", clean_name, raw)


def build_client_recipe_progress_hints(stored_recipe_manifests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for manifest in stored_recipe_manifests:
        row = build_stored_recipe_progress_hint(manifest)
        if row:
            rows.append(row)
    return rows


def build_client_skill_progress_hints(custom_manifests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return build_client_recipe_progress_hints(custom_manifests)


def daily_time_to_cron(value: str) -> str:
    text = str(value or "").strip()
    if not re.fullmatch(r"\d{2}:\d{2}", text):
        raise ValueError(_main_ui_text("de", "time_format_error", "Time must use HH:MM format."))
    hour = int(text[:2])
    minute = int(text[3:5])
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ValueError(_main_ui_text("de", "time_range_error", "Time is outside valid bounds."))
    return f"{minute} {hour} * * *"


def daily_time_from_cron(value: str) -> str:
    raw = str(value or "").strip()
    match = re.fullmatch(r"(\d{1,2})\s+(\d{1,2})\s+\*\s+\*\s+\*", raw)
    if not match:
        return ""
    minute = int(match.group(1))
    hour = int(match.group(2))
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return ""
    return f"{hour:02d}:{minute:02d}"


def normalize_keyword_list(values: list[str], max_items: int = 20) -> list[str]:
    rows: list[str] = []
    seen: set[str] = set()
    for raw in values:
        text = str(raw).strip().lower()
        text = re.sub(r"^[\-\*\d\.\)\s]+", "", text)
        text = text.strip(" \"'`;,")
        text = re.sub(r"\s+", " ", text)
        if not text or len(text) < 2 or text in seen:
            continue
        seen.add(text)
        rows.append(text[:80])
        if len(rows) >= max_items:
            break
    return rows


def extract_keyword_candidates(text: str) -> list[str]:
    raw = str(text or "").strip()
    if not raw:
        return []
    parsed: list[str] = []
    try:
        payload = json.loads(raw)
        if isinstance(payload, dict):
            values = payload.get("keywords", [])
            if isinstance(values, list):
                parsed = [str(item) for item in values]
        elif isinstance(payload, list):
            parsed = [str(item) for item in payload]
    except json.JSONDecodeError:
        pass
    if parsed:
        return normalize_keyword_list(parsed)
    lines: list[str] = []
    for row in raw.splitlines():
        parts = [piece.strip() for piece in row.split(",")]
        for part in parts:
            if part:
                lines.append(part)
    return normalize_keyword_list(lines)


def render_assistant_message_html(text: str) -> Markup:
    lines: list[str] = []
    for raw_line in str(text or "").splitlines():
        escaped_line = html.escape(str(raw_line or ""))

        def _replace_link(match: re.Match[str]) -> str:
            label = html.escape(match.group(1))
            url = html.escape(match.group(2), quote=True)
            return f'<a href="{url}" target="_blank" rel="noopener noreferrer">{label}</a>'

        rendered_line = _MARKDOWN_LINK_RE.sub(_replace_link, escaped_line)
        lines.append(rendered_line)
    return Markup("<br>".join(lines))


def intent_badge(intents: list[str], recipe_errors: list[str] | None = None) -> tuple[str, str]:
    from aria.core.recipe_runtime_contract import RECIPE_STATUS_INTENT
    from aria.core.recipe_runtime_contract import is_recipe_intent
    from aria.core.recipe_runtime_contract import is_recipe_status_intent

    if recipe_errors:
        text = " ".join(recipe_errors).lower()
        if "external_http_api_status" in text:
            for intent in intents:
                if not str(intent).startswith("capability:"):
                    continue
                badge = capability_badge(str(intent).split(":", 1)[1])
                if badge:
                    return badge
        if "memory_unavailable" in text:
            return "⚠", "memory_unavailable"
        if "embedding_failed" in text:
            return "⚠", "embedding_failed"
        if "capability_" in text:
            for intent in intents:
                if not str(intent).startswith("capability:"):
                    continue
                badge = capability_badge(str(intent).split(":", 1)[1])
                if badge:
                    return badge
            return "⚠", "capability_error"
        return "⚠", "memory_error"
    if "memory_recall" in intents:
        return "🧠", "memory_recall"
    if "memory_store" in intents:
        return "💾", "memory_store"
    if any(is_recipe_status_intent(intent) for intent in intents):
        return "🧩", RECIPE_STATUS_BADGE_LABEL
    for intent in intents:
        if is_recipe_intent(str(intent)):
            return "🧩", STORED_RECIPE_BADGE_LABEL
    for intent in intents:
        if not str(intent).startswith("capability:"):
            continue
        badge = capability_badge(str(intent).split(":", 1)[1])
        if badge:
            return badge
    if "connection_delete" in intents:
        return "🗑", "connection_delete"
    if "connection_create" in intents:
        return "🧩", "connection_create"
    if "connection_update" in intents:
        return "🛠", "connection_update"
    return "💬", "chat"


def friendly_error_text(recipe_errors: list[str] | None, *, language: str = "de") -> str:
    text = " ".join(recipe_errors or []).lower()
    if "external_http_api_status" in text:
        return ""
    if "_guardrail_blocked" in text:
        return ""
    if "memory_unavailable" in text:
        return _main_ui_text(language, "memory_unavailable", "Memory service is unavailable. I will answer without stored knowledge.")
    if "embedding_failed" in text:
        return _main_ui_text(language, "embedding_failed", "Text processing failed. Please check the embedding model/API key.")
    if "memory_error" in text:
        return _main_ui_text(language, "memory_error", "Memory processing failed. I will answer without memory context.")
    if "capability_" in text:
        return _main_ui_text(language, "capability_error", "The action could not be completed. Please check profile, target, and access rights.")
    return ""


def should_alert_recipe_errors(recipe_errors: list[str] | None) -> bool:
    cleaned = [str(item or "").strip().lower() for item in list(recipe_errors or []) if str(item or "").strip()]
    if not cleaned:
        return False
    quiet_prefixes = ("external_http_api_status",)
    quiet_markers = ("_guardrail_blocked",)
    return any(
        not item.startswith(quiet_prefixes) and not any(marker in item for marker in quiet_markers)
        for item in cleaned
    )


def discord_alert_error_lines(recipe_errors: list[str] | None, *, limit: int = 4) -> str:
    cleaned_rows: list[str] = []
    for raw in list(recipe_errors or [])[: max(1, int(limit or 4))]:
        text = str(raw or "").strip()
        if not text:
            continue
        first_line = ""
        for line in text.splitlines():
            candidate = str(line or "").strip()
            if not candidate:
                continue
            if candidate.startswith("====================") or candidate.startswith("SMB Header:") or candidate.startswith("SMB Data Packet"):
                break
            first_line = candidate
            break
        if not first_line:
            first_line = text.splitlines()[0].strip() if text.splitlines() else text
        first_line = re.sub(r"\s+", " ", first_line).strip()
        if len(first_line) > 220:
            first_line = first_line[:220].rstrip() + "…"
        cleaned_rows.append(first_line)
    return " | ".join(cleaned_rows)


def exception_response(request: Request, *, detail: str, status_code: int = 500) -> Response:
    lang = str(getattr(request.state, "lang", "de") or "de")
    clean_detail = str(detail or "").strip() or _main_ui_text(lang, "unexpected_error", "Unexpected error.")
    path = str(request.url.path or "").strip()
    accept = str(request.headers.get("accept", "") or "").lower()
    agent_name = str(getattr(request.state, "agent_name", "") or "ARIA").strip() or "ARIA"
    if path == "/chat":
        return JSONResponse(status_code=status_code, content={"detail": clean_detail})
    if "text/html" in accept:
        html_body = (
            f"<!DOCTYPE html><html lang='{html.escape(lang[:2] or 'de')}'><head><meta charset='UTF-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1.0'>"
            f"<title>{html.escape(_main_ui_text(lang, 'error_title', '{agent_name} error', agent_name=agent_name))}</title><link rel='stylesheet' href='/static/style.css'></head>"
            "<body><main class='config-layout'><section class='config-card'>"
            f"<h2>{html.escape(_main_ui_text(lang, 'page_load_failed', '{agent_name} could not load this page cleanly.', agent_name=agent_name))}</h2>"
            f"<p>{html.escape(clean_detail)}</p>"
            f"<p><a class='nav-link' href='/'>{html.escape(_main_ui_text(lang, 'back_to_chat', 'Back to chat'))}</a></p>"
            "</section></main></body></html>"
        )
        return HTMLResponse(status_code=status_code, content=html_body)
    return JSONResponse(status_code=status_code, content={"detail": clean_detail})


def lang_flag(code: str) -> str:
    lang = str(code or "").strip().lower()
    if lang.startswith("de"):
        return "🇩🇪"
    if lang.startswith("en"):
        return "🇬🇧"
    if len(lang) >= 2 and lang[:2].isalpha():
        pair = lang[:2].upper()
        return chr(ord(pair[0]) + 127397) + chr(ord(pair[1]) + 127397)
    return "🏳️"


def lang_label(code: str) -> str:
    lang = str(code or "").strip().lower()
    return LANGUAGE_LABELS.get(lang, lang.upper() or "LANG")


def current_memory_day() -> str:
    return datetime.now().strftime("%y%m%d")


def parse_collection_day_suffix(name: str) -> datetime | None:
    raw = str(name).strip()
    if len(raw) < 6:
        return None
    suffix = raw[-6:]
    if not suffix.isdigit():
        return None
    try:
        return datetime.strptime(suffix, "%y%m%d")
    except ValueError:
        return None


def read_doc_text(base_dir: Path, relative_path: str) -> str:
    doc_path = base_dir / relative_path
    if not doc_path.exists():
        return ""
    try:
        return doc_path.read_text(encoding="utf-8")
    except OSError:
        return ""


def localized_doc_path(base_dir: Path, relative_path: str, lang: str) -> str:
    clean_lang = str(lang or "").strip().lower()
    if not clean_lang:
        return relative_path
    doc_path = Path(relative_path)
    if doc_path.suffix.lower() != ".md":
        return relative_path
    lang_code = clean_lang[:2]
    if lang_code not in {"de", "en"}:
        return relative_path
    localized_name = f"{doc_path.stem}.{lang_code}{doc_path.suffix}"
    localized_path = doc_path.with_name(localized_name)
    if (base_dir / localized_path).exists():
        return localized_path.as_posix()
    return relative_path


def render_markdown_doc(text: str) -> Markup:
    if not text.strip():
        return Markup("")
    if markdown_lib is None:
        return Markup(f"<pre>{html.escape(text)}</pre>")
    rendered = markdown_lib.markdown(
        text,
        extensions=["fenced_code", "tables", "sane_lists"],
        output_format="html5",
    )
    return Markup(rendered)
