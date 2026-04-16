from __future__ import annotations

import re
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any
from uuid import uuid4

from aria.core.action_plan import ActionPlan, MemoryHints, build_action_plan
from aria.core.capability_catalog import build_capability_detail_lines, capability_executor_bindings
from aria.core.capability_context import CapabilityContextStore
from aria.core.capability_router import CapabilityRouter
from aria.core.connection_catalog import connection_kind_label
from aria.core.connection_semantic_resolver import ConnectionSemanticResolver
from aria.core.connection_semantic_resolver import build_connection_aliases
from aria.core.config import RoutingLanguageConfig, Settings
from aria.core.context import ContextAssembler
from aria.core.embedding_client import EmbeddingClient
from aria.core.error_interpreter import ErrorInterpreter
from aria.core.executor_registry import ExecutorRegistry
from aria.core.llm_client import LLMClient
from aria.core.memory_assist import MemoryAssistResolver
from aria.core.prompt_loader import PromptLoader
from aria.core.pricing_catalog import resolve_litellm_pricing_entry
from aria.core.router import KeywordRouter
from aria.core.qdrant_client import create_async_qdrant_client
from aria.core.routing_admin import build_connection_routing_index_status
from aria.core.routing_admin import routing_connections_collection_name
from aria.core.routing_index import DEFAULT_CONNECTION_ROUTING_KINDS
from aria.core.routing_index import RoutingIndexStore
from aria.core.routing_resolver import RoutingResolver
from aria.core.safe_fix import SafeFixExecutor, build_safe_fix_plan, extract_held_packages
from aria.core.skill_runtime import (
    CustomSkillRuntime,
    build_skill_status_text,
    load_custom_skill_toggles,
    load_custom_skill_runtime,
    match_custom_skill_intents,
    normalize_skill_keywords,
    normalize_skill_steps,
    render_step_template,
    resolve_custom_skill_intent_with_llm,
    sanitize_skill_id,
    should_skip_auto_memory_persist,
)
from aria.core.ssh_runtime import SSHRuntime
from aria.core.usage_meter import UsageMeter
from aria.skills.base import SkillResult
from aria.skills.memory import MemorySkill
from aria.skills.web_search import WebSearchSkill


@dataclass
class PipelineResult:
    request_id: str
    text: str
    usage: dict[str, int]
    intents: list[str]
    skill_errors: list[str]
    router_level: int
    duration_ms: int
    chat_cost_usd: float | None = None
    embedding_cost_usd: float | None = None
    total_cost_usd: float | None = None
    safe_fix_plan: list[dict[str, Any]] | None = None
    detail_lines: list[str] = field(default_factory=list)


