from __future__ import annotations

import contextlib
import html
import io
import imaplib
import json
import posixpath
import re
import smtplib
import xml.etree.ElementTree as ET
from datetime import datetime, time as dt_time, timedelta, timezone
from email import message_from_bytes
from email.header import make_header, decode_header
from email.message import EmailMessage
from email.utils import parsedate_to_datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Awaitable, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, quote, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import Request as URLRequest, urlopen

from aria.core.auto_memory import AutoMemoryExtractor
from aria.core.config import RoutingLanguageConfig
from aria.core.guardrails import evaluate_guardrail, resolve_guardrail_profile
from aria.core.notes_context import search_note_hits
from aria.core.safe_fix import format_held_packages_summary
from aria.skills.base import SkillResult


SSHExecutor = Callable[..., Awaitable[SkillResult]]
BASE_DIR = Path(__file__).resolve().parents[2]
_RSS_HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36 ARIA/1.0"
    ),
    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*;q=0.8",
}
_SKILL_ID_INVALID_RE = re.compile(r"[^a-z0-9_-]")
_SKILL_ID_DASH_RE = re.compile(r"-+")
_JSON_FENCE_START_RE = re.compile(r"^```(?:json)?\s*", re.IGNORECASE)
_JSON_FENCE_END_RE = re.compile(r"\s*```$")
_SKILL_TOKEN_SPLIT_RE = re.compile(r"[^a-z0-9]+")
_CONDITION_SOURCE_RE = re.compile(r"[^a-z0-9_-]")
_FEED_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


@lru_cache(maxsize=128)
def _compile_condition_regex(pattern: str, flags: int) -> re.Pattern[str]:
    return re.compile(pattern, flags=flags)


def _is_english(language: str | None) -> bool:
    return str(language or "").strip().lower().startswith("en")


def _msg(language: str | None, de: str, en: str) -> str:
    return en if _is_english(language) else de


def sanitize_skill_id(value: str) -> str:
    raw = str(value or "").strip().lower()
    raw = _SKILL_ID_INVALID_RE.sub("-", raw)
    raw = _SKILL_ID_DASH_RE.sub("-", raw).strip("-")
    return raw[:48]


