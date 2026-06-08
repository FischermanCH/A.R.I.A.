from __future__ import annotations

import asyncio

from aria.core.action_plan import ActionPlan
from aria.core.agentic_execution import AgenticExecutionRequest
from aria.core.agentic_execution import AgenticExecutionResult
from aria.core.agentic_execution_learning import AgenticExecutionLearningService
from aria.core.agentic_execution_registry import AgenticExecutionRegistry
from aria.core.agentic_execution_learning import suppress_auto_learning
from aria.core.agentic_capability_execution import GenericCapabilityExecutionHandler
from aria.core.agentic_capability_execution import GenericCapabilityExecutionHooks
from aria.core.agentic_rss_execution import RSSFeedExecutionHandler
from aria.core.agentic_rss_execution import RSSFeedExecutionHooks
from aria.core.agentic_ssh_execution import MultiTargetSSHExecutionHandler
from aria.core.agentic_ssh_execution import MultiTargetSSHExecutionHooks


async def _empty_execute(_plan: ActionPlan, _language: str) -> str:
    return ""


async def _empty_llm_summary(
    _message: str,
    _command: str,
    _records: list[dict[str, str]],
    _fallback: str,
    _language: str,
) -> tuple[str, str]:
    return "", ""


def _handler() -> MultiTargetSSHExecutionHandler:
    return MultiTargetSSHExecutionHandler(
        MultiTargetSSHExecutionHooks(
            routing_debug_enabled=lambda: False,
            payload_to_action_plan=lambda payload: ActionPlan(
                capability=str(payload.get("capability", "") or ""),
                connection_kind=str(payload.get("connection_kind", "") or ""),
            ),
            format_missing_message=lambda _plan, _language: "missing",
            format_execution_error=lambda _plan, exc, _language: str(exc),
            build_capability_detail_lines=lambda _plan, _language: [],
            text=lambda _language, _key, default="", **values: str(default).format(**values),
            learning_service=AgenticExecutionLearningService(
                schedule_followup=lambda _entry, _user_id, _language, _detail_lines, _curate: None
            ),
            payload_multi_target_refs=lambda payload: list(payload.get("connection_refs", []) or []),
            preflight_refs=lambda refs, _command: (refs, [], []),
            execute_plan=_empty_execute,
            remember_action=lambda _user_id, _plan: None,
            result_state=lambda _text: "ok",
            extract_free_disk_threshold_gib=lambda _message: None,
            extract_summary_free_disk_gib=lambda _text: None,
            operator_summary=lambda _language, target_count, _records: f"Overall: {target_count} targets.",
            relevant_result_texts=lambda _records: [],
            llm_operator_summary=_empty_llm_summary,
        )
    )


def test_agentic_execution_result_keeps_pipeline_tuple_shape() -> None:
    result = AgenticExecutionResult(
        intents=["capability:ssh_command"],
        text="ok",
        detail_lines=["debug"],
        errors=["err"],
    )

    assert result.as_pipeline_tuple() == (["capability:ssh_command"], "ok", ["debug"], ["err"])


def test_multi_target_ssh_handler_only_claims_matching_multi_target_payloads() -> None:
    handler = _handler()

    assert handler.can_handle(
        AgenticExecutionRequest(
            resolved={},
            payload={"capability": "ssh_command", "connection_kind": "ssh", "connection_refs": ["a", "b"]},
            action={},
            user_id="neo",
        )
    ) is True
    assert handler.can_handle(
        AgenticExecutionRequest(
            resolved={},
            payload={"capability": "feed_read", "connection_kind": "rss", "connection_refs": ["a", "b"]},
            action={},
            user_id="neo",
        )
    ) is False


