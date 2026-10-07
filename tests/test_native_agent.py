from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

from aria.modules.configuration_foundations.config import LLMConfig, Settings
from aria.modules.native_agent.handler import run_native_agent_turn
from aria.modules.memory.native_tools import native_tool_contributions as memory_native_tools
from aria.modules.connections_runtime_status.native_tools import native_tool_contributions as connection_native_tools
from aria.modules.pipeline_orchestrator.pipeline import Pipeline


def _response(*, content: str = "", tool_calls=None, finish_reason: str = "stop"):  # noqa: ANN001
    message = SimpleNamespace(content=content, tool_calls=list(tool_calls or []))
    return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason=finish_reason)])


def _tool_call(arguments: str = "{}") -> SimpleNamespace:
    return SimpleNamespace(
        id="call-memory-1",
        function=SimpleNamespace(name="recall_personal_memory", arguments=arguments),
    )


def _connections_tool_call(arguments: str = "{}") -> SimpleNamespace:
    return SimpleNamespace(
        id="call-connections-1",
        function=SimpleNamespace(name="list_connections", arguments=arguments),
    )


def _connection_lookup_tool_call(connection_ref: str, connection_kind: str = "") -> SimpleNamespace:
    arguments = {"connection_ref": connection_ref}
    if connection_kind:
        arguments["connection_kind"] = connection_kind
    return SimpleNamespace(
        id="call-connection-lookup-1",
        function=SimpleNamespace(
            name="lookup_connection",
            arguments=json.dumps(arguments),
        ),
    )


async def _claims(user_id: str):  # noqa: ANN001
    assert user_id == "u1"
    return ({
        "claim_id": "claim-1", "summary": "user prefers concise answers",
        "source_authority": "memory:personal_claim_store",
    },)


async def _connections(user_id: str, connection_kind: str):  # noqa: ANN001
    assert user_id == "u1"
    rows = (
        {"kind": "ssh", "ref": "home-server", "display_name": "Home Server", "target": "home.local",
         "source_authority": "connections:profile_store", "scope_user_id": "u1"},
        {"kind": "rss", "ref": "tech-news", "display_name": "Tech News", "target": "https://example.test/feed",
         "source_authority": "connections:profile_store", "scope_user_id": "u1"},
    )
    return tuple(row for row in rows if not connection_kind or row["kind"] == connection_kind)


def _bindings(*, claims=_claims, connections=_connections, memory=True, connection=False):  # noqa: ANN001
    owner = SimpleNamespace(
        memory_skill=object(), settings=SimpleNamespace(),
        _native_agent_claim_loader=claims,
        _native_agent_connection_loader=connections,
    )
    bindings = (
        *(memory_native_tools(owner) if memory else ()),
        *(connection_native_tools(owner) if connection else ()),
    )
    enabled_flags = {
        *(('native_agent_memory_enabled',) if memory else ()),
        *(('native_agent_connections_enabled',) if connection else ()),
    }
    return tuple(binding for binding in bindings if binding.contract.rollout_flag in enabled_flags)


def test_native_agent_connections_tool_lists_real_profiles_and_filter(tmp_path) -> None:  # noqa: ANN001
    calls: list[dict] = []

    async def completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return _response(tool_calls=[_connections_tool_call('{"connection_kind":"ssh"}')], finish_reason="tool_use")
        assert "home-server" in kwargs["messages"][-1]["content"]
        assert "tech-news" not in kwargs["messages"][-1]["content"]
        return _response(content="Du hast die SSH-Verbindung Home Server.")

    outcome = asyncio.run(run_native_agent_turn(
        message="Welche SSH-Verbindungen habe ich?", user_id="u1", turn_id="turn-connections",
        llm_config=LLMConfig(model="fake"), tool_bindings=_bindings(memory=False, connection=True),
        completion=completion, trace_root=tmp_path,
    ))

    assert outcome.kind == "final_answer"
    assert outcome.used_tool_names == ("list_connections",)
    assert calls[0]["tools"][0] == {
        "name": "list_connections",
        "description": "List all connection profiles available to the current user, optionally filtered by connection kind. This tool is read-only.",
        "input_schema": {
            "type": "object",
            "properties": {"connection_kind": {"type": "string"}},
            "required": [],
        },
    }
    assert [tool["name"] for tool in calls[0]["tools"]] == ["list_connections", "lookup_connection"]
    assert all("response_format" not in call for call in calls)


