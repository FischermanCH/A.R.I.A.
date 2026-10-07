from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from aria.modules import MODULE_MANIFESTS
from aria.modules.configuration_foundations.config import (
    ConnectionsConfig,
    GoogleCalendarConnectionConfig,
    LLMConfig,
    RSSConnectionConfig,
    SFTPConnectionConfig,
)
from aria.modules.native_agent.handler import MAX_TOOL_RESULT_CHARS, run_native_agent_turn
from aria.modules.native_agent.tool_registry import assemble_native_tools, select_relevant_native_tools


AUTHORITIES = {
    "rss": "rss:configured_profile", "google_calendar": "google_calendar:configured_profile",
    "sftp": "sftp:configured_profile", "smb": "smb:configured_profile", "imap": "imap:configured_profile",
}


def _owner(*, content: str = "source content", scope: str = "u1", authority: str = ""):
    calls = []

    async def loader(user_id, kind, ref, operation, parameters):  # noqa: ANN001
        calls.append((user_id, kind, ref, operation, parameters))
        return {
            "source_authority": authority or AUTHORITIES[kind], "scope_user_id": scope,
            "content": content, "password": "TOP-SECRET", "token": "TOKEN-SECRET",
        }

    return SimpleNamespace(
        settings=SimpleNamespace(), memory_skill=object(),
        _native_agent_connection_read_loader=loader, _test_calls=calls,
    )


def _tools(owner):  # noqa: ANN001
    return assemble_native_tools(
        MODULE_MANIFESTS, runtime_owner=owner,
        enabled_rollout_flags={"native_agent_memory_enabled", "native_agent_connections_enabled"},
    )


CASES = (
    ("rss_feed_read", {"connection_ref": "news", "requested_count": 5}, "rss", "read"),
    ("calendar_read", {"connection_ref": "work", "range_hint": "today"}, "google_calendar", "read"),
    ("file_list", {"connection_kind": "sftp", "connection_ref": "files", "path": "/docs"}, "sftp", "list"),
    ("file_read", {"connection_kind": "smb", "connection_ref": "share", "path": "/a.txt"}, "smb", "read"),
    ("mail_read", {"connection_ref": "inbox"}, "imap", "read"),
    ("mail_search", {"connection_ref": "inbox", "query": "invoice"}, "imap", "search"),
)


@pytest.mark.parametrize(("name", "arguments", "kind", "operation"), CASES)
def test_p2_r5_tools_are_read_only_scoped_allowlisted_and_exact(name, arguments, kind, operation) -> None:  # noqa: ANN001
    owner = _owner()
    binding = {item.contract.name: item for item in _tools(owner)}[name]
    result = asyncio.run(binding.handler(SimpleNamespace(user_id="u1"), arguments))
    payload = json.loads(result.content)
    assert payload["effect"] == "read_only"
    assert payload["content"] == "source content"
    assert "TOP-SECRET" not in result.content and "TOKEN-SECRET" not in result.content
    assert owner._test_calls[0][:4] == ("u1", kind, arguments["connection_ref"], operation)
    assert binding.contract.effect == "read_only"
    assert binding.contract.confirmation_required is False
    assert binding.contract.user_scoped is True


@pytest.mark.parametrize(("name", "arguments", "_kind", "_operation"), CASES)
def test_p2_r5_empty_results_are_honest(name, arguments, _kind, _operation) -> None:  # noqa: ANN001
    binding = {item.contract.name: item for item in _tools(_owner(content=""))}[name]
    result = asyncio.run(binding.handler(SimpleNamespace(user_id="u1"), arguments))
    assert '"status": "not_found_or_empty"' in result.content
    assert '"message":' in result.content


@pytest.mark.parametrize(("name", "arguments", "_kind", "_operation"), CASES)
def test_p2_r5_rejects_foreign_scope(name, arguments, _kind, _operation) -> None:  # noqa: ANN001
    binding = {item.contract.name: item for item in _tools(_owner(scope="u2"))}[name]
    with pytest.raises(ValueError, match="scope_mismatch"):
        asyncio.run(binding.handler(SimpleNamespace(user_id="u1"), arguments))


def test_p2_r5_registry_has_20_read_only_tools_and_offers_all_without_selector() -> None:
    tools = _tools(_owner())
    assert len(tools) == 20
    assert all(item.contract.effect == "read_only" for item in tools)
    assert len(asyncio.run(select_relevant_native_tools("read", tools, selector=None))) == 20


