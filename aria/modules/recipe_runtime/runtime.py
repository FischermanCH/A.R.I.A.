from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable
from urllib.request import urlopen

from aria.modules.configuration_foundations.config import RoutingLanguageConfig
from aria.modules.action_contracts.connection import guardrail_kind_for_capability
from aria.modules.runtime_guardrails.guardrails import evaluate_guardrail, resolve_guardrail_profile
from aria.modules.platform_primitives.i18n import I18NStore
from aria.modules.memory.recall_contract import build_memory_recall_params
from aria.modules.notes.context import note_context_block
from aria.modules.notes.context import note_context_detail_lines
from aria.modules.notes.context import search_note_hits
from aria.modules.memory.personal import consolidate_personal_claim_batch
from aria.modules.memory.personal import store_personal_claim
from aria.modules.recipe_runtime.file_adapters import RecipeFileRuntime
from aria.modules.recipe_runtime.http import RecipeHttpRuntime
from aria.modules.recipe_runtime.messaging import RecipeMessagingRuntime
from aria.modules.recipe_runtime.messaging import decode_mail_header as _messaging_decode_mail_header
from aria.modules.recipe_runtime.calendar import RecipeCalendarRuntime
from aria.modules.recipe_runtime.calendar import format_google_calendar_event_time as _calendar_format_event_time
from aria.modules.recipe_runtime.calendar import google_calendar_range_label as _calendar_range_label
from aria.modules.recipe_runtime.calendar import google_calendar_time_bounds as _calendar_time_bounds
from aria.modules.recipe_runtime.rss import RecipeRssRuntime
from aria.modules.recipe_runtime.rss import clean_feed_summary as _rss_clean_feed_summary
from aria.modules.recipe_runtime.rss import clean_feed_url as _rss_clean_feed_url
from aria.modules.recipe_runtime.rss import format_feed_timestamp as _rss_format_feed_timestamp
from aria.modules.recipe_runtime.rss import parse_feed_timestamp as _rss_parse_feed_timestamp
from aria.modules.recipe_runtime.rss import xml_name as _rss_xml_name
from aria.modules.recipe_runtime.steps import RecipeStepExecutor
from aria.modules.recipe_runtime.contracts import is_recipe_intent
from aria.modules.recipe_runtime.contracts import is_recipe_status_intent
from aria.modules.recipe_runtime.contracts import recipe_id_from_intent
from aria.modules.skill_contracts.contracts import SkillResult


SSHExecutor = Callable[..., Awaitable[SkillResult]]
BASE_DIR = Path(__file__).resolve().parents[3]
_RECIPE_RUNTIME_I18N = I18NStore(BASE_DIR / "aria" / "i18n")
_RECIPE_ID_INVALID_RE = re.compile(r"[^a-z0-9_-]")
_RECIPE_ID_DASH_RE = re.compile(r"-+")
_CONDITION_SOURCE_RE = re.compile(r"[^a-z0-9_-]")


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


def _legacy_recipe_dir_for(skills_dir: Path) -> Path:
    if skills_dir.name == "recipes" and skills_dir.parent.name == "data":
        return skills_dir.parent / "skills"
    return skills_dir.parent / "skills"


def _iter_runtime_recipe_manifest_paths(skills_dir: Path) -> list[Path]:
    rows: list[Path] = []
    seen_ids: set[str] = set()
    for root in (skills_dir, _legacy_recipe_dir_for(skills_dir)):
        if root == skills_dir:
            root.mkdir(parents=True, exist_ok=True)
        elif not root.exists():
            continue
        for path in sorted(root.glob("*.json")):
            if path.name.startswith("_"):
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                rows.append(path)
                continue
            recipe_id = sanitize_recipe_id(payload.get("id", "")) if isinstance(payload, dict) else ""
            dedupe_key = recipe_id or sanitize_recipe_id(path.stem)
            if dedupe_key and dedupe_key in seen_ids:
                continue
            if dedupe_key:
                seen_ids.add(dedupe_key)
            rows.append(path)
    return rows


def _runtime_recipe_cache_signature(files: list[Path], config_path: Path) -> tuple[tuple[str, int, int], ...]:
    rows: list[tuple[str, int, int]] = []
    for path in files + [config_path]:
        try:
            stat = path.stat()
        except OSError:
            rows.append((str(path), -1, -1))
            continue
        rows.append((str(path), int(stat.st_mtime_ns), int(stat.st_size)))
    return tuple(rows)


