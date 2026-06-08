from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable
from urllib.parse import urlencode
from urllib.request import urlopen

from aria.core.auto_memory import AutoMemoryExtractor
from aria.core.config import RoutingLanguageConfig
from aria.core.connection_action_contract import guardrail_kind_for_capability
from aria.core.guardrails import evaluate_guardrail, resolve_guardrail_profile
from aria.core.i18n import I18NStore
from aria.core.notes_context import search_note_hits
from aria.core.recipe_runtime_matching import looks_like_recipe_execution_request as _matching_looks_like_recipe_execution_request
from aria.core.recipe_runtime_matching import match_stored_recipe_intents as _matching_match_stored_recipe_intents
from aria.core.recipe_runtime_matching import recipe_match_score as _matching_recipe_match_score
from aria.core.recipe_runtime_matching import recipe_tokens as _matching_recipe_tokens
from aria.core.recipe_runtime_matching import resolve_stored_recipe_intent_with_llm as _matching_resolve_stored_recipe_intent_with_llm
from aria.core.recipe_runtime_matching import significant_recipe_tokens as _matching_significant_recipe_tokens
from aria.core.recipe_runtime_contract import RECIPE_STATUS_INTENT
from aria.core.recipe_runtime_file_adapters import RecipeFileRuntime
from aria.core.recipe_runtime_http import RecipeHttpRuntime
from aria.core.recipe_runtime_messaging import RecipeMessagingRuntime
from aria.core.recipe_runtime_messaging import decode_mail_header as _messaging_decode_mail_header
from aria.core.recipe_runtime_calendar import RecipeCalendarRuntime
from aria.core.recipe_runtime_calendar import format_google_calendar_event_time as _calendar_format_event_time
from aria.core.recipe_runtime_calendar import google_calendar_range_label as _calendar_range_label
from aria.core.recipe_runtime_calendar import google_calendar_time_bounds as _calendar_time_bounds
from aria.core.recipe_runtime_rss import RecipeRssRuntime
from aria.core.recipe_runtime_rss import clean_feed_summary as _rss_clean_feed_summary
from aria.core.recipe_runtime_rss import clean_feed_url as _rss_clean_feed_url
from aria.core.recipe_runtime_rss import format_feed_timestamp as _rss_format_feed_timestamp
from aria.core.recipe_runtime_rss import parse_feed_timestamp as _rss_parse_feed_timestamp
from aria.core.recipe_runtime_rss import xml_name as _rss_xml_name
from aria.core.recipe_runtime_status import build_recipe_status_text
from aria.core.recipe_runtime_steps import RecipeStepExecutor
from aria.core.recipe_runtime_steps import _evaluate_skill_step_condition
from aria.core.recipe_runtime_steps import _format_ssh_step_run_summary
from aria.core.recipe_runtime_steps import render_step_template
from aria.core.recipe_runtime_contract import is_recipe_intent
from aria.core.recipe_runtime_contract import is_recipe_status_intent
from aria.core.recipe_runtime_contract import recipe_id_from_intent
from aria.skills.base import SkillResult


SSHExecutor = Callable[..., Awaitable[SkillResult]]
BASE_DIR = Path(__file__).resolve().parents[2]
_RECIPE_RUNTIME_I18N = I18NStore(BASE_DIR / "aria" / "i18n")
_RECIPE_RUNTIME_LEXICON_PATH = BASE_DIR / "aria" / "lexicons" / "recipe_runtime.json"


