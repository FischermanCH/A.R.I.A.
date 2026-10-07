from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from aria.modules import MODULE_MANIFESTS
from aria.modules.configuration_foundations.config import LLMConfig, WebLLMConfig
from aria.modules.native_agent.handler import run_native_agent_turn
from aria.modules.native_agent.tool_registry import assemble_native_tools, select_relevant_native_tools
from aria.modules.native_web_llm.contracts import NativeWebCitation, NativeWebResult


def _response(
    *, content: str = "", tool_name: str = "", arguments: dict | None = None,
    tool_calls: list[SimpleNamespace] | None = None,
):
    calls = []
    finish = "stop"
    if tool_name:
        calls = [SimpleNamespace(id=f"call-{tool_name}", function=SimpleNamespace(
            name=tool_name, arguments=json.dumps(arguments or {}),
        ))]
        finish = "tool_use"
    elif tool_calls:
        calls = tool_calls
        finish = "tool_use"
    return SimpleNamespace(choices=[SimpleNamespace(
        message=SimpleNamespace(content=content, tool_calls=calls), finish_reason=finish,
    )])


class _WebGateway:
    def __init__(self) -> None:
        self.calls = []

    async def answer(self, request, **kwargs):  # noqa: ANN001
        self.calls.append((request, kwargs))
        return NativeWebResult(
            answer="Current release is 2.0.",
            citations=(NativeWebCitation(
                url="https://vendor.example/releases/2", title="Release 2", cited_text="Version 2.0",
                source="fixture.native_web",
            ),),
            model="fixture-web", provider_shape="fixture", native_search_uses=1,
            usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            duration_ms=12, provider_requests=1, main_llm_requests=0, retries=0,
            diagnostics={"request_input": "current release", "model": "fixture-web", "web_uses": 1},
        )


class _EvidenceStore:
    def __init__(self) -> None:
        self.lookups = []
        self.updates = []

    async def lookup(self, query):  # noqa: ANN001
        self.lookups.append(query)
        return ()

    def schedule_update(self, query, result):  # noqa: ANN001
        self.updates.append((query, result))
        return True


def _website_rows(*, foreign: bool = False):
    return ({
        "source_authority": "website_runtime:configured_profiles",
        "scope_user_id": "u2" if foreign else "u1",
        "ref": "docs", "title": "Docs", "url": "https://docs.example/",
        "group_name": "Product", "description": "Product documentation", "tags": ["docs"],
        "snapshot_text": "Stored release snapshot", "api_key": "TOP-SECRET",
    },)


def _owner(*, websites=None, web_enabled: bool = True):  # noqa: ANN001
    gateway = _WebGateway()
    evidence = _EvidenceStore()

    async def website_loader(_user_id):
        return _website_rows() if websites is None else websites

    settings = SimpleNamespace(
        web_llm=WebLLMConfig(
            model="fixture-web", enabled=web_enabled, capability_verified_at="2026-09-20T00:00:00Z",
            max_search_uses=2, max_output_tokens=700, search_context_size="medium",
        ),
    )
    return SimpleNamespace(
        settings=settings, memory_skill=object(), web_llm_gateway=gateway,
        web_evidence_store=evidence, _native_agent_website_loader=website_loader,
        _test_gateway=gateway, _test_evidence=evidence,
    )


def _tools(owner):  # noqa: ANN001
    return assemble_native_tools(
        MODULE_MANIFESTS, runtime_owner=owner,
        enabled_rollout_flags={"native_agent_memory_enabled", "native_agent_connections_enabled"},
    )


@pytest.mark.parametrize(("tool_name", "arguments", "needle"), (
    ("web_search_fetch", {"query": "current release"}, "https://vendor.example/releases/2"),
    ("website_list", {}, "docs.example"),
    ("website_read", {"website_ref": "docs"}, "Stored release snapshot"),
))
def test_p2_r4_native_tool_roundtrip_is_evidence_bound_and_allowlisted(
    tmp_path, tool_name: str, arguments: dict, needle: str,
) -> None:
    owner = _owner()
    calls = []

    async def completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return _response(tool_name=tool_name, arguments=arguments)
        result = kwargs["messages"][-1]["content"]
        assert needle in result
        assert "TOP-SECRET" not in result
        return _response(content=f"Evidence: {needle}")

    outcome = asyncio.run(run_native_agent_turn(
        message="read source", user_id="u1", turn_id=tool_name,
        llm_config=LLMConfig(model="fake"), tool_bindings=_tools(owner),
        completion=completion, trace_root=tmp_path,
    ))
    assert outcome.kind == "final_answer"
    assert outcome.used_tool_names == (tool_name,)