def test_native_agent_reports_completed_tool_steps_to_observational_callback(tmp_path) -> None:  # noqa: ANN001
    provider_calls = 0
    checkpoints: list[tuple[int, tuple[str, ...], str]] = []

    async def completion(**_kwargs):
        nonlocal provider_calls
        provider_calls += 1
        if provider_calls == 1:
            return _response(tool_calls=[_connections_tool_call()], finish_reason="tool_use")
        return _response(content="Done.")

    async def checkpoint(step_index: int, tool_names: tuple[str, ...], outcome_summary: str) -> None:
        checkpoints.append((step_index, tuple(tool_names), outcome_summary))

    outcome = asyncio.run(run_native_agent_turn(
        message="List connections", user_id="u1", turn_id="turn-checkpoint",
        llm_config=LLMConfig(model="fake"), tool_bindings=_bindings(memory=False, connection=True),
        completion=completion, trace_root=tmp_path, step_callback=checkpoint,
    ))

    assert outcome.kind == "final_answer"
    assert len(checkpoints) == 1
    assert checkpoints[0][0] == 1
    assert checkpoints[0][1] == ("list_connections",)
    assert "home-server" in checkpoints[0][2]


def test_native_agent_connections_unknown_kind_degrades_with_available_kinds(tmp_path) -> None:  # noqa: ANN001
    calls: list[dict] = []

    async def strict_connections(user_id: str, connection_kind: str):
        if connection_kind == "calendar":
            raise ValueError("connection_inventory_kind_unknown")
        return await _connections(user_id, connection_kind)

    async def completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return _response(
                tool_calls=[_connections_tool_call('{"connection_kind":"calendar"}')],
                finish_reason="tool_use",
            )
        result = json.loads(kwargs["messages"][-1]["content"])
        assert result == {
            "available_connection_kinds": ["rss", "ssh"],
            "connections": [],
            "message": "No connection profiles match the requested kind. Use one of the available exact kinds.",
            "requested_connection_kind": "calendar",
            "status": "connection_kind_unknown",
        }
        return _response(content="Verfuegbare Arten sind RSS und SSH.")

    outcome = asyncio.run(run_native_agent_turn(
        message="Welche Calendar-Verbindungen habe ich?", user_id="u1", turn_id="unknown-kind",
        llm_config=LLMConfig(model="fake"),
        tool_bindings=_bindings(connections=strict_connections, memory=False, connection=True),
        completion=completion, trace_root=tmp_path,
    ))
    assert outcome.kind == "final_answer"
    assert outcome.used_tool_names == ("list_connections",)
    assert len(calls) == 2


def test_native_agent_connections_unknown_kind_still_rejects_invalid_authority(tmp_path) -> None:  # noqa: ANN001
    async def invalid_authority(_user_id: str, connection_kind: str):
        if connection_kind:
            raise ValueError("connection_inventory_kind_unknown")
        return ({
            "kind": "ssh", "ref": "foreign", "display_name": "Foreign", "target": "foreign.local",
            "source_authority": "unknown:store", "scope_user_id": "u1",
        },)

    async def completion(**_kwargs):
        return _response(
            tool_calls=[_connections_tool_call('{"connection_kind":"calendar"}')],
            finish_reason="tool_use",
        )

    outcome = asyncio.run(run_native_agent_turn(
        message="Connections", user_id="u1", turn_id="unknown-kind-bad-authority",
        llm_config=LLMConfig(model="fake"),
        tool_bindings=_bindings(connections=invalid_authority, memory=False, connection=True),
        completion=completion, trace_root=tmp_path,
    ))
    assert outcome.kind == "fail_closed"
    assert outcome.reason == "native_agent_connection_source_authority_mismatch"


def test_native_agent_connection_lookup_returns_only_safe_exact_profile_metadata(tmp_path) -> None:  # noqa: ANN001
    calls: list[dict] = []

    async def connections_with_secrets(user_id: str, connection_kind: str):
        rows = list(await _connections(user_id, connection_kind))
        rows[0].update({"password": "never-return", "private_key": "secret-key", "token": "secret-token"})
        return tuple(rows)

    async def completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return _response(tool_calls=[_connection_lookup_tool_call("home-server")], finish_reason="tool_use")
        result = kwargs["messages"][-1]["content"]
        assert '"ref": "home-server"' in result and '"target": "home.local"' in result
        assert "never-return" not in result and "secret-key" not in result and "secret-token" not in result
        return _response(content="Home Server ist eine SSH-Verbindung zu home.local.")

    outcome = asyncio.run(run_native_agent_turn(
        message="Zeig mir die Details zu home-server", user_id="u1", turn_id="lookup-connection",
        llm_config=LLMConfig(model="fake"),
        tool_bindings=_bindings(connections=connections_with_secrets, memory=False, connection=True),
        completion=completion, trace_root=tmp_path,
    ))

    assert outcome.kind == "final_answer"
    assert outcome.used_tool_names == ("lookup_connection",)
    lookup_schema = next(tool for tool in calls[0]["tools"] if tool["name"] == "lookup_connection")
    assert lookup_schema["input_schema"] == {
        "type": "object",
        "properties": {
            "connection_ref": {"type": "string"},
            "connection_kind": {"type": "string"},
        },
        "required": ["connection_ref"],
    }