def load_stored_recipe_runtime(
    *,
    skills_dir: Path,
    config_path: Path,
    cache: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        files = _iter_runtime_recipe_manifest_paths(skills_dir)
        sign = _runtime_recipe_cache_signature(files, config_path)
        if sign == cache.get("sign"):
            return list(cache.get("rows", [])), cache

        toggles = load_recipe_toggles(config_path)
        rows: list[dict[str, Any]] = []
        errors: list[str] = []
        seen_ids: set[str] = set()
        for path in files:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(payload, dict):
                    errors.append(f"{path.name}: manifest_not_object")
                    continue
                recipe_id = sanitize_recipe_id(payload.get("id", ""))
                name = str(payload.get("name", "")).strip()
                if not recipe_id or not name:
                    errors.append(f"{path.name}: missing_id_or_name")
                    continue
                if recipe_id in seen_ids:
                    continue
                seen_ids.add(recipe_id)
                connections = payload.get("connections", [])
                if not isinstance(connections, list):
                    connections = []
                steps = normalize_recipe_steps(payload.get("steps", []))
                if not steps:
                    errors.append(f"{path.name}: no_valid_steps")
                    continue
                rows.append(
                    {
                        "id": recipe_id,
                        "name": name[:80],
                        "connections": [str(item).strip().lower() for item in connections if str(item).strip()][:20],
                        "description": str(payload.get("description", "")).strip()[:400],
                        "steps": steps,
                        "enabled": bool(toggles.get(recipe_id, bool(payload.get("enabled_default", True)))),
                    }
                )
            except Exception as exc:
                errors.append(f"{path.name}: {type(exc).__name__}")
                continue
        next_cache = {"sign": sign, "rows": rows, "errors": errors}
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


def should_skip_recipe_auto_memory_persist(intents: list[str]) -> bool:
    normalized = [str(intent).strip().lower() for intent in intents]
    if any(is_recipe_status_intent(intent) for intent in normalized):
        return True
    return any(is_recipe_intent(intent) for intent in normalized)


class RecipeRuntime:
    def __init__(
        self,
        *,
        settings: Any,
        llm_client: Any,
        memory_skill_getter: Callable[[], Any],
        execute_custom_ssh_command: SSHExecutor,
        extract_memory_store_text: Callable[..., str],
        extract_memory_recall_query: Callable[..., str],
        facts_collection_for_user: Callable[[str], str],
        preferences_collection_for_user: Callable[[str], str],
        normalize_spaces: Callable[[str], str],
        truncate_text: Callable[[str, int], str],
    ) -> None:
        self.settings = settings
        self.llm_client = llm_client
        self.memory_skill_getter = memory_skill_getter
        self.execute_custom_ssh_command = execute_custom_ssh_command
        self.extract_memory_store_text = extract_memory_store_text
        self.extract_memory_recall_query = extract_memory_recall_query
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

    async def execute_custom_steps(
        self, row: dict[str, Any], message: str, language: str = "de", *, user_id: str = "",
    ) -> SkillResult:
        from aria.modules.platform_primitives.recipe_progress import RECIPE_PROGRESS_STORE

        return await self.step_executor.execute(
            row=row, message=message, language=language, user_id=user_id,
            progress_store=RECIPE_PROGRESS_STORE if user_id else None,
        )

    async def _store_explicit_personal_memory(
        self,
        *,
        claims: list[dict[str, Any]],
        user_id: str,
        memory_skill: Any,
        facts_collection: str,
        preferences_collection: str,
        language: str,
        request_id: str = "",
    ) -> SkillResult:
        consolidation = await consolidate_personal_claim_batch(
            claims,
            llm_client=self.llm_client,
            user_id=user_id,
            request_id=request_id,
        )
        if not consolidation.get("ok"):
            return SkillResult(
                skill_name="personal_memory_capture",
                content=_recipe_text(
                    language,
                    "personal_memory_capture_not_stored",
                    "I could not derive a safe personal memory from that. Nothing was stored.",
                ),
                success=True,
                metadata={
                    "direct_chat_response": True,
                    "personal_claim_results": [],
                    "capture_stored": False,
                    "extraction_model": "turn_action_contract",
                    "extraction_usage": dict(consolidation.get("usage") or {}),
                    "detail_lines": [
                        "Routing Debug: personal_memory_capture outcome=not_stored "
                        "reason=claim_batch_consolidation_failed "
                        f"input_claims={int(consolidation.get('input_count', 0) or 0)} "
                        "authority=personal_claim_batch_v1"
                    ],
                },
            )
        consolidated_claims = list(consolidation.get("claims") or [])
        claim_results: list[dict[str, Any]] = []
        for claim in consolidated_claims:
            claim_result = await store_personal_claim(
                memory_skill=memory_skill,
                llm_client=self.llm_client,
                claim=claim,
                user_id=user_id,
                facts_collection=facts_collection,
                preferences_collection=preferences_collection,
                request_id=request_id,
            )
            claim_results.append(claim_result)

        stored_claims = [row for row in claim_results if row.get("stored")]
        review_claims = [
            row
            for row in claim_results
            if not row.get("stored") and row.get("claim")
        ]
        review_blockers = sorted(
            {
                str(blocker)
                for row in review_claims
                for blocker in list(row.get("activation_blockers") or [])
                if str(blocker)
            }
        )
        review_blocker_trace = ",".join(review_blockers) or "other_review_gate"
        relation_sources = sorted(
            {
                str(dict(row.get("relation") or {}).get("source") or "unknown")
                for row in claim_results
            }
        )
        relation_model_calls = sum(
            1
            for row in claim_results
            if str(dict(row.get("relation") or {}).get("source") or "") == "bounded_llm"
        )
        timing_totals = {
            key: sum(
                int(dict(row.get("timings") or {}).get(key, 0) or 0)
                for row in claim_results
            )
            for key in ("list_existing_ms", "relation_ms", "store_ms", "total_ms")
        }
        capture_runtime_detail = (
            "Routing Debug: personal_memory_capture_runtime "
            f"claims={len(claim_results)} relation_model_calls={relation_model_calls} "
            f"relation_sources={','.join(relation_sources) or '-'} "
            f"list_existing_ms={timing_totals['list_existing_ms']} "
            f"relation_ms={timing_totals['relation_ms']} "
            f"store_ms={timing_totals['store_ms']} total_ms={timing_totals['total_ms']}"
        )
        if stored_claims and review_claims:
            stored_values = [
                self.normalize_spaces(str((row.get("claim") or {}).get("value") or ""))
                for row in stored_claims
            ]
            review_values = [
                self.normalize_spaces(str((row.get("claim") or {}).get("value") or ""))
                for row in review_claims
            ]
            return SkillResult(
                skill_name="personal_memory_capture",
                content=_recipe_text(
                    language,
                    "personal_memory_capture_partial",
                    "Stored as personal memory: {stored_values}. Captured for review: {review_values}.",
                    stored_values="; ".join(value for value in stored_values if value),
                    review_values="; ".join(value for value in review_values if value),
                ),
                success=True,
                metadata={
                    "direct_chat_response": True,
                    "personal_claim_results": claim_results,
                    "review_required": True,
                    "extraction_model": "turn_action_contract",
                    "extraction_usage": dict(consolidation.get("usage") or {}),
                    "detail_lines": [
                        "Routing Debug: personal_memory_capture outcome=partial "
                        f"stored={len(stored_claims)} review={len(review_claims)} "
                        f"blockers={review_blocker_trace} "
                        f"input_claims={int(consolidation.get('input_count', 0) or 0)} "
                        f"consolidated_claims={len(consolidated_claims)} authority=personal_claim_v1",
                        capture_runtime_detail,
                    ],
                },
            )
        if stored_claims:
            values = [
                self.normalize_spaces(str((row.get("claim") or {}).get("value") or ""))
                for row in stored_claims
            ]
            values = [value for value in values if value]
            return SkillResult(
                skill_name="personal_memory_capture",
                content=_recipe_text(
                    language,
                    "personal_memory_capture_stored",
                    "Personal memory stored: {values}",
                    values="; ".join(values),
                ),
                success=True,
                metadata={
                    "direct_chat_response": True,
                    "personal_claim_results": claim_results,
                    "extraction_model": "turn_action_contract",
                    "extraction_usage": dict(consolidation.get("usage") or {}),
                    "detail_lines": [
                        "Routing Debug: personal_memory_capture outcome=stored "
                        f"claims={len(stored_claims)} "
                        f"input_claims={int(consolidation.get('input_count', 0) or 0)} "
                        f"consolidated_claims={len(consolidated_claims)} authority=personal_claim_v1",
                        capture_runtime_detail,
                    ],
                },
            )
        if review_claims:
            return SkillResult(
                skill_name="personal_memory_capture",
                content=_recipe_text(
                    language,
                    "personal_memory_capture_review",
                    "The personal memory was captured for review and is not active yet.",
                ),
                success=True,
                metadata={
                    "direct_chat_response": True,
                    "personal_claim_results": claim_results,
                    "review_required": True,
                    "extraction_model": "turn_action_contract",
                    "extraction_usage": dict(consolidation.get("usage") or {}),
                    "detail_lines": [
                        "Routing Debug: personal_memory_capture outcome=review "
                        f"claims={len(review_claims)} blockers={review_blocker_trace} "
                        "authority=personal_claim_v1",
                        capture_runtime_detail,
                    ],
                },
            )

        return SkillResult(
            skill_name="personal_memory_capture",
            content=_recipe_text(
                language,
                "personal_memory_capture_not_stored",
                "I could not derive a safe personal memory from that. Nothing was stored.",
            ),
            success=True,
            metadata={
                "direct_chat_response": True,
                "personal_claim_results": claim_results,
                "capture_stored": False,
                "extraction_model": "turn_action_contract",
                "extraction_usage": dict(consolidation.get("usage") or {}),
                "detail_lines": [
                    "Routing Debug: personal_memory_capture outcome=not_stored "
                    "reason=missing_or_invalid_turn_action_claim "
                    "authority=personal_claim_v1",
                    capture_runtime_detail,
                ],
            },
        )

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
        suppress_web_search_note_context: bool = False,
        query_overrides: dict[str, str] | None = None,
        context_overrides: dict[str, Any] | None = None,
    ) -> list[SkillResult]:
        results: list[SkillResult] = []
        runtime_recipes = runtime_recipes or []
        recipes_by_id = {str(row.get("id", "")): row for row in runtime_recipes}
        query_overrides = query_overrides or {}
        context_overrides = context_overrides or {}

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
        facts_collection = self.facts_collection_for_user(user_id)
        preferences_collection = self.preferences_collection_for_user(user_id)

        if explicit_store and memory_skill:
            action_inputs = context_overrides.get("action_inputs")
            capture_inputs = (
                action_inputs.get("personal_memory_capture")
                if isinstance(action_inputs, dict)
                else {}
            )
            claims = (
                list(capture_inputs.get("personal_claims") or [])
                if isinstance(capture_inputs, dict)
                else []
            )
            results.append(
                await self._store_explicit_personal_memory(
                    claims=claims,
                    user_id=user_id,
                    memory_skill=memory_skill,
                    facts_collection=facts_collection,
                    preferences_collection=preferences_collection,
                    language=language,
                    request_id=str(context_overrides.get("request_id") or ""),
                )
            )

        if "memory_recall" in intents and memory_skill:
            memory_recall_enabled = bool(context_overrides.get("memory_recall_enabled", True))
            if not memory_recall_enabled:
                pass
            else:
                recall_query = str(query_overrides.get("memory_recall") or "").strip() or self.extract_memory_recall_query(message, routing_profile)
                family_base = (facts_collection or memory_collection or session_collection or "").strip()
                memory_collections = getattr(self.settings.memory, "collections", None)
                family_defaults = {
                    "facts": 2,
                    "preferences": 1,
                    "sessions": 2,
                    "knowledge": 2,
                }
                merged_top_k = max(
                    int(self.settings.memory.top_k),
                    sum(
                        max(
                            0,
                            int(
                                getattr(
                                    getattr(memory_collections, name, None),
                                    "top_k",
                                    default,
                                )
                            ),
                        )
                        for name, default in family_defaults.items()
                    ),
                )
                recall_params = build_memory_recall_params(
                    context_overrides=context_overrides,
                    user_id=user_id,
                    collection=family_base,
                    top_k=int(context_overrides.get("memory_top_k") or merged_top_k),
                    default_include_documents=True,
                )
                recall_result = await memory_skill.execute(
                    query=recall_query,
                    params=recall_params,
                )
                recall_result.skill_name = "memory_recall"
                results.append(recall_result)

        notes_query = str(query_overrides.get("notes_search") or "").strip()
        if notes_query:
            note_hits = await search_note_hits(
                base_dir=BASE_DIR,
                username=user_id,
                settings=self.settings,
                query=notes_query,
                limit=8,
                allow_markdown_fallback=True,
            )
            if note_hits:
                results.append(
                    SkillResult(
                        skill_name="notes_search",
                        success=True,
                        content=note_context_block(note_hits, language=language),
                        metadata={
                            "detail_lines": [
                                f"Routing Debug: notes_retrieval query={notes_query}",
                                *note_context_detail_lines(note_hits, language=language),
                            ],
                            "sources": [
                                {
                                    "type": "note",
                                    "title": hit.title,
                                    "folder": hit.folder,
                                    "note_id": hit.note_id,
                                    "snippet": hit.snippet,
                                }
                                for hit in note_hits
                            ],
                        },
                    )
                )

        return results


CustomSkillRuntime = RecipeRuntime