def test_multi_target_ssh_handler_executes_allowed_targets_concurrently() -> None:
    active = 0
    max_active = 0

    async def execute_plan(_plan: ActionPlan, _language: str) -> str:
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0)
        active -= 1
        return "ok"

    handler = MultiTargetSSHExecutionHandler(
        MultiTargetSSHExecutionHooks(
            routing_debug_enabled=lambda: False,
            payload_to_action_plan=lambda payload: ActionPlan(
                capability=str(payload.get("capability", "") or ""),
                connection_kind=str(payload.get("connection_kind", "") or ""),
            ),
            format_missing_message=lambda _plan, _language: "missing",
            format_execution_error=lambda _plan, exc, _language: str(exc),
            build_capability_detail_lines=lambda _plan, _language: [],
            text=lambda _language, _key, default="", **values: str(default).format(**values),
            learning_service=AgenticExecutionLearningService(
                schedule_followup=lambda _entry, _user_id, _language, _detail_lines, _curate: None
            ),
            payload_multi_target_refs=lambda payload: list(payload.get("connection_refs", []) or []),
            preflight_refs=lambda refs, _command: (refs, [], []),
            execute_plan=execute_plan,
            remember_action=lambda _user_id, _plan: None,
            result_state=lambda _text: "ok",
            extract_free_disk_threshold_gib=lambda _message: None,
            extract_summary_free_disk_gib=lambda _text: None,
            operator_summary=lambda _language, target_count, _records: f"Overall: {target_count} targets.",
            relevant_result_texts=lambda _records: [],
            llm_operator_summary=_empty_llm_summary,
        ),
        max_concurrency=3,
    )

    result = asyncio.run(
        handler.execute(
            AgenticExecutionRequest(
                resolved={"query": "check all"},
                payload={
                    "capability": "ssh_command",
                    "connection_kind": "ssh",
                    "connection_refs": ["a", "b", "c"],
                    "content": "uptime",
                },
                action={},
                user_id="neo",
                language="de",
            )
        )
    )

    assert result.errors == []
    assert max_active > 1


def _rss_handler() -> RSSFeedExecutionHandler:
    return RSSFeedExecutionHandler(
        RSSFeedExecutionHooks(
            routing_debug_enabled=lambda: False,
            payload_to_action_plan=lambda payload: ActionPlan(
                capability=str(payload.get("capability", "") or ""),
                connection_kind=str(payload.get("connection_kind", "") or ""),
                connection_ref=str(payload.get("connection_ref", "") or ""),
                notes=list(payload.get("notes", []) or []),
            ),
            format_missing_message=lambda _plan, _language: "missing",
            format_execution_error=lambda _plan, exc, _language: str(exc),
            build_capability_detail_lines=lambda _plan, _language: [],
            text=lambda _language, _key, default="", **values: str(default).format(**values),
            learning_service=AgenticExecutionLearningService(
                schedule_followup=lambda _entry, _user_id, _language, _detail_lines, _curate: None
            ),
            execute_plan=_empty_execute,
            remember_action=lambda _user_id, _plan: None,
            rss_group_bundle_for_query=_empty_rss_group_bundle_for_query,
            rss_group_bundle_from_candidate_aliases=lambda _query, _selected_ref, _rows: None,
            build_rss_group_bundle_note=lambda group, refs: f"group:{group}:{','.join(refs)}",
            rss_digest_options_note_for_query=_empty_rss_digest_options_note_for_query,
        )
    )


async def _empty_rss_group_bundle_for_query(_query: str, _selected_ref: str) -> tuple[str, list[str]] | None:
    return None


async def _empty_rss_digest_options_note_for_query(_query: str, _language: str) -> str:
    return ""


def test_rss_feed_handler_only_claims_rss_feed_payloads() -> None:
    handler = _rss_handler()

    assert handler.can_handle(
        AgenticExecutionRequest(
            resolved={},
            payload={"capability": "feed_read", "connection_kind": "rss", "connection_ref": "security"},
            action={},
            user_id="neo",
        )
    ) is True
    assert handler.can_handle(
        AgenticExecutionRequest(
            resolved={},
            payload={"capability": "ssh_command", "connection_kind": "ssh"},
            action={},
            user_id="neo",
        )
    ) is False


def test_agentic_execution_registry_runs_first_matching_handler() -> None:
    class _NoopHandler:
        def can_handle(self, _request: AgenticExecutionRequest) -> bool:
            return False

        async def execute(self, _request: AgenticExecutionRequest) -> AgenticExecutionResult:
            raise AssertionError("non-matching handler must not execute")

    class _MatchHandler:
        def can_handle(self, _request: AgenticExecutionRequest) -> bool:
            return True

        async def execute(self, _request: AgenticExecutionRequest) -> AgenticExecutionResult:
            return AgenticExecutionResult(intents=["chat"], text="handled")

    async def _run() -> AgenticExecutionResult | None:
        return await AgenticExecutionRegistry([_NoopHandler(), _MatchHandler()]).execute_first(
            AgenticExecutionRequest(resolved={}, payload={}, action={}, user_id="neo")
        )

    import asyncio

    result = asyncio.run(_run())
    assert result is not None
    assert result.text == "handled"