def test_native_agent_connection_lookup_reports_exact_ref_not_found(tmp_path) -> None:  # noqa: ANN001
    calls: list[dict] = []

    async def completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return _response(tool_calls=[_connection_lookup_tool_call("missing-ref")], finish_reason="tool_use")
        assert '"status": "connection_not_found"' in kwargs["messages"][-1]["content"]
        assert '"connection_ref": "missing-ref"' in kwargs["messages"][-1]["content"]
        return _response(content="Keine Verbindung mit dieser exakten Referenz gefunden.")

    outcome = asyncio.run(run_native_agent_turn(
        message="Details zu missing-ref", user_id="u1", turn_id="lookup-missing",
        llm_config=LLMConfig(model="fake"), tool_bindings=_bindings(memory=False, connection=True),
        completion=completion, trace_root=tmp_path,
    ))
    assert outcome.kind == "final_answer"


def test_native_agent_connection_lookup_rejects_foreign_user_scope(tmp_path) -> None:  # noqa: ANN001
    async def foreign_rows(_user_id: str, _connection_kind: str):
        return ({"kind": "ssh", "ref": "home-server", "display_name": "Foreign", "target": "foreign.local",
                 "source_authority": "connections:profile_store", "scope_user_id": "u2"},)

    async def completion(**_kwargs):
        return _response(tool_calls=[_connection_lookup_tool_call("home-server")], finish_reason="tool_use")

    outcome = asyncio.run(run_native_agent_turn(
        message="Details", user_id="u1", turn_id="lookup-foreign",
        llm_config=LLMConfig(model="fake"),
        tool_bindings=_bindings(connections=foreign_rows, memory=False, connection=True),
        completion=completion, trace_root=tmp_path,
    ))
    assert outcome.kind == "fail_closed"
    assert outcome.reason == "native_agent_connection_scope_mismatch"


def test_native_agent_connection_lookup_rejects_model_user_scope_argument(tmp_path) -> None:  # noqa: ANN001
    async def completion(**_kwargs):
        call = SimpleNamespace(
            id="call-model-scope",
            function=SimpleNamespace(
                name="lookup_connection",
                arguments='{"connection_ref":"home-server","user_id":"u2"}',
            ),
        )
        return _response(tool_calls=[call], finish_reason="tool_use")

    outcome = asyncio.run(run_native_agent_turn(
        message="Details", user_id="u1", turn_id="lookup-model-scope",
        llm_config=LLMConfig(model="fake"), tool_bindings=_bindings(memory=False, connection=True),
        completion=completion, trace_root=tmp_path,
    ))
    assert outcome.kind == "fail_closed"
    assert outcome.reason == "native_agent_connection_lookup_arguments_invalid"


def test_native_agent_connection_lookup_returns_all_safe_exact_ref_matches(tmp_path) -> None:  # noqa: ANN001
    calls: list[dict] = []

    async def duplicate_rows(_user_id: str, _connection_kind: str):
        return tuple({
            "kind": kind, "ref": "duplicate", "display_name": kind, "target": f"{kind}.local",
            "source_authority": "connections:profile_store", "scope_user_id": "u1",
            "password": f"{kind}-password", "private_key": f"{kind}-key", "token": f"{kind}-token",
        } for kind in ("ssh", "rss"))

    async def completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return _response(tool_calls=[_connection_lookup_tool_call("duplicate")], finish_reason="tool_use")
        result = kwargs["messages"][-1]["content"]
        assert '"match_count": 2' in result
        assert '"kind": "ssh"' in result and '"kind": "rss"' in result
        assert '"target": "ssh.local"' in result and '"target": "rss.local"' in result
        assert "password" not in result and "private_key" not in result and "token" not in result
        return _response(content="Es gibt SSH und RSS mit dieser Referenz.")

    outcome = asyncio.run(run_native_agent_turn(
        message="Details", user_id="u1", turn_id="lookup-ambiguous",
        llm_config=LLMConfig(model="fake"),
        tool_bindings=_bindings(connections=duplicate_rows, memory=False, connection=True),
        completion=completion, trace_root=tmp_path,
    ))
    assert outcome.kind == "final_answer"
    assert outcome.used_tool_names == ("lookup_connection",)


