from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from aria.modules.configuration_foundations.config import LLMConfig, MCPServerConfig
from aria.modules.mcp.runtime import MCPClientManager, MCPDiscoveredTool, MCPServerStatus
from aria.modules.native_agent import handler as native_handler
from aria.modules.sdk import NativeToolBinding, NativeToolContext, NativeToolContract, NativeToolResult


def _response(*, content: str = "", tool_calls=(), finish_reason: str = "stop") -> SimpleNamespace:
    return SimpleNamespace(choices=[SimpleNamespace(
        message=SimpleNamespace(content=content, tool_calls=list(tool_calls)),
        finish_reason=finish_reason,
    )])


def _mcp_call() -> SimpleNamespace:
    return SimpleNamespace(
        id="call-blender",
        function=SimpleNamespace(
            name="mcp__blender__execute_blender_code",
            arguments='{"code":"create_blue_cube()"}',
        ),
    )


def _mcp_binding(calls: list[dict[str, str]]) -> NativeToolBinding:
    async def execute(_context: NativeToolContext, arguments) -> NativeToolResult:  # noqa: ANN001
        calls.append(dict(arguments))
        return NativeToolResult(
            '{"status":"ok","result":"blue cube created by Blender"}',
            "mcp__blender__execute_blender_code",
        )

    return NativeToolBinding(NativeToolContract(
        owner_module_id="test",
        name="mcp__blender__execute_blender_code",
        description="Execute test-only Blender code.",
        input_schema={
            "type": "object",
            "properties": {"code": {"type": "string"}},
            "required": ["code"],
        },
        effect="read_only",
        confirmation_required=False,
        source_authority="test:mcp",
        user_scoped=True,
        rollout_flag="test",
    ), execute)


def test_live_action_fabrication_retries_then_uses_real_mcp_tool(tmp_path) -> None:  # noqa: ANN001
    provider_calls: list[dict] = []
    tool_calls: list[dict[str, str]] = []

    async def completion(**kwargs):  # noqa: ANN003
        provider_calls.append(kwargs)
        if len(provider_calls) == 1:
            assert any("roten Wuerfel" in str(row.get("content", "")) for row in kwargs["messages"])
            return _response(content="Ich habe einen blauen Würfel neben dem roten Würfel erstellt.")
        if len(provider_calls) == 2:
            assert any(
                "You claimed to have performed an action" in str(row.get("content", ""))
                for row in kwargs["messages"]
            )
            return _response(tool_calls=(_mcp_call(),), finish_reason="tool_use")
        assert "blue cube created by Blender" in kwargs["messages"][-1]["content"]
        return _response(content="Blender hat den blauen Würfel erstellt.")

    outcome = asyncio.run(native_handler.run_native_agent_turn(
        message="Baue einen blauen Würfel in Blender.",
        user_id="alice",
        turn_id="action-fabrication-recovery",
        llm_config=LLMConfig(model="fake"),
        tool_bindings=(_mcp_binding(tool_calls),),
        recent_history=[
            {"role": "user", "text": "Baue einen roten Wuerfel."},
            {"role": "assistant", "text": "Der rote Wuerfel wurde erstellt."},
        ],
        completion=completion,
        trace_root=tmp_path,
    ))

    assert outcome.kind == "final_answer"
    assert outcome.message == "Blender hat den blauen Würfel erstellt."
    assert outcome.used_tool_names == ("mcp__blender__execute_blender_code",)
    assert outcome.reason == "native_agent_action_claim_retry"
    assert outcome.provider_calls == 3
    assert tool_calls == [{"code": "create_blue_cube()"}]


@pytest.mark.parametrize(
    ("message", "fabrication", "expected"),
    [
        (
            "Baue einen blauen Würfel.",
            "Ich habe einen blauen Würfel erstellt.",
            "Ich habe diese Aktion NICHT ausgeführt – in diesem Schritt wurde kein Werkzeug aufgerufen. Bitte versuche es erneut.",
        ),
        (
            "Build a blue cube.",
            "I have created a blue cube.",
            "I did NOT perform this action - no tool was called in this step. Please try again.",
        ),
    ],
)
def test_persistent_action_fabrication_returns_localized_refusal(
    tmp_path, message: str, fabrication: str, expected: str,
) -> None:  # noqa: ANN001
    calls = 0

    async def completion(**_kwargs):  # noqa: ANN003
        nonlocal calls
        calls += 1
        return _response(content=fabrication)

    outcome = asyncio.run(native_handler.run_native_agent_turn(
        message=message,
        user_id="alice",
        turn_id="persistent-action-fabrication",
        llm_config=LLMConfig(model="fake"),
        tool_bindings=(_mcp_binding([]),),
        completion=completion,
        trace_root=tmp_path,
    ))

    assert calls == 2
    assert outcome.kind == "final_answer"
    assert outcome.message == expected
    assert fabrication not in outcome.message
    assert outcome.reason == "native_agent_action_claim_blocked"
    assert outcome.used_tool_names == ()


