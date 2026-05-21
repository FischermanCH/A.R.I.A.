from __future__ import annotations

from aria.core.action_plan import ActionPlan
from aria.core.agentic_execution import AgenticExecutionRequest
from aria.core.agentic_execution import AgenticExecutionResult
from aria.core.agentic_execution_learning import AgenticExecutionLearningService
from aria.core.agentic_execution_registry import AgenticExecutionRegistry
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