def _generic_handler(
    *,
    executed: list[ActionPlan] | None = None,
    remembered: list[tuple[str, ActionPlan]] | None = None,
    scheduled: list[object] | None = None,
    content_access_result: tuple[str, list[str], list[str]] | None = None,
) -> GenericCapabilityExecutionHandler:
    async def _execute_plan(plan: ActionPlan, _language: str) -> str:
        if executed is not None:
            executed.append(plan)
        return "executed"

    async def _execute_content_access(
        _plan: ActionPlan,
        _user_id: str,
        _language: str,
    ) -> tuple[str, list[str], list[str]] | None:
        return content_access_result

    return GenericCapabilityExecutionHandler(
        GenericCapabilityExecutionHooks(
            routing_debug_enabled=lambda: True,
            payload_to_action_plan=lambda payload: ActionPlan(
                capability=str(payload.get("capability", "") or ""),
                connection_kind=str(payload.get("connection_kind", "") or ""),
                connection_ref=str(payload.get("connection_ref", "") or ""),
                path=str(payload.get("path", "") or ""),
                content=str(payload.get("content", "") or ""),
            ),
            format_missing_message=lambda _plan, _language: "missing",
            format_execution_error=lambda _plan, exc, _language: str(exc),
            build_capability_detail_lines=lambda plan, _language: [f"detail:{plan.connection_ref}"],
            text=lambda _language, _key, default="", **values: str(default).format(**values),
            learning_service=AgenticExecutionLearningService(
                schedule_followup=lambda entry, *_args: scheduled.append(entry) if scheduled is not None else None
            ),
            execute_plan=_execute_plan,
            remember_action=lambda user_id, plan: remembered.append((user_id, plan)) if remembered is not None else None,
            execute_content_access=_execute_content_access,
            capability_execution_error_code=lambda plan, exc: f"capability_{plan.capability}_error:{type(exc).__name__}",
        )
    )


def test_generic_capability_handler_executes_and_records_context() -> None:
    import asyncio

    executed: list[ActionPlan] = []
    remembered: list[tuple[str, ActionPlan]] = []
    scheduled: list[object] = []
    handler = _generic_handler(executed=executed, remembered=remembered, scheduled=scheduled)

    with suppress_auto_learning():
        result = asyncio.run(
            handler.execute(
                AgenticExecutionRequest(
                    resolved={"query": "send status"},
                    payload={
                        "capability": "webhook_send",
                        "connection_kind": "webhook",
                        "connection_ref": "alerts",
                        "content": "online",
                    },
                    action={"candidate_kind": "capability"},
                    user_id="neo",
                )
            )
        )

    assert result.intents == ["capability:webhook_send"]
    assert result.text == "executed"
    assert result.errors == []
    assert "agentic_runtime" in result.detail_lines[0]
    assert result.detail_lines[-1] == "detail:alerts"
    assert executed and executed[0].connection_ref == "alerts"
    assert remembered and remembered[0][0] == "neo"
    assert scheduled == []


def test_generic_capability_handler_uses_content_access_before_runtime() -> None:
    import asyncio

    executed: list[ActionPlan] = []
    remembered: list[tuple[str, ActionPlan]] = []
    scheduled: list[object] = []
    handler = _generic_handler(
        executed=executed,
        remembered=remembered,
        scheduled=scheduled,
        content_access_result=("content summary", ["content debug"], []),
    )

    result = asyncio.run(
        handler.execute(
            AgenticExecutionRequest(
                resolved={"query": "read latest mail"},
                payload={"capability": "mail_read", "connection_kind": "imap", "connection_ref": "inbox"},
                action={"candidate_kind": "capability"},
                user_id="neo",
            )
        )
    )

    assert result.intents == ["capability:mail_read"]
    assert result.text == "content summary"
    assert result.detail_lines == ["content debug"]
    assert result.errors == []
    assert executed == []
    assert remembered == []
    assert scheduled == []


def test_agentic_execution_learning_service_respects_suppression() -> None:
    scheduled: list[object] = []
    service = AgenticExecutionLearningService(
        schedule_followup=lambda entry, *_args: scheduled.append(entry)
    )

    with suppress_auto_learning():
        service.record_capability_success(
            action={},
            plan=ActionPlan(capability="calendar_read", connection_kind="google_calendar"),
            result_text="ok",
            user_message="was steht morgen im kalender",
            user_id="neo",
            language="de",
            detail_lines=[],
        )

    assert scheduled == []