def _load_recipe_runtime_lexicon() -> dict[str, Any]:
    try:
        raw = json.loads(_RECIPE_RUNTIME_LEXICON_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not load recipe runtime lexicon: {_RECIPE_RUNTIME_LEXICON_PATH}") from exc
    return raw if isinstance(raw, dict) else {}


_RECIPE_RUNTIME_LEXICON = _load_recipe_runtime_lexicon()


def _lexicon_set(name: str) -> set[str]:
    raw = _RECIPE_RUNTIME_LEXICON.get(name, [])
    if not isinstance(raw, list):
        return set()
    return {str(value).strip().lower() for value in raw if str(value).strip()}


def _lexicon_tuple(name: str) -> tuple[str, ...]:
    raw = _RECIPE_RUNTIME_LEXICON.get(name, [])
    if not isinstance(raw, list):
        return ()
    return tuple(str(value).strip().lower() for value in raw if str(value).strip())

_RECIPE_ID_INVALID_RE = re.compile(r"[^a-z0-9_-]")
_RECIPE_ID_DASH_RE = re.compile(r"-+")
_CONDITION_SOURCE_RE = re.compile(r"[^a-z0-9_-]")
_RECIPE_MATCH_STOPWORDS = _lexicon_set("skill_match_stopwords")
_RECIPE_ACTION_HINTS = _lexicon_set("skill_action_hints")
_RECIPE_EXECUTION_PHRASES = _lexicon_tuple("skill_execution_phrases")


def _recipe_text(language: str | None, key: str, default: str = "", **values: Any) -> str:
    template = _RECIPE_RUNTIME_I18N.t(language or "de", f"recipe_runtime.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template


def sanitize_recipe_id(value: str) -> str:
    raw = str(value or "").strip().lower()
    raw = _RECIPE_ID_INVALID_RE.sub("-", raw)
    raw = _RECIPE_ID_DASH_RE.sub("-", raw).strip("-")
    return raw[:48]


def normalize_recipe_keywords(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    rows: list[str] = []
    for item in value:
        text = str(item or "").strip().lower()
        if text:
            rows.append(text)
    return rows[:30]


def normalize_recipe_steps(value: Any) -> list[dict[str, Any]]:
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


sanitize_skill_id = sanitize_recipe_id
normalize_skill_keywords = normalize_recipe_keywords
normalize_skill_steps = normalize_recipe_steps
_SKILL_ID_INVALID_RE = _RECIPE_ID_INVALID_RE
_SKILL_ID_DASH_RE = _RECIPE_ID_DASH_RE


def load_recipe_toggles(config_path: Path) -> dict[str, bool]:
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
            recipe_id = sanitize_recipe_id(str(key))
            if not recipe_id or not isinstance(section, dict):
                continue
            toggles[recipe_id] = bool(section.get("enabled", True))
        return toggles
    except Exception:
        return {}


def load_stored_recipe_runtime(
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

        toggles = load_recipe_toggles(config_path)
        rows: list[dict[str, Any]] = []
        for path in files:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(payload, dict):
                    continue
                recipe_id = sanitize_recipe_id(payload.get("id", ""))
                name = str(payload.get("name", "")).strip()
                if not recipe_id or not name:
                    continue
                connections = payload.get("connections", [])
                if not isinstance(connections, list):
                    connections = []
                steps = normalize_recipe_steps(payload.get("steps", []))
                if not steps:
                    continue
                rows.append(
                    {
                        "id": recipe_id,
                        "name": name[:80],
                        "keywords": normalize_recipe_keywords(payload.get("router_keywords", [])),
                        "connections": [str(item).strip().lower() for item in connections if str(item).strip()][:20],
                        "description": str(payload.get("description", "")).strip()[:400],
                        "steps": steps,
                        "enabled": bool(toggles.get(recipe_id, bool(payload.get("enabled_default", True)))),
                    }
                )
            except Exception:
                continue
        next_cache = {"sign": sign, "rows": rows}
        return list(rows), next_cache
    except Exception:
        return [], cache


def load_recipe_runtime(
    *,
    skills_dir: Path,
    config_path: Path,
    cache: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    return load_stored_recipe_runtime(skills_dir=skills_dir, config_path=config_path, cache=cache)


def load_custom_skill_toggles(config_path: Path) -> dict[str, bool]:
    return load_recipe_toggles(config_path)


def load_custom_skill_runtime(
    *,
    skills_dir: Path,
    config_path: Path,
    cache: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    return load_recipe_runtime(skills_dir=skills_dir, config_path=config_path, cache=cache)


def match_stored_recipe_intents(message: str, runtime_recipes: list[dict[str, Any]]) -> list[str]:
    return _matching_match_stored_recipe_intents(
        message,
        runtime_recipes,
        stopwords=_RECIPE_MATCH_STOPWORDS,
        action_hints=_RECIPE_ACTION_HINTS,
    )


def match_custom_skill_intents(message: str, runtime_recipes: list[dict[str, Any]]) -> list[str]:
    return match_stored_recipe_intents(message, runtime_recipes)


def match_recipe_intents(message: str, runtime_recipes: list[dict[str, Any]]) -> list[str]:
    return match_stored_recipe_intents(message, runtime_recipes)


async def resolve_stored_recipe_intent_with_llm(
    message: str,
    runtime_recipes: list[dict[str, Any]],
    llm_client: Any | None,
) -> list[str]:
    return await _matching_resolve_stored_recipe_intent_with_llm(
        message,
        runtime_recipes,
        llm_client,
        action_hints=_RECIPE_ACTION_HINTS,
        execution_phrases=_RECIPE_EXECUTION_PHRASES,
        recipe_text=_recipe_text,
    )


async def resolve_custom_skill_intent_with_llm(
    message: str,
    runtime_recipes: list[dict[str, Any]],
    llm_client: Any | None,
) -> list[str]:
    return await resolve_stored_recipe_intent_with_llm(message, runtime_recipes, llm_client)


async def resolve_recipe_intent_with_llm(
    message: str,
    runtime_recipes: list[dict[str, Any]],
    llm_client: Any | None,
) -> list[str]:
    return await resolve_stored_recipe_intent_with_llm(message, runtime_recipes, llm_client)


def should_skip_recipe_auto_memory_persist(intents: list[str]) -> bool:
    normalized = [str(intent).strip().lower() for intent in intents]
    if any(is_recipe_status_intent(intent) for intent in normalized):
        return True
    return any(is_recipe_intent(intent) for intent in normalized)


def should_skip_auto_memory_persist(intents: list[str]) -> bool:
    return should_skip_recipe_auto_memory_persist(intents)


class RecipeRuntime:
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
        self.file_runtime = RecipeFileRuntime(
            get_connection_profile=self._get_connection_profile,
            resolve_local_path=self._resolve_local_path,
            enforce_file_guardrail=self._enforce_file_guardrail,
            format_directory_listing=self._format_directory_listing,
            truncate_text=self.truncate_text,
            recipe_text=_recipe_text,
        )
        self.rss_runtime = RecipeRssRuntime(
            get_connection_profile=self._get_connection_profile,
            truncate_text=self.truncate_text,
            recipe_text=_recipe_text,
        )
        self.calendar_runtime = RecipeCalendarRuntime(
            get_connection_profile=self._get_connection_profile,
            truncate_text=self.truncate_text,
            recipe_text=_recipe_text,
            urlopen_func=lambda *args, **kwargs: urlopen(*args, **kwargs),
        )
        self.http_runtime = RecipeHttpRuntime(
            get_connection_profile=self._get_connection_profile,
            enforce_connection_guardrail=self._enforce_connection_guardrail,
            truncate_text=self.truncate_text,
            recipe_text=_recipe_text,
            urlopen_func=lambda *args, **kwargs: urlopen(*args, **kwargs),
        )
        self.messaging_runtime = RecipeMessagingRuntime(
            get_connection_profile=self._get_connection_profile,
            format_timestamp=self._format_feed_timestamp,
            truncate_text=self.truncate_text,
            recipe_text=_recipe_text,
        )
        self.step_executor = RecipeStepExecutor(self)

    def _resolve_local_path(self, value: str) -> Path:
        path = Path(str(value or "").strip())
        if not path.is_absolute():
            path = (BASE_DIR / path).resolve()
        return path

    def _get_connection_profile(self, kind: str, connection_ref: str) -> Any:
        rows = getattr(getattr(self.settings, "connections", object()), str(kind).strip().lower(), {})
        connection = rows.get(connection_ref) if isinstance(rows, dict) else None
        if connection is None:
            raise ValueError(
                _recipe_text(
                    "de",
                    "connection_profile_not_found",
                    "{kind} profile not found: {connection_ref}",
                    kind=str(kind).upper(),
                    connection_ref=connection_ref,
                )
            )
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
            raise ValueError(_recipe_text("de", "guardrail_kind_mismatch", "{label} guardrail type does not match: {guardrail_ref}", label=label, guardrail_ref=guardrail_ref))
        if decision.reason == "guardrail_denied":
            raise ValueError(_recipe_text("de", "guardrail_denied", "{label} guardrail blocks this request: {guardrail_ref}", label=label, guardrail_ref=guardrail_ref))
        if decision.reason == "guardrail_not_allowed":
            raise ValueError(_recipe_text("de", "guardrail_not_allowed", "{label} guardrail does not allow this request: {guardrail_ref}", label=label, guardrail_ref=guardrail_ref))
        raise ValueError(_recipe_text("de", "guardrail_denied", "{label} guardrail blocks this request: {guardrail_ref}", label=label, guardrail_ref=guardrail_ref))

    def _enforce_file_guardrail(
        self,
        *,
        connection: Any,
        operation: str,
        resolved_path: str,
        content: str = "",
    ) -> None:
        clean_operation = str(operation or "").strip().lower()
        capability = {
            "read": "file_read",
            "write": "file_write",
            "list": "file_list",
        }.get(clean_operation, "")
        operation_aliases = {
            "read": "file_read file access read get download readonly",
            "write": "file_write file access write create upload put delete",
            "list": "file_list file access list read readonly directory",
        }.get(clean_operation, "file access")
        eval_parts = [operation_aliases, clean_operation, str(resolved_path or "").strip()]
        if content:
            eval_parts.append(str(content).strip())
        self._enforce_connection_guardrail(
            connection=connection,
            connection_ref="",
            guardrail_kind=guardrail_kind_for_capability(capability),
            evaluation_text=" ".join(part for part in eval_parts if part),
            label=_recipe_text("de", "file_label", "File"),
        )

    def _format_directory_listing(self, transport: str, resolved_path: str, names: list[str], *, language: str = "de") -> str:
        if not names:
            return _recipe_text(language, "message_768", '{transport} directory is empty: {resolved_path}', transport=transport, resolved_path=resolved_path)
        prefix = _recipe_text(language, "message_769", 'Contents of {resolved_path}:', resolved_path=resolved_path)
        return self.truncate_text(prefix + "\n- " + "\n- ".join(names), 1400)

    @staticmethod
    def _xml_name(tag: str) -> str:
        return _rss_xml_name(tag)

    @staticmethod
    def _clean_feed_url(value: str) -> str:
        return _rss_clean_feed_url(value)

    @staticmethod
    def _format_feed_timestamp(value: str) -> str:
        return _rss_format_feed_timestamp(value)

    @staticmethod
    def _google_calendar_time_bounds(range_hint: str) -> tuple[datetime, datetime, int]:
        return _calendar_time_bounds(range_hint)

    @staticmethod
    def _google_calendar_range_label(range_hint: str, *, language: str = "de") -> str:
        return _calendar_range_label(_recipe_text, range_hint, language=language)

    @staticmethod
    def _format_google_calendar_event_time(event: dict[str, Any], *, language: str = "de") -> str:
        return _calendar_format_event_time(_recipe_text, event, language=language)

    @staticmethod
    def _clean_feed_summary(value: str, limit: int = 220) -> str:
        return _rss_clean_feed_summary(value, limit=limit)

    @staticmethod
    def _parse_feed_timestamp(value: str) -> datetime | None:
        return _rss_parse_feed_timestamp(value)

    def _load_rss_entries(self, connection_ref: str, *, language: str = "de") -> tuple[str, list[dict[str, str]]]:
        return self.rss_runtime.load_entries(connection_ref, language=language)

    def _run_rss_read_step(self, connection_ref: str, *, language: str = "de", requested_count: int = 0) -> str:
        return self.rss_runtime.execute_read(connection_ref, language=language, requested_count=requested_count)

    def execute_rss_group_read(
        self,
        group_name: str,
        connection_refs: list[str],
        *,
        language: str = "de",
        requested_count: int = 0,
    ) -> str:
        return self.rss_runtime.execute_group_read(
            group_name,
            connection_refs,
            language=language,
            requested_count=requested_count,
            entry_loader=self._load_rss_entries,
        )

    def execute_sftp_read(self, connection_ref: str, remote_path: str) -> str:
        return self.file_runtime.execute_sftp_read(connection_ref, remote_path)

    def execute_sftp_write(self, connection_ref: str, remote_path: str, content: str) -> str:
        return self.file_runtime.execute_sftp_write(connection_ref, remote_path, content)

    def execute_sftp_list(self, connection_ref: str, remote_path: str, *, language: str = "de") -> str:
        return self.file_runtime.execute_sftp_list(connection_ref, remote_path, language=language)

    def execute_smb_read(self, connection_ref: str, remote_path: str) -> str:
        return self.file_runtime.execute_smb_read(connection_ref, remote_path)

    def execute_smb_write(self, connection_ref: str, remote_path: str, content: str) -> str:
        return self.file_runtime.execute_smb_write(connection_ref, remote_path, content)

    def execute_smb_list(self, connection_ref: str, remote_path: str, *, language: str = "de") -> str:
        return self.file_runtime.execute_smb_list(connection_ref, remote_path, language=language)

    def execute_rss_read(self, connection_ref: str, *, language: str = "de", requested_count: int = 0) -> str:
        return self._run_rss_read_step(connection_ref, language=language, requested_count=requested_count)

    def execute_google_calendar_read(
        self,
        connection_ref: str,
        range_hint: str = "upcoming",
        search_query: str = "",
        *,
        language: str = "de",
    ) -> str:
        return self.calendar_runtime.execute_read(
            connection_ref,
            range_hint,
            search_query,
            language=language,
        )

    def execute_webhook_send(self, connection_ref: str, content: str, *, language: str = "de") -> str:
        return self.http_runtime.execute_webhook_send(connection_ref, content, language=language)

    def execute_discord_send(self, connection_ref: str, content: str, *, language: str = "de") -> str:
        return self.http_runtime.execute_discord_send(connection_ref, content, language=language)

    def execute_http_api_request(
        self,
        connection_ref: str,
        request_path: str = "",
        content: str = "",
        *,
        language: str = "de",
        confirmed: bool = False,
    ) -> str:
        return self.http_runtime.execute_http_api_request(
            connection_ref,
            request_path,
            content,
            language=language,
            confirmed=confirmed,
        )

    def execute_email_send(self, connection_ref: str, content: str, *, language: str = "de") -> str:
        return self.messaging_runtime.execute_email_send(connection_ref, content, language=language)

    @staticmethod
    def _decode_mail_header(value: str) -> str:
        return _messaging_decode_mail_header(value)

    def _open_imap_connection(self, connection_ref: str, *, language: str = "de") -> Any:
        return self.messaging_runtime._open_imap_connection(connection_ref, language=language)

    def execute_imap_read(self, connection_ref: str, *, language: str = "de") -> str:
        return self.messaging_runtime.execute_imap_read(connection_ref, language=language)

    def execute_imap_search(self, connection_ref: str, query: str, *, language: str = "de") -> str:
        return self.messaging_runtime.execute_imap_search(connection_ref, query, language=language)

    def execute_mqtt_publish(self, connection_ref: str, topic: str, content: str, *, language: str = "de") -> str:
        return self.messaging_runtime.execute_mqtt_publish(connection_ref, topic, content, language=language)

    async def execute_custom_steps(self, row: dict[str, Any], message: str, language: str = "de") -> SkillResult:
        return await self.step_executor.execute(row=row, message=message, language=language)

    async def run_skills(
        self,
        intents: list[str],
        message: str,
        user_id: str,
        routing_profile: RoutingLanguageConfig,
        language: str = "de",
        runtime_recipes: list[dict[str, Any]] | None = None,
        memory_collection: str | None = None,
        session_collection: str | None = None,
        auto_memory_enabled: bool = False,
        suppress_web_search_note_context: bool = False,
    ) -> list[SkillResult]:
        results: list[SkillResult] = []
        runtime_recipes = runtime_recipes or []
        recipes_by_id = {str(row.get("id", "")): row for row in runtime_recipes}

        for intent in intents:
            if not is_recipe_intent(str(intent)):
                continue
            recipe_id = recipe_id_from_intent(str(intent))
            row = recipes_by_id.get(recipe_id)
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
                note_hits = []
                if not suppress_web_search_note_context:
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


CustomSkillRuntime = RecipeRuntime