def test_web_search_fetch_reuses_gateway_budgets_metering_context_and_evidence_store() -> None:
    owner = _owner()
    binding = {tool.contract.name: tool for tool in _tools(owner)}["web_search_fetch"]
    result = asyncio.run(binding.handler(SimpleNamespace(user_id="u1"), {"query": "current release"}))

    assert "https://vendor.example/releases/2" in result.content
    assert len(owner._test_gateway.calls) == 1
    request, kwargs = owner._test_gateway.calls[0]
    assert request.max_search_uses == 2
    assert request.max_output_tokens == 700
    assert request.search_context_size == "high"
    assert kwargs["user_id"] == "u1"
    assert kwargs["operation"] == "web_search_fetch"
    assert owner._test_evidence.lookups == ["current release"]
    assert len(owner._test_evidence.updates) == 1
    assert owner._native_web_debug_details == {
        "request_input": "current release", "model": "fixture-web", "web_uses": 1,
    }


def test_web_search_fetch_defaults_missing_context_size_to_high() -> None:
    owner = _owner()
    owner.settings.web_llm = SimpleNamespace(
        model="fixture-web", enabled=True, capability_verified_at="2026-09-20T00:00:00Z",
        max_search_uses=2, max_output_tokens=700, allowed_domains=(), required_url_prefixes=(),
    )
    binding = {tool.contract.name: tool for tool in _tools(owner)}["web_search_fetch"]

    asyncio.run(binding.handler(SimpleNamespace(user_id="u1"), {"query": "latest release"}))

    request, _kwargs = owner._test_gateway.calls[0]
    assert request.search_context_size == "high"


def test_web_search_fetch_forces_explicit_low_context_size_to_high() -> None:
    owner = _owner()
    owner.settings.web_llm.search_context_size = "low"
    binding = {tool.contract.name: tool for tool in _tools(owner)}["web_search_fetch"]

    asyncio.run(binding.handler(SimpleNamespace(user_id="u1"), {"query": "latest release"}))

    request, _kwargs = owner._test_gateway.calls[0]
    assert request.search_context_size == "high"


def test_sole_terminal_web_tool_returns_gateway_answer_without_recomposition(tmp_path) -> None:  # noqa: ANN001
    owner = _owner()
    calls: list[dict] = []

    async def completion(**kwargs):
        calls.append(kwargs)
        return _response(tool_name="web_search_fetch", arguments={"query": "current release"})

    outcome = asyncio.run(run_native_agent_turn(
        message="Search the Web for the current release", user_id="u1", turn_id="terminal-web",
        llm_config=LLMConfig(model="fake"), tool_bindings=_tools(owner),
        completion=completion, trace_root=tmp_path,
    ))

    assert outcome.kind == "final_answer"
    assert outcome.provider_calls == 1
    assert outcome.used_tool_names == ("web_search_fetch",)
    assert outcome.message == (
        "Current release is 2.0.\n\nSources:\n"
        "- [Release 2](https://vendor.example/releases/2)"
    )
    assert len(calls) == 1
    trace = [json.loads(line) for line in (tmp_path / "terminal-web.jsonl").read_text().splitlines()]
    assert trace[-1]["final_outcome"] == "terminal_final_answer"
    assert "https://vendor.example/releases/2" in trace[-1]["tool_result"]


def test_terminal_web_tool_with_another_tool_keeps_normal_composition(tmp_path) -> None:  # noqa: ANN001
    owner = _owner()
    calls: list[dict] = []
    combined_calls = [
        SimpleNamespace(id="call-web", function=SimpleNamespace(
            name="web_search_fetch", arguments=json.dumps({"query": "current release"}),
        )),
        SimpleNamespace(id="call-sites", function=SimpleNamespace(
            name="website_list", arguments="{}",
        )),
    ]

    async def completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return _response(tool_calls=combined_calls)
        assert "https://vendor.example/releases/2" in kwargs["messages"][-2]["content"]
        assert "docs.example" in kwargs["messages"][-1]["content"]
        return _response(content="Composed Web and configured-site answer.")

    outcome = asyncio.run(run_native_agent_turn(
        message="Compare the Web release with my configured sites", user_id="u1", turn_id="combined-web",
        llm_config=LLMConfig(model="fake"), tool_bindings=_tools(owner),
        completion=completion, trace_root=tmp_path,
    ))

    assert outcome.kind == "final_answer"
    assert outcome.message == "Composed Web and configured-site answer."
    assert outcome.provider_calls == 2
    assert outcome.used_tool_names == ("web_search_fetch", "website_list")
    assert len(calls) == 2