def test_native_agent_connection_lookup_can_filter_duplicate_ref_by_kind(tmp_path) -> None:  # noqa: ANN001
    calls: list[dict] = []

    async def duplicate_rows(_user_id: str, connection_kind: str):
        rows = tuple({
            "kind": kind, "ref": "duplicate", "display_name": kind, "target": f"{kind}.local",
            "source_authority": "connections:profile_store", "scope_user_id": "u1",
        } for kind in ("ssh", "sftp"))
        return tuple(row for row in rows if not connection_kind or row["kind"] == connection_kind)

    async def completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return _response(tool_calls=[_connection_lookup_tool_call("duplicate", "sftp")], finish_reason="tool_use")
        result = kwargs["messages"][-1]["content"]
        assert '"kind": "sftp"' in result and '"kind": "ssh"' not in result
        return _response(content="Das SFTP-Profil zeigt auf sftp.local.")

    outcome = asyncio.run(run_native_agent_turn(
        message="SFTP-Details", user_id="u1", turn_id="lookup-kind-filter",
        llm_config=LLMConfig(model="fake"),
        tool_bindings=_bindings(connections=duplicate_rows, memory=False, connection=True),
        completion=completion, trace_root=tmp_path,
    ))
    assert outcome.kind == "final_answer"


def test_native_agent_with_both_flags_offers_both_and_model_selects_each(tmp_path) -> None:  # noqa: ANN001
    async def run(selected_call, final_text, turn_id):  # noqa: ANN001
        calls: list[dict] = []

        async def completion(**kwargs):
            calls.append(kwargs)
            return _response(tool_calls=[selected_call], finish_reason="tool_use") if len(calls) == 1 else _response(content=final_text)

        outcome = await run_native_agent_turn(
            message="Frage", user_id="u1", turn_id=turn_id, llm_config=LLMConfig(model="fake"),
            tool_bindings=_bindings(memory=True, connection=True),
            completion=completion, trace_root=tmp_path,
        )
        return outcome, [tool["name"] for tool in calls[0]["tools"]]

    memory, memory_tools = asyncio.run(run(_tool_call(), "Memory", "both-memory"))
    connections, connection_tools = asyncio.run(run(_connections_tool_call(), "Connections", "both-connections"))

    assert memory.used_tool_names == ("recall_personal_memory",)
    assert connections.used_tool_names == ("list_connections",)
    assert memory_tools == connection_tools == [
        "recall_personal_memory", "memory_context_read", "list_connections", "lookup_connection",
    ]


def test_native_agent_rejects_connection_rows_for_another_user(tmp_path) -> None:  # noqa: ANN001
    async def completion(**_kwargs):
        return _response(tool_calls=[_connections_tool_call()], finish_reason="tool_use")

    async def foreign_rows(_user_id: str, _connection_kind: str):
        return ({"kind": "ssh", "ref": "foreign", "display_name": "Foreign", "target": "foreign.local",
                 "source_authority": "connections:profile_store", "scope_user_id": "u2"},)

    outcome = asyncio.run(run_native_agent_turn(
        message="Welche Verbindungen?", user_id="u1", turn_id="foreign-connections",
        llm_config=LLMConfig(model="fake"),
        tool_bindings=_bindings(connections=foreign_rows, memory=False, connection=True),
        completion=completion, trace_root=tmp_path,
    ))

    assert outcome.kind == "fail_closed"
    assert outcome.reason == "native_agent_connection_scope_mismatch"


def test_native_agent_no_connections_returns_authoritative_empty_result(tmp_path) -> None:  # noqa: ANN001
    calls: list[dict] = []

    async def completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return _response(tool_calls=[_connections_tool_call()], finish_reason="tool_use")
        assert '"status": "no_connections"' in kwargs["messages"][-1]["content"]
        return _response(content="Du hast keine Verbindungen.")

    async def no_connections(user_id: str, connection_kind: str):
        assert user_id == "u1" and connection_kind == ""
        return ()

    outcome = asyncio.run(run_native_agent_turn(
        message="Welche Verbindungen habe ich?", user_id="u1", turn_id="no-connections",
        llm_config=LLMConfig(model="fake"),
        tool_bindings=_bindings(connections=no_connections, memory=False, connection=True),
        completion=completion, trace_root=tmp_path,
    ))

    assert outcome.kind == "final_answer"
    assert outcome.message == "Du hast keine Verbindungen."


