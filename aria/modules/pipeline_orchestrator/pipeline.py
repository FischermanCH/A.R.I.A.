from __future__ import annotations

import asyncio
import inspect
import json
import logging
import re
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from aria.modules.action_contracts.plan import ActionPlan
# Stable synthetic-test hook; all owner mixins import this same class object.
from aria.modules.platform_primitives.bounded_decision import BoundedDecisionClient
from aria.modules.pipeline_orchestrator.agent_jobs import AgentJobRecord, AgentJobStore
from aria.modules.capability_context.store import CapabilityContextStore
from aria.modules.connections_catalog.catalog import connection_kind_label
from aria.modules.configuration_foundations.config import RoutingLanguageConfig, Settings
from aria.modules.pipeline_contracts.context_assembler import ContextAssembler
from aria.modules.pipeline_contracts.context_contracts import RuntimeOutcomeFrame
from aria.modules.pipeline_contracts.context_contracts import TurnFrame
from aria.modules.model_gateway_clients.embedding import EmbeddingClient
from aria.modules.integration_support.error_interpreter import ErrorInterpreter
from aria.modules.recipe_runtime.pipeline_helpers import PipelineRecipeHelpersMixin
from aria.modules.ssh_runtime.pipeline_helpers import PipelineSSHHelpersMixin
from aria.modules.model_gateway_clients.llm import LLMClient
from aria.modules.platform_primitives.stage_timing import StageTimingLedger
from aria.modules.platform_primitives.stage_timing import insert_stage_timing_detail_lines
from aria.modules.pipeline_capability_execution.executor import PipelineCapabilityExecutor
from aria.modules.pipeline_capability_execution.executor import website_rows_from_settings
from aria.modules.capability_error_messages.messages import capability_execution_error_code
from aria.modules.capability_error_messages.messages import format_capability_execution_error
from aria.modules.capability_error_messages.messages import format_capability_missing_message
from aria.modules.capability_error_messages.messages import sanitize_capability_error
from aria.modules.pipeline_contracts.result import PipelineResult
from aria.modules.native_agent.pipeline_bridge import run_native_agent_first_stage
from aria.modules.native_agent.handler import (
    NativeAgentAwaitingConfirmation,
    NativeAgentPaused,
    NativeAgentStepCancelled,
)
from aria.modules.native_agent.tool_registry import EmbeddingNativeToolRelevanceSelector
from aria.modules.platform_primitives.prompt_loader import PromptLoader
from aria.modules.pipeline_contracts.text import _PIPELINE_I18N
from aria.modules.pipeline_contracts.text import pipeline_text as _pipeline_text
from aria.modules.pipeline_pending_action_contracts.contracts import append_debug_detail_lines
from aria.modules.pipeline_contracts.capability_details import default_mqtt_topic_from_settings
from aria.modules.model_usage_observability.pricing_catalog import resolve_pricing_entry
from aria.modules.rss_digest.execution_policy import RssActionSelectionPolicy
from aria.modules.ssh_runtime.held_packages import extract_held_packages
from aria.modules.recipe_runtime.runtime import RecipeRuntime
from aria.modules.ssh_runtime.runtime import SSHRuntime
from aria.modules.platform_primitives.text_utils import extract_json_object as core_extract_json_object
from aria.modules.platform_primitives.text_utils import is_english
from aria.modules.platform_primitives.text_utils import localized_text
from aria.modules.operator_trace_boundary.operator_trace import append_operator_trace_detail_lines
from aria.modules.agentic_stabilization.gate import append_stabilization_gate_detail_lines
from aria.modules.agentic_stabilization.gate import enforce_stabilization_gate_answerability

from aria.modules.model_usage_observability.usage_meter import UsageMeter
from aria.modules.native_web_llm.gateway import NativeWebLLMGateway
from aria.modules.native_web_llm.evidence import PublicWebEvidenceStore
from aria.modules.native_web_llm.pipeline_mixin import NativeWebPipelineMixin
from aria.modules.skill_contracts.contracts import SkillResult
from aria.modules.memory_learning_bridge.skill import MemorySkill
from aria.modules.mcp.runtime import MCPClientManager

# Public synthetic-test hooks retained across the owner split.


def _bounded_agent_job_notice_result(value: object, *, limit: int = 1500) -> str:
    normalized = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    normalized = "\n".join(
        re.sub(r"[ \t]+", " ", line).strip()
        for line in normalized.split("\n")
    )
    normalized = re.sub(r"\n{3,}", "\n\n", normalized).strip()
    if len(normalized) <= limit:
        return normalized
    cutoff = max(0, limit - 1)
    for match in re.finditer(r"\[[^\]\n]{1,300}\]\([^\)\n]{1,1000}\)", normalized):
        if match.start() < cutoff < match.end():
            cutoff = match.start()
            break
    return normalized[:cutoff].rstrip() + "…"
_STATIC_TEST_HOOKS = (BoundedDecisionClient, _PIPELINE_I18N)
LOGGER = logging.getLogger(__name__)