def test_terminal_web_tool_after_prior_observation_keeps_normal_composition(tmp_path) -> None:  # noqa: ANN001
    owner = _owner()
    calls: list[dict] = []

    async def completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return _response(tool_name="website_list")
        if len(calls) == 2:
            return _response(tool_name="web_search_fetch", arguments={"query": "current release"})
        assert "https://vendor.example/releases/2" in kwargs["messages"][-1]["content"]
        return _response(content="Composed answer after both observations.")

    outcome = asyncio.run(run_native_agent_turn(
        message="Compare configured and current public release sources", user_id="u1",
        turn_id="observed-then-web", llm_config=LLMConfig(model="fake"),
        tool_bindings=_tools(owner), completion=completion, trace_root=tmp_path,
    ))

    assert outcome.kind == "final_answer"
    assert outcome.message == "Composed answer after both observations."
    assert outcome.provider_calls == 3
    assert outcome.used_tool_names == ("website_list", "web_search_fetch")
    assert len(calls) == 3


def test_web_search_fetch_fails_closed_without_configured_verified_gateway() -> None:
    owner = _owner(web_enabled=False)
    binding = {tool.contract.name: tool for tool in _tools(owner)}["web_search_fetch"]
    with pytest.raises(RuntimeError, match="native_agent_web_gateway_unavailable"):
        asyncio.run(binding.handler(SimpleNamespace(user_id="u1"), {"query": "current release"}))
    assert owner._test_gateway.calls == []


def test_website_tools_reject_foreign_scope_and_secret_bearing_url() -> None:
    foreign = _owner(websites=_website_rows(foreign=True))
    binding = {tool.contract.name: tool for tool in _tools(foreign)}["website_list"]
    with pytest.raises(ValueError, match="native_agent_website_scope_mismatch"):
        asyncio.run(binding.handler(SimpleNamespace(user_id="u1"), {}))

    unsafe = ({**_website_rows()[0], "url": "https://user:password@docs.example/private"},)
    owner = _owner(websites=unsafe)
    binding = {tool.contract.name: tool for tool in _tools(owner)}["website_read"]
    result = asyncio.run(binding.handler(SimpleNamespace(user_id="u1"), {"website_ref": "docs"}))
    assert "password" not in result.content
    assert '"url": ""' in result.content


def test_website_tools_report_honest_empty_and_exact_not_found() -> None:
    bindings = {tool.contract.name: tool for tool in _tools(_owner(websites=()))}
    inventory = asyncio.run(bindings["website_list"].handler(SimpleNamespace(user_id="u1"), {}))
    missing = asyncio.run(bindings["website_read"].handler(
        SimpleNamespace(user_id="u1"), {"website_ref": "missing"},
    ))
    assert '"status": "no_websites"' in inventory.content
    assert '"status": "website_not_found"' in missing.content


@pytest.mark.parametrize(("tool_name", "arguments"), (
    ("web_search_fetch", {"query": "x", "api_key": "secret"}),
    ("website_list", {"user_id": "u2"}),
    ("website_read", {"website_ref": "docs", "fetch": True}),
))
def test_p2_r4_tools_reject_unknown_or_model_controlled_arguments(tool_name: str, arguments: dict) -> None:
    binding = {tool.contract.name: tool for tool in _tools(_owner())}[tool_name]
    with pytest.raises(ValueError, match="arguments_invalid"):
        asyncio.run(binding.handler(SimpleNamespace(user_id="u1"), arguments))


def test_registry_has_twenty_read_only_tools_and_offers_all_without_selector() -> None:
    tools = _tools(_owner())
    assert len(tools) == 20
    assert {tool.contract.name for tool in tools} >= {"web_search_fetch", "website_list", "website_read"}
    assert all(tool.contract.effect == "read_only" for tool in tools)
    assert all(not tool.contract.confirmation_required for tool in tools)
    assert [tool.contract.name for tool in tools if tool.contract.terminal] == ["web_search_fetch"]

    async def selector(*_args):
        raise AssertionError("selector must not run at twenty tools")

    assert asyncio.run(select_relevant_native_tools("question", tools, selector=selector)) == tools