def test_native_agent_memory_tool_roundtrip_is_source_bound_and_traced(tmp_path) -> None:  # noqa: ANN001
    calls: list[dict] = []

    async def completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return _response(tool_calls=[_tool_call()], finish_reason="tool_use")
        content = calls[-1]["messages"][-1]["content"]
        rendered = "".join(
            str(block.get("text") or "") for block in content if isinstance(block, dict)
        ) if isinstance(content, list) else str(content)
        assert "claim-1" in rendered
        return _response(content="Du bevorzugst knappe Antworten.")

    outcome = asyncio.run(run_native_agent_turn(
        message="Was hast du dir ueber mich gemerkt?",
        user_id="u1",
        turn_id="turn-memory",
        llm_config=LLMConfig(model="claude-sonnet-4-5"),
        tool_bindings=_bindings(),
        completion=completion,
        trace_root=tmp_path,
    ))

    assert outcome.kind == "final_answer"
    assert outcome.message == "Du bevorzugst knappe Antworten."
    assert outcome.provider_calls == 2
    assert calls[0]["tools"][0]["name"] == "recall_personal_memory"
    assert calls[0]["tools"][0]["input_schema"] == {
        "type": "object", "properties": {}, "required": [],
    }
    assert all("response_format" not in call for call in calls)
    rows = [json.loads(line) for line in (tmp_path / "turn-memory.jsonl").read_text().splitlines()]
    assert rows[0]["chosen_tool"] == "recall_personal_memory"
    assert rows[0]["tool_arguments"] == {}
    assert "claim-1" in rows[0]["tool_result"]
    assert rows[-1]["final_outcome"] == "final_answer"


def test_native_agent_chat_can_answer_directly_without_tool(tmp_path) -> None:  # noqa: ANN001
    calls: list[dict] = []

    async def completion(**kwargs):
        calls.append(kwargs)
        return _response(content="Hallo aus dem nativen Agenten.")

    outcome = asyncio.run(run_native_agent_turn(
        message="Hallo", user_id="u1", turn_id="turn-chat",
        llm_config=LLMConfig(model="claude-sonnet-4-5"), tool_bindings=_bindings(),
        completion=completion, trace_root=tmp_path,
    ))

    assert outcome.kind == "final_answer"
    assert outcome.message == "Hallo aus dem nativen Agenten."
    assert outcome.provider_calls == 1
    assert len(calls) == 1


def test_native_agent_budget_exhaustion_synthesizes_best_effort_answer(tmp_path) -> None:  # noqa: ANN001
    calls: list[dict] = []

    async def completion(**kwargs):
        calls.append(kwargs)
        if "tool_choice" not in kwargs:
            assert any('"claim_id": "claim-1"' in str(row.get("content", "")) for row in kwargs["messages"])
            return _response(content="Teilantwort aus den gelesenen Ergebnissen; weitere Quellen konnten nicht mehr geprüft werden.")
        return _response(tool_calls=[_tool_call()], finish_reason="tool_use")

    outcome = asyncio.run(run_native_agent_turn(
        message="Prüfe viele Quellen", user_id="u1", turn_id="budget-best-effort",
        llm_config=LLMConfig(model="fake"), tool_bindings=_bindings(),
        completion=completion, trace_root=tmp_path, max_steps=3, max_provider_calls=3,
    ))

    assert outcome.kind == "final_answer"
    assert outcome.reason == "native_agent_budget_best_effort"
    assert "Teilantwort" in outcome.message
    assert outcome.provider_calls == 3
    assert [call.get("tool_choice") for call in calls] == ["auto", "auto", None]
    assert "tools" in calls[-1]
    rows = [json.loads(line) for line in (tmp_path / "budget-best-effort.jsonl").read_text().splitlines()]
    assert rows[-1]["final_outcome"] == "best_effort_final_answer"


def test_native_agent_budget_finalizer_failure_is_honest_not_safety_claim(tmp_path) -> None:  # noqa: ANN001
    async def completion(**kwargs):
        if "tool_choice" not in kwargs:
            raise RuntimeError("finalizer unavailable")
        return _response(tool_calls=[_tool_call()], finish_reason="tool_use")

    outcome = asyncio.run(run_native_agent_turn(
        message="Prüfe viele Quellen", user_id="u1", turn_id="budget-finalizer-error",
        llm_config=LLMConfig(model="fake"), tool_bindings=_bindings(),
        completion=completion, trace_root=tmp_path, max_steps=2, max_provider_calls=2,
    ))

    assert outcome.kind == "final_answer"
    assert outcome.reason == "native_agent_budget_finalization_degraded"
    assert "Sicherheit" not in outcome.message and "safely" not in outcome.message.lower()
    assert "Partially completed" in outcome.message
    assert "final summary" in outcome.message