def test_unanchored_recap_retries_once_and_anchored_recap_passes(tmp_path) -> None:  # noqa: ANN001
    calls = 0

    async def completion(**kwargs):  # noqa: ANN003
        nonlocal calls
        calls += 1
        if calls == 1:
            return _response(content="Ich habe einen roten Würfel gebaut.")
        assert any("only recapping an action from an earlier turn" in str(row.get("content", "")) for row in kwargs["messages"])
        return _response(content="Vorhin habe ich einen roten Würfel gebaut.")

    outcome = asyncio.run(native_handler.run_native_agent_turn(
        message="Was hast du gerade gebaut?",
        user_id="alice",
        turn_id="anchored-recap-retry",
        llm_config=LLMConfig(model="fake"),
        tool_bindings=(_mcp_binding([]),),
        completion=completion,
        trace_root=tmp_path,
    ))

    assert calls == 2
    assert outcome.message == "Vorhin habe ich einen roten Würfel gebaut."
    assert outcome.reason == "native_agent_action_claim_retry"


@pytest.mark.parametrize(
    "answer",
    [
        "Vorhin habe ich einen roten Würfel gebaut.",
        "Im vorherigen Schritt habe ich den Würfel erstellt.",
        "Im Hintergrund-Auftrag wurde der Würfel erstellt.",
        "Earlier, I created a red cube.",
        "In the previous turn, the cube was created.",
        "In the background job, I built the scene.",
    ],
)
def test_already_anchored_recap_passes_without_retry(tmp_path, answer: str) -> None:  # noqa: ANN001
    calls = 0

    async def completion(**_kwargs):  # noqa: ANN003
        nonlocal calls
        calls += 1
        return _response(content=answer)

    outcome = asyncio.run(native_handler.run_native_agent_turn(
        message="Recap the action.", user_id="alice", turn_id="anchored-recap",
        llm_config=LLMConfig(model="fake"), tool_bindings=(_mcp_binding([]),),
        completion=completion, trace_root=tmp_path,
    ))

    assert calls == 1
    assert outcome.message == answer
    assert outcome.reason == ""


@pytest.mark.parametrize(
    "text",
    [
        "Ich habe den Würfel nicht erstellt.",
        "Ich habe keinen Würfel gelöscht.",
        "Nie habe ich die Datei entfernt.",
        "Soll ich einen Würfel erstellen?",
        "Kann ich den Würfel bauen?",
        "Ich würde den Würfel erstellen.",
        "Erstelle den Würfel in Blender.",
        "Hier ist Beispielcode:\n```python\nprint('I have created the cube')\n```",
        "I have not created the cube.",
        "I never deleted the cube.",
        "I couldn't create the cube.",
        "Would you like me to create it?",
        "Can I build the cube?",
        "Create the cube in Blender.",
        "Use `print('I created the cube')` in the example.",
    ],
)
def test_action_claim_detector_ignores_negation_offers_instructions_and_code(text: str) -> None:
    assert native_handler._looks_like_unsourced_action_claim(text) is False


@pytest.mark.parametrize(
    "text",
    [
        "Ich habe den Würfel erstellt.",
        "Habe ich den Würfel erfolgreich gebaut.",
        "Die Datei wurde gelöscht.",
        "Die Objekte wurden erfolgreich platziert.",
        "Die Konfiguration ist jetzt aktualisiert.",
        "I've created the cube.",
        "I have renamed the object.",
        "I ran the command.",
        "The object has been placed.",
        "The files were successfully removed.",
    ],
)
def test_action_claim_detector_matches_assertive_de_and_en_completion(text: str) -> None:
    assert native_handler._looks_like_unsourced_action_claim(text) is True


