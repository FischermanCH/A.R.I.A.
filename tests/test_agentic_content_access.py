from __future__ import annotations

import asyncio

from aria.core.action_plan import ActionPlan
from aria.core.agentic_content_access import READ_SEARCH_PLANNER_ROLES
from aria.core.agentic_content_access import AgenticContentAccessResult
from aria.core.agentic_content_access import AgenticContentAccessRequest
from aria.core.agentic_content_access import content_access_request_from_action_plan
from aria.core.agentic_content_access_registry import AgenticContentAccessRegistry
from aria.core.config import Settings
from aria.core.pipeline import Pipeline


def test_content_access_request_maps_mail_search_from_contract() -> None:
    plan = ActionPlan(
        capability="mail_search",
        connection_kind="imap",
        connection_ref="ops-inbox",
        content="invoice from acme",
    )

    request = content_access_request_from_action_plan(plan, user_id="u1", language="en", limit=5)

    assert request == AgenticContentAccessRequest(
        capability="mail_search",
        connection_kind="imap",
        connection_ref="ops-inbox",
        planner_role="search",
        query="invoice from acme",
        selector="",
        limit=5,
        user_id="u1",
        language="en",
        sensitive_content=True,
    )


def test_content_access_request_rejects_send_side_effects() -> None:
    plan = ActionPlan(
        capability="email_send",
        connection_kind="email",
        connection_ref="smtp-main",
        content="hello",
    )

    assert content_access_request_from_action_plan(plan) is None


def test_content_access_request_requires_target_when_contract_requires_it() -> None:
    plan = ActionPlan(
        capability="file_read",
        connection_kind="smb",
        connection_ref="",
        path="/secret.txt",
    )

    assert content_access_request_from_action_plan(plan) is None


def test_content_access_roles_are_read_search_or_list_only() -> None:
    assert READ_SEARCH_PLANNER_ROLES == {"list", "read", "search"}


class _FakeContentHandler:
    def __init__(self, accepted_capability: str) -> None:
        self.accepted_capability = accepted_capability

    def can_handle(self, request: AgenticContentAccessRequest) -> bool:
        return request.capability == self.accepted_capability

    async def access(self, request: AgenticContentAccessRequest) -> AgenticContentAccessResult:
        return AgenticContentAccessResult(summary=f"handled:{request.capability}", sensitive_content=request.sensitive_content)


def test_content_access_registry_uses_first_matching_handler() -> None:
    registry = AgenticContentAccessRegistry(
        handlers=[
            _FakeContentHandler("file_read"),
            _FakeContentHandler("mail_search"),
        ]
    )
    request = AgenticContentAccessRequest(
        capability="mail_search",
        connection_kind="imap",
        connection_ref="ops-inbox",
        planner_role="search",
        sensitive_content=True,
    )

    result = asyncio.run(registry.access_first(request))

    assert result == AgenticContentAccessResult(summary="handled:mail_search", sensitive_content=True)


def test_pipeline_content_access_hook_uses_registered_handler_for_mail_search() -> None:
    pipeline = Pipeline(
        settings=Settings.model_validate({"llm": {"model": "fake"}, "memory": {"enabled": False}, "token_tracking": {"enabled": False}}),
        prompt_loader=None,  # type: ignore[arg-type]
        llm_client=None,
    )
    pipeline._content_access_registry = AgenticContentAccessRegistry([_FakeContentHandler("mail_search")])
    plan = ActionPlan(
        capability="mail_search",
        connection_kind="imap",
        connection_ref="ops-inbox",
        content="backup failed",
    )

    result = asyncio.run(pipeline._execute_content_access_if_available(plan, user_id="u1", language="de"))

    assert result == ("handled:mail_search", [], [])


def test_pipeline_content_access_hook_falls_back_without_handler() -> None:
    pipeline = Pipeline(
        settings=Settings.model_validate({"llm": {"model": "fake"}, "memory": {"enabled": False}, "token_tracking": {"enabled": False}}),
        prompt_loader=None,  # type: ignore[arg-type]
        llm_client=None,
    )
    plan = ActionPlan(
        capability="mail_search",
        connection_kind="imap",
        connection_ref="ops-inbox",
        content="backup failed",
    )

    assert asyncio.run(pipeline._execute_content_access_if_available(plan, user_id="u1", language="de")) is None