class Pipeline(
    NativeWebPipelineMixin,
    PipelineRecipeHelpersMixin,
    PipelineSSHHelpersMixin,
):
    """Session 2 Pipeline: Load -> Route -> Skills -> Context -> LLM -> Track."""

    def __init__(
        self,
        settings: Settings,
        prompt_loader: PromptLoader,
        llm_client: LLMClient,
        capability_context_store: CapabilityContextStore | None = None,
        usage_meter: UsageMeter | None = None,
        embedding_client: EmbeddingClient | None = None,
        web_llm_gateway: NativeWebLLMGateway | None = None,
        web_evidence_store: PublicWebEvidenceStore | None = None,
    ):
        self.settings = settings
        self.prompt_loader = prompt_loader
        self.llm_client = llm_client
        self.usage_meter = usage_meter or UsageMeter(settings)
        if hasattr(self.llm_client, "usage_meter") and getattr(self.llm_client, "usage_meter", None) is None:
            self.llm_client.usage_meter = self.usage_meter
        self.embedding_client = embedding_client or EmbeddingClient(settings.embeddings, usage_meter=self.usage_meter)
        self._native_tool_descriptor_embedding_cache: dict[tuple[str, str], tuple[float, ...]] = {}
        self._native_tool_relevance_selector = EmbeddingNativeToolRelevanceSelector(
            embedding_client=self.embedding_client,
            descriptor_cache=self._native_tool_descriptor_embedding_cache,
        )
        self._native_mcp_client = MCPClientManager(settings.mcp_servers)
        self.web_llm_gateway = web_llm_gateway
        self.web_evidence_store = web_evidence_store

        self.capability_context_store = capability_context_store
        self.context_assembler = ContextAssembler()
        self.token_tracker = self.usage_meter.token_tracker

        self.memory_skill: MemorySkill | None = None
        if settings.memory.enabled and settings.memory.backend.lower() == "qdrant":
            self.memory_skill = MemorySkill(
                memory=settings.memory,
                embeddings=settings.embeddings,
                embedding_client=self.embedding_client,
                usage_meter=self.usage_meter,
            )
        self._project_root = Path(__file__).resolve().parents[3]
        self._stored_recipes_dir = self._project_root / "data" / "recipes"
        self._config_path = self._project_root / "config" / "config.yaml"
        self._error_interpreter = ErrorInterpreter(self._project_root / "config" / "error_interpreter.yaml")
        self._stored_recipe_cache: dict[str, Any] = {"sign": None, "rows": []}
        self._ssh_runtime = SSHRuntime(
            settings=self.settings,
            error_interpreter=self._error_interpreter,
            normalize_spaces=self._normalize_spaces,
            truncate_text=self._truncate_text,
            extract_held_packages=extract_held_packages,
        )
        self._recipe_runtime = RecipeRuntime(
            settings=self.settings,
            llm_client=self.llm_client,
            memory_skill_getter=lambda: self.memory_skill,
            execute_custom_ssh_command=self._execute_custom_ssh_command,
            extract_memory_store_text=self._extract_memory_store_text,
            extract_memory_recall_query=self._extract_memory_recall_query,
            facts_collection_for_user=self._facts_collection_for_user,
            preferences_collection_for_user=self._preferences_collection_for_user,
            normalize_spaces=self._normalize_spaces,
            truncate_text=self._truncate_text,
        )
        self._skill_runtime = self._recipe_runtime
        self._rss_action_selection_policy = RssActionSelectionPolicy(
            settings=self.settings,
            llm_client=self.llm_client,
        )
        self._capability_executor = PipelineCapabilityExecutor(
            skill_runtime=self._skill_runtime,
            execute_custom_ssh_command=lambda **kwargs: self._execute_custom_ssh_command(**kwargs),
            parse_rss_group_bundle_note=self._parse_rss_group_bundle_note,
            call_with_optional_language=self._call_with_optional_language,
            website_rows=self._website_rows,
            default_mqtt_topic=self._default_mqtt_topic,
            msg=self._msg,
            normalize_spaces=self._normalize_spaces,
            extract_json_object=self._extract_json_object,
        )
        self._aria_turn_frames: dict[str, TurnFrame] = {}
        self._runtime_outcome_frames: dict[str, RuntimeOutcomeFrame] = {}
        self._last_meta_catalog_fallback_debug_lines: list[str] = []
        self._agent_job_tasks: set[asyncio.Task[Any]] = set()
        self._agent_job_store: AgentJobStore | None = None
        self._agent_job_store_path: Path | None = None
        self._agent_job_notifier: Any | None = None

    @staticmethod
    def _connection_kind_label(kind: str) -> str:
        return connection_kind_label(kind)

    @staticmethod
    def _is_english(language: str | None) -> bool:
        return is_english(language)

    @classmethod
    def _msg(cls, language: str | None, de: str, en: str) -> str:
        return localized_text(language, de=de, en=en)

    def _load_recent_capability_context(self, user_id: str) -> dict[str, Any]:
        if self.capability_context_store is None:
            return {}
        try:
            row = self.capability_context_store.load_recent(user_id)
        except Exception:
            return {}
        return row if isinstance(row, dict) else {}

    @staticmethod
    def _extract_json_object(text: str) -> dict[str, Any]:
        return core_extract_json_object(text) or {}

    def _parse_rss_group_bundle_note(self, notes: list[str] | tuple[str, ...] | None) -> tuple[str, list[str]] | None:
        return self._rss_action_selection_policy.parse_group_bundle_note(notes)

    @staticmethod
    def _call_with_optional_language(func: Any, *args: Any, language: str = "de", **kwargs: Any) -> Any:
        try:
            return func(*args, language=language, **kwargs)
        except TypeError as exc:
            unexpected = re.search(r"unexpected keyword argument '([^']+)'", str(exc))
            if not unexpected:
                raise
            bad_keyword = unexpected.group(1)
            if bad_keyword == "language":
                if kwargs:
                    try:
                        return func(*args, **kwargs)
                    except TypeError as retry_exc:
                        retry_unexpected = re.search(r"unexpected keyword argument '([^']+)'", str(retry_exc))
                        if retry_unexpected and retry_unexpected.group(1) in kwargs:
                            retry_kwargs = dict(kwargs)
                            retry_kwargs.pop(retry_unexpected.group(1), None)
                            return func(*args, **retry_kwargs)
                        raise
                return func(*args)
            if bad_keyword in kwargs:
                retry_kwargs = dict(kwargs)
                retry_kwargs.pop(bad_keyword, None)
                return Pipeline._call_with_optional_language(func, *args, language=language, **retry_kwargs)
            raise

    def _default_mqtt_topic(self, connection_ref: str) -> str:
        return default_mqtt_topic_from_settings(self.settings, connection_ref)

    def _routing_debug_enabled(self) -> bool:
        return bool(getattr(getattr(self.settings, "ui", object()), "debug_mode", False))

    def get_agent_job_store(self) -> AgentJobStore:
        path = Path(getattr(self, "_project_root", Path.cwd())) / "data" / "runtime" / "agent_jobs.sqlite3"
        if getattr(self, "_agent_job_store", None) is None or getattr(self, "_agent_job_store_path", None) != path:
            self._agent_job_store = AgentJobStore(path)
            self._agent_job_store_path = path
        return self._agent_job_store

    def list_agent_jobs(self, user_id: str, *, limit: int = 20) -> list[dict[str, Any]]:
        try:
            self.sweep_stale_agent_jobs(now=time.time())
        except Exception:
            pass
        loop = getattr(self.settings, "agentic_loop", object())
        extension = int(getattr(loop, "native_agent_budget_extension_steps", 32) or 32)
        hard_cap = int(getattr(loop, "native_agent_budget_max_total", 160) or 160)
        rows: list[dict[str, Any]] = []
        for record in self.get_agent_job_store().list_for_user(user_id, limit=limit):
            row = record.as_dict()
            state = record.resume_state or {}
            current = max(int(state.get("budget_max_steps") or 0), int(state.get("budget_max_provider_calls") or 0))
            row["budget_extension_steps"] = extension
            row["budget_can_extend"] = record.pause_reason == "budget_reached" and current < hard_cap
            rows.append(row)
        return rows

    def append_agent_job_detail_line(self, user_id: str, job_id: str, detail_line: str) -> bool:
        return self.get_agent_job_store().append_detail_line(
            job_id,
            user_id=user_id,
            detail_line=detail_line,
        )

    def request_agent_job_cancel(self, user_id: str, job_id: str, *, event_key: str = "") -> str:
        store = self.get_agent_job_store()
        before = store.get(job_id)
        if event_key and before is not None and before.user_id == user_id:
            loop = getattr(self.settings, "agentic_loop", object())
            claim = store.claim_budget_action(
                job_id, user_id=user_id, event_key=event_key, action="cancel",
                extension=int(getattr(loop, "native_agent_budget_extension_steps", 32) or 32),
                hard_cap=int(getattr(loop, "native_agent_budget_max_total", 160) or 160),
            )
            outcome = "requested" if claim.status == "claimed" else claim.status
        else:
            outcome = store.request_cancel(job_id, user_id=user_id)
        if (
            outcome == "requested" and before is not None and before.user_id == user_id
            and before.status == "awaiting_confirmation"
        ):
            token = str((before.resume_state or {}).get("pending_token") or "")
            pending_store = getattr(self, "_native_pending_store", None)
            if token and pending_store is not None:
                try:
                    pending_store.consume(user_id=user_id, token=token)
                except Exception:
                    pass
        if outcome == "requested" and before is not None and before.user_id == user_id and before.status in {"paused", "awaiting_confirmation"}:
            language = str((before.resume_state or {}).get("language") or "en")
            try:
                task = asyncio.create_task(self._notify_agent_job_terminal(
                    store=store, job_id=job_id, user_id=user_id, language=language,
                    status="cancelled", result="cancelled_by_user",
                ))
                self._track_agent_job_task(task)
            except RuntimeError:
                pass
        return outcome

    def request_agent_job_pause(self, user_id: str, job_id: str) -> str:
        return self.get_agent_job_store().request_pause(job_id, user_id=user_id)

    def request_agent_job_correction(self, user_id: str, job_id: str, text: str) -> str:
        return self.get_agent_job_store().queue_correction(
            job_id, user_id=user_id, text=text,
        )

    def _track_agent_job_task(self, task: asyncio.Task[Any]) -> None:
        tasks = getattr(self, "_agent_job_tasks", None)
        if tasks is None:
            tasks = set()
            self._agent_job_tasks = tasks
        tasks.add(task)

        def release(completed: asyncio.Task[Any]) -> None:
            tasks.discard(completed)
            if not completed.cancelled():
                try:
                    completed.exception()
                except Exception:
                    pass

        task.add_done_callback(release)

    async def _notify_agent_job_paused(
        self, *, store: AgentJobStore, job_id: str, user_id: str,
        language: str | None, step_index: int,
    ) -> None:
        record = store.get(job_id)
        event_key = record.event_key if record is not None else ""
        notifier = getattr(self, "_agent_job_notifier", None)
        if not callable(notifier) or not event_key or not store.mark_event_notified(job_id, event_key):
            return
        safe_job_id = "".join(
            character for character in str(job_id) if character.isalnum() or character in "_-"
        )[:64]
        link_label = self._pipeline_text(language, "agent_job_continue_link", "Continue in the job panel →")
        link = f"[{link_label}](/jobs/panel?job={safe_job_id}#job-{safe_job_id})"
        if record is not None and record.pause_reason == "budget_reached":
            extension = int(getattr(getattr(self.settings, "agentic_loop", object()), "native_agent_budget_extension_steps", 32) or 32)
            text = self._pipeline_text(
                language, "agent_job_budget_reached_notice",
                "⏸ Step budget reached after {step} steps. Choose: ▶ {extension} more steps, ✅ finish now, or ⏹ cancel. {link}",
                step=max(0, int(step_index)), extension=extension, link=link,
            )
            badge_intent = "agent_job_budget_reached"
        else:
            text = self._pipeline_text(
                language, "agent_job_paused_notice",
                "⏸ Background task paused after step {step}. {link}",
                step=max(0, int(step_index)), link=link,
            )
            badge_intent = "agent_job_paused"
        usage = dict(record.usage or {}) if record is not None else {}
        tokens = max(0, int(usage.get("input_tokens", 0) or 0) + int(usage.get("output_tokens", 0) or 0))
        cost_value = usage.get("cost_usd")
        cost = f"${float(cost_value):.4f}" if cost_value is not None else "n/a"
        if tokens or cost_value is not None:
            usage_line = f"≈ {tokens:,} Tokens".replace(",", " ")
            if cost_value is not None:
                usage_line += f" · ≈ {cost}"
            text = f"{text}\n\n{usage_line}"
        try:
            emitted = notifier(
                user_id,
                job_id=safe_job_id,
                text=text,
                badge_icon="⏸",
                badge_intent=badge_intent,
                badge_tokens=tokens,
                badge_cost_usd=cost,
                badge_duration="0.0",
                badge_details=[
                    "Routing Debug: agent_job "
                    f"status=paused job_id={safe_job_id} steps={max(0, int(step_index))}"
                ],
                request_id=str((record.resume_state or {}).get("turn_id") or "") if record else "",
                event_key=event_key,
            )
            if inspect.isawaitable(emitted):
                await emitted
        except Exception as exc:
            LOGGER.warning(
                "Agent job pause notice failed for %s (%s)",
                safe_job_id,
                type(exc).__name__,
            )

    async def _notify_agent_job_awaiting_confirmation(
        self, *, store: AgentJobStore, job_id: str, user_id: str,
        language: str | None, snapshot: dict[str, Any],
    ) -> None:
        token = str(snapshot.get("pending_token") or "")
        if not token or not store.mark_event_notified(job_id, f"confirmation#{token}"):
            return
        notifier = getattr(self, "_agent_job_notifier", None)
        if not callable(notifier):
            return
        safe_job_id = "".join(
            character for character in str(job_id) if character.isalnum() or character in "_-"
        )[:64]
        preview = " ".join(str(snapshot.get("pending_preview") or "").split())[:1200]
        link_label = self._pipeline_text(language, "agent_job_link", "View job →")
        text = self._pipeline_text(
            language,
            "agent_job_confirmation_notice",
            "❓ Background task needs your confirmation: {preview}\n\n[{link}](/jobs/panel#job-{job_id})",
            preview=preview,
            link=link_label,
            job_id=safe_job_id,
        )
        emitted = notifier(
            user_id,
            job_id=safe_job_id,
            text=text,
            badge_icon="❓",
            badge_intent="agent_job_awaiting_confirmation",
            badge_tokens=0,
            badge_cost_usd="n/a",
            badge_duration="0.0",
            badge_details=[
                "Routing Debug: agent_job "
                f"status=awaiting_confirmation job_id={safe_job_id}"
            ],
            request_id=str(snapshot.get("turn_id") or ""),
            event_key=f"confirmation#{token}",
        )
        if inspect.isawaitable(emitted):
            await emitted

    async def resume_agent_job(
        self, user_id: str, job_id: str, *, budget_action: str = "", event_key: str = "",
    ) -> str:
        store = self.get_agent_job_store()
        before = store.get(job_id)
        if before is None or before.user_id != user_id:
            return "not_found"
        if budget_action in {"extend", "finish"}:
            loop = getattr(self.settings, "agentic_loop", object())
            claim = store.claim_budget_action(
                job_id, user_id=user_id,
                event_key=event_key or before.event_key,
                action=budget_action,
                extension=int(getattr(loop, "native_agent_budget_extension_steps", 32) or 32),
                hard_cap=int(getattr(loop, "native_agent_budget_max_total", 160) or 160),
            )
            if claim.status != "claimed":
                return claim.status
            state = claim.state
        else:
            state = store.claim_resume(job_id, user_id=user_id)
        if state is None:
            return "not_running"
        message = str(state.get("original_message") or before.goal)
        language = str(state.get("language") or "en")
        auth_role = str(state.get("auth_role") or "")
        turn_id = str(state.get("turn_id") or ("aj-resume-" + uuid4().hex))
        start = time.perf_counter()
        timing = StageTimingLedger(enabled=self._routing_debug_enabled())

        async def checkpoint(
            step_index: int, tool_names: tuple[str, ...], outcome_summary: str,
        ) -> None:
            store.append_step(
                job_id, step_index=int(step_index),
                tool_names=tuple(str(name) for name in tool_names),
                outcome_summary=str(outcome_summary),
            )
            if store.is_cancel_requested(job_id, user_id=user_id):
                raise NativeAgentStepCancelled("cancel_requested")

        async def pause_check() -> bool:
            return store.is_pause_requested(job_id, user_id=user_id)

        async def pause_refused(reason: str) -> None:
            store.refuse_pause(
                job_id, user_id=user_id,
                reason="pause_state_too_large" if reason == "resume_state_too_large" else reason,
            )

        async def correction_drain() -> tuple[str, ...]:
            return store.drain_corrections(job_id, user_id=user_id)

        async def detached_check() -> bool:
            return True

        async def usage_checkpoint(usage: dict[str, Any]) -> None:
            store.set_usage(job_id, usage)

        async def run_resumed_job() -> PipelineResult | None:
            try:
                result = await run_native_agent_first_stage(
                    self,
                    message=message,
                    user_id=user_id,
                    auth_role=auth_role,
                    request_id=turn_id,
                    source="agent_job_resume",
                    start=start,
                    recent_history=None,
                    confirmation_token="",
                    language=language,
                    step_callback=checkpoint,
                    pause_check=pause_check,
                    pause_refused=pause_refused,
                    correction_drain=correction_drain,
                    detached_check=detached_check,
                    usage_callback=usage_checkpoint,
                    resume_state=state,
                )
            except asyncio.CancelledError:
                raise
            except NativeAgentPaused as exc:
                if store.set_paused(job_id, exc.snapshot, reason=exc.reason):
                    await self._notify_agent_job_paused(
                        store=store, job_id=job_id, user_id=user_id, language=language,
                        step_index=int(exc.snapshot.get("step_index") or 0),
                    )
                elif store.is_cancel_requested(job_id, user_id=user_id):
                    store.set_terminal(job_id, status="cancelled", result="cancelled_by_user")
                    await self._notify_agent_job_terminal(
                        store=store, job_id=job_id, user_id=user_id, language=language,
                        status="cancelled", result="cancelled_by_user",
                    )
                return None
            except NativeAgentAwaitingConfirmation as exc:
                if store.set_awaiting_confirmation(job_id, exc.snapshot):
                    await self._notify_agent_job_awaiting_confirmation(
                        store=store, job_id=job_id, user_id=user_id,
                        language=language, snapshot=exc.snapshot,
                    )
                return None
            except NativeAgentStepCancelled:
                store.set_terminal(job_id, status="cancelled", result="cancelled_by_user")
                await self._notify_agent_job_terminal(
                    store=store, job_id=job_id, user_id=user_id, language=language,
                    status="cancelled", result="cancelled_by_user",
                )
                return None
            except Exception as exc:
                error = str(exc) or type(exc).__name__
                store.set_terminal(job_id, status="error", result=error)
                await self._notify_agent_job_terminal(
                    store=store, job_id=job_id, user_id=user_id, language=language,
                    status="error", result=error,
                )
                return None
            terminal_result = (
                self._finalize_process_result(result, start=start, timing=timing, language=language)
                if result is not None else None
            )
            failed = terminal_result is None or bool(terminal_result.skill_errors)
            terminal_text = (
                ",".join(terminal_result.skill_errors)
                if terminal_result is not None and terminal_result.skill_errors
                else terminal_result.text if terminal_result is not None else "native_agent_disabled"
            )
            terminal_warning = ""
            if terminal_result is not None and any(
                line == "Routing Debug: native_agent_budget_incomplete=yes"
                for line in terminal_result.detail_lines
            ):
                terminal_warning = "native_agent_budget_incomplete"
            elif terminal_result is not None and any(
                line == "Routing Debug: native_agent_summary_warning=yes"
                for line in terminal_result.detail_lines
            ):
                terminal_warning = "native_agent_summary_unavailable"
            store.set_terminal(
                job_id, status="error" if failed else "done", result=terminal_text,
                warning="" if failed else terminal_warning,
            )
            if terminal_result is not None:
                step_count = len((store.get(job_id) or before).step_log)
                terminal_result.detail_lines.append(
                    f"Routing Debug: agent_job resumed=yes steps={step_count}"
                )
            await self._notify_agent_job_terminal(
                store=store, job_id=job_id, user_id=user_id, language=language,
                status="error" if failed else "done", result=terminal_text,
                warning="" if failed else terminal_warning,
                terminal_result=terminal_result,
            )
            return terminal_result

        task = asyncio.create_task(run_resumed_job(), name=f"aria-agent-job-resume-{job_id}")
        self._track_agent_job_task(task)
        store.clear_resume_state(job_id, user_id=user_id)
        return "started"

    async def resolve_agent_job_confirmation(
        self, user_id: str, job_id: str, *, approve: bool,
    ) -> str:
        """Resolve one detached-job confirmation, then reuse the pause/resume loop."""

        store = self.get_agent_job_store()
        before = store.get(job_id)
        if before is None or before.user_id != user_id:
            return "not_found"
        state = store.claim_confirmation_resume(job_id, user_id=user_id)
        if state is None:
            return "not_running"
        token = str(state.get("pending_token") or "")
        call_id = str(state.get("pending_call_id") or "")
        tool_name = str(state.get("pending_tool_name") or "")
        message = str(state.get("original_message") or before.goal)
        language = str(state.get("language") or "en")
        auth_role = str(state.get("auth_role") or "")
        turn_id = str(state.get("turn_id") or ("aj-confirm-" + uuid4().hex))

        async def continue_after_resolution_impl() -> None:
            if approve:
                result = await run_native_agent_first_stage(
                    self,
                    message=message,
                    user_id=user_id,
                    auth_role=auth_role,
                    request_id=turn_id,
                    source="agent_job_confirmation",
                    start=time.perf_counter(),
                    recent_history=None,
                    confirmation_token=token,
                    language=language,
                )
                refused = bool(
                    result is None
                    or any("outcome=confirmation_refused" in line for line in result.detail_lines)
                )
                tool_result = (
                    json.dumps({"status": "confirmation_expired"}, ensure_ascii=True)
                    if refused
                    else str(result.text or "")
                )
                if not refused and tool_name:
                    state.setdefault("used_tool_names", []).append(tool_name)
                    state.setdefault("successful_tool_names", []).append(tool_name)
            else:
                pending_store = getattr(self, "_native_pending_store", None)
                if token and pending_store is not None:
                    try:
                        pending_store.consume(user_id=user_id, token=token)
                    except Exception:
                        pass
                tool_result = json.dumps({"status": "declined_by_user"}, ensure_ascii=True)

            messages = state.get("messages")
            if not isinstance(messages, list):
                messages = []
                state["messages"] = messages
            messages.append({"role": "tool", "tool_call_id": call_id, "content": tool_result})
            deferred_result = json.dumps(
                {"status": "not_executed", "reason": "deferred_by_confirmation"},
                ensure_ascii=True,
            )
            for deferred in state.pop("pending_deferred_calls", ()):
                if isinstance(deferred, dict) and str(deferred.get("call_id") or ""):
                    messages.append({
                        "role": "tool",
                        "tool_call_id": str(deferred.get("call_id")),
                        "content": deferred_result,
                    })
            for key in ("pending_token", "pending_call_id", "pending_tool_name", "pending_preview"):
                state.pop(key, None)
            if not store.stage_resume_state(job_id, state, user_id=user_id):
                return
            await self.resume_agent_job(user_id, job_id)

        async def continue_after_resolution() -> None:
            try:
                await continue_after_resolution_impl()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                reason = _bounded_agent_job_notice_result(
                    f"confirmation_resume_failed:{type(exc).__name__}: {exc}",
                    limit=800,
                )
                store.set_terminal(job_id, status="error", result=reason)
                await self._notify_agent_job_terminal(
                    store=store,
                    job_id=job_id,
                    user_id=user_id,
                    language=language,
                    status="error",
                    result=reason,
                )

        task = asyncio.create_task(
            continue_after_resolution(),
            name=f"aria-agent-job-confirm-{job_id}",
        )
        self._track_agent_job_task(task)
        return "started"

    async def _notify_agent_job_terminal(
        self,
        *,
        store: AgentJobStore,
        job_id: str,
        user_id: str,
        language: str | None,
        status: str,
        result: str,
        warning: str = "",
        terminal_result: PipelineResult | None = None,
    ) -> None:
        notifier = getattr(self, "_agent_job_notifier", None)
        if not callable(notifier) or not store.mark_notified(job_id):
            return
        safe_result = _bounded_agent_job_notice_result(result)
        safe_job_id = "".join(
            character for character in str(job_id) if character.isalnum() or character in "_-"
        )[:64]
        link_label = self._pipeline_text(language, "agent_job_link", "View job →")
        link = f"[{link_label}](/jobs/panel?job={safe_job_id}#job-{safe_job_id})"
        if status == "done":
            if warning in {"native_agent_budget_incomplete", "native_agent_summary_unavailable"}:
                text = self._pipeline_text(
                    language,
                    "agent_job_partial_summary_notice" if warning == "native_agent_summary_unavailable" else "agent_job_partial_notice",
                    "⚠️ Background task partially completed: {result}\n\n{link}",
                    result=safe_result,
                    link=link,
                )
                badge_icon = "⚠️"
            else:
                warning_text = ""
                text = self._pipeline_text(
                    language,
                    "agent_job_done_notice",
                    "✅ Background task finished: {result}{warning}\n\n{link}",
                    result=safe_result,
                    warning=warning_text,
                    link=link,
                )
                badge_icon = "✅"
        elif status == "cancelled":
            text = self._pipeline_text(
                language,
                "agent_job_cancelled_notice",
                "⏹ Background task cancelled. Steps already completed remain in place.\n\n{link}",
                link=link,
            )
            badge_icon = "⏹"
        else:
            text = self._pipeline_text(
                language,
                "agent_job_error_notice",
                "⚠️ Background task failed: {reason}\n\n{link}",
                reason=safe_result or "unknown_error",
                link=link,
            )
            badge_icon = "⚠️"
        record = store.get(job_id)
        step_count = len(record.step_log) if record is not None else 0
        details = list(record.detail_lines) if record is not None else []
        if terminal_result is not None:
            details.extend(
                line for line in terminal_result.detail_lines
                if line not in details
            )
        details.append(
            "Routing Debug: agent_job "
            f"status={status} job_id={safe_job_id} steps={step_count}"
        )
        usage = dict(terminal_result.usage) if terminal_result is not None else {}
        tokens = int(usage.get("total_tokens", 0) or 0)
        total_cost = terminal_result.total_cost_usd if terminal_result is not None else None
        cost = f"${total_cost:.6f}" if total_cost is not None else "n/a"
        segment_duration_ms = int(terminal_result.duration_ms or 0) if terminal_result is not None else 0
        total_duration_ms = max(
            max(0, segment_duration_ms),
            max(0, int((record.updated_at - record.created_at) * 1000))
            if record is not None else 0,
        )
        details.append(
            "Routing Debug: agent_job_duration "
            f"total_ms={total_duration_ms} segment_ms={max(0, segment_duration_ms)}"
        )
        try:
            emitted = notifier(
                user_id,
                job_id=safe_job_id,
                text=text,
                badge_icon=badge_icon,
                badge_intent=f"agent_job_{status}",
                badge_tokens=tokens,
                badge_cost_usd=cost,
                badge_duration=f"{total_duration_ms / 1000:.1f}",
                badge_details=details,
                request_id=str(terminal_result.request_id or "") if terminal_result is not None else "",
                event_key="terminal",
            )
            if inspect.isawaitable(emitted):
                await emitted
        except Exception as exc:
            LOGGER.warning(
                "Agent job completion notice failed for %s (%s)",
                safe_job_id,
                type(exc).__name__,
            )

    def delete_agent_job(self, user_id: str, job_id: str) -> str:
        record = self.get_agent_job_store().get(job_id)
        if record is not None and record.user_id == user_id:
            self._invalidate_agent_job_pending_token(record)
        return self.get_agent_job_store().delete_terminal(job_id, user_id=user_id)

    def clear_terminal_agent_jobs(self, user_id: str) -> int:
        store = self.get_agent_job_store()
        for record in store.list_for_user(user_id, limit=100):
            if record.status in {"done", "error", "cancelled"}:
                self._invalidate_agent_job_pending_token(record)
        return store.delete_terminal_for_user(user_id)

    def _invalidate_agent_job_pending_token(self, record: AgentJobRecord) -> None:
        token = str((record.resume_state or {}).get("pending_token") or "")
        pending_store = getattr(self, "_native_pending_store", None)
        if token and pending_store is not None:
            try:
                pending_store.consume(user_id=record.user_id, token=token)
            except Exception:
                pass

    def sweep_stale_agent_jobs(self, *, now: float | None = None) -> int:
        current = float(time.time() if now is None else now)
        loop = getattr(self.settings, "agentic_loop", object())
        budget = float(getattr(loop, "async_agent_job_sync_budget_seconds", 25.0) or 25.0)
        stale_after = max(120.0, budget * 4.0)
        store = self.get_agent_job_store()
        changed = store.mark_stale_interrupted(
            stale_before=current - stale_after,
            now=current,
        )
        paused_days = int(getattr(loop, "agent_job_stale_paused_days", 7) or 7)
        for record in store.stale_paused(stale_before=current - paused_days * 86400):
            self._invalidate_agent_job_pending_token(record)
            if store.cancel_stale_paused(record.job_id, now=current):
                changed += 1
                try:
                    task = asyncio.create_task(self._notify_agent_job_terminal(
                        store=store, job_id=record.job_id, user_id=record.user_id,
                        language=str((record.resume_state or {}).get("language") or "en"),
                        status="cancelled", result="stale_paused_timeout",
                    ))
                    self._track_agent_job_task(task)
                except RuntimeError:
                    pass
        retention_days = int(getattr(loop, "agent_job_retention_days", 14) or 14)
        changed += store.purge_terminal_before(stale_before=current - retention_days * 86400)
        return changed

    def _append_debug_detail_lines(self, resolved: dict[str, Any], *lines: str) -> dict[str, Any]:
        return append_debug_detail_lines(resolved, *lines, routing_debug_enabled=self._routing_debug_enabled())

    @staticmethod
    def _pipeline_text(language: str | None, key: str, default: str = "", **values: object) -> str:
        return _pipeline_text(language, key, default, **values)

    @staticmethod
    def _insert_stage_timing_detail_lines(
        detail_lines: list[str] | None,
        timing: StageTimingLedger,
    ) -> list[str]:
        return insert_stage_timing_detail_lines(detail_lines, timing)

    @staticmethod
    def _skill_errors(skill_results: list[SkillResult]) -> list[str]:
        errors: list[str] = []
        for result in skill_results:
            if result.success or not result.error:
                continue
            metadata = result.metadata or {}
            errors.append(str(metadata.get("error_code", "") or result.error))
        return errors

    @staticmethod
    def _collect_skill_detail_lines(skill_results: list[SkillResult]) -> list[str]:
        lines: list[str] = []
        seen: set[str] = set()
        for result in skill_results:
            raw_lines = (result.metadata or {}).get("detail_lines")
            if not isinstance(raw_lines, list):
                continue
            for row in raw_lines:
                text = str(row).strip()
                if text and text not in seen:
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
        prefix = self.settings.memory.collections.facts.prefix.strip() or "aria_facts"
        return f"{prefix}_{self._slug_user_id(user_id)}"

    def _preferences_collection_for_user(self, user_id: str) -> str:
        prefix = self.settings.memory.collections.preferences.prefix.strip() or "aria_preferences"
        return f"{prefix}_{self._slug_user_id(user_id)}"

    def _extract_memory_store_text(self, message: str, routing_profile: RoutingLanguageConfig | None = None) -> str:
        del routing_profile
        return self._normalize_spaces(message)

    def _extract_memory_recall_query(self, message: str, routing_profile: RoutingLanguageConfig | None = None) -> str:
        del routing_profile
        return self._normalize_spaces(message)

    def _extract_web_search_query(self, message: str, routing_profile: RoutingLanguageConfig | None = None) -> str:
        del routing_profile
        return self._normalize_spaces(message)

    @staticmethod
    def _truncate_text(text: str, limit: int = 1200) -> str:
        raw = str(text or "").strip()
        if len(raw) <= limit:
            return raw
        return raw[:limit] + "\n[... gekuerzt]"

    def _current_usage_snapshot(self) -> dict[str, Any]:
        snapshot = self.usage_meter.snapshot_scope(None)
        usage = dict(snapshot.get("usage", {}) or {})
        embedding_usage = dict(snapshot.get("embedding_usage", {}) or {})
        return {
            "usage": {key: int(usage.get(key, 0) or 0) for key in ("prompt_tokens", "completion_tokens", "total_tokens")},
            "embedding_usage": {
                **{key: int(embedding_usage.get(key, 0) or 0) for key in ("prompt_tokens", "completion_tokens", "total_tokens")},
                "calls": int(embedding_usage.get("calls", 0) or 0),
            },
            "chat_model": str(snapshot.get("chat_model", "") or self.settings.llm.model).strip(),
            "embedding_model": str(snapshot.get("embedding_model", "") or self.settings.embeddings.model).strip(),
            "chat_cost_usd": snapshot.get("chat_cost_usd"),
            "embedding_cost_usd": snapshot.get("embedding_cost_usd"),
            "total_cost_usd": snapshot.get("total_cost_usd"),
        }

    def _available_connection_kinds_for_aria_turn(self) -> tuple[str, ...]:
        raw = getattr(self.settings, "connections", None)
        rows = raw.model_dump() if hasattr(raw, "model_dump") else {}
        if not isinstance(rows, dict):
            return ()
        from aria.modules.connections_catalog.catalog import ordered_connection_kinds
        return tuple(kind for kind in ordered_connection_kinds() if isinstance(rows.get(kind), dict) and rows[kind])

    def _finalize_process_result(
        self,
        result: PipelineResult,
        *,
        start: float,
        timing: StageTimingLedger,
        language: str | None = None,
    ) -> PipelineResult:
        timing.add("pipeline_wall_time", int((time.perf_counter() - start) * 1000))
        result.detail_lines = self._insert_stage_timing_detail_lines(result.detail_lines, timing)
        result.detail_lines = append_stabilization_gate_detail_lines(result.detail_lines)
        result.text, result.detail_lines = enforce_stabilization_gate_answerability(
            result.text, result.detail_lines, language=language,
        )
        result.detail_lines = append_operator_trace_detail_lines(result.detail_lines)
        return result





















































    @staticmethod
    def _extract_held_packages(text: str) -> list[str]:
        return extract_held_packages(text)

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
        policy_confirmed: bool = False,
    ) -> SkillResult:
        return await self._ssh_runtime.execute_custom_ssh_command(
            skill_id=skill_id,
            skill_name=skill_name,
            connection_ref=connection_ref,
            command_template=command_template,
            message=message,
            timeout_seconds=timeout_seconds,
            language=language,
            policy_confirmed=policy_confirmed,
        )

    async def _execute_custom_steps(
        self, row: dict[str, Any], message: str, language: str = "de", *, user_id: str = "",
    ) -> SkillResult:
        return await self._skill_runtime.execute_custom_steps(
            row=row, message=message, language=language, user_id=user_id,
        )

    @staticmethod
    def _normalize_model_name(value: str) -> str:
        return value.strip().lower()

    def _resolve_pricing_entry(self, entries: dict[str, object], model_name: str) -> object | None:
        return resolve_pricing_entry(
            entries,
            model_name,
            model_aliases=getattr(self.settings.pricing, "model_aliases", {}),
        )

    async def _run_skills(
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
        return await self._skill_runtime.run_skills(
            intents=intents,
            message=message,
            user_id=user_id,
            routing_profile=routing_profile,
            language=language,
            runtime_recipes=runtime_recipes,
            memory_collection=memory_collection,
            session_collection=session_collection,
            suppress_web_search_note_context=suppress_web_search_note_context,
            query_overrides=query_overrides,
            context_overrides=context_overrides,
        )








































    async def _execute_file_read(self, plan: ActionPlan, *, language: str = "de") -> str:
        return await self._capability_executor.execute_file_read(plan, language=language)

    async def _execute_file_write(self, plan: ActionPlan, *, language: str = "de") -> str:
        return await self._capability_executor.execute_file_write(plan, language=language)

    async def _execute_file_list(self, plan: ActionPlan, *, language: str = "de") -> str:
        return await self._capability_executor.execute_file_list(plan, language=language)

    async def _execute_feed_read(self, plan: ActionPlan, *, language: str = "de") -> str:
        return await self._capability_executor.execute_feed_read(plan, language=language)

    def _website_rows(self) -> dict[str, dict[str, object]]:
        return website_rows_from_settings(self.settings)

    async def _execute_website_read(self, plan: ActionPlan, *, language: str = "de") -> str:
        return await self._capability_executor.execute_website_read(plan, language=language)

    async def _execute_website_list(self, plan: ActionPlan, *, language: str = "de") -> str:
        return await self._capability_executor.execute_website_list(plan, language=language)

    async def _execute_calendar_read(self, plan: ActionPlan, *, language: str = "de") -> str:
        return await self._capability_executor.execute_calendar_read(plan, language=language)

    async def _execute_webhook_send(self, plan: ActionPlan, *, language: str = "de") -> str:
        return await self._capability_executor.execute_webhook_send(plan, language=language)

    async def _execute_discord_send(self, plan: ActionPlan, *, language: str = "de") -> str:
        return await self._capability_executor.execute_discord_send(plan, language=language)

    async def _execute_api_request(self, plan: ActionPlan, *, language: str = "de") -> str:
        return await self._capability_executor.execute_api_request(plan, language=language)

    async def _execute_email_send(self, plan: ActionPlan, *, language: str = "de") -> str:
        return await self._capability_executor.execute_email_send(plan, language=language)

    async def _execute_mail_read(self, plan: ActionPlan, *, language: str = "de") -> str:
        return await self._capability_executor.execute_mail_read(plan, language=language)

    async def _execute_mail_search(self, plan: ActionPlan, *, language: str = "de") -> str:
        return await self._capability_executor.execute_mail_search(plan, language=language)

    async def _execute_mqtt_publish(self, plan: ActionPlan, *, language: str = "de") -> str:
        return await self._capability_executor.execute_mqtt_publish(plan, language=language)

    async def _execute_ssh_command(self, plan: ActionPlan, *, language: str = "de") -> str:
        return await self._capability_executor.execute_ssh_command(plan, language=language)

    def _can_salvage_partial_ssh_result(self, result: SkillResult) -> bool:
        return self._capability_executor.can_salvage_partial_ssh_result(result)

    def _format_capability_missing_message(self, plan: ActionPlan, *, language: str | None = None) -> str:
        connection_rows = getattr(getattr(self.settings, "connections", object()), plan.connection_kind, {})
        return format_capability_missing_message(plan, connection_rows=connection_rows, language=language)

    def _sanitize_capability_error(self, exc: Exception, *, language: str | None = None) -> str:
        return sanitize_capability_error(exc, language=language)

    def _format_capability_execution_error(self, plan: ActionPlan, exc: Exception, *, language: str | None = None) -> str:
        return format_capability_execution_error(plan, exc, language=language)

    def _capability_execution_error_code(self, plan: ActionPlan, exc: Exception) -> str:
        return capability_execution_error_code(plan, exc)































































































































    async def process(
        self,
        message: str,
        user_id: str = "web",
        source: str = "web",
        language: str | None = None,
        memory_collection: str | None = None,
        session_collection: str | None = None,
        recent_history: list[dict[str, Any]] | None = None,
        auth_role: str = "",
        confirmation_token: str = "",
    ) -> PipelineResult:
        del memory_collection, session_collection
        start = time.perf_counter()
        timing = StageTimingLedger(enabled=self._routing_debug_enabled())
        request_id = str(uuid4())
        native_kwargs = {
            "message": message,
            "user_id": user_id,
            "auth_role": auth_role,
            "request_id": request_id,
            "source": source,
            "start": start,
            "recent_history": recent_history,
            "confirmation_token": confirmation_token,
            "language": language or "en",
        }
        if str(confirmation_token or "").strip():
            native_agent_result = await run_native_agent_first_stage(self, **native_kwargs)
        else:
            store: AgentJobStore | None = None
            job_id = "aj" + uuid4().hex[:18]
            worker_id = str(id(self))
            buffered_steps: list[tuple[int, tuple[str, ...], str]] = []
            state: dict[str, Any] = {"detached": False, "usage": {}}

            async def checkpoint(
                step_index: int, tool_names: tuple[str, ...], outcome_summary: str,
            ) -> None:
                row = (int(step_index), tuple(str(name) for name in tool_names), str(outcome_summary))
                if state["detached"] and store is not None:
                    store.append_step(
                        job_id, step_index=row[0], tool_names=row[1], outcome_summary=row[2],
                    )
                    if store.is_cancel_requested(job_id, user_id=user_id):
                        raise NativeAgentStepCancelled("cancel_requested")
                else:
                    buffered_steps.append(row)

            async def pause_check() -> bool:
                return bool(
                    state["detached"] and store is not None
                    and store.is_pause_requested(job_id, user_id=user_id)
                )

            async def pause_refused(reason: str) -> None:
                if state["detached"] and store is not None:
                    store.refuse_pause(
                        job_id, user_id=user_id,
                        reason="pause_state_too_large" if reason == "resume_state_too_large" else reason,
                    )

            async def correction_drain() -> tuple[str, ...]:
                if state["detached"] and store is not None:
                    return store.drain_corrections(job_id, user_id=user_id)
                return ()

            async def detached_check() -> bool:
                return bool(state["detached"])

            async def usage_checkpoint(usage: dict[str, Any]) -> None:
                state["usage"] = dict(usage)
                if state["detached"] and store is not None:
                    store.set_usage(job_id, usage)

            async def run_native_job() -> PipelineResult | None:
                try:
                    result = await run_native_agent_first_stage(
                        self, **native_kwargs, step_callback=checkpoint,
                        pause_check=pause_check, pause_refused=pause_refused,
                        correction_drain=correction_drain,
                        detached_check=detached_check,
                        usage_callback=usage_checkpoint,
                    )
                except asyncio.CancelledError:
                    raise
                except NativeAgentPaused as exc:
                    if state["detached"] and store is not None:
                        if store.set_paused(job_id, exc.snapshot, reason=exc.reason):
                            await self._notify_agent_job_paused(
                                store=store, job_id=job_id, user_id=user_id,
                                language=language,
                                step_index=int(exc.snapshot.get("step_index") or 0),
                            )
                        elif store.is_cancel_requested(job_id, user_id=user_id):
                            store.set_terminal(job_id, status="cancelled", result="cancelled_by_user")
                            await self._notify_agent_job_terminal(
                                store=store, job_id=job_id, user_id=user_id,
                                language=language, status="cancelled",
                                result="cancelled_by_user",
                            )
                    return None
                except NativeAgentAwaitingConfirmation as exc:
                    if state["detached"] and store is not None:
                        if store.set_awaiting_confirmation(job_id, exc.snapshot):
                            await self._notify_agent_job_awaiting_confirmation(
                                store=store, job_id=job_id, user_id=user_id,
                                language=language, snapshot=exc.snapshot,
                            )
                    return None
                except NativeAgentStepCancelled:
                    if state["detached"] and store is not None:
                        store.set_terminal(
                            job_id, status="cancelled", result="cancelled_by_user",
                        )
                        await self._notify_agent_job_terminal(
                            store=store, job_id=job_id, user_id=user_id,
                            language=language, status="cancelled",
                            result="cancelled_by_user",
                        )
                    return None
                except Exception as exc:
                    if state["detached"] and store is not None:
                        error = str(exc) or type(exc).__name__
                        store.set_terminal(job_id, status="error", result=error)
                        await self._notify_agent_job_terminal(
                            store=store, job_id=job_id, user_id=user_id,
                            language=language, status="error", result=error,
                        )
                    raise
                if state["detached"] and store is not None:
                    try:
                        terminal_result = (
                            self._finalize_process_result(result, start=start, timing=timing, language=language)
                            if result is not None else None
                        )
                        failed = terminal_result is None or bool(terminal_result.skill_errors)
                        terminal_text = (
                            ",".join(terminal_result.skill_errors)
                            if terminal_result is not None and terminal_result.skill_errors
                            else terminal_result.text if terminal_result is not None else "native_agent_disabled"
                        )
                        terminal_warning = ""
                        if terminal_result is not None and any(
                            line == "Routing Debug: native_agent_budget_incomplete=yes"
                            for line in terminal_result.detail_lines
                        ):
                            terminal_warning = "native_agent_budget_incomplete"
                        elif terminal_result is not None and any(
                            line == "Routing Debug: native_agent_summary_warning=yes"
                            for line in terminal_result.detail_lines
                        ):
                            terminal_warning = "native_agent_summary_unavailable"
                        store.set_terminal(
                            job_id,
                            status="error" if failed else "done",
                            result=terminal_text,
                            warning="" if failed else terminal_warning,
                        )
                        await self._notify_agent_job_terminal(
                            store=store, job_id=job_id, user_id=user_id,
                            language=language,
                            status="error" if failed else "done",
                            result=terminal_text,
                            warning="" if failed else terminal_warning,
                            terminal_result=terminal_result,
                        )
                        return terminal_result
                    except Exception as exc:
                        error = str(exc) or type(exc).__name__
                        store.set_terminal(job_id, status="error", result=error)
                        await self._notify_agent_job_terminal(
                            store=store, job_id=job_id, user_id=user_id,
                            language=language, status="error", result=error,
                        )
                        raise
                return result

            task = asyncio.create_task(run_native_job(), name=f"aria-agent-job-{job_id}")
            self._track_agent_job_task(task)
            budget = float(getattr(getattr(self.settings, "agentic_loop", object()), "async_agent_job_sync_budget_seconds", 25.0) or 25.0)
            budget = min(89.0, max(0.01, budget))
            try:
                native_agent_result = await asyncio.wait_for(asyncio.shield(task), timeout=budget)
            except TimeoutError:
                state["detached"] = True
                store = self.get_agent_job_store()
                store.create(
                    job_id=job_id, user_id=user_id, goal=message,
                    status="detached", worker_id=worker_id,
                )
                for step_index, tool_names, outcome_summary in buffered_steps:
                    store.append_step(
                        job_id, step_index=step_index, tool_names=tool_names,
                        outcome_summary=outcome_summary,
                    )
                if state.get("usage"):
                    store.set_usage(job_id, dict(state["usage"]))
                text = self._pipeline_text(
                    language,
                    "agent_job_detached",
                    "The task is continuing in the background. Job ID: {job_id}. "
                    "Status: [View job →](/jobs/panel#job-{job_id})",
                    job_id=job_id,
                )
                detached_result = PipelineResult(
                    request_id=request_id, text=text,
                    usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                    intents=["native_agent"], skill_errors=[], router_level=2,
                    duration_ms=int((time.perf_counter() - start) * 1000),
                    detail_lines=[
                        "Routing Debug: agent_job "
                        f"status=detached job_id={job_id} sync_budget_ms={int(budget * 1000)}"
                    ],
                    agent_job_id=job_id,
                )
                return self._finalize_process_result(
                    detached_result, start=start, timing=timing, language=language,
                )
        if native_agent_result is not None:
            return self._finalize_process_result(native_agent_result, start=start, timing=timing, language=language)
        degraded = PipelineResult(
            request_id=request_id,
            text="The native agent is disabled for this turn.",
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            intents=["native_agent"],
            skill_errors=["native_agent_disabled"],
            router_level=0,
            duration_ms=int((time.perf_counter() - start) * 1000),
            detail_lines=[
                "Routing Debug: native_agent_position=only_path outcome=degraded reason=native_agent_disabled"
            ],
        )
        return self._finalize_process_result(degraded, start=start, timing=timing, language=language)