def test_p2_r5_large_file_result_is_globally_capped_with_honest_notice(tmp_path) -> None:  # noqa: ANN001
    tools = _tools(_owner(content="x" * (MAX_TOOL_RESULT_CHARS * 2)))
    responses = [
        SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            content="", tool_calls=[SimpleNamespace(id="c1", function=SimpleNamespace(
                name="file_read", arguments=json.dumps({"connection_kind": "sftp", "connection_ref": "files", "path": "/large"}),
            ))],
        ), finish_reason="tool_use")]),
        SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="bounded answer", tool_calls=[]), finish_reason="stop")]),
    ]
    seen = []

    async def completion(**kwargs):
        seen.append(kwargs)
        return responses.pop(0)

    outcome = asyncio.run(run_native_agent_turn(
        message="read file", user_id="u1", turn_id="cap", llm_config=LLMConfig(model="fake"),
        tool_bindings=tools, completion=completion, trace_root=tmp_path,
    ))
    tool_result = seen[1]["messages"][-1]["content"]
    assert outcome.kind == "final_answer"
    assert len(tool_result) <= MAX_TOOL_RESULT_CHARS
    assert '"truncated": true' in tool_result and "gekuerzt" in tool_result


def test_p2_r5_native_roundtrip_selects_requested_tool(tmp_path) -> None:  # noqa: ANN001
    responses = [
        SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            content="", tool_calls=[SimpleNamespace(id="c1", function=SimpleNamespace(
                name="mail_search", arguments='{"connection_ref":"inbox","query":"invoice"}',
            ))],
        ), finish_reason="tool_use")]),
        SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="mail result", tool_calls=[]), finish_reason="stop")]),
    ]

    async def completion(**_kwargs):
        return responses.pop(0)

    outcome = asyncio.run(run_native_agent_turn(
        message="search mail", user_id="u1", turn_id="mail", llm_config=LLMConfig(model="fake"),
        tool_bindings=_tools(_owner()), completion=completion, trace_root=tmp_path,
    ))
    assert outcome.kind == "final_answer"
    assert outcome.used_tool_names == ("mail_search",)


class _FallbackRuntime:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def execute_rss_read(self, ref: str, *, requested_count: int) -> str:
        self.calls.append(("rss", ref, requested_count))
        return "Configured feed item"

    def execute_sftp_list(self, ref: str, *, remote_path: str) -> str:
        self.calls.append(("sftp_list", ref, remote_path))
        return "remote.txt"

    def execute_google_calendar_read(self, ref: str, *, range_hint: str, search_query: str) -> str:
        self.calls.append(("calendar", ref, range_hint, search_query))
        return "Calendar event"


class _FailingFallbackRuntime(_FallbackRuntime):
    def execute_rss_read(self, ref: str, *, requested_count: int) -> str:
        self.calls.append(("rss", ref, requested_count))
        raise OSError("feed endpoint unavailable")

    def execute_sftp_list(self, ref: str, *, remote_path: str) -> str:
        self.calls.append(("sftp_list", ref, remote_path))
        raise FileNotFoundError(2, "No such file or directory", "/run/secrets/missing-key")


def _fallback_owner(*, runtime=None) -> SimpleNamespace:  # noqa: ANN001
    runtime = runtime or _FallbackRuntime()
    return SimpleNamespace(
        settings=SimpleNamespace(connections=ConnectionsConfig(
            rss={"news-feed": RSSConnectionConfig(url="https://example.test/feed")},
            sftp={"files": SFTPConnectionConfig(host="files.example.test")},
            google_calendar={"work": GoogleCalendarConnectionConfig(calendar_id="work")},
        )),
        memory_skill=object(), _skill_runtime=runtime, _test_runtime=runtime,
    )


def test_rss_fallback_resolves_configured_profile_by_dict_key() -> None:
    owner = _fallback_owner()
    binding = {item.contract.name: item for item in _tools(owner)}["rss_feed_read"]
    result = asyncio.run(binding.handler(
        SimpleNamespace(user_id="u1"), {"connection_ref": "news-feed", "requested_count": 3},
    ))
    payload = json.loads(result.content)
    assert payload["status"] == "ok"
    assert payload["content"] == "Configured feed item"
    assert owner._test_runtime.calls == [("rss", "news-feed", 3)]


def test_file_list_fallback_resolves_configured_profile_by_dict_key() -> None:
    owner = _fallback_owner()
    binding = {item.contract.name: item for item in _tools(owner)}["file_list"]
    result = asyncio.run(binding.handler(SimpleNamespace(user_id="u1"), {
        "connection_kind": "sftp", "connection_ref": "files", "path": "/incoming",
    }))
    payload = json.loads(result.content)
    assert payload["status"] == "ok"
    assert payload["content"] == "remote.txt"
    assert owner._test_runtime.calls == [("sftp_list", "files", "/incoming")]