def test_native_agent_rejects_non_authoritative_memory_evidence(tmp_path) -> None:  # noqa: ANN001
    responses = iter([_response(tool_calls=[_tool_call()], finish_reason="tool_use")])

    async def completion(**_kwargs):
        return next(responses)

    async def wrong_source(_user_id: str):
        return ({
            "claim_id": "claim-1", "summary": "untrusted",
            "source_authority": "unknown:store",
        },)

    outcome = asyncio.run(run_native_agent_turn(
        message="Was ist gespeichert?", user_id="u1", turn_id="wrong-source",
        llm_config=LLMConfig(model="fake"), tool_bindings=_bindings(claims=wrong_source),
        completion=completion, trace_root=tmp_path,
    ))

    assert outcome.kind == "fail_closed"
    assert outcome.reason == "native_agent_memory_source_authority_mismatch"


def test_native_agent_rejects_unknown_tool_authority(tmp_path) -> None:  # noqa: ANN001
    async def completion(**_kwargs):
        call = SimpleNamespace(id="call-write", function=SimpleNamespace(name="write_memory", arguments="{}"))
        return _response(tool_calls=[call], finish_reason="tool_use")

    outcome = asyncio.run(run_native_agent_turn(
        message="Speichere etwas", user_id="u1", turn_id="unknown-tool",
        llm_config=LLMConfig(model="fake"), tool_bindings=_bindings(),
        completion=completion, trace_root=tmp_path,
    ))

    assert outcome.kind == "fail_closed"
    assert outcome.reason == "native_agent_tool_authority_mismatch"


def test_native_agent_no_claims_returns_authoritative_empty_result(tmp_path) -> None:  # noqa: ANN001
    calls: list[dict] = []

    async def completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return _response(tool_calls=[_tool_call()], finish_reason="tool_use")
        assert '"status": "no_personal_claims"' in kwargs["messages"][-1]["content"]
        return _response(content="Ich habe nichts ueber dich gespeichert.")

    async def no_claims(_user_id: str):
        return ()

    outcome = asyncio.run(run_native_agent_turn(
        message="Was ist gespeichert?", user_id="u1", turn_id="no-claims",
        llm_config=LLMConfig(model="fake"), tool_bindings=_bindings(claims=no_claims),
        completion=completion, trace_root=tmp_path,
    ))

    assert outcome.kind == "final_answer"
    assert outcome.message == "Ich habe nichts ueber dich gespeichert."


class _PromptLoader:
    def get_persona(self) -> str:
        return "ARIA"


class _LegacyLLM:
    def __init__(self) -> None:
        self.operations: list[str] = []

    async def chat(self, messages, **kwargs):  # noqa: ANN001
        self.operations.append(str(kwargs.get("operation") or ""))
        raise AssertionError("legacy LLM must be unreachable while native agent owns the turn")


class _MemorySkill:
    async def list_personal_claims(self, *, user_id: str, limit: int = 48):  # noqa: ANN001
        assert user_id == "u1"
        return [{
            "personal_claim_contract": "personal_claim_v1", "claim_id": "claim-1",
            "claim_status": "active", "claim_subject": "user", "claim_predicate": "prefers",
            "claim_value": "knappe Antworten", "claim_scope": "global", "claim_authority": "explicit_user",
        }]


def _settings(*, native_enabled: bool, memory_enabled: bool | None = None, connections_enabled: bool = False) -> Settings:
    memory_flag = native_enabled if memory_enabled is None else memory_enabled
    return Settings.model_validate({
        "llm": {"model": "fake"}, "memory": {"enabled": False},
        "agentic_loop": {
            "enabled": native_enabled,
            "native_agent_memory_enabled": memory_flag,
            "native_agent_connections_enabled": connections_enabled,
        },
        "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
    })