def normalize_skill_keywords(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    rows: list[str] = []
    for item in value:
        text = str(item or "").strip().lower()
        if text:
            rows.append(text)
    return rows[:30]


def _extract_json_object(raw: str) -> dict[str, Any] | None:
    text = str(raw or "").strip()
    if not text:
        return None
    if text.startswith("```"):
        text = _JSON_FENCE_START_RE.sub("", text)
        text = _JSON_FENCE_END_RE.sub("", text)
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        payload = json.loads(text[start : end + 1])
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


_SKILL_MATCH_STOPWORDS = {
    "auf",
    "aus",
    "bei",
    "bitte",
    "das",
    "dem",
    "den",
    "der",
    "die",
    "du",
    "ein",
    "eine",
    "einen",
    "einer",
    "einem",
    "er",
    "es",
    "fuer",
    "für",
    "im",
    "in",
    "ist",
    "mach",
    "machst",
    "mir",
    "mit",
    "nach",
    "noch",
    "oder",
    "per",
    "the",
    "und",
    "uns",
    "via",
    "vom",
    "von",
    "was",
    "wie",
}

_SKILL_ACTION_HINTS = {
    "aktualisiere",
    "analyse",
    "analysiere",
    "build",
    "check",
    "deploy",
    "diagnose",
    "execute",
    "fix",
    "mach",
    "machst",
    "patch",
    "patchen",
    "prüf",
    "pruef",
    "report",
    "run",
    "send",
    "starte",
    "start",
    "teste",
    "trigger",
    "update",
    "upgrade",
}


def _skill_tokens(value: str) -> list[str]:
    return [token for token in _SKILL_TOKEN_SPLIT_RE.split(str(value or "").lower()) if token]


def _significant_skill_tokens(value: str) -> list[str]:
    rows: list[str] = []
    for token in _skill_tokens(value):
        if len(token) < 4:
            continue
        if token in _SKILL_MATCH_STOPWORDS:
            continue
        if token not in rows:
            rows.append(token)
    return rows


def _skill_match_score(message: str, row: dict[str, Any]) -> int:
    lower = str(message or "").strip().lower()
    if not lower:
        return 0
    message_tokens = set(_significant_skill_tokens(lower))
    if not message_tokens:
        return 0

    best_score = 0
    keywords = row.get("keywords", [])
    if isinstance(keywords, list):
        for keyword in keywords:
            phrase = str(keyword or "").strip().lower()
            if not phrase:
                continue
            if phrase in lower:
                best_score = max(best_score, 120 + len(phrase))
                continue
            phrase_tokens = _significant_skill_tokens(phrase)
            if not phrase_tokens:
                continue
            first_token = phrase_tokens[0]
            if first_token not in message_tokens:
                continue
            overlap = sum(1 for token in phrase_tokens if token in message_tokens)
            if overlap == len(phrase_tokens) and overlap >= 2:
                best_score = max(best_score, 95 + overlap * 10 + len(phrase_tokens))
                continue
            if overlap >= 2:
                best_score = max(best_score, 55 + overlap * 12)

    name_tokens = set(_significant_skill_tokens(str(row.get("name", ""))))
    if name_tokens:
        overlap = len(name_tokens & message_tokens)
        if overlap >= 2:
            best_score = max(best_score, 48 + overlap * 9)

    skill_id_tokens = set(_significant_skill_tokens(str(row.get("id", ""))))
    if skill_id_tokens:
        overlap = len(skill_id_tokens & message_tokens)
        if overlap >= 2:
            best_score = max(best_score, 52 + overlap * 10)

    description_tokens = set(_significant_skill_tokens(str(row.get("description", ""))))
    if description_tokens:
        overlap = len(description_tokens & message_tokens)
        if overlap >= 3:
            best_score = max(best_score, 42 + overlap * 8)

    combined_tokens = set()
    combined_tokens.update(name_tokens)
    combined_tokens.update(skill_id_tokens)
    combined_tokens.update(description_tokens)
    if isinstance(keywords, list):
        for keyword in keywords:
            combined_tokens.update(_significant_skill_tokens(str(keyword or "")))
    action_overlap = len(combined_tokens & message_tokens)
    if action_overlap >= 2 and any(token in _SKILL_ACTION_HINTS for token in _skill_tokens(lower)):
        best_score = max(best_score, 58 + action_overlap * 7)

    connections = row.get("connections", [])
    if isinstance(connections, list):
        connection_tokens = {token for item in connections for token in _significant_skill_tokens(str(item))}
        overlap = len(connection_tokens & message_tokens)
        if overlap >= 1 and best_score > 0:
            best_score += 6

    return best_score


def _looks_like_skill_execution_request(message: str) -> bool:
    tokens = set(_skill_tokens(message))
    if not tokens:
        return False
    if any(token in _SKILL_ACTION_HINTS for token in tokens):
        return True
    phrases = (
        "kannst du",
        "machst du",
        "fuehr",
        "führ",
        "bitte ",
    )
    lower = str(message or "").strip().lower()
    return any(phrase in lower for phrase in phrases)


def normalize_skill_steps(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    steps: list[dict[str, Any]] = []
    for idx, raw in enumerate(value):
        if not isinstance(raw, dict):
            continue
        step_type = str(raw.get("type", "")).strip().lower()
        if step_type not in {"ssh_run", "llm_transform", "discord_send", "chat_send", "sftp_read", "sftp_write", "smb_read", "smb_write", "rss_read"}:
            continue
        step_id = str(raw.get("id", "")).strip().lower() or f"s{idx + 1}"
        step_name = str(raw.get("name", "")).strip()[:80]
        params = raw.get("params", {})
        if not isinstance(params, dict):
            params = {}
        norm_params = {str(k).strip(): str(v).strip() for k, v in params.items() if str(k).strip()}
        condition = raw.get("condition", {})
        norm_condition: dict[str, Any] | None = None
        if isinstance(condition, dict):
            source = str(condition.get("source", "")).strip().lower()
            operator = str(condition.get("operator", "")).strip().lower()
            if operator in {"equals", "not_equals", "contains", "not_contains", "regex", "is_empty", "not_empty"}:
                norm_condition = {
                    "source": _CONDITION_SOURCE_RE.sub("", source)[:40],
                    "operator": operator,
                    "value": str(condition.get("value", "")).strip()[:1200],
                    "ignore_case": bool(condition.get("ignore_case", False)),
                }
        row = {
            "id": step_id[:20],
            "name": step_name,
            "type": step_type,
            "params": norm_params,
            "on_error": str(raw.get("on_error", "stop")).strip().lower() or "stop",
        }
        if norm_condition:
            row["condition"] = norm_condition
        steps.append(row)
    return steps


def _evaluate_skill_step_condition(condition: dict[str, Any], values: dict[str, str]) -> bool:
    source = str(condition.get("source", "")).strip().lower()
    operator = str(condition.get("operator", "")).strip().lower()
    expected = str(condition.get("value", ""))
    ignore_case = bool(condition.get("ignore_case", False))
    actual = str(values.get(source, "")) if source else ""

    if ignore_case:
        actual_cmp = actual.lower()
        expected_cmp = expected.lower()
    else:
        actual_cmp = actual
        expected_cmp = expected

    if operator == "equals":
        return actual_cmp == expected_cmp
    if operator == "not_equals":
        return actual_cmp != expected_cmp
    if operator == "contains":
        return expected_cmp in actual_cmp
    if operator == "not_contains":
        return expected_cmp not in actual_cmp
    if operator == "regex":
        flags = re.IGNORECASE if ignore_case else 0
        try:
            return _compile_condition_regex(expected, flags).search(actual) is not None
        except re.error:
            return False
    if operator == "is_empty":
        return not actual.strip()
    if operator == "not_empty":
        return bool(actual.strip())
    return True


def render_step_template(template: str, values: dict[str, str]) -> str:
    rendered = str(template or "")
    for key, value in values.items():
        rendered = rendered.replace("{" + key + "}", str(value))
    return rendered


def _format_ssh_step_run_summary(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""
    lines = ["Technischer Lauf:"]
    for row in rows:
        connection_ref = str(row.get("connection_ref", "")).strip()
        target = str(row.get("target", "")).strip()
        exit_code = int(row.get("exit_code", 0) or 0)
        duration = float(row.get("duration_seconds", 0.0) or 0.0)
        held = row.get("held_packages", [])
        warnings = row.get("warning_hints", [])
        status = "ok" if exit_code == 0 else f"Exit {exit_code}"
        details = [status, f"{duration:.1f}s"]
        if isinstance(held, list) and held:
            details.append(f"{len(held)} gehalten")
        if isinstance(warnings, list) and warnings:
            details.append("Warnungen: " + ", ".join(str(item) for item in warnings if str(item).strip()))
        place = f"{connection_ref} ({target})" if target else connection_ref
        lines.append(f"- {place}: " + ", ".join(details))
    return "\n".join(lines)


def load_custom_skill_toggles(config_path: Path) -> dict[str, bool]:
    try:
        if not config_path.exists():
            return {}
        import yaml

        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            return {}
        skills = raw.get("skills", {})
        if not isinstance(skills, dict):
            return {}
        custom = skills.get("custom", {})
        if not isinstance(custom, dict):
            return {}
        toggles: dict[str, bool] = {}
        for key, section in custom.items():
            skill_id = sanitize_skill_id(str(key))
            if not skill_id or not isinstance(section, dict):
                continue
            toggles[skill_id] = bool(section.get("enabled", True))
        return toggles
    except Exception:
        return {}


def load_custom_skill_runtime(
    *,
    skills_dir: Path,
    config_path: Path,
    cache: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        skills_dir.mkdir(parents=True, exist_ok=True)
        files = [path for path in sorted(skills_dir.glob("*.json")) if not path.name.startswith("_")]
        sign = tuple((file.name, file.stat().st_mtime) for file in files)
        if sign == cache.get("sign"):
            return list(cache.get("rows", [])), cache

        toggles = load_custom_skill_toggles(config_path)
        rows: list[dict[str, Any]] = []
        for path in files:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(payload, dict):
                    continue
                skill_id = sanitize_skill_id(payload.get("id", ""))
                name = str(payload.get("name", "")).strip()
                if not skill_id or not name:
                    continue
                connections = payload.get("connections", [])
                if not isinstance(connections, list):
                    connections = []
                steps = normalize_skill_steps(payload.get("steps", []))
                if not steps:
                    continue
                rows.append(
                    {
                        "id": skill_id,
                        "name": name[:80],
                        "keywords": normalize_skill_keywords(payload.get("router_keywords", [])),
                        "connections": [str(item).strip().lower() for item in connections if str(item).strip()][:20],
                        "description": str(payload.get("description", "")).strip()[:400],
                        "steps": steps,
                        "enabled": bool(toggles.get(skill_id, bool(payload.get("enabled_default", True)))),
                    }
                )
            except Exception:
                continue
        next_cache = {"sign": sign, "rows": rows}
        return list(rows), next_cache
    except Exception:
        return [], cache


def match_custom_skill_intents(message: str, runtime_skills: list[dict[str, Any]]) -> list[str]:
    text = str(message or "").strip()
    if not text:
        return []
    scored: list[tuple[int, str]] = []
    for row in runtime_skills:
        if not row.get("enabled", False):
            continue
        skill_id = str(row.get("id", "")).strip()
        if not skill_id:
            continue
        score = _skill_match_score(text, row)
        if score >= 55:
            scored.append((score, skill_id))
    if not scored:
        return []
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [f"custom_skill:{skill_id}" for _, skill_id in scored[:3]]


async def resolve_custom_skill_intent_with_llm(
    message: str,
    runtime_skills: list[dict[str, Any]],
    llm_client: Any | None,
) -> list[str]:
    if llm_client is None:
        return []
    clean_message = str(message or "").strip()
    if not clean_message:
        return []
    if not _looks_like_skill_execution_request(clean_message):
        return []

    rows_for_prompt: list[str] = []
    valid_ids: set[str] = set()
    for row in runtime_skills:
        if not bool(row.get("enabled", False)):
            continue
        skill_id = str(row.get("id", "")).strip()
        if not skill_id:
            continue
        valid_ids.add(skill_id)
        keywords = row.get("keywords", [])
        if not isinstance(keywords, list):
            keywords = []
        connections = row.get("connections", [])
        if not isinstance(connections, list):
            connections = []
        rows_for_prompt.append(
            "\n".join(
                [
                    f"- id: {skill_id}",
                    f"  name: {str(row.get('name', '')).strip() or skill_id}",
                    f"  description: {str(row.get('description', '')).strip() or '-'}",
                    f"  connections: {', '.join(str(item).strip() for item in connections if str(item).strip()) or '-'}",
                    f"  keywords: {', '.join(str(item).strip() for item in keywords if str(item).strip()) or '-'}",
                ]
            )
        )
    if not valid_ids:
        return []

    system_prompt = (
        "Du waehlst genau einen passenden Custom Skill fuer eine Nutzeranfrage aus. "
        "Antworte nur als JSON im Format "
        '{"id":"<skill-id oder leer>","confidence":"high|medium|low","reason":"kurz"}. '
        "Waehle nur einen Skill aus der Liste. Wenn nichts wirklich passt, gib eine leere id zurueck. "
        "Bevorzuge nur dann medium oder high, wenn die Anfrage klar nach einer Ausfuehrung oder Aktion klingt."
    )
    user_prompt = "\n".join(
        [
            f"Nutzeranfrage: {clean_message}",
            "",
            "Verfuegbare Skills:",
            *rows_for_prompt,
        ]
    )
    try:
        response = await llm_client.chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
        )
    except Exception:
        return []

    payload = _extract_json_object(getattr(response, "content", "") or "") or {}
    skill_id = str(payload.get("id", "")).strip()
    confidence = str(payload.get("confidence", "")).strip().lower()
    if confidence not in {"high", "medium"}:
        return []
    if skill_id not in valid_ids:
        return []
    return [f"custom_skill:{skill_id}"]


def should_skip_auto_memory_persist(intents: list[str]) -> bool:
    normalized = [str(intent).strip().lower() for intent in intents]
    if "skill_status" in normalized:
        return True
    return any(intent.startswith("custom_skill:") for intent in normalized)


def build_skill_status_text(settings: Any, runtime_custom_skills: list[dict[str, Any]], auto_memory_enabled: bool) -> str:
    lines = ["Skills (Runtime-Status):", ""]
    searxng_rows = getattr(getattr(settings, "connections", object()), "searxng", {})
    core_rows = [
        ("Memory", bool(settings.memory.enabled), "Speichert und ruft Wissen via Qdrant ab."),
        ("Auto-Memory", bool(auto_memory_enabled), "Extrahiert Fakten/Präferenzen automatisch aus Chat-Nachrichten."),
        (
            "Web Search",
            bool(isinstance(searxng_rows, dict) and searxng_rows),
            "Durchsucht das Web ueber SearXNG und liefert Quellen direkt im Chat.",
        ),
    ]
    custom_rows: list[tuple[str, bool, str]] = []
    for row in sorted(runtime_custom_skills, key=lambda item: str(item.get("name", "")).lower()):
        name = str(row.get("name", "")).strip() or str(row.get("id", "custom"))
        enabled = bool(row.get("enabled", False))
        description = str(row.get("description", "")).strip() or "Kein Zweck hinterlegt."
        connections = row.get("connections", [])
        if isinstance(connections, list) and connections:
            conn_text = ", ".join(str(item).strip() for item in connections if str(item).strip())
            if conn_text:
                description = f"{description} (Connections: {conn_text})"
        custom_rows.append((name, enabled, description))

    active_rows: list[tuple[str, str, str]] = []
    inactive_rows: list[tuple[str, str, str]] = []
    for name, enabled, purpose in core_rows:
        (active_rows if enabled else inactive_rows).append(("Core", name, purpose))
    for name, enabled, purpose in custom_rows:
        (active_rows if enabled else inactive_rows).append(("Custom", name, purpose))

    lines.append("Aktiv:")
    if active_rows:
        for kind, name, purpose in active_rows:
            lines.append(f"- [{kind}] {name} — {purpose}")
    else:
        lines.append("- Keine aktiven Skills.")

    lines.append("")
    lines.append("Deaktiviert:")
    if inactive_rows:
        for kind, name, purpose in inactive_rows:
            lines.append(f"- [{kind}] {name} — {purpose}")
    else:
        lines.append("- Keine deaktivierten Skills.")
    return "\n".join(lines)


class CustomSkillRuntime:
    _feed_tracking_keys = {
        "wt_mc",
        "fbclid",
        "gclid",
        "mc_cid",
        "mc_eid",
        "igshid",
        "mkt_tok",
    }

    def __init__(
        self,
        *,
        settings: Any,
        llm_client: Any,
        memory_skill_getter: Callable[[], Any],
        web_search_skill_getter: Callable[[], Any],
        execute_custom_ssh_command: SSHExecutor,
        extract_memory_store_text: Callable[..., str],
        extract_memory_recall_query: Callable[..., str],
        extract_web_search_query: Callable[..., str],
        facts_collection_for_user: Callable[[str], str],
        preferences_collection_for_user: Callable[[str], str],
        normalize_spaces: Callable[[str], str],
        truncate_text: Callable[[str, int], str],
    ) -> None:
        self.settings = settings
        self.llm_client = llm_client
        self.memory_skill_getter = memory_skill_getter
        self.web_search_skill_getter = web_search_skill_getter
        self.execute_custom_ssh_command = execute_custom_ssh_command
        self.extract_memory_store_text = extract_memory_store_text
        self.extract_memory_recall_query = extract_memory_recall_query
        self.extract_web_search_query = extract_web_search_query
        self.facts_collection_for_user = facts_collection_for_user
        self.preferences_collection_for_user = preferences_collection_for_user
        self.normalize_spaces = normalize_spaces
        self.truncate_text = truncate_text

    def _resolve_local_path(self, value: str) -> Path:
        path = Path(str(value or "").strip())
        if not path.is_absolute():
            path = (BASE_DIR / path).resolve()
        return path

    def _get_connection_profile(self, kind: str, connection_ref: str) -> Any:
        rows = getattr(getattr(self.settings, "connections", object()), str(kind).strip().lower(), {})
        connection = rows.get(connection_ref) if isinstance(rows, dict) else None
        if connection is None:
            raise ValueError(f"{str(kind).upper()}-Profil nicht gefunden: {connection_ref}")
        return connection

    def _enforce_connection_guardrail(
        self,
        *,
        connection: Any,
        connection_ref: str,
        guardrail_kind: str,
        evaluation_text: str,
        label: str,
    ) -> None:
        guardrail_ref = str(getattr(connection, "guardrail_ref", "") or "").strip()
        if not guardrail_ref:
            return
        guardrail_profile = resolve_guardrail_profile(self.settings, guardrail_ref)
        decision = evaluate_guardrail(
            profile_ref=guardrail_ref,
            profile=guardrail_profile,
            kind=guardrail_kind,
            text=evaluation_text,
        )
        if decision.allowed:
            return
        if decision.reason.startswith("guardrail_kind_mismatch"):
            raise ValueError(f"{label}-Guardrail-Typ passt nicht: {guardrail_ref}")
        if decision.reason == "guardrail_denied":
            raise ValueError(f"{label}-Guardrail blockiert die Anfrage: {guardrail_ref}")
        if decision.reason == "guardrail_not_allowed":
            raise ValueError(f"{label}-Guardrail erlaubt diese Anfrage nicht: {guardrail_ref}")
        raise ValueError(f"{label}-Guardrail blockiert die Anfrage: {guardrail_ref}")

    def _enforce_file_guardrail(
        self,
        *,
        connection: Any,
        operation: str,
        resolved_path: str,
        content: str = "",
    ) -> None:
        eval_parts = [str(operation or "").strip().lower(), str(resolved_path or "").strip()]
        if content:
            eval_parts.append(str(content).strip())
        self._enforce_connection_guardrail(
            connection=connection,
            connection_ref="",
            guardrail_kind="file_access",
            evaluation_text=" ".join(part for part in eval_parts if part),
            label="Datei",
        )

    def _format_directory_listing(self, transport: str, resolved_path: str, names: list[str], *, language: str = "de") -> str:
        if not names:
            return _msg(language, f"{transport}-Verzeichnis leer: {resolved_path}", f"{transport} directory is empty: {resolved_path}")
        prefix = _msg(language, f"Inhalt von {resolved_path}:", f"Contents of {resolved_path}:")
        return self.truncate_text(prefix + "\n- " + "\n- ".join(names), 1400)

    @staticmethod
    def _xml_name(tag: str) -> str:
        raw = str(tag or "")
        return raw.split("}", 1)[-1].lower()

    @classmethod
    def _clean_feed_url(cls, value: str) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        try:
            parts = urlsplit(raw)
            query_pairs = []
            for key, item in parse_qsl(parts.query, keep_blank_values=True):
                lower_key = str(key or "").strip().lower()
                if lower_key.startswith("utm_") or lower_key in cls._feed_tracking_keys:
                    continue
                query_pairs.append((key, item))
            cleaned_query = urlencode(query_pairs, doseq=True)
            return urlunsplit((parts.scheme, parts.netloc, parts.path, cleaned_query, ""))
        except Exception:
            return raw

    @staticmethod
    def _format_feed_timestamp(value: str) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return parsed.strftime("%Y-%m-%d %H:%M")
        except Exception:
            pass
        try:
            parsed = parsedate_to_datetime(raw)
            return parsed.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return raw

    @staticmethod
    def _google_calendar_time_bounds(range_hint: str) -> tuple[datetime, datetime, int]:
        now = datetime.now().astimezone()
        start_of_today = datetime.combine(now.date(), dt_time.min, tzinfo=now.tzinfo)
        clean = str(range_hint or "").strip().lower()
        if clean == "today":
            return start_of_today, start_of_today + timedelta(days=1), 12
        if clean == "tomorrow":
            start = start_of_today + timedelta(days=1)
            return start, start + timedelta(days=1), 12
        if clean == "day_after_tomorrow":
            start = start_of_today + timedelta(days=2)
            return start, start + timedelta(days=1), 12
        if clean == "this_week":
            start = start_of_today
            return start, start + timedelta(days=7), 20
        if clean == "next_week":
            days_until_next_week = 7 - start_of_today.weekday()
            start = start_of_today + timedelta(days=days_until_next_week)
            return start, start + timedelta(days=7), 20
        if clean == "next":
            return now, now + timedelta(days=30), 5
        return now, now + timedelta(days=14), 10

    @staticmethod
    def _google_calendar_range_label(range_hint: str, *, language: str = "de") -> str:
        clean = str(range_hint or "").strip().lower()
        labels = {
            "today": _msg(language, "heute", "today"),
            "tomorrow": _msg(language, "morgen", "tomorrow"),
            "day_after_tomorrow": _msg(language, "übermorgen", "the day after tomorrow"),
            "this_week": _msg(language, "diese Woche", "this week"),
            "next_week": _msg(language, "nächste Woche", "next week"),
            "next": _msg(language, "den nächsten Termin", "the next appointment"),
            "upcoming": _msg(language, "die nächsten Termine", "the upcoming events"),
        }
        return labels.get(clean, labels["upcoming"])

    @staticmethod
    def _format_google_calendar_event_time(event: dict[str, Any], *, language: str = "de") -> str:
        start = dict(event.get("start", {}) or {})
        date_value = str(start.get("date", "") or "").strip()
        datetime_value = str(start.get("dateTime", "") or "").strip()
        if date_value:
            try:
                parsed = datetime.fromisoformat(date_value)
                return parsed.strftime("%Y-%m-%d") + _msg(language, " · ganztägig", " · all-day")
            except Exception:
                return date_value
        if datetime_value:
            try:
                parsed = datetime.fromisoformat(datetime_value.replace("Z", "+00:00"))
                return parsed.astimezone().strftime("%Y-%m-%d %H:%M")
            except Exception:
                return datetime_value
        return ""

    @staticmethod
    def _google_calendar_token_request_body(connection: Any) -> bytes:
        return urlencode(
            {
                "client_id": str(getattr(connection, "client_id", "") or "").strip(),
                "client_secret": str(getattr(connection, "client_secret", "") or "").strip(),
                "refresh_token": str(getattr(connection, "refresh_token", "") or "").strip(),
                "grant_type": "refresh_token",
            }
        ).encode("utf-8")

    @staticmethod
    def _clean_feed_summary(value: str, limit: int = 220) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        text = html.unescape(raw)
        text = _FEED_BR_RE.sub("\n", text)
        text = _HTML_TAG_RE.sub(" ", text)
        text = _WHITESPACE_RE.sub(" ", text).strip()
        if not text:
            return ""
        if len(text) <= limit:
            return text
        short = text[:limit].rsplit(" ", 1)[0].strip()
        return (short or text[:limit]).rstrip(".,;:") + "…"

    def _run_rss_read_step(self, connection_ref: str, *, language: str = "de") -> str:
        connection = self._get_connection_profile("rss", connection_ref)
        feed_url = str(getattr(connection, "feed_url", "")).strip()
        timeout_seconds = int(getattr(connection, "timeout_seconds", 10) or 10)
        if not feed_url:
            raise ValueError(_msg(language, "RSS-Feed-URL fehlt im Profil.", "RSS feed URL is missing in the profile."))

        req = URLRequest(feed_url, headers=_RSS_HTTP_HEADERS, method="GET")
        try:
            with urlopen(req, timeout=max(5, timeout_seconds)) as resp:  # noqa: S310
                payload = resp.read(1024 * 512)
        except URLError as exc:
            raise ValueError(_msg(language, f"RSS-Abruf fehlgeschlagen: {exc}", f"RSS fetch failed: {exc}")) from exc
        except Exception as exc:  # noqa: BLE001
            raise ValueError(_msg(language, f"RSS-Abruf fehlgeschlagen: {exc}", f"RSS fetch failed: {exc}")) from exc

        text = payload.decode("utf-8", errors="replace").strip()
        try:
            root = ET.fromstring(text)
        except Exception as exc:  # noqa: BLE001
            raise ValueError(_msg(language, f"RSS-Feed ist kein gültiges XML: {exc}", f"RSS feed is not valid XML: {exc}")) from exc

        entries: list[dict[str, str]] = []
        feed_title = ""
        root_name = self._xml_name(root.tag)
        if root_name == "rss":
            channel = next((child for child in root if self._xml_name(child.tag) == "channel"), None)
            if channel is not None:
                for item in channel:
                    item_name = self._xml_name(item.tag)
                    if item_name == "title" and not feed_title:
                        feed_title = str(item.text or "").strip() or feed_title
                        continue
                    if item_name != "item":
                        continue
                    title = ""
                    link = ""
                    published = ""
                    summary = ""
                    for child in item:
                        name = self._xml_name(child.tag)
                        if name == "title":
                            title = str(child.text or "").strip()
                        elif name == "link":
                            link = str(child.text or "").strip()
                        elif name in {"pubdate", "published", "updated"}:
                            published = str(child.text or "").strip()
                        elif name in {"description", "summary", "content", "content:encoded"}:
                            summary = ET.tostring(child, encoding="unicode", method="xml") if list(child) else str(child.text or "").strip()
                    if title or link:
                        entries.append({"title": title, "link": link, "published": published, "summary": summary})
        elif root_name == "feed":
            for item in root:
                item_name = self._xml_name(item.tag)
                if item_name == "title" and not feed_title:
                    feed_title = str(item.text or "").strip() or feed_title
                    continue
                if item_name != "entry":
                    continue
                title = ""
                link = ""
                published = ""
                summary = ""
                for child in item:
                    name = self._xml_name(child.tag)
                    if name == "title":
                        title = str(child.text or "").strip()
                    elif name == "link":
                        link = str(child.attrib.get("href", "") or child.text or "").strip()
                    elif name in {"updated", "published"}:
                        published = str(child.text or "").strip()
                    elif name in {"summary", "content", "subtitle"}:
                        summary = ET.tostring(child, encoding="unicode", method="xml") if list(child) else str(child.text or "").strip()
                if title or link:
                    entries.append({"title": title, "link": link, "published": published, "summary": summary})

        if not entries:
            return self.truncate_text(
                _msg(
                    language,
                    f"Feed `{connection_ref}` wurde geladen, aber es wurden keine Einträge gefunden.",
                    f"Feed `{connection_ref}` was loaded, but no entries were found.",
                ),
                1400,
            )

        lines = [_msg(language, f"Neueste Einträge aus {feed_title or connection_ref}:", f"Latest entries from {feed_title or connection_ref}:")]
        for idx, item in enumerate(entries[:5], start=1):
            title = item.get("title", "").strip() or _msg(language, "(ohne Titel)", "(untitled)")
            link = self._clean_feed_url(item.get("link", ""))
            published = self._format_feed_timestamp(item.get("published", ""))
            summary = self._clean_feed_summary(item.get("summary", ""))
            line = f"{idx}. {title}"
            if link:
                line = f"{idx}. [{title}]({link})"
            if published:
                line += f"\n   {published}"
            lines.append(line)
            if summary:
                lines.append(f"   {summary}")
            if idx < min(len(entries), 5):
                lines.append("")
        return self.truncate_text("\n".join(lines), 1800)

    def _build_sftp_connect_kwargs(self, connection: Any) -> dict[str, Any]:
        host = str(getattr(connection, "host", "")).strip()
        user = str(getattr(connection, "user", "")).strip()
        password = str(getattr(connection, "password", "")).strip()
        key_path = str(getattr(connection, "key_path", "")).strip()
        port = int(getattr(connection, "port", 22) or 22)
        timeout_seconds = int(getattr(connection, "timeout_seconds", 10) or 10)

        if not host:
            raise ValueError("SFTP-Host fehlt im Profil.")
        if not user:
            raise ValueError("SFTP-User fehlt im Profil.")

        connect_kwargs: dict[str, Any] = {
            "hostname": host,
            "port": max(1, port),
            "username": user,
            "timeout": max(5, timeout_seconds),
            "allow_agent": False,
            "look_for_keys": False,
        }
        if key_path:
            key_file = self._resolve_local_path(key_path)
            if not key_file.exists():
                raise ValueError(f"SFTP-Key nicht gefunden: {key_path}")
            connect_kwargs["key_filename"] = str(key_file)
        elif password:
            connect_kwargs["password"] = password
        else:
            raise ValueError("SFTP-Authentisierung fehlt im Profil.")
        return connect_kwargs

    def _resolve_sftp_target_path(self, connection: Any, remote_path: str) -> str:
        root_path = str(getattr(connection, "root_path", "")).strip()
        clean_remote_path = str(remote_path).strip()
        if not clean_remote_path:
            return ""
        if clean_remote_path.startswith("/"):
            return posixpath.normpath(clean_remote_path)
        if root_path:
            return posixpath.normpath(posixpath.join(root_path, clean_remote_path))
        return posixpath.normpath(clean_remote_path)

    def _build_smb_connection(self, connection: Any) -> tuple[Any, str]:
        host = str(getattr(connection, "host", "")).strip()
        share = str(getattr(connection, "share", "")).strip()
        user = str(getattr(connection, "user", "")).strip()
        password = str(getattr(connection, "password", "")).strip()
        port = int(getattr(connection, "port", 445) or 445)
        timeout_seconds = int(getattr(connection, "timeout_seconds", 10) or 10)

        if not host:
            raise ValueError("SMB-Host fehlt im Profil.")
        if not share:
            raise ValueError("SMB-Share fehlt im Profil.")
        if not user:
            raise ValueError("SMB-User fehlt im Profil.")
        if not password:
            raise ValueError("SMB-Passwort fehlt im Profil.")

        try:
            from smb.SMBConnection import SMBConnection  # type: ignore[import-not-found]
        except Exception as exc:  # noqa: BLE001
            raise ValueError("Python-Modul 'pysmb' fehlt. Bitte installieren und ARIA neu starten.") from exc

        conn = SMBConnection(user, password, "aria", host, use_ntlm_v2=True, is_direct_tcp=True)
        ok = conn.connect(host, max(1, port), timeout=max(5, timeout_seconds))
        if not ok:
            raise ValueError("SMB-Verbindung konnte nicht aufgebaut werden.")
        return conn, share

    def _resolve_smb_target_path(self, connection: Any, remote_path: str) -> str:
        root_path = str(getattr(connection, "root_path", "")).strip()
        clean_remote_path = str(remote_path).strip()
        base_path = root_path or "/"
        if clean_remote_path and clean_remote_path.startswith("/"):
            return posixpath.normpath(clean_remote_path)
        if clean_remote_path:
            return posixpath.normpath(posixpath.join(base_path, clean_remote_path))
        return posixpath.normpath(base_path)

    def _run_sftp_read_step(self, connection_ref: str, remote_path: str) -> str:
        connection = self._get_connection_profile("sftp", connection_ref)

        connect_kwargs = self._build_sftp_connect_kwargs(connection)
        resolved_path = self._resolve_sftp_target_path(connection, remote_path)

        if not resolved_path:
            raise ValueError("SFTP-Dateipfad fehlt.")
        self._enforce_file_guardrail(connection=connection, operation="read", resolved_path=resolved_path)

        try:
            import paramiko  # type: ignore[import-not-found]
        except Exception as exc:  # noqa: BLE001
            raise ValueError("Python-Modul 'paramiko' fehlt. Bitte installieren und ARIA neu starten.") from exc

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(**connect_kwargs)
            sftp = client.open_sftp()
            try:
                with sftp.open(resolved_path, "r") as handle:
                    payload = handle.read()
            finally:
                try:
                    sftp.close()
                except Exception:
                    pass
        finally:
            try:
                client.close()
            except Exception:
                pass

        if isinstance(payload, bytes):
            text = payload.decode("utf-8", errors="replace")
        else:
            text = str(payload)
        return self.truncate_text(text.strip(), 1400)

    def _run_sftp_write_step(self, connection_ref: str, remote_path: str, content: str) -> str:
        connection = self._get_connection_profile("sftp", connection_ref)

        connect_kwargs = self._build_sftp_connect_kwargs(connection)
        resolved_path = self._resolve_sftp_target_path(connection, remote_path)

        if not resolved_path:
            raise ValueError("SFTP-Dateipfad fehlt.")
        self._enforce_file_guardrail(connection=connection, operation="write", resolved_path=resolved_path, content=content)

        try:
            import paramiko  # type: ignore[import-not-found]
        except Exception as exc:  # noqa: BLE001
            raise ValueError("Python-Modul 'paramiko' fehlt. Bitte installieren und ARIA neu starten.") from exc

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(**connect_kwargs)
            sftp = client.open_sftp()
            try:
                current_path = ""
                parent_dir = posixpath.dirname(resolved_path)
                for part in [item for item in parent_dir.split("/") if item]:
                    current_path = f"{current_path}/{part}" if current_path else f"/{part}"
                    try:
                        sftp.stat(current_path)
                    except Exception:
                        sftp.mkdir(current_path)
                with sftp.open(resolved_path, "w") as handle:
                    handle.write(content)
            finally:
                try:
                    sftp.close()
                except Exception:
                    pass
        finally:
            try:
                client.close()
            except Exception:
                pass

        return f"SFTP-Datei geschrieben: {resolved_path} ({len(content)} Zeichen)"

    def _run_sftp_list_step(self, connection_ref: str, remote_path: str) -> str:
        connection = self._get_connection_profile("sftp", connection_ref)

        connect_kwargs = self._build_sftp_connect_kwargs(connection)
        resolved_path = self._resolve_sftp_target_path(connection, remote_path or ".")
        self._enforce_file_guardrail(connection=connection, operation="list", resolved_path=resolved_path)

        try:
            import paramiko  # type: ignore[import-not-found]
        except Exception as exc:  # noqa: BLE001
            raise ValueError("Python-Modul 'paramiko' fehlt. Bitte installieren und ARIA neu starten.") from exc

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(**connect_kwargs)
            sftp = client.open_sftp()
            try:
                entries = sftp.listdir_attr(resolved_path)
            finally:
                try:
                    sftp.close()
                except Exception:
                    pass
        finally:
            try:
                client.close()
            except Exception:
                pass

        names: list[str] = []
        for entry in entries[:40]:
            filename = str(getattr(entry, "filename", "")).strip()
            if not filename:
                continue
            if hasattr(entry, "st_mode") and int(getattr(entry, "st_mode", 0) or 0) & 0o040000:
                names.append(filename + "/")
            else:
                names.append(filename)
        return self._format_directory_listing("SFTP", resolved_path, names)

    def _run_smb_read_step(self, connection_ref: str, remote_path: str) -> str:
        connection = self._get_connection_profile("smb", connection_ref)

        resolved_path = self._resolve_smb_target_path(connection, remote_path)
        if not resolved_path:
            raise ValueError("SMB-Dateipfad fehlt.")
        self._enforce_file_guardrail(connection=connection, operation="read", resolved_path=resolved_path)

        conn, share = self._build_smb_connection(connection)
        buffer = io.BytesIO()
        try:
            conn.retrieveFile(share, resolved_path, buffer)
        finally:
            try:
                conn.close()
            except Exception:
                pass

        text = buffer.getvalue().decode("utf-8", errors="replace")
        return self.truncate_text(text.strip(), 1400)

    def _run_smb_write_step(self, connection_ref: str, remote_path: str, content: str) -> str:
        connection = self._get_connection_profile("smb", connection_ref)

        resolved_path = self._resolve_smb_target_path(connection, remote_path)
        if not resolved_path:
            raise ValueError("SMB-Dateipfad fehlt.")
        self._enforce_file_guardrail(connection=connection, operation="write", resolved_path=resolved_path, content=content)

        conn, share = self._build_smb_connection(connection)
        try:
            parent_dir = posixpath.dirname(resolved_path)
            current_path = ""
            for part in [item for item in parent_dir.split("/") if item]:
                current_path = f"{current_path}/{part}" if current_path else f"/{part}"
                try:
                    conn.createDirectory(share, current_path)
                except Exception:
                    pass
            conn.storeFile(share, resolved_path, io.BytesIO(content.encode("utf-8")))
        finally:
            try:
                conn.close()
            except Exception:
                pass

        return f"SMB-Datei geschrieben: {resolved_path} ({len(content)} Zeichen)"

    def _run_smb_list_step(self, connection_ref: str, remote_path: str) -> str:
        connection = self._get_connection_profile("smb", connection_ref)

        resolved_path = self._resolve_smb_target_path(connection, remote_path or ".")
        self._enforce_file_guardrail(connection=connection, operation="list", resolved_path=resolved_path)
        conn, share = self._build_smb_connection(connection)
        try:
            entries = conn.listPath(share, resolved_path)
        finally:
            try:
                conn.close()
            except Exception:
                pass

        names: list[str] = []
        for entry in entries[:40]:
            filename = str(getattr(entry, "filename", "")).strip()
            if not filename or filename in {".", ".."}:
                continue
            if bool(getattr(entry, "isDirectory", False)):
                names.append(filename + "/")
            else:
                names.append(filename)
        return self._format_directory_listing("SMB", resolved_path, names)

    def execute_sftp_read(self, connection_ref: str, remote_path: str) -> str:
        return self._run_sftp_read_step(connection_ref, remote_path)

    def execute_sftp_write(self, connection_ref: str, remote_path: str, content: str) -> str:
        return self._run_sftp_write_step(connection_ref, remote_path, content)

    def execute_sftp_list(self, connection_ref: str, remote_path: str, *, language: str = "de") -> str:
        connection = self._get_connection_profile("sftp", connection_ref)

        connect_kwargs = self._build_sftp_connect_kwargs(connection)
        resolved_path = self._resolve_sftp_target_path(connection, remote_path or ".")
        self._enforce_file_guardrail(connection=connection, operation="list", resolved_path=resolved_path)

        try:
            import paramiko  # type: ignore[import-not-found]
        except Exception as exc:  # noqa: BLE001
            raise ValueError("Python-Modul 'paramiko' fehlt. Bitte installieren und ARIA neu starten.") from exc

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(**connect_kwargs)
            sftp = client.open_sftp()
            try:
                entries = sftp.listdir_attr(resolved_path)
            finally:
                try:
                    sftp.close()
                except Exception:
                    pass
        finally:
            try:
                client.close()
            except Exception:
                pass

        names: list[str] = []
        for entry in entries[:40]:
            filename = str(getattr(entry, "filename", "")).strip()
            if not filename:
                continue
            if hasattr(entry, "st_mode") and int(getattr(entry, "st_mode", 0) or 0) & 0o040000:
                names.append(filename + "/")
            else:
                names.append(filename)
        return self._format_directory_listing("SFTP", resolved_path, names, language=language)

    def execute_smb_read(self, connection_ref: str, remote_path: str) -> str:
        return self._run_smb_read_step(connection_ref, remote_path)

    def execute_smb_write(self, connection_ref: str, remote_path: str, content: str) -> str:
        return self._run_smb_write_step(connection_ref, remote_path, content)

    def execute_smb_list(self, connection_ref: str, remote_path: str, *, language: str = "de") -> str:
        connection = self._get_connection_profile("smb", connection_ref)

        resolved_path = self._resolve_smb_target_path(connection, remote_path or ".")
        self._enforce_file_guardrail(connection=connection, operation="list", resolved_path=resolved_path)
        conn, share = self._build_smb_connection(connection)
        try:
            entries = conn.listPath(share, resolved_path)
        finally:
            try:
                conn.close()
            except Exception:
                pass

        names: list[str] = []
        for entry in entries[:40]:
            filename = str(getattr(entry, "filename", "")).strip()
            if not filename or filename in {".", ".."}:
                continue
            if bool(getattr(entry, "isDirectory", False)):
                names.append(filename + "/")
            else:
                names.append(filename)
        return self._format_directory_listing("SMB", resolved_path, names, language=language)

    def execute_rss_read(self, connection_ref: str, *, language: str = "de") -> str:
        return self._run_rss_read_step(connection_ref, language=language)

    def execute_google_calendar_read(
        self,
        connection_ref: str,
        range_hint: str = "upcoming",
        search_query: str = "",
        *,
        language: str = "de",
    ) -> str:
        connection = self._get_connection_profile("google_calendar", connection_ref)
        calendar_id = str(getattr(connection, "calendar_id", "primary") or "primary").strip() or "primary"
        client_id = str(getattr(connection, "client_id", "") or "").strip()
        client_secret = str(getattr(connection, "client_secret", "") or "").strip()
        refresh_token = str(getattr(connection, "refresh_token", "") or "").strip()
        timeout_seconds = int(getattr(connection, "timeout_seconds", 10) or 10)
        if not client_id:
            raise ValueError(_msg(language, "Google-Client-ID fehlt im Profil.", "Google client ID is missing in the profile."))
        if not client_secret:
            raise ValueError(_msg(language, "Google-Client-Secret fehlt im Profil.", "Google client secret is missing in the profile."))
        if not refresh_token:
            raise ValueError(_msg(language, "Google-Refresh-Token fehlt im Profil.", "Google refresh token is missing in the profile."))

        token_request = URLRequest(
            "https://oauth2.googleapis.com/token",
            data=self._google_calendar_token_request_body(connection),
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "ARIA/1.0",
            },
            method="POST",
        )
        try:
            with urlopen(token_request, timeout=max(5, timeout_seconds)) as resp:  # noqa: S310
                token_payload = json.loads(resp.read().decode("utf-8", errors="replace"))
        except HTTPError as exc:
            raise ValueError(
                _msg(
                    language,
                    f"Google-Kalender-Anmeldung fehlgeschlagen: HTTP {exc.code}. Bitte Verbindung erneut prüfen.",
                    f"Google Calendar sign-in failed: HTTP {exc.code}. Please re-check the connection.",
                )
            ) from exc
        except URLError as exc:
            raise ValueError(_msg(language, f"Google-Kalender-Verbindung fehlgeschlagen: {exc}", f"Google Calendar connection failed: {exc}")) from exc
        except Exception as exc:  # noqa: BLE001
            raise ValueError(_msg(language, f"Google-Kalender-Anmeldung fehlgeschlagen: {exc}", f"Google Calendar sign-in failed: {exc}")) from exc

        access_token = str((token_payload or {}).get("access_token", "") or "").strip()
        if not access_token:
            raise ValueError(_msg(language, "Google hat kein Zugriffstoken zurückgegeben.", "Google did not return an access token."))

        start_at, end_at, max_results = self._google_calendar_time_bounds(range_hint)
        query_pairs: list[tuple[str, str]] = [
            ("singleEvents", "true"),
            ("orderBy", "startTime"),
            ("showDeleted", "false"),
            ("maxResults", str(max_results)),
            ("timeMin", start_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")),
            ("timeMax", end_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")),
        ]
        clean_search = str(search_query or "").strip()
        if clean_search:
            query_pairs.append(("q", clean_search))
        events_url = (
            f"https://www.googleapis.com/calendar/v3/calendars/{quote(calendar_id, safe='')}/events?"
            + urlencode(query_pairs)
        )
        events_request = URLRequest(
            events_url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "User-Agent": "ARIA/1.0",
            },
            method="GET",
        )
        try:
            with urlopen(events_request, timeout=max(5, timeout_seconds)) as resp:  # noqa: S310
                events_payload = json.loads(resp.read().decode("utf-8", errors="replace"))
        except HTTPError as exc:
            raise ValueError(
                _msg(
                    language,
                    f"Google-Kalender-Abruf fehlgeschlagen: HTTP {exc.code}. Bitte Kalender-ID und Berechtigungen prüfen.",
                    f"Google Calendar fetch failed: HTTP {exc.code}. Please check the calendar ID and permissions.",
                )
            ) from exc
        except URLError as exc:
            raise ValueError(_msg(language, f"Google-Kalender-Abruf fehlgeschlagen: {exc}", f"Google Calendar fetch failed: {exc}")) from exc
        except Exception as exc:  # noqa: BLE001
            raise ValueError(_msg(language, f"Google-Kalender-Abruf fehlgeschlagen: {exc}", f"Google Calendar fetch failed: {exc}")) from exc

        calendar_summary = str((events_payload or {}).get("summary", "") or "").strip() or calendar_id
        items = list((events_payload or {}).get("items", []) or [])
        if not items:
            base = _msg(
                language,
                f"Keine Termine für {self._google_calendar_range_label(range_hint, language=language)} in `{calendar_summary}` gefunden.",
                f"No events found for {self._google_calendar_range_label(range_hint, language=language)} in `{calendar_summary}`.",
            )
            if clean_search:
                base += _msg(language, f" Filter: {clean_search}", f" Filter: {clean_search}")
            return base

        header = _msg(
            language,
            f"Kalender `{calendar_summary}` für {self._google_calendar_range_label(range_hint, language=language)}:",
            f"Calendar `{calendar_summary}` for {self._google_calendar_range_label(range_hint, language=language)}:",
        )
        lines = [header]
        for index, item in enumerate(items[:max_results], start=1):
            event = dict(item or {})
            summary = str(event.get("summary", "") or "").strip() or _msg(language, "(ohne Titel)", "(untitled)")
            when = self._format_google_calendar_event_time(event, language=language)
            location = str(event.get("location", "") or "").strip()
            line = f"{index}. {summary}"
            if when:
                line += f" [{when}]"
            lines.append(line)
            if location:
                lines.append(f"   {_msg(language, 'Ort', 'Location')}: {location}")
        return self.truncate_text("\n".join(lines), 1800)

    def execute_webhook_send(self, connection_ref: str, content: str, *, language: str = "de") -> str:
        connection = self._get_connection_profile("webhook", connection_ref)
        webhook_url = str(getattr(connection, "url", "")).strip()
        if not webhook_url:
            raise ValueError(_msg(language, f"Webhook-URL fehlt im Profil: {connection_ref}", f"Webhook URL is missing in profile: {connection_ref}"))
        timeout_seconds = int(getattr(connection, "timeout_seconds", 10) or 10)
        method = str(getattr(connection, "method", "POST")).strip().upper() or "POST"
        content_type = str(getattr(connection, "content_type", "application/json")).strip() or "application/json"
        payload_text = str(content or "").strip()
        if not payload_text:
            raise ValueError(_msg(language, "Webhook-Inhalt fehlt.", "Webhook content is missing."))
        self._enforce_connection_guardrail(
            connection=connection,
            connection_ref=connection_ref,
            guardrail_kind="http_request",
            evaluation_text=" ".join(
                part
                for part in (
                    method,
                    webhook_url,
                    content_type,
                    payload_text,
                )
                if str(part).strip()
            ),
            label="HTTP",
        )

        if "json" in content_type.lower():
            payload = json.dumps({"message": payload_text}, ensure_ascii=False).encode("utf-8")
        else:
            payload = payload_text.encode("utf-8")

        req = URLRequest(
            webhook_url,
            data=payload,
            headers={
                "Content-Type": content_type,
                "User-Agent": "ARIA/1.0",
            },
            method=method,
        )
        try:
            with urlopen(req, timeout=max(5, timeout_seconds)) as resp:  # noqa: S310
                status_code = int(getattr(resp, "status", 200) or 200)
                _ = resp.read()
        except URLError as exc:
            raise ValueError(_msg(language, f"Webhook-Senden fehlgeschlagen: {exc}", f"Webhook send failed: {exc}")) from exc
        except Exception as exc:  # noqa: BLE001
            raise ValueError(_msg(language, f"Webhook-Senden fehlgeschlagen: {exc}", f"Webhook send failed: {exc}")) from exc
        if status_code >= 400:
            raise ValueError(_msg(language, f"Webhook-Senden fehlgeschlagen: HTTP {status_code}", f"Webhook send failed: HTTP {status_code}"))
        return _msg(
            language,
            f"Webhook gesendet via `{connection_ref}` ({method}, {status_code})",
            f"Webhook sent via `{connection_ref}` ({method}, {status_code})",
        )

    def execute_discord_send(self, connection_ref: str, content: str, *, language: str = "de") -> str:
        connection = self._get_connection_profile("discord", connection_ref)
        if not bool(getattr(connection, "allow_skill_messages", True)):
            raise ValueError(_msg(language, "Discord-Profil erlaubt aktuell keine Skill-/Chat-Nachrichten.", "Discord profile currently does not allow skill/chat messages."))
        webhook_url = str(getattr(connection, "webhook_url", "")).strip()
        if not webhook_url:
            raise ValueError(_msg(language, f"Discord-Webhook fehlt im Profil: {connection_ref}", f"Discord webhook is missing in profile: {connection_ref}"))
        payload_text = str(content or "").strip()
        if not payload_text:
            raise ValueError(_msg(language, "Discord-Inhalt fehlt.", "Discord content is missing."))
        payload = json.dumps({"content": payload_text[:1900]}, ensure_ascii=False).encode("utf-8")
        req = URLRequest(
            webhook_url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "ARIA/1.0",
            },
            method="POST",
        )
        try:
            with urlopen(req, timeout=10) as resp:  # noqa: S310
                status_code = int(getattr(resp, "status", 204) or 204)
                _ = resp.read()
        except URLError as exc:
            raise ValueError(_msg(language, f"Discord-Senden fehlgeschlagen: {exc}", f"Discord send failed: {exc}")) from exc
        except Exception as exc:  # noqa: BLE001
            raise ValueError(_msg(language, f"Discord-Senden fehlgeschlagen: {exc}", f"Discord send failed: {exc}")) from exc
        if status_code >= 400:
            raise ValueError(_msg(language, f"Discord-Senden fehlgeschlagen: HTTP {status_code}", f"Discord send failed: HTTP {status_code}"))
        return _msg(language, f"Discord gesendet via `{connection_ref}`", f"Discord message sent via `{connection_ref}`")

    def execute_http_api_request(self, connection_ref: str, request_path: str = "", content: str = "", *, language: str = "de") -> str:
        connection = self._get_connection_profile("http_api", connection_ref)
        base_url = str(getattr(connection, "base_url", "")).strip()
        if not base_url:
            raise ValueError(_msg(language, f"Base URL fehlt im HTTP-API-Profil: {connection_ref}", f"Base URL is missing in the HTTP API profile: {connection_ref}"))
        timeout_seconds = int(getattr(connection, "timeout_seconds", 10) or 10)
        method = str(getattr(connection, "method", "GET")).strip().upper() or "GET"
        health_path = str(getattr(connection, "health_path", "/")).strip() or "/"
        auth_token = str(getattr(connection, "auth_token", "")).strip()
        resolved_path = str(request_path or "").strip() or health_path
        target_url = urljoin(base_url.rstrip("/") + "/", resolved_path.lstrip("/"))
        self._enforce_connection_guardrail(
            connection=connection,
            connection_ref=connection_ref,
            guardrail_kind="http_request",
            evaluation_text=" ".join(
                part
                for part in (
                    method,
                    target_url,
                    resolved_path,
                    str(content or "").strip(),
                )
                if str(part).strip()
            ),
            label="HTTP",
        )
        headers = {"User-Agent": "ARIA/1.0"}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        payload = None
        if method in {"POST", "PUT", "PATCH"}:
            headers["Content-Type"] = "application/json"
            payload_text = str(content or "").strip()
            payload = json.dumps({"message": payload_text}, ensure_ascii=False).encode("utf-8") if payload_text else b"{}"

        req = URLRequest(
            target_url,
            data=payload,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(req, timeout=max(5, timeout_seconds)) as resp:  # noqa: S310
                body = resp.read()
                status_code = int(getattr(resp, "status", 200) or 200)
                content_type = str(getattr(resp, "headers", {}).get("Content-Type", "") if getattr(resp, "headers", None) else "")
        except URLError as exc:
            raise ValueError(_msg(language, f"HTTP-API-Aufruf fehlgeschlagen: {exc}", f"HTTP API request failed: {exc}")) from exc
        except Exception as exc:  # noqa: BLE001
            raise ValueError(_msg(language, f"HTTP-API-Aufruf fehlgeschlagen: {exc}", f"HTTP API request failed: {exc}")) from exc
        if status_code >= 400:
            raise ValueError(_msg(language, f"HTTP-API-Aufruf fehlgeschlagen: HTTP {status_code}", f"HTTP API request failed: HTTP {status_code}"))

        text = body.decode("utf-8", errors="replace").strip()
        if text:
            if "json" in content_type.lower():
                try:
                    parsed = json.loads(text)
                    text = json.dumps(parsed, ensure_ascii=False, indent=2)
                except Exception:
                    pass
            return self.truncate_text(text, 1400)
        return _msg(language, f"HTTP API ausgeführt via `{connection_ref}` ({method}, {status_code})", f"HTTP API executed via `{connection_ref}` ({method}, {status_code})")

    def execute_email_send(self, connection_ref: str, content: str, *, language: str = "de") -> str:
        connection = self._get_connection_profile("email", connection_ref)
        host = str(getattr(connection, "smtp_host", "")).strip()
        user = str(getattr(connection, "user", "")).strip()
        password = str(getattr(connection, "password", "")).strip()
        from_email = str(getattr(connection, "from_email", "")).strip() or user
        to_email = str(getattr(connection, "to_email", "")).strip()
        port = int(getattr(connection, "port", 587) or 587)
        timeout_seconds = int(getattr(connection, "timeout_seconds", 10) or 10)
        use_ssl = bool(getattr(connection, "use_ssl", False))
        starttls = bool(getattr(connection, "starttls", True))
        body = str(content or "").strip()
        if not host:
            raise ValueError(_msg(language, "SMTP-Host fehlt im Profil.", "SMTP host is missing in the profile."))
        if not user:
            raise ValueError(_msg(language, "SMTP-User fehlt im Profil.", "SMTP user is missing in the profile."))
        if not password:
            raise ValueError(_msg(language, "SMTP-Passwort fehlt im Profil.", "SMTP password is missing in the profile."))
        if not to_email:
            raise ValueError(_msg(language, "Standard-Empfänger fehlt im SMTP-Profil.", "Default recipient is missing in the SMTP profile."))
        if not body:
            raise ValueError(_msg(language, "Mail-Inhalt fehlt.", "Email content is missing."))

        msg = EmailMessage()
        msg["From"] = from_email
        msg["To"] = to_email
        msg["Subject"] = _msg(language, "ARIA Nachricht", "ARIA message")
        msg.set_content(body)

        try:
            if use_ssl:
                server = smtplib.SMTP_SSL(host, max(1, port), timeout=max(5, timeout_seconds))
            else:
                server = smtplib.SMTP(host, max(1, port), timeout=max(5, timeout_seconds))
            with server:
                server.ehlo()
                if starttls and not use_ssl:
                    server.starttls()
                    server.ehlo()
                server.login(user, password)
                server.send_message(msg)
        except Exception as exc:  # noqa: BLE001
            raise ValueError(_msg(language, f"SMTP-Senden fehlgeschlagen: {exc}", f"SMTP send failed: {exc}")) from exc
        return _msg(language, f"Mail gesendet via `{connection_ref}` an {to_email}", f"Email sent via `{connection_ref}` to {to_email}")

    @staticmethod
    def _decode_mail_header(value: str) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        try:
            return str(make_header(decode_header(raw))).strip()
        except Exception:
            return raw

    def _open_imap_connection(self, connection_ref: str, *, language: str = "de") -> tuple[imaplib.IMAP4, str]:
        connection = self._get_connection_profile("imap", connection_ref)
        host = str(getattr(connection, "host", "")).strip()
        user = str(getattr(connection, "user", "")).strip()
        password = str(getattr(connection, "password", "")).strip()
        mailbox = str(getattr(connection, "mailbox", "INBOX")).strip() or "INBOX"
        port = int(getattr(connection, "port", 993) or 993)
        use_ssl = bool(getattr(connection, "use_ssl", True))
        if not host:
            raise ValueError(_msg(language, "IMAP-Host fehlt im Profil.", "IMAP host is missing in the profile."))
        if not user:
            raise ValueError(_msg(language, "IMAP-User fehlt im Profil.", "IMAP user is missing in the profile."))
        if not password:
            raise ValueError(_msg(language, "IMAP-Passwort fehlt im Profil.", "IMAP password is missing in the profile."))
        try:
            client = imaplib.IMAP4_SSL(host, max(1, port)) if use_ssl else imaplib.IMAP4(host, max(1, port))
            status, _ = client.login(user, password)
            if status != "OK":
                raise ValueError(_msg(language, "IMAP-Login fehlgeschlagen.", "IMAP login failed."))
            status, _ = client.select(mailbox, readonly=True)
            if status != "OK":
                raise ValueError(_msg(language, f"IMAP-Mailbox nicht erreichbar: {mailbox}", f"IMAP mailbox not reachable: {mailbox}"))
            return client, mailbox
        except Exception as exc:  # noqa: BLE001
            raise ValueError(_msg(language, f"IMAP-Verbindung fehlgeschlagen: {exc}", f"IMAP connection failed: {exc}")) from exc

    def execute_imap_read(self, connection_ref: str, *, language: str = "de") -> str:
        client, mailbox = self._open_imap_connection(connection_ref, language=language)
        try:
            status, data = client.search(None, "ALL")
            if status != "OK":
                raise ValueError(_msg(language, "IMAP-Suche fehlgeschlagen.", "IMAP search failed."))
            ids = [item for item in (data[0].split() if data and data[0] else [])][-5:]
            if not ids:
                return _msg(language, f"Mailbox leer: {mailbox}", f"Mailbox is empty: {mailbox}")
            lines = [_msg(language, f"Latest emails from {mailbox}:", f"Latest emails from {mailbox}:")]
            for idx, msg_id in enumerate(reversed(ids), start=1):
                status, payload = client.fetch(msg_id, "(RFC822.HEADER)")
                if status != "OK" or not payload:
                    continue
                header_bytes = b""
                for part in payload:
                    if isinstance(part, tuple) and len(part) > 1 and isinstance(part[1], (bytes, bytearray)):
                        header_bytes = bytes(part[1])
                        break
                if not header_bytes:
                    continue
                msg = message_from_bytes(header_bytes)
                subject = self._decode_mail_header(msg.get("Subject", "")) or _msg(language, "(ohne Betreff)", "(no subject)")
                sender = self._decode_mail_header(msg.get("From", "")) or "-"
                date = self._format_feed_timestamp(msg.get("Date", ""))
                line = f"{idx}. {subject}"
                if date:
                    line += f" [{date}]"
                lines.append(line)
                lines.append(f"   {_msg(language, 'From', 'From')}: {sender}")
            return self.truncate_text("\n".join(lines), 1400)
        finally:
            with contextlib.suppress(Exception):
                client.logout()

    def execute_imap_search(self, connection_ref: str, query: str, *, language: str = "de") -> str:
        term = str(query or "").strip()
        if not term:
            raise ValueError(_msg(language, "Suchbegriff für Mail-Suche fehlt.", "Search term for mail search is missing."))
        client, mailbox = self._open_imap_connection(connection_ref, language=language)
        try:
            status, data = client.search(None, "TEXT", f'"{term}"')
            if status != "OK":
                raise ValueError(_msg(language, "IMAP-Suche fehlgeschlagen.", "IMAP search failed."))
            ids = [item for item in (data[0].split() if data and data[0] else [])][-5:]
            if not ids:
                return _msg(language, f"Keine Treffer in {mailbox} für „{term}“.", f"No matches in {mailbox} for “{term}”.")
            lines = [_msg(language, f"Treffer in {mailbox} für „{term}“:", f"Matches in {mailbox} for “{term}”:")]
            for idx, msg_id in enumerate(reversed(ids), start=1):
                status, payload = client.fetch(msg_id, "(RFC822.HEADER)")
                if status != "OK" or not payload:
                    continue
                header_bytes = b""
                for part in payload:
                    if isinstance(part, tuple) and len(part) > 1 and isinstance(part[1], (bytes, bytearray)):
                        header_bytes = bytes(part[1])
                        break
                if not header_bytes:
                    continue
                msg = message_from_bytes(header_bytes)
                subject = self._decode_mail_header(msg.get("Subject", "")) or _msg(language, "(ohne Betreff)", "(no subject)")
                sender = self._decode_mail_header(msg.get("From", "")) or "-"
                date = self._format_feed_timestamp(msg.get("Date", ""))
                line = f"{idx}. {subject}"
                if date:
                    line += f" [{date}]"
                lines.append(line)
                lines.append(f"   {_msg(language, 'From', 'From')}: {sender}")
            return self.truncate_text("\n".join(lines), 1400)
        finally:
            with contextlib.suppress(Exception):
                client.logout()

    def execute_mqtt_publish(self, connection_ref: str, topic: str, content: str, *, language: str = "de") -> str:
        connection = self._get_connection_profile("mqtt", connection_ref)
        host = str(getattr(connection, "host", "")).strip()
        user = str(getattr(connection, "user", "")).strip()
        password = str(getattr(connection, "password", "")).strip()
        default_topic = str(getattr(connection, "topic", "")).strip()
        resolved_topic = str(topic or "").strip() or default_topic
        port = int(getattr(connection, "port", 1883) or 1883)
        timeout_seconds = int(getattr(connection, "timeout_seconds", 10) or 10)
        use_tls = bool(getattr(connection, "use_tls", False))
        payload = str(content or "").strip()
        if not host:
            raise ValueError(_msg(language, "MQTT-Host fehlt im Profil.", "MQTT host is missing in the profile."))
        if not user:
            raise ValueError(_msg(language, "MQTT-User fehlt im Profil.", "MQTT user is missing in the profile."))
        if not password:
            raise ValueError(_msg(language, "MQTT-Passwort fehlt im Profil.", "MQTT password is missing in the profile."))
        if not resolved_topic:
            raise ValueError(_msg(language, "MQTT-Topic fehlt. Entweder im Profil hinterlegen oder im Prompt angeben.", "MQTT topic is missing. Configure it in the profile or provide it in the prompt."))
        if not payload:
            raise ValueError(_msg(language, "MQTT-Nachricht fehlt.", "MQTT message is missing."))
        try:
            import paho.mqtt.client as mqtt  # type: ignore[import-not-found]
        except Exception as exc:
            raise ValueError(_msg(language, "Python-Modul 'paho-mqtt' fehlt. Bitte installieren und ARIA neu starten.", "Python module 'paho-mqtt' is missing. Please install it and restart ARIA.")) from exc

        result: dict[str, Any] = {"published": False, "rc": None}
        client = mqtt.Client()
        client.username_pw_set(user, password)
        if use_tls:
            client.tls_set()

        def _on_connect(_client: Any, _userdata: Any, _flags: Any, rc: int, _properties: Any = None) -> None:
            result["rc"] = rc
            if int(rc) == 0:
                info = _client.publish(resolved_topic, payload)
                result["published"] = bool(getattr(info, "rc", 1) == 0)
                try:
                    _client.disconnect()
                except Exception:
                    pass

        client.on_connect = _on_connect
        try:
            client.connect(host, max(1, port), keepalive=max(5, timeout_seconds))
            client.loop_start()
            deadline = time.time() + max(5, timeout_seconds)
            while not result["published"] and result["rc"] is None and time.time() < deadline:
                time.sleep(0.1)
            if result["rc"] is not None and int(result["rc"]) != 0:
                raise ValueError(_msg(language, f"MQTT-Connect fehlgeschlagen (rc={result['rc']}).", f"MQTT connect failed (rc={result['rc']})."))
            if not result["published"]:
                raise ValueError(_msg(language, "MQTT-Publish fehlgeschlagen oder Timeout.", "MQTT publish failed or timed out."))
        except Exception as exc:  # noqa: BLE001
            raise ValueError(_msg(language, f"MQTT-Publish fehlgeschlagen: {exc}", f"MQTT publish failed: {exc}")) from exc
        finally:
            with contextlib.suppress(Exception):
                client.loop_stop()
            with contextlib.suppress(Exception):
                client.disconnect()
        return _msg(language, f"MQTT gesendet via `{connection_ref}` auf Topic `{resolved_topic}`", f"MQTT published via `{connection_ref}` on topic `{resolved_topic}`")

    async def execute_custom_steps(self, row: dict[str, Any], message: str, language: str = "de") -> SkillResult:
        skill_id = str(row.get("id", "")).strip() or "custom"
        skill_name = str(row.get("name", skill_id)).strip() or skill_id
        steps = row.get("steps", [])
        if not isinstance(steps, list) or not steps:
            return SkillResult(
                skill_name=f"custom_skill_{skill_id}",
                content="",
                success=False,
                error="custom_skill_steps_missing",
            )

        outputs: dict[str, str] = {}
        last_output = self.normalize_spaces(message)
        executed: list[str] = []
        held_by_connection: dict[str, list[str]] = {}
        connection_targets: dict[str, str] = {}
        error_interpretations: dict[str, dict[str, str]] = {}
        ssh_run_summaries: list[dict[str, Any]] = []
        direct_chat = False
        skipped: list[str] = []
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0

        for idx, step in enumerate(steps, start=1):
            if not isinstance(step, dict):
                continue
            step_id = str(step.get("id", "")).strip() or f"s{idx}"
            step_type = str(step.get("type", "")).strip().lower()
            on_error = str(step.get("on_error", "stop")).strip().lower() or "stop"
            params = step.get("params", {})
            if not isinstance(params, dict):
                params = {}
            values = {
                "query": self.normalize_spaces(message),
                "prev_output": last_output,
                "last_output": last_output,
            }
            for key, val in outputs.items():
                values[f"{key}_output"] = val
                values[key] = val
            condition = step.get("condition", {})
            if isinstance(condition, dict) and condition:
                if not _evaluate_skill_step_condition(condition, values):
                    outputs[step_id] = ""
                    skipped.append(step_id)
                    executed.append(f"{idx}.{step_type}(skipped)")
                    continue

            if step_type == "ssh_run":
                configured_connection_ref = str(params.get("connection_ref", "")).strip()
                cmd_tpl = str(params.get("command", "")).strip()
                cmd = render_step_template(cmd_tpl, values)
                ssh_result = await self.execute_custom_ssh_command(
                    skill_id=skill_id,
                    skill_name=skill_name,
                    connection_ref=configured_connection_ref,
                    command_template=cmd,
                    message=message,
                    timeout_seconds=int(params.get("timeout_seconds", 0) or 0) or None,
                    language=language,
                )
                if not ssh_result.success:
                    meta = ssh_result.metadata or {}
                    interpretation = meta.get("error_interpretation")
                    if configured_connection_ref and isinstance(interpretation, dict):
                        error_interpretations[configured_connection_ref] = {
                            "title": str(interpretation.get("title", "")).strip(),
                            "cause": str(interpretation.get("cause", "")).strip(),
                            "next_step": str(interpretation.get("next_step", "")).strip(),
                        }
                    if on_error == "continue":
                        err_text = ssh_result.error or "ssh_step_failed"
                        last_output = f"[Step {step_id} Fehler] {err_text}"
                        outputs[step_id] = last_output
                        executed.append(f"{idx}.ssh_run(error-continue)")
                        continue
                    return ssh_result
                last_output = ssh_result.content
                outputs[step_id] = last_output
                executed.append(f"{idx}.ssh_run")
                meta = ssh_result.metadata or {}
                resolved_connection_ref = str(meta.get("custom_connection_ref", "")).strip()
                resolved_connection_target = str(meta.get("custom_connection_target", "")).strip()
                held_packages = meta.get("custom_held_packages", [])
                ssh_run_summaries.append(
                    {
                        "connection_ref": resolved_connection_ref or configured_connection_ref,
                        "target": resolved_connection_target,
                        "exit_code": int(meta.get("custom_exit_code", 0) or 0),
                        "duration_seconds": float(meta.get("custom_duration_seconds", 0.0) or 0.0),
                        "held_packages": held_packages if isinstance(held_packages, list) else [],
                        "warning_hints": meta.get("custom_warning_hints", []) if isinstance(meta.get("custom_warning_hints", []), list) else [],
                    }
                )
                if resolved_connection_ref and isinstance(held_packages, list) and held_packages:
                    merged = held_by_connection.setdefault(resolved_connection_ref, [])
                    for pkg in held_packages:
                        package_name = str(pkg).strip().lower()
                        if package_name and package_name not in merged:
                            merged.append(package_name)
                    if resolved_connection_target:
                        connection_targets[resolved_connection_ref] = resolved_connection_target
                continue

            if step_type == "sftp_read":
                connection_ref = str(params.get("connection_ref", "")).strip().lower()
                remote_path_tmpl = str(params.get("remote_path", "")).strip()
                remote_path = render_step_template(remote_path_tmpl, values)
                try:
                    last_output = self._run_sftp_read_step(connection_ref, remote_path)
                except Exception as exc:  # noqa: BLE001
                    failure = SkillResult(
                        skill_name=f"custom_skill_{skill_id}",
                        content="",
                        success=False,
                        error=f"custom_skill_sftp_read_error:{exc}",
                    )
                    if on_error == "continue":
                        err_text = failure.error or "sftp_read_error"
                        last_output = f"[Step {step_id} Fehler] {err_text}"
                        outputs[step_id] = last_output
                        executed.append(f"{idx}.sftp_read(error-continue)")
                        continue
                    return failure
                outputs[step_id] = last_output
                executed.append(f"{idx}.sftp_read")
                continue

            if step_type == "sftp_write":
                connection_ref = str(params.get("connection_ref", "")).strip().lower()
                remote_path_tmpl = str(params.get("remote_path", "")).strip()
                content_tmpl = str(params.get("content", "")).strip() or "{prev_output}"
                remote_path = render_step_template(remote_path_tmpl, values)
                rendered_content = render_step_template(content_tmpl, values)
                try:
                    last_output = self._run_sftp_write_step(connection_ref, remote_path, rendered_content)
                except Exception as exc:  # noqa: BLE001
                    failure = SkillResult(
                        skill_name=f"custom_skill_{skill_id}",
                        content="",
                        success=False,
                        error=f"custom_skill_sftp_write_error:{exc}",
                    )
                    if on_error == "continue":
                        err_text = failure.error or "sftp_write_error"
                        last_output = f"[Step {step_id} Fehler] {err_text}"
                        outputs[step_id] = last_output
                        executed.append(f"{idx}.sftp_write(error-continue)")
                        continue
                    return failure
                outputs[step_id] = last_output
                executed.append(f"{idx}.sftp_write")
                continue

            if step_type == "smb_read":
                connection_ref = str(params.get("connection_ref", "")).strip().lower()
                remote_path_tmpl = str(params.get("remote_path", "")).strip()
                remote_path = render_step_template(remote_path_tmpl, values)
                try:
                    last_output = self._run_smb_read_step(connection_ref, remote_path)
                except Exception as exc:  # noqa: BLE001
                    failure = SkillResult(
                        skill_name=f"custom_skill_{skill_id}",
                        content="",
                        success=False,
                        error=f"custom_skill_smb_read_error:{exc}",
                    )
                    if on_error == "continue":
                        err_text = failure.error or "smb_read_error"
                        last_output = f"[Step {step_id} Fehler] {err_text}"
                        outputs[step_id] = last_output
                        executed.append(f"{idx}.smb_read(error-continue)")
                        continue
                    return failure
                outputs[step_id] = last_output
                executed.append(f"{idx}.smb_read")
                continue

            if step_type == "smb_write":
                connection_ref = str(params.get("connection_ref", "")).strip().lower()
                remote_path_tmpl = str(params.get("remote_path", "")).strip()
                content_tmpl = str(params.get("content", "")).strip() or "{prev_output}"
                remote_path = render_step_template(remote_path_tmpl, values)
                rendered_content = render_step_template(content_tmpl, values)
                try:
                    last_output = self._run_smb_write_step(connection_ref, remote_path, rendered_content)
                except Exception as exc:  # noqa: BLE001
                    failure = SkillResult(
                        skill_name=f"custom_skill_{skill_id}",
                        content="",
                        success=False,
                        error=f"custom_skill_smb_write_error:{exc}",
                    )
                    if on_error == "continue":
                        err_text = failure.error or "smb_write_error"
                        last_output = f"[Step {step_id} Fehler] {err_text}"
                        outputs[step_id] = last_output
                        executed.append(f"{idx}.smb_write(error-continue)")
                        continue
                    return failure
                outputs[step_id] = last_output
                executed.append(f"{idx}.smb_write")
                continue

            if step_type == "rss_read":
                connection_ref = str(params.get("connection_ref", "")).strip().lower()
                try:
                    last_output = self._run_rss_read_step(connection_ref)
                except Exception as exc:  # noqa: BLE001
                    failure = SkillResult(
                        skill_name=f"custom_skill_{skill_id}",
                        content="",
                        success=False,
                        error=f"custom_skill_rss_read_error:{exc}",
                    )
                    if on_error == "continue":
                        err_text = failure.error or "rss_read_error"
                        last_output = f"[Step {step_id} Fehler] {err_text}"
                        outputs[step_id] = last_output
                        executed.append(f"{idx}.rss_read(error-continue)")
                        continue
                    return failure
                outputs[step_id] = last_output
                executed.append(f"{idx}.rss_read")
                continue

            if step_type == "llm_transform":
                prompt_tmpl = str(params.get("prompt", "")).strip() or "Fasse das kurz zusammen:\n{prev_output}"
                rendered = render_step_template(prompt_tmpl, values)
                rsp = await self.llm_client.chat(
                    [
                        {"role": "system", "content": "Du bist ein knapper Skill-Transformer. Antworte nur mit dem Ergebnis."},
                        {"role": "user", "content": rendered},
                    ]
                )
                last_output = self.truncate_text(rsp.content, 1400)
                usage = rsp.usage if isinstance(rsp.usage, dict) else {}
                prompt_tokens += int(usage.get("prompt_tokens", 0) or 0)
                completion_tokens += int(usage.get("completion_tokens", 0) or 0)
                total_tokens += int(usage.get("total_tokens", 0) or 0)
                outputs[step_id] = last_output
                executed.append(f"{idx}.llm_transform")
                continue

            if step_type == "discord_send":
                connection_ref = str(params.get("connection_ref", "")).strip().lower()
                webhook = ""
                if connection_ref:
                    discord_conn = getattr(getattr(self.settings, "connections", object()), "discord", {}).get(connection_ref)
                    if discord_conn is not None:
                        if not bool(getattr(discord_conn, "allow_skill_messages", True)):
                            failure = SkillResult(
                                skill_name=f"custom_skill_{skill_id}",
                                content="",
                                success=False,
                                error="custom_skill_discord_messages_disabled",
                            )
                            if on_error == "continue":
                                err_text = failure.error or "discord_send_error"
                                last_output = f"[Step {step_id} Fehler] {err_text}"
                                outputs[step_id] = last_output
                                executed.append(f"{idx}.discord_send(error-continue)")
                                continue
                            return failure
                        webhook = str(getattr(discord_conn, "webhook_url", "")).strip()
                if not webhook:
                    webhook = str(params.get("webhook_url", "")).strip()
                if not webhook:
                    failure = SkillResult(
                        skill_name=f"custom_skill_{skill_id}",
                        content="",
                        success=False,
                        error="custom_skill_discord_missing_webhook",
                    )
                    if on_error == "continue":
                        err_text = failure.error or "discord_step_failed"
                        last_output = f"[Step {step_id} Fehler] {err_text}"
                        outputs[step_id] = last_output
                        executed.append(f"{idx}.discord_send(error-continue)")
                        continue
                    return failure
                body_tmpl = str(params.get("message", "")).strip() or "{prev_output}"
                content = render_step_template(body_tmpl, values)
                payload = json.dumps({"content": content[:1900]}).encode("utf-8")
                try:
                    req = URLRequest(
                        webhook,
                        data=payload,
                        headers={
                            "Content-Type": "application/json",
                            "User-Agent": "ARIA/1.0",
                        },
                        method="POST",
                    )
                    with urlopen(req, timeout=10) as resp:  # noqa: S310
                        _ = resp.read()
                except URLError as exc:
                    failure = SkillResult(
                        skill_name=f"custom_skill_{skill_id}",
                        content="",
                        success=False,
                        error=f"custom_skill_discord_send_error:{exc}",
                    )
                    if on_error == "continue":
                        err_text = failure.error or "discord_send_error"
                        last_output = f"[Step {step_id} Fehler] {err_text}"
                        outputs[step_id] = last_output
                        executed.append(f"{idx}.discord_send(error-continue)")
                        continue
                    return failure
                except Exception as exc:  # noqa: BLE001
                    failure = SkillResult(
                        skill_name=f"custom_skill_{skill_id}",
                        content="",
                        success=False,
                        error=f"custom_skill_discord_send_error:{exc}",
                    )
                    if on_error == "continue":
                        err_text = failure.error or "discord_send_error"
                        last_output = f"[Step {step_id} Fehler] {err_text}"
                        outputs[step_id] = last_output
                        executed.append(f"{idx}.discord_send(error-continue)")
                        continue
                    return failure
                last_output = f"Discord gesendet ({len(content)} Zeichen)."
                outputs[step_id] = content
                executed.append(f"{idx}.discord_send")
                continue

            if step_type == "chat_send":
                body_tmpl = (
                    str(params.get("chat_message", "")).strip()
                    or str(params.get("message", "")).strip()
                    or "{prev_output}"
                )
                content = render_step_template(body_tmpl, values)
                last_output = self.truncate_text(content, 1400)
                outputs[step_id] = last_output
                executed.append(f"{idx}.chat_send")
                direct_chat = True
                continue

            failure = SkillResult(
                skill_name=f"custom_skill_{skill_id}",
                content="",
                success=False,
                error=f"custom_skill_unknown_step_type:{step_type}",
            )
            if on_error == "continue":
                err_text = failure.error or "unknown_step_type"
                last_output = f"[Step {step_id} Fehler] {err_text}"
                outputs[step_id] = last_output
                executed.append(f"{idx}.unknown(error-continue)")
                continue
            return failure

        lines = [f"[Custom Skill Steps] {skill_name}", "Ausgefuehrt: " + ", ".join(executed)]
        ssh_summary = _format_ssh_step_run_summary(ssh_run_summaries)
        if ssh_summary:
            lines.append(ssh_summary)
        held_summary = format_held_packages_summary(held_by_connection, connection_targets)
        if held_summary:
            lines.append(held_summary)
        if last_output:
            lines.append("Ergebnis:\n" + self.truncate_text(last_output, 1400))
        meta: dict[str, Any] = {
            "custom_skill_id": skill_id,
            "custom_skill_name": skill_name,
            "custom_execution": "steps",
            "custom_steps_executed": executed,
            "custom_steps_skipped": skipped,
            "direct_chat_response": direct_chat,
            "custom_ssh_run_summary": ssh_summary,
            "custom_held_packages_by_connection": held_by_connection,
            "custom_connection_targets": connection_targets,
            "custom_held_summary": held_summary,
            "error_interpretations_by_connection": error_interpretations,
        }
        if direct_chat and last_output:
            final_chat = last_output
            if ssh_summary and ssh_summary not in final_chat:
                final_chat = f"{final_chat}\n\n{ssh_summary}"
            if held_summary and held_summary not in final_chat:
                final_chat = f"{final_chat}\n\n{held_summary}"
            meta["direct_chat_text"] = final_chat
        if total_tokens > 0:
            meta["extraction_model"] = self.settings.llm.model
            meta["extraction_usage"] = {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "calls": 1,
            }
        return SkillResult(
            skill_name=f"custom_skill_{skill_id}",
            content="\n".join(lines),
            success=True,
            metadata=meta,
        )

    async def run_skills(
        self,
        intents: list[str],
        message: str,
        user_id: str,
        routing_profile: RoutingLanguageConfig,
        language: str = "de",
        runtime_custom_skills: list[dict[str, Any]] | None = None,
        memory_collection: str | None = None,
        session_collection: str | None = None,
        auto_memory_enabled: bool = False,
    ) -> list[SkillResult]:
        results: list[SkillResult] = []
        runtime_custom_skills = runtime_custom_skills or []
        custom_by_id = {str(row.get("id", "")): row for row in runtime_custom_skills}

        for intent in intents:
            if not str(intent).startswith("custom_skill:"):
                continue
            skill_id = str(intent).split(":", 1)[1].strip()
            row = custom_by_id.get(skill_id)
            if not row:
                continue
            steps = row.get("steps", [])
            if not isinstance(steps, list) or not steps:
                continue
            results.append(await self.execute_custom_steps(row=row, message=message, language=language))

        memory_skill = self.memory_skill_getter()

        explicit_store = "memory_store" in intents
        explicit_recall = "memory_recall" in intents
        explicit_web_search = "web_search" in intents
        skip_auto_persist = should_skip_auto_memory_persist(intents)
        facts_collection = self.facts_collection_for_user(user_id)
        preferences_collection = self.preferences_collection_for_user(user_id)

        if "memory_store" in intents and memory_skill:
            store_text = self.extract_memory_store_text(message, routing_profile)
            store_result = await memory_skill.execute(
                query=store_text,
                params={
                    "action": "store",
                    "text": store_text,
                    "user_id": user_id,
                    "collection": facts_collection,
                    "memory_type": "fact",
                    "source": "explicit",
                },
            )
            results.append(store_result)

        if "memory_recall" in intents and memory_skill:
            recall_query = self.extract_memory_recall_query(message, routing_profile)
            family_base = (facts_collection or memory_collection or session_collection or "").strip()
            merged_top_k = max(
                int(self.settings.memory.top_k),
                int(self.settings.auto_memory.session_recall_top_k) + int(self.settings.auto_memory.user_recall_top_k),
            )
            recall_result = await memory_skill.execute(
                query=recall_query,
                params={
                    "action": "recall",
                    "top_k": merged_top_k,
                    "user_id": user_id,
                    "collection": family_base,
                },
            )
            recall_result.skill_name = "memory_recall"
            results.append(recall_result)

        if "web_search" in intents:
            web_search_skill = self.web_search_skill_getter()
            if web_search_skill is not None:
                web_query = self.extract_web_search_query(message, routing_profile)
                note_hits = await search_note_hits(
                    base_dir=BASE_DIR,
                    username=user_id,
                    settings=self.settings,
                    query=web_query,
                    limit=3,
                )
                web_result = await web_search_skill.execute(
                    web_query,
                    {
                        "action": "search",
                        "user_id": user_id,
                        "language": language,
                        "note_context_hits": [hit.as_dict() for hit in note_hits],
                    },
                )
                web_result.skill_name = "web_search"
                results.append(web_result)

        if auto_memory_enabled and not explicit_recall and not explicit_web_search and memory_skill:
            auto = AutoMemoryExtractor.decide(
                message,
                max_facts=self.settings.auto_memory.max_facts_per_message,
            )
            if auto.recall_query:
                session_recall = await memory_skill.execute(
                    query=auto.recall_query,
                    params={
                        "action": "recall",
                        "top_k": self.settings.auto_memory.session_recall_top_k,
                        "user_id": user_id,
                        "collection": session_collection or memory_collection or "",
                    },
                )
                if session_recall.content and "Keine passende Erinnerung gefunden." not in session_recall.content:
                    session_recall.skill_name = "memory_session"
                    session_recall.content = f"[Session Memory]\n{session_recall.content}"
                    results.append(session_recall)

                user_recall = await memory_skill.execute(
                    query=auto.recall_query,
                    params={
                        "action": "recall",
                        "top_k": self.settings.auto_memory.user_recall_top_k,
                        "user_id": user_id,
                        "collection": memory_collection or "",
                    },
                )
                if user_recall.content and "Keine passende Erinnerung gefunden." not in user_recall.content:
                    user_recall.skill_name = "memory_user"
                    user_recall.content = f"[User Memory]\n{user_recall.content}"
                    results.append(user_recall)

            if not explicit_store and not skip_auto_persist and auto.facts:
                for fact in auto.facts:
                    store_result = await memory_skill.execute(
                        query=fact,
                        params={
                            "action": "store",
                            "text": fact,
                            "user_id": user_id,
                            "collection": facts_collection,
                            "memory_type": "fact",
                            "source": "auto",
                        },
                    )
                    if not store_result.success:
                        results.append(store_result)

            if not explicit_store and not skip_auto_persist and auto.preferences:
                for preference in auto.preferences:
                    pref_result = await memory_skill.execute(
                        query=preference,
                        params={
                            "action": "store",
                            "text": preference,
                            "user_id": user_id,
                            "collection": preferences_collection,
                            "memory_type": "preference",
                            "source": "auto",
                        },
                    )
                    if not pref_result.success:
                        results.append(pref_result)

            if session_collection and not skip_auto_persist and auto.should_persist_session:
                session_note = self.normalize_spaces(message)
                if session_note:
                    session_result = await memory_skill.execute(
                        query=session_note,
                        params={
                            "action": "store",
                            "text": session_note,
                            "user_id": user_id,
                            "collection": session_collection,
                            "memory_type": "session",
                            "source": "auto_session",
                        },
                    )
                    if not session_result.success:
                        results.append(session_result)

            results.append(
                SkillResult(
                    skill_name="auto_memory_extraction",
                    content="",
                    success=True,
                    metadata={
                        "extraction_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                        "extraction_model": "rule_based",
                    },
                )
            )

        return results
