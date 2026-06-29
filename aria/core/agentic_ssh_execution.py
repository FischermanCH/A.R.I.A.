from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from aria.core.action_plan import ActionPlan
from aria.core.agentic_execution import AgenticExecutionHooks
from aria.core.agentic_execution import AgenticExecutionRequest
from aria.core.agentic_execution import AgenticExecutionResult
from aria.core.agentic_runtime_debug import runtime_debug_line_for_plan
from aria.core.capability_catalog import normalize_capability
from aria.core.connection_catalog import normalize_connection_kind


@dataclass(slots=True)
class MultiTargetSSHExecutionHooks(AgenticExecutionHooks):
    payload_multi_target_refs: Callable[[dict[str, Any]], list[str]]
    preflight_refs: Callable[[list[str], str], tuple[list[str], list[dict[str, str]], list[str]]]
    execute_plan: Callable[[ActionPlan, str], Awaitable[str]]
    remember_action: Callable[[str, ActionPlan], None]
    remember_multi_target_action: Callable[[str, dict[str, Any], list[str], str, str], None]
    result_state: Callable[[str], str]
    extract_free_disk_threshold_gib: Callable[[str], tuple[float, str] | None]
    extract_summary_free_disk_gib: Callable[[str], tuple[float, str] | None]
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
        query = str(request.resolved.get("query", "") or "")
        free_disk_threshold = self._hooks.extract_free_disk_threshold_gib(query)
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
                state = self._hooks.result_state(clean_text)
                threshold_text = ""
                free_disk = self._hooks.extract_summary_free_disk_gib(clean_text) if free_disk_threshold else None
                if free_disk_threshold and free_disk:
                    threshold_gib, threshold_label = free_disk_threshold
                    free_gib, free_label = free_disk
                    if free_gib < threshold_gib:
                        state = "attention"
                        threshold_text = self._hooks.text(
                            request.language,
                            "multi_target_ssh_disk_threshold_below",
                            "`{ref}` below requested free-disk threshold {threshold}: {free} free.",
                            ref=ref,
                            threshold=threshold_label,
                            free=free_label,
                        )
                    elif state == "ok":
                        threshold_text = self._hooks.text(
                            request.language,
                            "multi_target_ssh_disk_threshold_ok",
                            "`{ref}` has at least {threshold} free ({free}).",
                            ref=ref,
                            threshold=threshold_label,
                            free=free_label,
                        )
                record = {
                    "ref": ref,
                    "state": state,
                    "text": threshold_text or clean_text,
                    "raw_text": clean_text,
                }

            self._hooks.remember_action(request.user_id, plan)
            self._hooks.learning_service.record_capability_success(
                action=request.action,
                plan=plan,
                result_text=clean_text,
                user_message=query,
                user_id=request.user_id,
                language=request.language,
                detail_lines=target_detail_lines,
                curate=False,
            )
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
                    result_records.append({str(key): str(value) for key, value in record.items()})
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
            free_disk_threshold=free_disk_threshold,
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
    def _task_intent_from_payload(payload: dict[str, Any]) -> str:
        for note in list(payload.get("notes", []) or []):
            clean = str(note or "").strip().lower()
            if clean.startswith("target_intent:"):
                return clean.split(":", 1)[1].strip()
        command = str(payload.get("content", "") or "").strip().lower()
        if "apt list --upgradable" in command:
            return "package_update_check"
        return ""

    @staticmethod
    def _followup_affordances_for_command(command: str, payload: dict[str, Any]) -> list[str]:
        task_intent = MultiTargetSSHExecutionHandler._task_intent_from_payload(payload)
        if task_intent == "package_update_check" or "apt list --upgradable" in str(command or "").strip().lower():
            return ["rank_updates", "list_packages_by_server", "explain_update_relevance", "rerun_update_check"]
        return ["summarize_targets", "explain_result", "rerun_check"]

    async def _build_summary(
        self,
        *,
        request: AgenticExecutionRequest,
        command: str,
        records: list[dict[str, str]],
        original_count: int,
        free_disk_threshold: tuple[float, str] | None,
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
        threshold_records = [row for row in records if str(row.get("raw_text", "") or "").strip()] if free_disk_threshold else []
        if free_disk_threshold and threshold_records:
            threshold_gib, threshold_label = free_disk_threshold
            threshold_ok = 0
            threshold_below = 0
            for row in threshold_records:
                parsed_free = self._hooks.extract_summary_free_disk_gib(str(row.get("raw_text", "") or ""))
                if not parsed_free:
                    continue
                if parsed_free[0] >= threshold_gib:
                    threshold_ok += 1
                else:
                    threshold_below += 1
            if threshold_below <= 0:
                operator_summary = self._hooks.text(
                    request.language,
                    "multi_target_ssh_disk_threshold_all_ok",
                    "Overall: {ok_count}/{count} SSH targets have at least {threshold} free. No action required.",
                    ok_count=threshold_ok,
                    count=original_count,
                    threshold=threshold_label,
                )
            else:
                operator_summary = self._hooks.text(
                    request.language,
                    "multi_target_ssh_disk_threshold_mixed",
                    "Overall: {ok_count}/{count} SSH targets have at least {threshold} free; {below_count} are below the requested threshold.",
                    ok_count=threshold_ok,
                    count=original_count,
                    below_count=threshold_below,
                    threshold=threshold_label,
                )
        else:
            operator_summary = self._hooks.operator_summary(request.language, original_count, records)
        operator_ms = int((time.perf_counter() - summary_started) * 1000)
        summary = f"{operator_summary} {relevant_summary}".strip()
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
        if llm_debug_line and self._hooks.routing_debug_enabled():
            detail_lines.append(llm_debug_line)
        if self._hooks.routing_debug_enabled():
            total_ms = int((time.perf_counter() - summary_started) * 1000)
            detail_lines.append(
                "Routing Debug: multi_target_ssh_summary_timing "
                f"records={len(records)} operator_ms={operator_ms} llm_ms={llm_ms} total_ms={total_ms}"
            )
        return summary