def test_native_agent_short_circuits_before_arbitration(tmp_path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.chdir(tmp_path)
    completions = iter([
        _response(tool_calls=[_tool_call()], finish_reason="tool_use"),
        _response(content="Du bevorzugst knappe Antworten."),
    ])

    async def completion(**_kwargs):
        return next(completions)

    llm = _LegacyLLM()
    pipeline = Pipeline(settings=_settings(native_enabled=True), prompt_loader=_PromptLoader(), llm_client=llm)
    pipeline.memory_skill = _MemorySkill()
    pipeline._native_agent_completion = completion

    result = asyncio.run(pipeline.process("Was hast du dir gemerkt?", user_id="u1", source="test"))

    assert result.text == "Du bevorzugst knappe Antworten."
    assert llm.operations == []
    assert any("native_agent_position=pre_arbitration" in line for line in result.detail_lines)


def test_native_agent_direct_chat_short_circuits_before_arbitration(tmp_path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.chdir(tmp_path)

    async def completion(**_kwargs):
        return _response(content="Direkte native Chat-Antwort.")

    llm = _LegacyLLM()
    pipeline = Pipeline(settings=_settings(native_enabled=True), prompt_loader=_PromptLoader(), llm_client=llm)
    pipeline.memory_skill = _MemorySkill()
    pipeline._native_agent_completion = completion

    result = asyncio.run(pipeline.process("Hallo", user_id="u1", source="test"))

    assert result.text == "Direkte native Chat-Antwort."
    assert result.intents == ["chat"]
    assert llm.operations == []


def test_native_agent_is_delivery_default_and_short_circuits_before_arbitration(tmp_path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.chdir(tmp_path)
    settings = Settings.model_validate({
        "llm": {"model": "fake"},
        "memory": {"enabled": False},
        "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
    })
    rollout_defaults = settings.agentic_loop.model_dump()
    assert rollout_defaults.pop("native_web_debug_details") is False
    assert rollout_defaults.pop("native_agent_mcp_enabled") is False
    assert rollout_defaults.pop("native_tool_selector_top_k") == 16
    assert rollout_defaults.pop("native_agent_max_steps") == 32
    assert rollout_defaults.pop("native_agent_max_provider_calls") == 32
    assert rollout_defaults.pop("native_agent_mcp_vision_max_live_images") == 4
    assert rollout_defaults.pop("native_agent_mcp_vision_max_lifetime_images") == 24
    assert rollout_defaults.pop("async_agent_job_sync_budget_seconds") == 25.0
    assert rollout_defaults.pop("native_agent_budget_extension_steps") == 32
    assert rollout_defaults.pop("native_agent_budget_max_total") == 160
    assert rollout_defaults.pop("agent_job_retention_days") == 14
    assert rollout_defaults.pop("agent_job_stale_paused_days") == 7
    assert all(value is True for value in rollout_defaults.values())

    async def completion(**_kwargs):
        return _response(content="Native delivery default.")

    llm = _LegacyLLM()
    pipeline = Pipeline(settings=settings, prompt_loader=_PromptLoader(), llm_client=llm)
    pipeline.memory_skill = _MemorySkill()
    pipeline._native_agent_completion = completion

    result = asyncio.run(pipeline.process("Hallo", user_id="u1", source="test"))

    assert result.text == "Native delivery default."
    assert llm.operations == []
    assert any("native_agent_position=pre_arbitration" in line for line in result.detail_lines)


def test_native_agent_connections_short_circuits_before_arbitration_and_binds_user(tmp_path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.chdir(tmp_path)
    completions = iter([
        _response(tool_calls=[_connections_tool_call()], finish_reason="tool_use"),
        _response(content="Du hast Home Server und Tech News."),
    ])

    async def completion(**kwargs):
        if len(kwargs["messages"]) > 2:
            tool_result = kwargs["messages"][-1]["content"]
            assert '"scope_user_id"' not in tool_result
        return next(completions)

    settings = _settings(native_enabled=True, memory_enabled=False, connections_enabled=True)
    settings.connections.ssh["home-server"] = {"host": "home.local", "title": "Home Server"}
    settings.connections.rss["tech-news"] = {"url": "https://example.test/feed", "title": "Tech News"}
    llm = _LegacyLLM()
    pipeline = Pipeline(settings=settings, prompt_loader=_PromptLoader(), llm_client=llm)
    pipeline.memory_skill = _MemorySkill()
    pipeline._native_agent_completion = completion

    result = asyncio.run(pipeline.process("Welche Verbindungen habe ich?", user_id="u1", source="test"))

    assert result.text == "Du hast Home Server und Tech News."
    assert result.intents == ["connections"]
    assert llm.operations == []
    assert any("native_agent_position=pre_arbitration" in line for line in result.detail_lines)


def test_native_agent_connections_rejects_model_supplied_user_scope(tmp_path) -> None:  # noqa: ANN001
    async def completion(**_kwargs):
        return _response(
            tool_calls=[_connections_tool_call('{"connection_kind":"ssh","user_id":"u2"}')],
            finish_reason="tool_use",
        )

    outcome = asyncio.run(run_native_agent_turn(
        message="Welche Verbindungen hat u2?", user_id="u1", turn_id="model-user-scope",
        llm_config=LLMConfig(model="fake"), tool_bindings=_bindings(memory=False, connection=True),
        completion=completion, trace_root=tmp_path,
    ))

    assert outcome.kind == "fail_closed"
    assert outcome.reason == "native_agent_connection_arguments_invalid"


def test_native_agent_flag_off_returns_honest_degraded_result() -> None:
    class LegacyAnswerLLM(_LegacyLLM):
        async def chat(self, messages, **kwargs):  # noqa: ANN001
            raise AssertionError("precomputed legacy arbitration should not call the LLM")

    pipeline = Pipeline(settings=_settings(native_enabled=False), prompt_loader=_PromptLoader(), llm_client=LegacyAnswerLLM())
    result = asyncio.run(pipeline.process("Hallo", user_id="u1", source="test"))

    assert result.text == "The native agent is disabled for this turn."
    assert result.skill_errors == ["native_agent_disabled"]


def test_native_agent_includes_bounded_recent_history_before_current_message(tmp_path) -> None:
    captured: list[dict] = []
    history = [
        {"role": "system", "text": "discard system"},
        {"role": "tool", "text": "discard tool"},
        {"role": "user", "text": "discarded by last-ten bound"},
        *(
            {"role": "user" if index % 2 == 0 else "assistant", "text": f"history-{index}-" + ("x" * 1600)}
            for index in range(10)
        ),
        {"role": "assistant", "text": "   "},
    ]

    async def completion(**kwargs):
        captured.extend(kwargs["messages"])
        return _response(content="Ja, ich knuepfe an den Vorlauf an.")

    outcome = asyncio.run(run_native_agent_turn(
        message="ja gerne", user_id="u1", turn_id="history-followup",
        llm_config=LLMConfig(model="fake"), tool_bindings=_bindings(),
        recent_history=history, completion=completion, trace_root=tmp_path,
    ))

    assert outcome.kind == "final_answer"
    assert captured[0]["role"] == "system"
    assert captured[-1] == {"role": "user", "content": "ja gerne"}
    assert len(captured) == 12
    assert [row["role"] for row in captured[1:-1]] == [
        "user", "assistant", "user", "assistant", "user",
        "assistant", "user", "assistant", "user", "assistant",
    ]
    assert all(len(row["content"]) == 1500 for row in captured[1:-1])
    assert all("discard" not in row["content"] for row in captured)


def test_native_agent_without_recent_history_keeps_first_turn_messages(tmp_path) -> None:
    captured: list[dict] = []

    async def completion(**kwargs):
        captured.extend(kwargs["messages"])
        return _response(content="Hallo.")

    outcome = asyncio.run(run_native_agent_turn(
        message="Hallo", user_id="u1", turn_id="history-absent",
        llm_config=LLMConfig(model="fake"), tool_bindings=_bindings(),
        completion=completion, trace_root=tmp_path,
    ))

    assert outcome.kind == "final_answer"
    assert [row["role"] for row in captured] == ["system", "user"]
    assert captured[-1]["content"] == "Hallo"


def test_native_agent_drops_confirmation_control_echoes_from_recent_history(tmp_path) -> None:
    captured: list[dict] = []
    history = [
        {"role": "user", "text": "Fuehre SSH Update debsrv-pihole aus"},
        {"role": "assistant", "text": "Soll das Rezept ausgefuehrt werden?"},
        {"role": "user", "text": "confirm action nad05a824c8e25"},
        {"role": "assistant", "text": "Das Rezept wurde ausgefuehrt."},
        {"role": "user", "text": "Run action"},
    ]

    async def completion(**kwargs):
        captured.extend(kwargs["messages"])
        leaked = any("nad05a824c8e25" in str(row.get("content", "")) for row in kwargs["messages"])
        if leaked:
            return _response(tool_calls=[SimpleNamespace(
                id="bad-recipe", function=SimpleNamespace(
                    name="recipes_execute", arguments='{"recipe_id":"nad05a824c8e25"}',
                ),
            )], finish_reason="tool_use")
        return _response(content="Ich versuche das benannte Rezept erneut.")

    outcome = asyncio.run(run_native_agent_turn(
        message="versuch es noch einmal", user_id="u1", turn_id="history-confirm-echo",
        llm_config=LLMConfig(model="fake"), tool_bindings=_bindings(),
        recent_history=history, completion=completion, trace_root=tmp_path,
    ))

    assert outcome.kind == "final_answer"
    assert [row["content"] for row in captured[1:-1]] == [
        "Fuehre SSH Update debsrv-pihole aus",
        "Soll das Rezept ausgefuehrt werden?\n\nDas Rezept wurde ausgefuehrt.",
    ]