def test_calendar_fallback_resolves_configured_profile_by_dict_key() -> None:
    owner = _fallback_owner()
    binding = {item.contract.name: item for item in _tools(owner)}["calendar_read"]
    result = asyncio.run(binding.handler(SimpleNamespace(user_id="u1"), {
        "connection_ref": "work", "range_hint": "today", "query": "planning",
    }))
    payload = json.loads(result.content)
    assert payload["status"] == "ok"
    assert payload["content"] == "Calendar event"
    assert owner._test_runtime.calls == [("calendar", "work", "today", "planning")]


def test_sftp_runtime_error_degrades_to_bounded_read_failed_without_raise() -> None:
    owner = _fallback_owner(runtime=_FailingFallbackRuntime())
    binding = {item.contract.name: item for item in _tools(owner)}["file_list"]
    result = asyncio.run(binding.handler(SimpleNamespace(user_id="u1"), {
        "connection_kind": "sftp", "connection_ref": "files", "path": "/incoming",
    }))
    payload = json.loads(result.content)
    assert payload["status"] == "read_failed"
    assert payload["error_class"] == "FileNotFoundError"
    assert payload["detail"] == "[Errno 2] No such file or directory: '/run/secrets/missing-key'"
    assert len(payload["detail"]) <= 200
    assert "host" not in payload and "password" not in payload and "token" not in payload
    assert owner._test_runtime.calls == [("sftp_list", "files", "/incoming")]


def test_rss_runtime_error_degrades_to_bounded_read_failed_without_raise() -> None:
    owner = _fallback_owner(runtime=_FailingFallbackRuntime())
    binding = {item.contract.name: item for item in _tools(owner)}["rss_feed_read"]
    result = asyncio.run(binding.handler(
        SimpleNamespace(user_id="u1"), {"connection_ref": "news-feed", "requested_count": 3},
    ))
    payload = json.loads(result.content)
    assert payload["status"] == "read_failed"
    assert payload["error_class"] == "OSError"
    assert payload["detail"] == "feed endpoint unavailable"
    assert len(payload["detail"]) <= 200
    assert owner._test_runtime.calls == [("rss", "news-feed", 3)]


def test_connection_read_missing_runtime_method_is_not_masked_as_read_failed() -> None:
    owner = _fallback_owner(runtime=SimpleNamespace(calls=[]))
    binding = {item.contract.name: item for item in _tools(owner)}["file_list"]
    with pytest.raises(AttributeError, match="execute_sftp_list"):
        asyncio.run(binding.handler(SimpleNamespace(user_id="u1"), {
            "connection_kind": "sftp", "connection_ref": "files", "path": "/incoming",
        }))


@pytest.mark.parametrize(("tool_name", "arguments"), (
    ("rss_feed_read", {"connection_ref": "missing"}),
    ("file_list", {"connection_kind": "sftp", "connection_ref": "missing", "path": "/incoming"}),
))
def test_connection_read_fallback_unknown_dict_key_is_honest_without_runtime_call(
    tool_name: str, arguments: dict,
) -> None:
    owner = _fallback_owner()
    binding = {item.contract.name: item for item in _tools(owner)}[tool_name]
    result = asyncio.run(binding.handler(SimpleNamespace(user_id="u1"), arguments))
    assert json.loads(result.content)["status"] == "not_found_or_empty"
    assert owner._test_runtime.calls == []


@pytest.mark.parametrize(("row", "reason"), (
    ({"source_authority": "sftp:configured_profile", "scope_user_id": "u2", "content": "x"}, "scope_mismatch"),
    ({"source_authority": "wrong:authority", "scope_user_id": "u1", "content": "x"}, "authority_mismatch"),
    ("not-a-mapping", "result_invalid"),
))
def test_connection_read_injected_loader_guards_remain_fail_closed(row, reason: str) -> None:  # noqa: ANN001
    async def loader(*_args):
        return row

    owner = SimpleNamespace(
        settings=SimpleNamespace(), memory_skill=object(),
        _native_agent_connection_read_loader=loader,
    )
    binding = {item.contract.name: item for item in _tools(owner)}["file_list"]
    with pytest.raises(ValueError, match=reason):
        asyncio.run(binding.handler(SimpleNamespace(user_id="u1"), {
            "connection_kind": "sftp", "connection_ref": "files", "path": "/incoming",
        }))
