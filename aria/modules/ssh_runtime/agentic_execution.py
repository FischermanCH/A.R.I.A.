from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from aria.modules.action_contracts.plan import ActionPlan
from aria.modules.runtime_execution_registry.contracts import AgenticExecutionHooks
from aria.modules.runtime_execution_registry.contracts import AgenticExecutionRequest
from aria.modules.runtime_execution_registry.contracts import AgenticExecutionResult
from aria.modules.action_runtime_debug.debug import runtime_debug_line_for_plan
from aria.modules.action_contracts.capabilities import normalize_capability
from aria.modules.connections_catalog.catalog import normalize_connection_kind


@dataclass(slots=True)
class MultiTargetSSHExecutionHooks(AgenticExecutionHooks):
    payload_multi_target_refs: Callable[[dict[str, Any]], list[str]]
    preflight_refs: Callable[[list[str], str], tuple[list[str], list[dict[str, str]], list[str]]]
    execute_plan: Callable[[ActionPlan, str], Awaitable[str]]
    remember_action: Callable[[str, ActionPlan], None]
    remember_multi_target_action: Callable[[str, dict[str, Any], list[str], str, str], None]
    configured_connection_refs: Callable[[str], list[str]]
    extract_disk_measurement: Callable[[str], dict[str, Any] | None]
    operator_summary: Callable[[str, int, list[dict[str, str]]], str]
    relevant_result_texts: Callable[[list[dict[str, str]]], list[str]]
    llm_operator_summary: Callable[[str, str, list[dict[str, str]], str, str], Awaitable[tuple[str, str]]]


