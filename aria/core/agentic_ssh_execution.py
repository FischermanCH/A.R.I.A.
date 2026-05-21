from __future__ import annotations

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
    result_state: Callable[[str], str]
    extract_free_disk_threshold_gib: Callable[[str], tuple[float, str] | None]
    extract_summary_free_disk_gib: Callable[[str], tuple[float, str] | None]
    operator_summary: Callable[[str, int, list[dict[str, str]]], str]
    relevant_result_texts: Callable[[list[dict[str, str]]], list[str]]
    llm_operator_summary: Callable[[str, str, list[dict[str, str]], str, str], Awaitable[tuple[str, str]]]


class MultiTargetSSHExecutionHandler:
    def __init__(self, hooks: MultiTargetSSHExecutionHooks) -> None:
        self._hooks = hooks

    def can_handle(self, request: AgenticExecutionRequest) -> bool:
        payload = dict(request.payload or {})
        return (
            normalize_capability(str(payload.get("capability", "") or "")) == "ssh_command"
            and normalize_connection_kind(str(payload.get("connection_kind", "") or "")) == "ssh"
            and bool(self._hooks.payload_multi_target_refs(payload))
        )

    async def execute(self, request: AgenticExecutionRequest) -> AgenticExecutionResult:
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
        allowed_refs, blocked_refs, preflight_detail_lines = self._hooks.preflight_refs(refs, command)
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

        for ref in allowed_refs:
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
                detail_lines.append(runtime_debug_line_for_plan(plan))
            detail_lines.extend(self._hooks.build_capability_detail_lines(plan, request.language))
            try:
                result_text = await self._hooks.execute_plan(plan, request.language)
            except Exception as exc:
                error_text = self._hooks.format_execution_error(plan, exc, request.language)
                errors.append(f"capability_ssh_command_error:{ref}:{type(exc).__name__}")
                result_records.append({"ref": ref, "state": "error", "text": error_text})
                continue

            success_count += 1
            clean_text = str(result_text or "").strip()
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
                result_records.append(
                    {
                        "ref": ref,
                        "state": state,
                        "text": threshold_text or clean_text,
                        "raw_text": clean_text,
                    }
                )

            self._hooks.remember_action(request.user_id, plan)
            self._hooks.learning_service.record_capability_success(
                action=request.action,
                plan=plan,
                result_text=clean_text,
                user_message=query,
                user_id=request.user_id,
                language=request.language,
                detail_lines=detail_lines,
                curate=False,
            )

        summary = await self._build_summary(
            request=request,
            command=command,
            records=result_records,
            original_count=original_count,
            free_disk_threshold=free_disk_threshold,
            detail_lines=detail_lines,
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
        return AgenticExecutionResult(intents=intents, text=text, detail_lines=detail_lines, errors=errors)

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
        summary = f"{operator_summary} {relevant_summary}".strip()
        llm_summary, llm_debug_line = await self._hooks.llm_operator_summary(
            str(request.resolved.get("query", "") or ""),
            command,
            records,
            summary,
            request.language,
        )
        if llm_summary:
            summary = llm_summary
        if llm_debug_line and self._hooks.routing_debug_enabled():
            detail_lines.append(llm_debug_line)
        return summary