def test_tool_backed_action_claim_is_unchanged(tmp_path) -> None:  # noqa: ANN001
    provider_calls = 0
    tool_calls: list[dict[str, str]] = []

    async def completion(**_kwargs):  # noqa: ANN003
        nonlocal provider_calls
        provider_calls += 1
        if provider_calls == 1:
            return _response(tool_calls=(_mcp_call(),), finish_reason="tool_use")
        return _response(content="Ich habe den Würfel erstellt.")

    outcome = asyncio.run(native_handler.run_native_agent_turn(
        message="Baue einen Würfel.", user_id="alice", turn_id="tool-backed-action",
        llm_config=LLMConfig(model="fake"), tool_bindings=(_mcp_binding(tool_calls),),
        completion=completion, trace_root=tmp_path,
    ))

    assert provider_calls == 2
    assert outcome.message == "Ich habe den Würfel erstellt."
    assert outcome.reason == ""
    assert len(tool_calls) == 1


def test_resource_and_action_guards_have_independent_one_shot_budget(tmp_path) -> None:  # noqa: ANN001
    answers = iter((
        "Die Datei /tmp/demo enthaelt erfundene Daten.",
        "Ich habe den Würfel erstellt.",
        "Ich habe weder eine Datei gelesen noch eine Aktion ausgeführt.",
    ))
    calls = 0

    async def completion(**_kwargs):  # noqa: ANN003
        nonlocal calls
        calls += 1
        return _response(content=next(answers))

    outcome = asyncio.run(native_handler.run_native_agent_turn(
        message="Prüfe und handle.", user_id="alice", turn_id="independent-guards",
        llm_config=LLMConfig(model="fake"), tool_bindings=(_mcp_binding([]),),
        completion=completion, trace_root=tmp_path, max_steps=1, max_provider_calls=3,
    ))

    assert calls == 3
    assert outcome.kind == "final_answer"
    assert outcome.message == "Ich habe weder eine Datei gelesen noch eine Aktion ausgeführt."
    assert outcome.reason == "native_agent_action_claim_retry"


def _server() -> MCPServerConfig:
    return MCPServerConfig.model_validate({
        "transport": "sse", "url": "https://private.invalid/events", "enabled": True,
    })


@pytest.mark.parametrize(
    ("exc", "error"),
    [
        (ConnectionError("bridge down"), "ConnectionError"),
        (asyncio.TimeoutError(), "TimeoutError"),
        (RuntimeError("mcp_session_closed"), "mcp_session_closed"),
    ],
)
def test_mcp_transport_call_failure_marks_status_unreachable_and_enters_cooldown(
    monkeypatch, exc: Exception, error: str,
) -> None:
    now = [100.0]
    manager = MCPClientManager({"blender": _server()}, clock=lambda: now[0])
    manager._discovery["blender"] = (MCPDiscoveredTool(
        server_name="blender", remote_name="inspect", description="",
        input_schema={"type": "object"}, annotations={}, read_only=True,
    ),)
    manager._statuses["blender"] = MCPServerStatus("blender", True, 1)

    async def fail(*_args, **_kwargs):  # noqa: ANN002, ANN003
        raise exc

    monkeypatch.setattr(manager, "_run_server_operation", fail)

    async def scenario() -> None:
        result = await manager._call_remote("blender", "inspect", {}, intent="inspect")
        assert result.content == '{"error":"mcp_call_failed","status":"error"}'
        assert manager.statuses() == (MCPServerStatus("blender", False, 0, error),)
        assert manager._failure_at["blender"] == 100.0
        snapshot = await manager.discover_all(block_cold=True)
        assert snapshot["blender"] == ()
        assert manager.statuses()[0].connected is False

    asyncio.run(scenario())


def test_mcp_remote_tool_error_keeps_server_connected(monkeypatch) -> None:
    manager = MCPClientManager({"blender": _server()}, clock=lambda: 100.0)
    manager._statuses["blender"] = MCPServerStatus("blender", True, 2)

    async def remote_error(*_args, **_kwargs):  # noqa: ANN002, ANN003
        return SimpleNamespace(is_error=True, content=[{"type": "text", "text": "invalid scene"}])

    monkeypatch.setattr(manager, "_run_server_operation", remote_error)

    async def scenario() -> None:
        result = await manager._call_remote("blender", "inspect", {}, intent="inspect")
        assert '"error":"mcp_tool_error"' in result.content
        assert manager.statuses() == (MCPServerStatus("blender", True, 2),)
        assert "blender" not in manager._failure_at

    asyncio.run(scenario())