class MultiTargetSSHExecutionHandler:
    def __init__(self, hooks: MultiTargetSSHExecutionHooks, *, max_concurrency: int = 10) -> None:
        self._hooks = hooks
        self._max_concurrency = max(1, int(max_concurrency or 1))

    def can_handle(self, request: AgenticExecutionRequest) -> bool:
        payload = dict(request.payload or {})
        return (
            normalize_capability(str(payload.get("capability", "") or "")) == "ssh_command"
            and normalize_connection_kind(str(payload.get("connection_kind", "") or "")) == "ssh"
            and bool(self._hooks.payload_multi_target_refs(payload))
        )

    async def execute(self, request: AgenticExecutionRequest) -> AgenticExecutionResult:
        total_started = time.perf_counter()
        payload = dict(request.payload or {})
        refs = self._hooks.payload_multi_target_refs(payload)
        command = str(payload.get("content", "") or "").strip()
        intents = ["capability:ssh_command"]
        if not refs or not command:
            plan = self._hooks.payload_to_action_plan(payload)
            return AgenticExecutionResult(
                intents=intents,
                text=self._hooks.format_missing_message(plan, request.language),
            )

        detail_lines: list[str] = []
        result_records: list[dict[str, str]] = []
        errors: list[str] = []
        success_count = 0
        original_count = len(refs)
        configured_count = len(self._hooks.configured_connection_refs("ssh"))
        partial_scope_count = (
            configured_count
            if configured_count > original_count and not self._full_kind_scope_requested(payload)
            else 0
        )
        query = str(request.resolved.get("query", "") or "")
        preflight_started = time.perf_counter()
        allowed_refs, blocked_refs, preflight_detail_lines = self._hooks.preflight_refs(refs, command)
        preflight_ms = int((time.perf_counter() - preflight_started) * 1000)
        if self._hooks.routing_debug_enabled():
            detail_lines.extend(preflight_detail_lines)

        for blocked in blocked_refs:
            ref = str(blocked.get("ref", "") or "").strip()
            reason = str(blocked.get("reason", "") or "").strip() or "blocked"
            errors.append(f"capability_ssh_command_blocked:{ref}:{reason}")
            result_records.append(
                {
                    "ref": ref,
                    "state": "blocked",
                    "text": self._hooks.text(
                        request.language,
                        "multi_target_ssh_blocked_target",
                        "{ref} blocked: {reason}.",
                        ref=ref,
                        reason=reason,
                    ),
                }
            )

        async def _execute_allowed_ref(ref: str) -> dict[str, Any]:
            target_started = time.perf_counter()
            target_detail_lines: list[str] = []
            plan = ActionPlan(
                capability="ssh_command",
                connection_kind="ssh",
                connection_ref=ref,
                content=command,
                plan_class=str(payload.get("plan_class", "") or "").strip().lower(),
                behavior_profile=str(payload.get("behavior_profile", "") or "").strip().lower(),
                resolution_source="plural_target_scope",
                notes=list(payload.get("notes", []) or []),
            )
            if self._hooks.routing_debug_enabled():
                target_detail_lines.append(runtime_debug_line_for_plan(plan))
            target_detail_lines.extend(self._hooks.build_capability_detail_lines(plan, request.language))
            try:
                result_text = await self._hooks.execute_plan(plan, request.language)
            except Exception as exc:
                error_text = self._hooks.format_execution_error(plan, exc, request.language)
                duration_ms = int((time.perf_counter() - target_started) * 1000)
                return {
                    "success": False,
                    "errors": [f"capability_ssh_command_error:{ref}:{type(exc).__name__}"],
                    "record": {"ref": ref, "state": "error", "text": error_text},
                    "detail_lines": target_detail_lines,
                    "duration_ms": duration_ms,
                }

            clean_text = str(result_text or "").strip()
            record: dict[str, str] | None = None
            if clean_text:
                record = {
                    "ref": ref,
                    "state": "ok",
                    "text": clean_text,
                    "raw_text": clean_text,
                }
                disk_measurement = self._hooks.extract_disk_measurement(clean_text)
                if disk_measurement:
                    record["disk_measurement"] = disk_measurement
                    record.update(
                        {
                            "disk_mount": str(disk_measurement.get("mount", "") or ""),
                            "disk_use_pct": disk_measurement.get("use_pct", 0.0),
                            "disk_avail_gib": disk_measurement.get("avail_gib", 0.0),
                            "disk_avail_label": str(disk_measurement.get("avail_label", "") or ""),
                        }
                    )

            self._hooks.remember_action(request.user_id, plan)
            duration_ms = int((time.perf_counter() - target_started) * 1000)
            return {
                "success": True,
                "errors": [],
                "record": record,
                "detail_lines": target_detail_lines,
                "duration_ms": duration_ms,
            }

        async def _run_allowed_ref(ref: str, semaphore: asyncio.Semaphore) -> dict[str, Any]:
            async with semaphore:
                return await _execute_allowed_ref(ref)

        execution_ms = 0
        target_timings: list[tuple[str, str, int]] = []
        if allowed_refs:
            semaphore = asyncio.Semaphore(min(self._max_concurrency, len(allowed_refs)))
            execution_started = time.perf_counter()
            target_results = await asyncio.gather(*[_run_allowed_ref(ref, semaphore) for ref in allowed_refs])
            execution_ms = int((time.perf_counter() - execution_started) * 1000)
            for target_result in target_results:
                detail_lines.extend(list(target_result.get("detail_lines", []) or []))
                errors.extend([str(item) for item in list(target_result.get("errors", []) or []) if str(item)])
                record = target_result.get("record")
                record_ref = ""
                record_state = "empty"
                if isinstance(record, dict):
                    result_records.append(self._clean_record(record))
                    record_ref = str(record.get("ref", "") or "").strip()
                    record_state = str(record.get("state", "") or "").strip() or record_state
                if bool(target_result.get("success")):
                    success_count += 1
                duration_ms = int(target_result.get("duration_ms", 0) or 0)
                if record_ref:
                    target_timings.append((record_ref, record_state, duration_ms))
                    if self._hooks.routing_debug_enabled():
                        detail_lines.append(
                            "Routing Debug: multi_target_ssh_target_timing "
                            f"ref={record_ref} state={record_state} ms={duration_ms}"
                        )

        summary_started = time.perf_counter()
        summary = await self._build_summary(
            request=request,
            command=command,
            records=result_records,
            original_count=original_count,
            configured_count=configured_count,
            partial_scope_count=partial_scope_count,
            detail_lines=detail_lines,
        )
        summary_ms = int((time.perf_counter() - summary_started) * 1000)
        remember_started = time.perf_counter()
        self._hooks.remember_multi_target_action(
            request.user_id,
            payload,
            refs,
            command,
            summary,
        )
        remember_ms = int((time.perf_counter() - remember_started) * 1000)
        if self._hooks.routing_debug_enabled():
            detail_lines.append(
                self._result_contract_debug_line(
                    payload=payload,
                    command=command,
                    records=result_records,
                    original_count=original_count,
                    allowed_count=len(allowed_refs),
                    blocked_count=len(blocked_refs),
                    free_disk_threshold=None,
                )
            )
            slowest_ref = "-"
            max_target_ms = 0
            if target_timings:
                slowest_ref, _slowest_state, max_target_ms = max(target_timings, key=lambda item: item[2])
            total_ms = int((time.perf_counter() - total_started) * 1000)
            detail_lines.append(
                "Routing Debug: multi_target_ssh_timing "
                f"targets={original_count} allowed={len(allowed_refs)} blocked={len(blocked_refs)} "
                f"preflight_ms={preflight_ms} execution_ms={execution_ms} summary_ms={summary_ms} "
                f"remember_ms={remember_ms} total_ms={total_ms} slowest_ref={slowest_ref} "
                f"max_target_ms={max_target_ms}"
            )
        if errors:
            text = self._hooks.text(
                request.language,
                "multi_target_ssh_partial",
                "Checked {count} SSH targets; {success_count} succeeded and {error_count} failed. {summary}",
                count=original_count,
                success_count=success_count,
                error_count=len(errors),
                summary=summary,
            )
        else:
            text = self._hooks.text(
                request.language,
                "multi_target_ssh_success",
                "Checked {count} SSH targets. {summary}",
                count=original_count,
                summary=summary,
            )
        if partial_scope_count and self._hooks.routing_debug_enabled():
            detail_lines.append(
                "Routing Debug: multi_target_ssh_scope_boundary "
                f"selected={original_count} configured={partial_scope_count} claim_scope=selected_only"
            )
        metadata = {
            "runtime_outcome": {
                "surface_id": "connections",
                "kind": "ssh",
                "capability": "ssh_command",
                "task_intent": self._task_intent_from_payload(payload),
                "command": command,
                "targets": refs,
                "records": result_records,
                "summary": summary,
                "followup_affordances": self._followup_affordances_for_command(command, payload),
            }
        }
        return AgenticExecutionResult(intents=intents, text=text, detail_lines=detail_lines, errors=errors, metadata=metadata)

    @staticmethod
    def _full_kind_scope_requested(payload: dict[str, Any]) -> bool:
        notes = [str(item or "").strip().lower() for item in list(payload.get("notes", []) or []) if str(item).strip()]
        return "target_scope_authority:full_kind" in notes or "turn_contract_target_refs:full_kind" in notes

    @staticmethod
    def _clean_record(record: dict[str, Any]) -> dict[str, Any]:
        clean: dict[str, Any] = {}
        for key, value in dict(record or {}).items():
            clean_key = str(key or "").strip()
            if not clean_key:
                continue
            if clean_key == "disk_measurement" and isinstance(value, dict):
                clean[clean_key] = dict(value)
            elif isinstance(value, (int, float, bool)):
                clean[clean_key] = value
            else:
                clean[clean_key] = str(value)
        return clean

    @staticmethod
    def _task_intent_from_payload(payload: dict[str, Any]) -> str:
        for key in ("task_intent", "target_intent"):
            clean_value = str(payload.get(key, "") or "").strip().lower()
            if clean_value:
                return clean_value
        for note in list(payload.get("notes", []) or []):
            clean = str(note or "").strip().lower()
            if clean.startswith("target_intent:"):
                return clean.split(":", 1)[1].strip()
        command = str(payload.get("content", "") or "").strip().lower()
        if "apt list --upgradable" in command:
            return "package_update_check"
        return ""

    @classmethod
    def _result_contract_debug_line(
        cls,
        *,
        payload: dict[str, Any],
        command: str,
        records: list[dict[str, str]],
        original_count: int,
        allowed_count: int,
        blocked_count: int,
        free_disk_threshold: tuple[float, str] | None,
    ) -> str:
        state_counts = cls._state_counts(records)
        assumption = cls._result_assumption(
            payload=payload,
            command=command,
            free_disk_threshold=free_disk_threshold,
        )
        notable = cls._notable_refs(records)
        confidence = cls._result_confidence(records, allowed_count=allowed_count, blocked_count=blocked_count)
        task_intent = cls._task_intent_from_payload(payload) or "runtime_check"
        return (
            "Routing Debug: multi_target_ssh_result_contract "
            f"task_intent={cls._field_value(task_intent)} command_profile={cls._command_profile(command)} "
            f"targets={original_count} allowed={allowed_count} blocked={blocked_count} records={len(records)} "
            f"ok={state_counts.get('ok', 0)} attention={state_counts.get('attention', 0)} "
            f"error={state_counts.get('error', 0)} empty={state_counts.get('empty', 0)} "
            f"assumption={cls._field_value(assumption)} notable={cls._field_value(notable)} "
            f"confidence={confidence} source=runtime_records"
        )

    @staticmethod
    def _state_counts(records: list[dict[str, str]]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for row in records:
            state = str(row.get("state", "") or "").strip().lower() or "unknown"
            counts[state] = counts.get(state, 0) + 1
        return counts

    @classmethod
    def _result_assumption(
        cls,
        *,
        payload: dict[str, Any],
        command: str,
        free_disk_threshold: tuple[float, str] | None,
    ) -> str:
        if free_disk_threshold:
            return f"requested_free_disk_threshold:{free_disk_threshold[1]}"
        task_intent = cls._task_intent_from_payload(payload)
        command_profile = cls._command_profile(command)
        if task_intent == "package_update_check" or command_profile == "package_updates":
            return "available_updates_only"
        if command_profile == "disk_capacity":
            return "no_user_threshold_capacity_review"
        if command_profile == "host_health":
            return "runtime_snapshot_review"
        return "executed_command_output_review"

    @staticmethod
    def _notable_refs(records: list[dict[str, str]], *, limit: int = 5) -> str:
        notable_refs: list[str] = []
        for row in records:
            state = str(row.get("state", "") or "").strip().lower()
            ref = str(row.get("ref", "") or "").strip()
            if ref and state and state != "ok":
                notable_refs.append(ref)
        if not notable_refs:
            return "-"
        visible = notable_refs[: max(1, int(limit or 1))]
        suffix = f",+{len(notable_refs) - len(visible)}" if len(notable_refs) > len(visible) else ""
        return ",".join(visible) + suffix

    @staticmethod
    def _result_confidence(records: list[dict[str, str]], *, allowed_count: int, blocked_count: int) -> str:
        if blocked_count > 0:
            return "medium"
        if not records or len(records) < allowed_count:
            return "low"
        states = {str(row.get("state", "") or "").strip().lower() for row in records}
        if states <= {"ok"}:
            return "high"
        if "error" in states or "blocked" in states:
            return "medium"
        return "high"

    @staticmethod
    def _command_profile(command: str) -> str:
        clean = str(command or "").strip().lower()
        if "apt list --upgradable" in clean:
            return "package_updates"
        if "df" in clean:
            return "disk_capacity"
        if "uptime" in clean or "free " in clean or clean == "free":
            return "host_health"
        return "ssh_command"

    @staticmethod
    def _field_value(value: str) -> str:
        clean = str(value or "").strip()
        if not clean:
            return "-"
        return "_".join(clean.split())[:160]

    @staticmethod
    def _followup_affordances_for_command(command: str, payload: dict[str, Any]) -> list[str]:
        task_intent = MultiTargetSSHExecutionHandler._task_intent_from_payload(payload)
        if task_intent == "package_update_check" or "apt list --upgradable" in str(command or "").strip().lower():
            return ["rank_updates", "list_packages_by_server", "explain_update_relevance", "rerun_update_check"]
        return ["summarize_targets", "explain_result", "rerun_check"]

    def _scope_limited_summary(
        self,
        summary: str,
        *,
        language: str,
        selected_count: int,
        configured_count: int,
    ) -> str:
        if selected_count <= 0 or configured_count <= selected_count:
            return summary
        clean = str(summary or "").strip()
        replacements = (
            ("alle Server", "alle geprueften SSH-Ziele"),
            ("allen Servern", "allen geprueften SSH-Zielen"),
            ("all servers", "all checked SSH targets"),
            ("all hosts", "all checked SSH targets"),
        )
        for source, target in replacements:
            clean = re.sub(re.escape(source), target, clean, flags=re.IGNORECASE)
        if str(language or "").lower().startswith("en"):
            prefix = (
                f"Scope: checked {selected_count} of {configured_count} configured SSH targets; "
                "the result only covers the checked targets."
            )
        else:
            prefix = (
                f"Scope: Geprueft wurden {selected_count} von {configured_count} konfigurierten SSH-Zielen; "
                "die Aussage gilt nur f"
                "uer diese geprueften Ziele."
            )
        return f"{prefix} {clean}".strip()

    async def _build_summary(
        self,
        *,
        request: AgenticExecutionRequest,
        command: str,
        records: list[dict[str, str]],
        original_count: int,
        configured_count: int,
        partial_scope_count: int,
        detail_lines: list[str],
    ) -> str:
        summary_started = time.perf_counter()
        relevant_summary = " ".join(self._hooks.relevant_result_texts(records)).strip()
        if not records and not relevant_summary:
            return self._hooks.text(
                request.language,
                "multi_target_ssh_no_output",
                "No SSH target returned output.",
            )
        operator_summary = self._hooks.operator_summary(request.language, original_count, records)
        operator_ms = int((time.perf_counter() - summary_started) * 1000)
        summary = f"{operator_summary} {relevant_summary}".strip()
        if partial_scope_count:
            summary = self._scope_limited_summary(
                summary,
                language=request.language,
                selected_count=original_count,
                configured_count=partial_scope_count,
            )
        llm_started = time.perf_counter()
        llm_summary, llm_debug_line = await self._hooks.llm_operator_summary(
            str(request.resolved.get("query", "") or ""),
            command,
            records,
            summary,
            request.language,
        )
        llm_ms = int((time.perf_counter() - llm_started) * 1000)
        if llm_summary:
            summary = llm_summary
            if partial_scope_count:
                summary = self._scope_limited_summary(
                    summary,
                    language=request.language,
                    selected_count=original_count,
                    configured_count=partial_scope_count,
                )
        if llm_debug_line and self._hooks.routing_debug_enabled():
            detail_lines.append(llm_debug_line)
        if self._hooks.routing_debug_enabled():
            total_ms = int((time.perf_counter() - summary_started) * 1000)
            detail_lines.append(
                "Routing Debug: multi_target_ssh_summary_timing "
                f"records={len(records)} operator_ms={operator_ms} llm_ms={llm_ms} total_ms={total_ms}"
            )
        return summary