class Pipeline:
    """Session 2 Pipeline: Load -> Route -> Skills -> Context -> LLM -> Track."""

    def __init__(
        self,
        settings: Settings,
        prompt_loader: PromptLoader,
        llm_client: LLMClient,
        capability_context_store: CapabilityContextStore | None = None,
        usage_meter: UsageMeter | None = None,
        embedding_client: EmbeddingClient | None = None,
    ):
        self.settings = settings
        self.prompt_loader = prompt_loader
        self.llm_client = llm_client
        self.usage_meter = usage_meter or UsageMeter(settings)
        if hasattr(self.llm_client, "usage_meter") and getattr(self.llm_client, "usage_meter", None) is None:
            self.llm_client.usage_meter = self.usage_meter
        self.embedding_client = embedding_client or EmbeddingClient(settings.embeddings, usage_meter=self.usage_meter)

        self.router = KeywordRouter(settings.routing.for_language(None))
        self.capability_router = CapabilityRouter()
        self.capability_context_store = capability_context_store
        self.context_assembler = ContextAssembler()
        self.token_tracker = self.usage_meter.token_tracker

        self.memory_skill: MemorySkill | None = None
        if settings.memory.enabled and settings.memory.backend.lower() == "qdrant":
            self.memory_skill = MemorySkill(
                memory=settings.memory,
                embeddings=settings.embeddings,
                embedding_client=self.embedding_client,
            )
        self.web_search_skill: WebSearchSkill | None = None
        if isinstance(getattr(getattr(settings, "connections", object()), "searxng", {}), dict):
            self.web_search_skill = WebSearchSkill(settings=self.settings)
        self._project_root = Path(__file__).resolve().parents[2]
        self._custom_skills_dir = self._project_root / "data" / "skills"
        self._config_path = self._project_root / "config" / "config.yaml"
        self._error_interpreter = ErrorInterpreter(self._project_root / "config" / "error_interpreter.yaml")
        self._custom_skill_cache: dict[str, Any] = {"sign": None, "rows": []}
        self._ssh_runtime = SSHRuntime(
            settings=self.settings,
            error_interpreter=self._error_interpreter,
            normalize_spaces=self._normalize_spaces,
            truncate_text=self._truncate_text,
            extract_held_packages=extract_held_packages,
        )
        self._safe_fix_executor = SafeFixExecutor(self._execute_custom_ssh_command)
        self._skill_runtime = CustomSkillRuntime(
            settings=self.settings,
            llm_client=self.llm_client,
            memory_skill_getter=lambda: self.memory_skill,
            web_search_skill_getter=lambda: self.web_search_skill,
            execute_custom_ssh_command=self._execute_custom_ssh_command,
            extract_memory_store_text=self._extract_memory_store_text,
            extract_memory_recall_query=self._extract_memory_recall_query,
            extract_web_search_query=self._extract_web_search_query,
            facts_collection_for_user=self._facts_collection_for_user,
            preferences_collection_for_user=self._preferences_collection_for_user,
            normalize_spaces=self._normalize_spaces,
            truncate_text=self._truncate_text,
        )
        self._memory_assist = MemoryAssistResolver(lambda: self.memory_skill, lambda: self.capability_context_store)
        self._semantic_connection_resolver = ConnectionSemanticResolver(self.llm_client)
        self._executor_registry = ExecutorRegistry()
        handler_map = {
            "file_read": self._execute_file_read,
            "file_write": self._execute_file_write,
            "file_list": self._execute_file_list,
            "feed_read": self._execute_feed_read,
            "webhook_send": self._execute_webhook_send,
            "discord_send": self._execute_discord_send,
            "api_request": self._execute_api_request,
            "email_send": self._execute_email_send,
            "mail_read": self._execute_mail_read,
            "mail_search": self._execute_mail_search,
            "mqtt_publish": self._execute_mqtt_publish,
            "ssh_command": self._execute_ssh_command,
        }
        for connection_kind, capability in capability_executor_bindings():
            handler = handler_map.get(capability)
            if handler is not None:
                self._executor_registry.register(connection_kind, capability, handler)

    @staticmethod
    def _connection_kind_label(kind: str) -> str:
        return connection_kind_label(kind)

    @staticmethod
    def _is_english(language: str | None) -> bool:
        return str(language or "").strip().lower().startswith("en")

    @classmethod
    def _msg(cls, language: str | None, de: str, en: str) -> str:
        return en if cls._is_english(language) else de

    @staticmethod
    def _call_with_optional_language(func: Any, *args: Any, language: str = "de") -> Any:
        try:
            return func(*args, language=language)
        except TypeError as exc:
            if "unexpected keyword argument 'language'" not in str(exc):
                raise
            return func(*args)

    def _default_mqtt_topic(self, connection_ref: str) -> str:
        connection_rows = getattr(getattr(self.settings, "connections", object()), "mqtt", {})
        if not isinstance(connection_rows, dict):
            return ""
        row = connection_rows.get(connection_ref, {})
        if isinstance(row, dict):
            return str(row.get("topic", "")).strip()
        return str(getattr(row, "topic", "")).strip()

    def _build_capability_detail_lines(self, plan: ActionPlan, *, language: str | None = None) -> list[str]:
        effective_plan = plan
        if str(plan.capability or "").strip().lower() == "mqtt_publish" and not str(plan.path or "").strip():
            effective_plan = replace(plan, path=self._default_mqtt_topic(plan.connection_ref))
        elif str(plan.capability or "").strip().lower() == "mail_search" and str(plan.content or "").strip():
            effective_plan = replace(plan, content=self._truncate_text(plan.content, 160))
        return build_capability_detail_lines(effective_plan, self._connection_kind_label, language=language)

    def _routing_debug_enabled(self) -> bool:
        return bool(getattr(getattr(self.settings, "ui", object()), "debug_mode", False))

    def _routing_debug_line(self, text: str) -> list[str]:
        return [text] if self._routing_debug_enabled() and str(text or "").strip() else []

    def _qdrant_routing_enabled(self) -> bool:
        return bool(getattr(self.settings.routing, "qdrant_connection_routing_enabled", False))

    def _qdrant_routing_limit(self) -> int:
        try:
            return max(1, min(20, int(getattr(self.settings.routing, "qdrant_candidate_limit", 5) or 5)))
        except (TypeError, ValueError):
            return 5

    def _qdrant_routing_threshold(self) -> float:
        try:
            return max(0.0, min(1.0, float(getattr(self.settings.routing, "qdrant_score_threshold", 0.72) or 0.0)))
        except (TypeError, ValueError):
            return 0.72

    def _qdrant_ask_on_low_confidence(self) -> bool:
        return bool(getattr(self.settings.routing, "qdrant_ask_on_low_confidence", True))

    async def _resolve_qdrant_connection_hint(
        self,
        message: str,
        connection_pools: dict[str, dict[str, Any]],
        *,
        preferred_kind: str = "",
        language: str | None = None,
    ) -> tuple[MemoryHints, list[str], bool]:
        del language
        if not self._qdrant_routing_enabled():
            return MemoryHints(), [], False
        clean_kind = str(preferred_kind or "").strip().lower()
        if clean_kind and clean_kind not in set(DEFAULT_CONNECTION_ROUTING_KINDS):
            return MemoryHints(), self._routing_debug_line(f"Routing: Qdrant skipped for unsupported kind `{clean_kind}`."), False
        if clean_kind and clean_kind not in connection_pools:
            return MemoryHints(), [], False

        status = await build_connection_routing_index_status(self.settings)
        if status.get("status") == "error":
            return (
                MemoryHints(),
                self._routing_debug_line(
                    f"Routing: Qdrant skipped, index status failed: {status.get('detail') or status.get('message') or 'unknown'}"
                ),
                self._qdrant_ask_on_low_confidence(),
            )
        if bool(status.get("stale")):
            return (
                MemoryHints(),
                self._routing_debug_line("Routing: Qdrant skipped because the routing index is outdated."),
                self._qdrant_ask_on_low_confidence(),
            )
        if str(status.get("status", "") or "").lower() != "ok":
            return (
                MemoryHints(),
                self._routing_debug_line(
                    f"Routing: Qdrant skipped, index is not ready: {status.get('message') or 'unknown'}"
                ),
                self._qdrant_ask_on_low_confidence(),
            )

        memory = self.settings.memory
        qdrant = create_async_qdrant_client(
            url=memory.qdrant_url,
            api_key=getattr(memory, "qdrant_api_key", "") or None,
            timeout=8,
        )
        try:
            store = RoutingIndexStore(
                qdrant=qdrant,
                embedding_client=self.embedding_client,
                collection_name=routing_connections_collection_name(self.settings),
            )
            resolver = RoutingResolver(candidate_provider=store)
            decision = await resolver.resolve_connection(
                message,
                connection_pools,
                preferred_kind=clean_kind,
                qdrant_limit=self._qdrant_routing_limit(),
                qdrant_score_threshold=self._qdrant_routing_threshold(),
            )
        finally:
            close = getattr(qdrant, "close", None)
            if close is not None:
                result = close()
                if hasattr(result, "__await__"):
                    await result

        if not decision.found:
            candidate_count = len(decision.candidates)
            if candidate_count:
                return (
                    MemoryHints(),
                    self._routing_debug_line(
                        f"Routing: Qdrant returned {candidate_count} candidate(s), none accepted."
                    ),
                    self._qdrant_ask_on_low_confidence(),
                )
            return (
                MemoryHints(),
                self._routing_debug_line("Routing: Qdrant found no accepted candidate."),
                self._qdrant_ask_on_low_confidence(),
            )

        detail = self._routing_debug_line(
            f"Routing: Qdrant selected `{decision.kind}/{decision.ref}` "
            f"score={decision.score:.3f} source={decision.source}."
        )
        return (
            MemoryHints(
                connection_kind=decision.kind,
                connection_ref=decision.ref,
                source=decision.source or "qdrant_routing",
                notes=[f"qdrant_routing:{decision.kind}/{decision.ref}:{decision.score:.3f}"],
            ),
            detail,
            False,
        )

    @staticmethod
    def _collect_skill_detail_lines(skill_results: list[SkillResult]) -> list[str]:
        lines: list[str] = []
        seen: set[str] = set()
        for result in skill_results:
            meta = result.metadata or {}
            raw_lines = meta.get("detail_lines")
            if not isinstance(raw_lines, list):
                continue
            for row in raw_lines:
                text = str(row).strip()
                if not text or text in seen:
                    continue
                seen.add(text)
                lines.append(text)
        return lines

    @staticmethod
    def _normalize_spaces(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _slug_user_id(user_id: str) -> str:
        clean = re.sub(r"[^a-zA-Z0-9_-]", "_", user_id.strip().lower())
        clean = re.sub(r"_+", "_", clean).strip("_")
        return clean or "web"

    def _facts_collection_for_user(self, user_id: str) -> str:
        slug = self._slug_user_id(user_id)
        prefix = self.settings.memory.collections.facts.prefix.strip() or "aria_facts"
        return f"{prefix}_{slug}"

    def _preferences_collection_for_user(self, user_id: str) -> str:
        slug = self._slug_user_id(user_id)
        prefix = self.settings.memory.collections.preferences.prefix.strip() or "aria_preferences"
        return f"{prefix}_{slug}"

    def _extract_memory_store_text(
        self,
        message: str,
        routing_profile: RoutingLanguageConfig | None = None,
    ) -> str:
        text = self._normalize_spaces(message)
        lower = text.lower()
        active_routing = routing_profile or self.settings.routing.for_language(None)

        prefixes = [p.lower() for p in active_routing.memory_store_prefixes if p.strip()]

        for prefix in prefixes:
            if lower.startswith(prefix):
                extracted = text[len(prefix):].strip(" .,:;!?")
                if extracted:
                    return extracted

        parts = re.split(r"\b(?:dass|das)\b", text, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) == 2:
            extracted = parts[1].strip(" .,:;!?")
            if extracted:
                return extracted

        return text

    def _extract_memory_recall_query(
        self,
        message: str,
        routing_profile: RoutingLanguageConfig | None = None,
    ) -> str:
        text = self._normalize_spaces(message)
        active_routing = routing_profile or self.settings.routing.for_language(None)
        cleanup_keywords = [re.escape(k) for k in active_routing.memory_recall_cleanup_keywords if k.strip()]
        pattern = r"\b(" + "|".join(cleanup_keywords) + r")\b" if cleanup_keywords else r"$^"
        cleaned = re.sub(
            pattern,
            " ",
            text,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"[?!.:,;]+", " ", cleaned)
        cleaned = self._normalize_spaces(cleaned)
        return cleaned or text

    def _extract_web_search_query(
        self,
        message: str,
        routing_profile: RoutingLanguageConfig | None = None,
    ) -> str:
        text = self._normalize_spaces(message)
        lower = text.lower()
        active_routing = routing_profile or self.settings.routing.for_language(None)

        prefixes = [p.lower() for p in active_routing.web_search_prefixes if p.strip()]
        for prefix in prefixes:
            if lower.startswith(prefix):
                extracted = text[len(prefix):].strip(" .,:;!?")
                if extracted:
                    return extracted

        cleanup_keywords = [re.escape(k) for k in active_routing.web_search_cleanup_keywords if k.strip()]
        if cleanup_keywords:
            text = re.sub(r"\b(" + "|".join(cleanup_keywords) + r")\b", " ", text, flags=re.IGNORECASE)
        text = re.sub(r"[?!.:,;]+", " ", text)
        text = self._normalize_spaces(text)
        return text or message

    @staticmethod
    def _sanitize_skill_id(value: str) -> str:
        return sanitize_skill_id(value)

    @staticmethod
    def _normalize_skill_keywords(value: Any) -> list[str]:
        return normalize_skill_keywords(value)

    @staticmethod
    def _normalize_skill_steps(value: Any) -> list[dict[str, Any]]:
        return normalize_skill_steps(value)

    @staticmethod
    def _render_step_template(template: str, values: dict[str, str]) -> str:
        return render_step_template(template, values)

    def _load_custom_skill_toggles(self) -> dict[str, bool]:
        return load_custom_skill_toggles(self._config_path)

    def _load_custom_skill_runtime(self) -> list[dict[str, Any]]:
        rows, cache = load_custom_skill_runtime(
            skills_dir=self._custom_skills_dir,
            config_path=self._config_path,
            cache=self._custom_skill_cache,
        )
        self._custom_skill_cache = cache
        return rows

    def _match_custom_skill_intents(self, message: str, runtime_skills: list[dict[str, Any]]) -> list[str]:
        return match_custom_skill_intents(message, runtime_skills)

    async def _resolve_custom_skill_intent_with_llm(self, message: str, runtime_skills: list[dict[str, Any]]) -> list[str]:
        return await resolve_custom_skill_intent_with_llm(message, runtime_skills, self.llm_client)

    @staticmethod
    def _should_skip_auto_memory_persist(intents: list[str]) -> bool:
        return should_skip_auto_memory_persist(intents)

    def _build_skill_status_text(self, runtime_custom_skills: list[dict[str, Any]], auto_memory_enabled: bool) -> str:
        return build_skill_status_text(self.settings, runtime_custom_skills, auto_memory_enabled)

    @staticmethod
    def _truncate_text(text: str, limit: int = 1200) -> str:
        raw = str(text or "").strip()
        if len(raw) <= limit:
            return raw
        return raw[:limit] + "\n[... gekuerzt]"

    @staticmethod
    def _extract_held_packages(text: str) -> list[str]:
        return extract_held_packages(text)

    @staticmethod
    def _format_held_packages_summary(
        held_by_connection: dict[str, list[str]],
        connection_targets: dict[str, str],
    ) -> str:
        if not held_by_connection:
            return ""
        lines = [
            "Hinweis: Zurückgehaltene Pakete erkannt:",
        ]
        merged: list[str] = []
        seen: set[str] = set()
        for conn_ref in sorted(held_by_connection.keys()):
            pkgs = held_by_connection.get(conn_ref, [])
            if not pkgs:
                continue
            target = connection_targets.get(conn_ref, "").strip()
            place = f"{conn_ref} ({target})" if target else conn_ref
            lines.append(f"- {place}: {', '.join(pkgs)}")
            for pkg in pkgs:
                if pkg not in seen:
                    seen.add(pkg)
                    merged.append(pkg)
        if merged:
            lines.append("")
            lines.append("Safe-Fix (manuell bestätigen):")
            lines.append("sudo apt install --only-upgrade " + " ".join(merged))
        return "\n".join(lines)

    @staticmethod
    def _build_safe_fix_plan(skill_results: list[SkillResult]) -> list[dict[str, Any]]:
        return build_safe_fix_plan(skill_results)

    async def execute_safe_fix_plan(self, plan: list[dict[str, Any]], language: str = "de") -> SkillResult:
        return await self._safe_fix_executor.execute_plan(plan, language=language)

    async def _execute_custom_ssh_command(
        self,
        *,
        skill_id: str,
        skill_name: str,
        connection_ref: str,
        command_template: str,
        message: str,
        timeout_seconds: int | None = None,
        language: str = "de",
    ) -> SkillResult:
        return await self._ssh_runtime.execute_custom_ssh_command(
            skill_id=skill_id,
            skill_name=skill_name,
            connection_ref=connection_ref,
            command_template=command_template,
            message=message,
            timeout_seconds=timeout_seconds,
            language=language,
        )

    async def _execute_custom_steps(self, row: dict[str, Any], message: str, language: str = "de") -> SkillResult:
        return await self._skill_runtime.execute_custom_steps(row=row, message=message, language=language)

    @staticmethod
    def _normalize_model_name(value: str) -> str:
        return value.strip().lower()

    @staticmethod
    def _resolve_pricing_entry(entries: dict[str, object], model_name: str) -> object | None:
        clean = str(model_name or "").strip()
        if not clean:
            return None
        if entries:
            if clean in entries:
                return entries[clean]
            lowered = {str(k).strip().lower(): v for k, v in entries.items()}
            entry = lowered.get(clean.lower())
            if entry is not None:
                return entry
        return resolve_litellm_pricing_entry(clean)

    async def _run_skills(
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
        return await self._skill_runtime.run_skills(
            intents=intents,
            message=message,
            user_id=user_id,
            routing_profile=routing_profile,
            language=language,
            runtime_custom_skills=runtime_custom_skills,
            memory_collection=memory_collection,
            session_collection=session_collection,
            auto_memory_enabled=auto_memory_enabled,
        )

    async def _execute_file_read(self, plan: ActionPlan, *, language: str = "de") -> str:
        if plan.connection_kind == "smb":
            return self._skill_runtime.execute_smb_read(plan.connection_ref, plan.path)
        return self._skill_runtime.execute_sftp_read(plan.connection_ref, plan.path)

    async def _execute_file_write(self, plan: ActionPlan, *, language: str = "de") -> str:
        if plan.connection_kind == "smb":
            return self._skill_runtime.execute_smb_write(plan.connection_ref, plan.path, plan.content)
        return self._skill_runtime.execute_sftp_write(plan.connection_ref, plan.path, plan.content)

    async def _execute_file_list(self, plan: ActionPlan, *, language: str = "de") -> str:
        if plan.connection_kind == "smb":
            return self._call_with_optional_language(
                self._skill_runtime.execute_smb_list,
                plan.connection_ref,
                plan.path or ".",
                language=language,
            )
        return self._call_with_optional_language(
            self._skill_runtime.execute_sftp_list,
            plan.connection_ref,
            plan.path or ".",
            language=language,
        )

    async def _execute_feed_read(self, plan: ActionPlan, *, language: str = "de") -> str:
        return self._call_with_optional_language(self._skill_runtime.execute_rss_read, plan.connection_ref, language=language)

    async def _execute_webhook_send(self, plan: ActionPlan, *, language: str = "de") -> str:
        return self._call_with_optional_language(
            self._skill_runtime.execute_webhook_send,
            plan.connection_ref,
            plan.content,
            language=language,
        )

    async def _execute_discord_send(self, plan: ActionPlan, *, language: str = "de") -> str:
        return self._call_with_optional_language(
            self._skill_runtime.execute_discord_send,
            plan.connection_ref,
            plan.content,
            language=language,
        )

    async def _execute_api_request(self, plan: ActionPlan, *, language: str = "de") -> str:
        return self._call_with_optional_language(
            self._skill_runtime.execute_http_api_request,
            plan.connection_ref,
            plan.path,
            plan.content,
            language=language,
        )

    async def _execute_email_send(self, plan: ActionPlan, *, language: str = "de") -> str:
        return self._call_with_optional_language(
            self._skill_runtime.execute_email_send,
            plan.connection_ref,
            plan.content,
            language=language,
        )

    async def _execute_mail_read(self, plan: ActionPlan, *, language: str = "de") -> str:
        return self._call_with_optional_language(self._skill_runtime.execute_imap_read, plan.connection_ref, language=language)

    async def _execute_mail_search(self, plan: ActionPlan, *, language: str = "de") -> str:
        return self._call_with_optional_language(
            self._skill_runtime.execute_imap_search,
            plan.connection_ref,
            plan.content,
            language=language,
        )

    async def _execute_mqtt_publish(self, plan: ActionPlan, *, language: str = "de") -> str:
        topic = str(plan.path or "").strip() or self._default_mqtt_topic(plan.connection_ref)
        return self._call_with_optional_language(
            self._skill_runtime.execute_mqtt_publish,
            plan.connection_ref,
            topic,
            plan.content,
            language=language,
        )

    async def _execute_ssh_command(self, plan: ActionPlan, *, language: str = "de") -> str:
        result = await self._execute_custom_ssh_command(
            skill_id="direct-ssh-command",
            skill_name="SSH Command",
            connection_ref=plan.connection_ref,
            command_template=plan.content,
            message=plan.content,
            language=language,
        )
        if result.success:
            return result.content
        raise ValueError(str(result.error or "").strip() or self._msg(language, "SSH-Befehl fehlgeschlagen.", "SSH command failed."))

    def _format_capability_missing_message(self, plan: ActionPlan, *, language: str | None = None) -> str:
        connection_rows = getattr(getattr(self.settings, "connections", object()), plan.connection_kind, {})
        available_refs = sorted(connection_rows.keys()) if isinstance(connection_rows, dict) else []
        kind_label = self._connection_kind_label(plan.connection_kind)
        if plan.requested_connection_ref:
            text = self._msg(
                language,
                f"Ich habe das gewünschte {kind_label}-Profil `{plan.requested_connection_ref}` nicht gefunden.",
                f"I could not find the requested {kind_label} profile `{plan.requested_connection_ref}`.",
            )
            if available_refs:
                text += self._msg(
                    language,
                    f" Verfügbare {kind_label}-Profile: ",
                    f" Available {kind_label} profiles: ",
                ) + ", ".join(available_refs) + "."
            return text
        if self._is_english(language):
            labels = {
                "connection_ref": f"which {kind_label} profile / target I should use",
                "path": "which file path I should use",
                "content": "which content I should send or write",
            }
        else:
            labels = {
                "connection_ref": f"welches {kind_label}-Profil / welches Ziel ich verwenden soll",
                "path": "welchen Dateipfad ich verwenden soll",
                "content": "welchen Inhalt ich schreiben soll",
            }
        if plan.capability == "ssh_command":
            labels["content"] = self._msg(language, "welchen Befehl ich ausführen soll", "which command I should run")
        missing = [labels.get(item, item) for item in plan.missing_fields]
        intro = self._msg(language, f"Ich kann das über {kind_label} erledigen", f"I can do this via {kind_label}")
        if plan.capability == "feed_read":
            intro = self._msg(language, "Ich kann diesen Feed lesen", "I can read this feed")
        if plan.capability == "webhook_send":
            intro = self._msg(language, "Ich kann das per Webhook senden", "I can send this via webhook")
        if plan.capability == "discord_send":
            intro = self._msg(language, "Ich kann das nach Discord senden", "I can send this to Discord")
        if plan.capability == "api_request":
            intro = self._msg(language, "Ich kann diese HTTP-API ansprechen", "I can call this HTTP API")
        if plan.capability == "email_send":
            intro = self._msg(language, "Ich kann diese Nachricht per Mail senden", "I can send this message by email")
        if plan.capability == "mail_read":
            intro = self._msg(language, "Ich kann die Mailbox lesen", "I can read the mailbox")
        if plan.capability == "mail_search":
            intro = self._msg(language, "Ich kann die Mailbox durchsuchen", "I can search the mailbox")
        if plan.capability == "mqtt_publish":
            intro = self._msg(language, "Ich kann diese Nachricht per MQTT veröffentlichen", "I can publish this message via MQTT")
        if plan.capability == "ssh_command":
            intro = self._msg(language, "Ich kann den SSH-Befehl ausführen", "I can run the SSH command")
        text = intro + self._msg(language, ", brauche aber noch: ", ", but I still need: ") + "; ".join(missing) + "."
        if "connection_ref" in plan.missing_fields and available_refs:
            text += self._msg(language, f" Verfügbare {kind_label}-Profile: ", f" Available {kind_label} profiles: ") + ", ".join(available_refs) + "."
        return text

    def _sanitize_capability_error(self, exc: Exception, *, language: str | None = None) -> str:
        if isinstance(exc, ValueError):
            return str(exc).strip() or self._msg(language, "Ungültige Eingabe.", "Invalid input.")
        raw = str(exc).strip()
        if raw:
            return raw[:220]
        return self._msg(language, "Unerwarteter Laufzeitfehler.", "Unexpected runtime error.")

    def _format_capability_execution_error(self, plan: ActionPlan, exc: Exception, *, language: str | None = None) -> str:
        labels = {
            "feed_read": self._msg(language, "Der Feed konnte nicht gelesen werden.", "The feed could not be read."),
            "webhook_send": self._msg(language, "Der Webhook konnte nicht gesendet werden.", "The webhook could not be sent."),
            "discord_send": self._msg(language, "Die Discord-Nachricht konnte nicht gesendet werden.", "The Discord message could not be sent."),
            "api_request": self._msg(language, "Die HTTP-API-Anfrage konnte nicht ausgeführt werden.", "The HTTP API request could not be executed."),
            "email_send": self._msg(language, "Die Mail konnte nicht gesendet werden.", "The email could not be sent."),
            "mail_read": self._msg(language, "Die Mailbox konnte nicht gelesen werden.", "The mailbox could not be read."),
            "mail_search": self._msg(language, "Die Mailbox konnte nicht durchsucht werden.", "The mailbox could not be searched."),
            "mqtt_publish": self._msg(language, "Die MQTT-Nachricht konnte nicht veröffentlicht werden.", "The MQTT message could not be published."),
            "ssh_command": self._msg(language, "Der SSH-Befehl konnte nicht ausgeführt werden.", "The SSH command could not be executed."),
        }
        default_label = self._msg(
            language,
            f"Die {self._connection_kind_label(plan.connection_kind)}-Aktion konnte nicht ausgeführt werden.",
            f"The {self._connection_kind_label(plan.connection_kind)} action could not be executed.",
        )
        base = labels.get(str(plan.capability or "").strip().lower(), default_label)
        reason = self._sanitize_capability_error(exc, language=language)
        return self._msg(language, f"{base} Grund: {reason}", f"{base} Reason: {reason}")

    async def _try_ssh_command_action(
        self,
        message: str,
        *,
        language: str | None = None,
    ) -> tuple[list[str], str, list[str], ActionPlan, list[str]] | None:
        rows = getattr(getattr(self.settings, "connections", object()), "ssh", {})
        if not isinstance(rows, dict) or not rows:
            return None

        alias_rows: dict[str, list[str]] = {}
        for ref, row in rows.items():
            clean_ref = str(ref).strip()
            if clean_ref:
                alias_rows[clean_ref] = build_connection_aliases("ssh", clean_ref, row)

        draft = self.capability_router.classify(
            message,
            language=language,
            available_connection_refs_by_kind={"ssh": rows.keys()},
            available_connection_aliases_by_kind={"ssh": alias_rows} if alias_rows else None,
        )
        if draft is None or draft.capability != "ssh_command":
            return None

        hints = MemoryHints()
        qdrant_details: list[str] = []
        if not str(draft.explicit_connection_ref or "").strip():
            hints, qdrant_details, _qdrant_block_fallback = await self._resolve_qdrant_connection_hint(
                message,
                {"ssh": rows},
                preferred_kind="ssh",
                language=language,
            )

        plan = build_action_plan(draft, hints, available_connection_refs=sorted(rows.keys()))
        intent = [f"capability:{plan.capability}"]
        if not plan.is_complete:
            return intent, self._format_capability_missing_message(plan, language=language), qdrant_details, plan, []

        details = qdrant_details + self._build_capability_detail_lines(plan, language=language)
        try:
            result_text = await self._execute_ssh_command(plan, language=str(language or "de"))
        except Exception as exc:
            error_text = self._format_capability_execution_error(plan, exc, language=language)
            error_code = f"capability_{plan.capability}_error:{type(exc).__name__}"
            return intent, error_text, details, plan, [error_code]
        return intent, result_text, details, plan, []

    async def _try_capability_action(
        self,
        message: str,
        user_id: str,
        language: str | None = None,
    ) -> tuple[list[str], str, list[str], ActionPlan, list[str]] | None:
        connection_pools: dict[str, dict[str, Any]] = {}
        for kind in ("sftp", "smb", "rss", "webhook", "discord", "http_api", "email", "imap", "mqtt"):
            rows = getattr(getattr(self.settings, "connections", object()), kind, {})
            if isinstance(rows, dict) and rows:
                connection_pools[kind] = rows
        if not connection_pools:
            return None

        connection_aliases_by_kind: dict[str, dict[str, list[str]]] = {}
        for kind, rows in connection_pools.items():
            alias_rows: dict[str, list[str]] = {}
            for ref, row in rows.items():
                clean_ref = str(ref).strip()
                if not clean_ref:
                    continue
                alias_rows[clean_ref] = build_connection_aliases(kind, clean_ref, row)
            if alias_rows:
                connection_aliases_by_kind[kind] = alias_rows

        draft = self.capability_router.classify(
            message,
            language=language,
            available_connection_refs_by_kind={kind: rows.keys() for kind, rows in connection_pools.items()},
            available_connection_aliases_by_kind=connection_aliases_by_kind,
        )
        if draft is None:
            return None

        candidate_connections = connection_pools.get(draft.connection_kind, {})
        hints = await self._memory_assist.resolve(
            draft=draft,
            message=message,
            user_id=user_id,
            available_connections=candidate_connections,
        )
        qdrant_details: list[str] = []
        qdrant_block_fallback = False
        if not hints.connection_ref and candidate_connections:
            semantic_hint = self._semantic_connection_resolver.resolve_connection(
                message,
                {draft.connection_kind: candidate_connections},
            )
            if semantic_hint.connection_ref:
                hints = replace(
                    hints,
                    connection_kind=semantic_hint.connection_kind or draft.connection_kind,
                    connection_ref=semantic_hint.connection_ref,
                    source=semantic_hint.source or hints.source,
                    notes=list(hints.notes) + ([semantic_hint.note] if semantic_hint.note else []),
                )
        if not hints.connection_ref and candidate_connections:
            qdrant_hints, qdrant_details, qdrant_block_fallback = await self._resolve_qdrant_connection_hint(
                message,
                connection_pools,
                preferred_kind=draft.connection_kind,
                language=language,
            )
            if qdrant_hints.connection_ref:
                hints = qdrant_hints
        if not hints.connection_ref and candidate_connections and not qdrant_block_fallback:
            semantic_hint = await self._semantic_connection_resolver.resolve_connection_with_llm(
                message,
                {draft.connection_kind: candidate_connections},
                preferred_kind=draft.connection_kind,
            )
            if semantic_hint.connection_ref:
                hints = replace(
                    hints,
                    connection_kind=semantic_hint.connection_kind or draft.connection_kind,
                    connection_ref=semantic_hint.connection_ref,
                    source=semantic_hint.source or hints.source,
                    notes=list(hints.notes) + ([semantic_hint.note] if semantic_hint.note else []),
                )
        if not hints.connection_ref and draft.connection_kind == "rss" and not qdrant_block_fallback:
            semantic_hint = await self._semantic_connection_resolver.resolve_rss_ref(message, candidate_connections)
            if semantic_hint.connection_ref:
                hints = replace(
                    hints,
                    connection_kind=semantic_hint.connection_kind or draft.connection_kind,
                    connection_ref=semantic_hint.connection_ref,
                    source=semantic_hint.source or hints.source,
                    notes=list(hints.notes) + ([semantic_hint.note] if semantic_hint.note else []),
                )
        resolved_kind = hints.connection_kind or draft.connection_kind
        if resolved_kind != draft.connection_kind and resolved_kind in connection_pools:
            draft = replace(draft, connection_kind=resolved_kind)
            candidate_connections = connection_pools.get(draft.connection_kind, {})
        plan = build_action_plan(draft, hints, available_connection_refs=sorted(candidate_connections.keys()))
        intent = [f"capability:{plan.capability}"]
        if not plan.is_complete:
            return intent, self._format_capability_missing_message(plan, language=language), qdrant_details, plan, []

        details = qdrant_details + self._build_capability_detail_lines(plan, language=language)
        try:
            result_text = await self._executor_registry.execute(plan, language=str(language or "de"))
        except Exception as exc:
            error_text = self._format_capability_execution_error(plan, exc, language=language)
            error_code = f"capability_{plan.capability}_error:{type(exc).__name__}"
            return intent, error_text, details, plan, [error_code]
        return intent, result_text, details, plan, []

    def _classify_capability_draft(
        self,
        message: str,
        *,
        language: str | None = None,
    ) -> Any | None:
        connection_pools: dict[str, dict[str, Any]] = {}
        for kind in ("sftp", "smb", "rss", "webhook", "discord", "http_api", "email", "imap", "mqtt"):
            rows = getattr(getattr(self.settings, "connections", object()), kind, {})
            if isinstance(rows, dict) and rows:
                connection_pools[kind] = rows
        if not connection_pools:
            return None

        connection_aliases_by_kind: dict[str, dict[str, list[str]]] = {}
        for kind, rows in connection_pools.items():
            alias_rows: dict[str, list[str]] = {}
            for ref, row in rows.items():
                clean_ref = str(ref).strip()
                if not clean_ref:
                    continue
                alias_rows[clean_ref] = build_connection_aliases(kind, clean_ref, row)
            if alias_rows:
                connection_aliases_by_kind[kind] = alias_rows

        return self.capability_router.classify(
            message,
            language=language,
            available_connection_refs_by_kind={kind: rows.keys() for kind, rows in connection_pools.items()},
            available_connection_aliases_by_kind=connection_aliases_by_kind,
        )

    def classify_routing(self, message: str, *, language: str | None = None) -> RouterDecision:
        routing_profile = self.settings.routing.for_language(language)
        return self.router.classify(message, routing=routing_profile)

    async def process(
        self,
        message: str,
        user_id: str = "web",
        source: str = "web",
        language: str | None = None,
        memory_collection: str | None = None,
        session_collection: str | None = None,
        auto_memory_enabled: bool = False,
    ) -> PipelineResult:
        start = time.perf_counter()
        request_id = str(uuid4())

        persona = self.prompt_loader.get_persona()
        routing_profile = self.settings.routing.for_language(language)
        decision = self.classify_routing(message, language=language)
        runtime_custom_skills = self._load_custom_skill_runtime()
        if "skill_status" in decision.intents:
            duration_ms = int((time.perf_counter() - start) * 1000)
            text = self._build_skill_status_text(runtime_custom_skills, auto_memory_enabled)
            usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            await self.token_tracker.log(
                request_id=request_id,
                user_id=user_id,
                intents=["skill_status"],
                router_level=decision.level,
                usage=usage,
                chat_model=self.settings.llm.model,
                embedding_model=self.settings.embeddings.model,
                embedding_usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0},
                chat_cost_usd=None,
                embedding_cost_usd=None,
                total_cost_usd=None,
                duration_ms=duration_ms,
                source=source,
                skill_errors=[],
                extraction_model="rule_based",
                extraction_usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0},
            )
            return PipelineResult(
                request_id=request_id,
                text=text,
                usage=usage,
                intents=["skill_status"],
                skill_errors=[],
                router_level=decision.level,
                duration_ms=duration_ms,
                chat_cost_usd=None,
                embedding_cost_usd=None,
                total_cost_usd=None,
                safe_fix_plan=None,
            )

        custom_intents: list[str] = []
        capability_result = None
        if decision.intents in (["chat"], ["memory_recall"]):
            capability_result = await self._try_ssh_command_action(message, language=language)
            if capability_result is None:
                capability_draft = self._classify_capability_draft(message, language=language)
                if capability_draft is not None and str(getattr(capability_draft, "explicit_connection_ref", "")).strip():
                    capability_result = await self._try_capability_action(message, user_id, language=language)
            if capability_result is not None:
                capability_intents, capability_text, capability_details, capability_plan, capability_errors = capability_result
                if capability_plan.capability == "ssh_command" or (
                    capability_plan.is_complete and capability_plan.resolution_source == "explicit"
                ):
                    duration_ms = int((time.perf_counter() - start) * 1000)
                    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
                    await self.token_tracker.log(
                        request_id=request_id,
                        user_id=user_id,
                        intents=capability_intents,
                        router_level=decision.level,
                        usage=usage,
                        chat_model=self.settings.llm.model,
                        embedding_model=self.settings.embeddings.model,
                        embedding_usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0},
                        chat_cost_usd=None,
                        embedding_cost_usd=None,
                        total_cost_usd=None,
                        duration_ms=duration_ms,
                        source=source,
                        skill_errors=capability_errors,
                        extraction_model="capability_router",
                        extraction_usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0},
                    )
                    if self.capability_context_store is not None and capability_plan.is_complete:
                        try:
                            self.capability_context_store.remember_action(
                                user_id,
                                capability=capability_plan.capability,
                                connection_kind=capability_plan.connection_kind,
                                connection_ref=capability_plan.connection_ref,
                                path=capability_plan.path,
                            )
                        except Exception:
                            pass
                    return PipelineResult(
                        request_id=request_id,
                        text=capability_text,
                        usage=usage,
                        intents=capability_intents,
                        skill_errors=capability_errors,
                        router_level=decision.level,
                        duration_ms=duration_ms,
                        chat_cost_usd=None,
                        embedding_cost_usd=None,
                        total_cost_usd=None,
                        safe_fix_plan=None,
                        detail_lines=capability_details,
                    )
            custom_intents = self._match_custom_skill_intents(message, runtime_custom_skills)
        if decision.intents in (["chat"], ["memory_recall"]) and not custom_intents and capability_result is None:
            capability_result = await self._try_capability_action(message, user_id, language=language)
        if decision.intents in (["chat"], ["memory_recall"]) and not custom_intents and capability_result is not None:
            capability_intents, capability_text, capability_details, capability_plan, capability_errors = capability_result
            duration_ms = int((time.perf_counter() - start) * 1000)
            usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            await self.token_tracker.log(
                request_id=request_id,
                user_id=user_id,
                intents=capability_intents,
                router_level=decision.level,
                usage=usage,
                chat_model=self.settings.llm.model,
                embedding_model=self.settings.embeddings.model,
                embedding_usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0},
                chat_cost_usd=None,
                embedding_cost_usd=None,
                total_cost_usd=None,
                duration_ms=duration_ms,
                source=source,
                skill_errors=capability_errors,
                extraction_model="capability_router",
                extraction_usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0},
            )
            if self.capability_context_store is not None and capability_plan.is_complete:
                try:
                    self.capability_context_store.remember_action(
                        user_id,
                        capability=capability_plan.capability,
                        connection_kind=capability_plan.connection_kind,
                        connection_ref=capability_plan.connection_ref,
                        path=capability_plan.path,
                    )
                except Exception:
                    pass
            return PipelineResult(
                request_id=request_id,
                text=capability_text,
                usage=usage,
                intents=capability_intents,
                skill_errors=capability_errors,
                router_level=decision.level,
                duration_ms=duration_ms,
                chat_cost_usd=None,
                embedding_cost_usd=None,
                total_cost_usd=None,
                safe_fix_plan=None,
                detail_lines=capability_details,
            )
        if decision.intents in (["chat"], ["memory_recall"]) and not custom_intents:
            custom_intents = await self._resolve_custom_skill_intent_with_llm(message, runtime_custom_skills)

        merged_intents = list(decision.intents)
        for intent in custom_intents:
            if intent not in merged_intents:
                merged_intents.append(intent)
        skill_results = await self._run_skills(
            merged_intents,
            message,
            user_id,
            routing_profile=routing_profile,
            language=str(language or "de"),
            runtime_custom_skills=runtime_custom_skills,
            memory_collection=memory_collection,
            session_collection=session_collection,
            auto_memory_enabled=auto_memory_enabled,
        )
        safe_fix_plan = self._build_safe_fix_plan(skill_results)
        web_search_results = [result for result in skill_results if result.skill_name == "web_search"]
        has_web_search_context = any(result.success and bool(str(result.content or "").strip()) for result in web_search_results)
        if "web_search" in merged_intents and web_search_results and not has_web_search_context:
            primary_error = next(
                (str(result.error or "").strip() for result in web_search_results if str(result.error or "").strip()),
                "Websuche fehlgeschlagen.",
            )
            duration_ms = int((time.perf_counter() - start) * 1000)
            usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            await self.token_tracker.log(
                request_id=request_id,
                user_id=user_id,
                intents=merged_intents,
                router_level=decision.level,
                usage=usage,
                chat_model=self.settings.llm.model,
                embedding_model=self.settings.embeddings.model,
                embedding_usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0},
                chat_cost_usd=None,
                embedding_cost_usd=None,
                total_cost_usd=None,
                duration_ms=duration_ms,
                source=source,
                skill_errors=[primary_error],
                extraction_model="web_search_precheck",
                extraction_usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0},
            )
            return PipelineResult(
                request_id=request_id,
                text=primary_error,
                usage=usage,
                intents=merged_intents,
                skill_errors=[primary_error],
                router_level=decision.level,
                duration_ms=duration_ms,
                chat_cost_usd=None,
                embedding_cost_usd=None,
                total_cost_usd=None,
                safe_fix_plan=safe_fix_plan,
                detail_lines=self._collect_skill_detail_lines(skill_results),
            )

        direct_chat_result = next(
            (
                result
                for result in skill_results
                if bool((result.metadata or {}).get("direct_chat_response")) and bool(result.success)
            ),
            None,
        )
        if (
            direct_chat_result is not None
            and any(str(intent).startswith("custom_skill:") for intent in merged_intents)
            and all(str(intent) == "chat" or str(intent).startswith("custom_skill:") for intent in merged_intents)
        ):
            skill_detail_lines = self._collect_skill_detail_lines(skill_results)
            duration_ms = int((time.perf_counter() - start) * 1000)
            usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            await self.token_tracker.log(
                request_id=request_id,
                user_id=user_id,
                intents=merged_intents,
                router_level=decision.level,
                usage=usage,
                chat_model=self.settings.llm.model,
                embedding_model=self.settings.embeddings.model,
                embedding_usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0},
                chat_cost_usd=None,
                embedding_cost_usd=None,
                total_cost_usd=None,
                duration_ms=duration_ms,
                source=source,
                skill_errors=[r.error for r in skill_results if not r.success and r.error],
                extraction_model="rule_based",
                extraction_usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0},
            )
            return PipelineResult(
                request_id=request_id,
                text=str((direct_chat_result.metadata or {}).get("direct_chat_text") or direct_chat_result.content),
                usage=usage,
                intents=merged_intents,
                skill_errors=[r.error for r in skill_results if not r.success and r.error],
                router_level=decision.level,
                duration_ms=duration_ms,
                chat_cost_usd=None,
                embedding_cost_usd=None,
                total_cost_usd=None,
                safe_fix_plan=safe_fix_plan,
                detail_lines=skill_detail_lines,
            )

        prompts = self.context_assembler.build(
            persona=persona,
            skill_results=skill_results,
            user_message=message,
            language=str(language or "de"),
        )

        with self.usage_meter.scope(
            request_id=request_id,
            user_id=user_id,
            source=source,
            router_level=decision.level,
        ) as usage_scope:
            llm_response = await self.llm_client.chat(prompts)
            duration_ms = int((time.perf_counter() - start) * 1000)
            usage_snapshot = self.usage_meter.snapshot_scope(usage_scope)

        embedding_model = str(usage_snapshot.get("embedding_model", "")).strip() or self.settings.embeddings.model
        extraction_prompt_tokens = 0
        extraction_completion_tokens = 0
        extraction_total_tokens = 0
        extraction_calls = 0
        extraction_model = "rule_based"
        for result in skill_results:
            meta = result.metadata or {}
            extract_usage = meta.get("extraction_usage")
            if isinstance(extract_usage, dict):
                extraction_prompt_tokens += int(extract_usage.get("prompt_tokens", 0) or 0)
                extraction_completion_tokens += int(extract_usage.get("completion_tokens", 0) or 0)
                extraction_total_tokens += int(extract_usage.get("total_tokens", 0) or 0)
                extraction_calls += 1
            if meta.get("extraction_model"):
                extraction_model = str(meta["extraction_model"])

        usage_total = usage_snapshot.get("usage", {}) if isinstance(usage_snapshot, dict) else {}
        if not bool(getattr(llm_response, "metered", False)):
            usage_total = {
                "prompt_tokens": int(llm_response.usage.get("prompt_tokens", 0) or 0),
                "completion_tokens": int(llm_response.usage.get("completion_tokens", 0) or 0),
                "total_tokens": int(llm_response.usage.get("total_tokens", 0) or 0),
            }
        embedding_usage = usage_snapshot.get("embedding_usage", {}) if isinstance(usage_snapshot, dict) else {}
        if not isinstance(embedding_usage, dict):
            embedding_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0}

        chat_cost_usd = usage_snapshot.get("chat_cost_usd") if isinstance(usage_snapshot, dict) else None
        embedding_cost_usd = usage_snapshot.get("embedding_cost_usd") if isinstance(usage_snapshot, dict) else None
        total_cost_usd = usage_snapshot.get("total_cost_usd") if isinstance(usage_snapshot, dict) else None

        if not bool(getattr(llm_response, "metered", False)) and self.settings.pricing.enabled:
            chat_price_cfg = self._resolve_pricing_entry(
                self.settings.pricing.chat_models,
                self.settings.llm.model,
            )
            if chat_price_cfg:
                prompt_tokens = int(llm_response.usage.get("prompt_tokens", 0) or 0)
                completion_tokens = int(llm_response.usage.get("completion_tokens", 0) or 0)
                chat_cost_usd = (
                    (prompt_tokens * float(chat_price_cfg.input_per_million))
                    + (completion_tokens * float(chat_price_cfg.output_per_million))
                ) / 1_000_000
                total_cost_usd = chat_cost_usd if embedding_cost_usd is None else float(chat_cost_usd + float(embedding_cost_usd))

        await self.token_tracker.log(
            request_id=request_id,
            user_id=user_id,
            intents=merged_intents,
            router_level=decision.level,
            usage=usage_total,
            chat_model=str(usage_snapshot.get("chat_model", "")).strip() or self.settings.llm.model,
            embedding_model=embedding_model,
            embedding_usage=embedding_usage,
            chat_cost_usd=chat_cost_usd,
            embedding_cost_usd=embedding_cost_usd,
            total_cost_usd=total_cost_usd,
            duration_ms=duration_ms,
            source=source,
            skill_errors=[r.error for r in skill_results if not r.success and r.error],
            extraction_model=extraction_model,
            extraction_usage={
                "prompt_tokens": extraction_prompt_tokens,
                "completion_tokens": extraction_completion_tokens,
                "total_tokens": extraction_total_tokens,
                "calls": extraction_calls,
            },
        )

        skill_detail_lines = self._collect_skill_detail_lines(skill_results)

        return PipelineResult(
            request_id=request_id,
            text=llm_response.content,
            usage=usage_total,
            intents=merged_intents,
            skill_errors=[r.error for r in skill_results if not r.success and r.error],
            router_level=decision.level,
            duration_ms=duration_ms,
            chat_cost_usd=chat_cost_usd,
            embedding_cost_usd=embedding_cost_usd,
            total_cost_usd=total_cost_usd,
            safe_fix_plan=safe_fix_plan,
            detail_lines=skill_detail_lines,
        )
