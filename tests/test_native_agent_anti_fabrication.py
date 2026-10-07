from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from aria.modules.configuration_foundations.config import LLMConfig
from aria.modules.native_agent import handler as native_handler
from aria.modules.sdk import NativeToolBinding, NativeToolContext, NativeToolContract, NativeToolResult


def _response(*, content: str = "", tool_calls=(), finish_reason: str = "stop") -> SimpleNamespace:
    return SimpleNamespace(choices=[SimpleNamespace(
        message=SimpleNamespace(content=content, tool_calls=list(tool_calls)),
        finish_reason=finish_reason,
    )])


def _file_read_call() -> SimpleNamespace:
    return SimpleNamespace(
        id="call-file-read",
        function=SimpleNamespace(
            name="file_read",
            arguments='{"connection_kind":"sftp","connection_ref":"files","path":"/host.conf"}',
        ),
    )


def _file_read_binding(calls: list[dict[str, str]]) -> NativeToolBinding:
    async def read_file(_context: NativeToolContext, arguments) -> NativeToolResult:  # noqa: ANN001
        calls.append(dict(arguments))
        return NativeToolResult(
            '{"status":"ok","path":"/host.conf","content":"authoritative=true"}',
            "file_read",
        )

    return NativeToolBinding(NativeToolContract(
        owner_module_id="test",
        name="file_read",
        description="Read an exact file.",
        input_schema={
            "type": "object",
            "properties": {
                "connection_kind": {"type": "string"},
                "connection_ref": {"type": "string"},
                "path": {"type": "string"},
            },
            "required": ["connection_kind", "connection_ref", "path"],
        },
        effect="read_only",
        confirmation_required=False,
        source_authority="test:file",
        user_scoped=True,
        rollout_flag="test",
    ), read_file)


def test_unsourced_resource_claim_retries_once_then_uses_real_read(tmp_path) -> None:  # noqa: ANN001
    provider_calls: list[dict] = []
    read_calls: list[dict[str, str]] = []

    async def completion(**kwargs):  # noqa: ANN003
        provider_calls.append(kwargs)
        if len(provider_calls) == 1:
            return _response(content="Die Datei /host.conf enthaelt fabricated=true.")
        if len(provider_calls) == 2:
            assert any(
                "You presented the content/output/status of a resource without calling any tool this turn"
                in str(row.get("content", ""))
                for row in kwargs["messages"]
            )
            return _response(tool_calls=(_file_read_call(),), finish_reason="tool_use")
        assert "authoritative=true" in kwargs["messages"][-1]["content"]
        return _response(content="Die Datei /host.conf enthaelt authoritative=true.")

    outcome = asyncio.run(native_handler.run_native_agent_turn(
        message="Was steht in /host.conf?",
        user_id="alice",
        turn_id="anti-fabrication-recovery",
        llm_config=LLMConfig(model="fake"),
        tool_bindings=(_file_read_binding(read_calls),),
        completion=completion,
        trace_root=tmp_path,
    ))

    assert outcome.kind == "final_answer"
    assert outcome.message == "Die Datei /host.conf enthaelt authoritative=true."
    assert "fabricated=true" not in outcome.message
    assert outcome.used_tool_names == ("file_read",)
    assert outcome.provider_calls == 3
    assert len(read_calls) == 1


@pytest.mark.parametrize(
    ("message", "fabrication", "expected"),
    [
        (
            "Was steht in /host.conf?",
            "Der Inhalt der Datei /host.conf ist fabricated=true.",
            "Ich kann den Inhalt gerade nicht ueber ein Werkzeug abrufen und gebe keine erfundenen Daten aus - bitte versuch es erneut.",
        ),
        (
            "What is in /host.conf?",
            "The content of the file /host.conf is fabricated=true.",
            "I cannot retrieve the content through a tool right now and will not provide fabricated data - please try again.",
        ),
    ],
)
def test_persistent_unsourced_resource_claim_returns_localized_refusal(
    tmp_path, message: str, fabrication: str, expected: str,
) -> None:  # noqa: ANN001
    calls = 0
    read_calls: list[dict[str, str]] = []

    async def completion(**_kwargs):  # noqa: ANN003
        nonlocal calls
        calls += 1
        return _response(content=fabrication)

    outcome = asyncio.run(native_handler.run_native_agent_turn(
        message=message,
        user_id="alice",
        turn_id=f"persistent-{calls}",
        llm_config=LLMConfig(model="fake"),
        tool_bindings=(_file_read_binding(read_calls),),
        completion=completion,
        trace_root=tmp_path,
    ))

    assert calls == 2
    assert outcome.kind == "final_answer"
    assert outcome.message == expected
    assert "fabricated=true" not in outcome.message
    assert outcome.used_tool_names == ()
    assert outcome.provider_calls == 2


@pytest.mark.parametrize(
    "text",
    [
        "Hallo! Wie kann ich dir helfen?",
        "Was ist der Inhalt der Datei /host.conf?",
        "Which directory contains the generated script?",
        "Hier ist ein Bash-Script:\n```bash\necho 'the file /tmp/x contains demo'\n```",
        "Use `echo 'directory contains demo'` in your generated script.",
    ],
)
def test_unsourced_resource_claim_detector_ignores_conversation_and_code(text: str) -> None:
    assert native_handler._looks_like_unsourced_resource_claim(text) is False


@pytest.mark.parametrize(
    "text",
    [
        "Inhalt der Datei /host.conf: fabricated=true",
        "Ausgabe des Befehls uname -a: Linux host",
        "Die Datei /host.conf enthaelt fabricated=true.",
        "Status von srv-a ist online.",
        "Das Verzeichnis enthaelt drei Dateien.",
        "Content of the file /host.conf: fabricated=true",
        "Output of the command uname -a: Linux host",
        "The file /host.conf contains fabricated=true.",
        "Status of srv-a is online.",
        "The directory contains three files.",
    ],
)
def test_unsourced_resource_claim_detector_matches_only_assertive_resource_phrases(text: str) -> None:
    assert native_handler._looks_like_unsourced_resource_claim(text) is True


def test_normal_tool_backed_read_is_unchanged(tmp_path) -> None:  # noqa: ANN001
    provider_calls = 0
    read_calls: list[dict[str, str]] = []

    async def completion(**kwargs):  # noqa: ANN003
        nonlocal provider_calls
        provider_calls += 1
        if provider_calls == 1:
            return _response(tool_calls=(_file_read_call(),), finish_reason="tool_use")
        assert "authoritative=true" in kwargs["messages"][-1]["content"]
        return _response(content="The file /host.conf contains authoritative=true.")

    outcome = asyncio.run(native_handler.run_native_agent_turn(
        message="Read /host.conf.",
        user_id="alice",
        turn_id="normal-read",
        llm_config=LLMConfig(model="fake"),
        tool_bindings=(_file_read_binding(read_calls),),
        completion=completion,
        trace_root=tmp_path,
    ))

    assert outcome.kind == "final_answer"
    assert outcome.message == "The file /host.conf contains authoritative=true."
    assert outcome.used_tool_names == ("file_read",)
    assert outcome.provider_calls == 2
    assert len(read_calls) == 1


@pytest.mark.parametrize(
    "answer",
    [
        "Hallo! Wie kann ich dir helfen?",
        "Hier ist ein Bash-Script:\n```bash\nprintf '%s\\n' hello\n```",
    ],
)
def test_no_tool_conversation_and_code_return_unchanged(tmp_path, answer: str) -> None:  # noqa: ANN001
    calls = 0
    read_calls: list[dict[str, str]] = []

    async def completion(**_kwargs):  # noqa: ANN003
        nonlocal calls
        calls += 1
        return _response(content=answer)

    outcome = asyncio.run(native_handler.run_native_agent_turn(
        message="Antworte direkt.",
        user_id="alice",
        turn_id=f"normal-no-tool-{calls}",
        llm_config=LLMConfig(model="fake"),
        tool_bindings=(_file_read_binding(read_calls),),
        completion=completion,
        trace_root=tmp_path,
    ))

    assert calls == 1
    assert outcome.kind == "final_answer"
    assert outcome.message == answer
    assert outcome.used_tool_names == ()
    assert read_calls == []


def test_prompt_requires_fresh_tool_for_known_default_and_prior_resource_content(tmp_path) -> None:  # noqa: ANN001
    captured = ""
    read_calls: list[dict[str, str]] = []

    async def completion(**kwargs):  # noqa: ANN003
        nonlocal captured
        captured = str(kwargs["messages"][0]["content"])
        return _response(content="I cannot access that resource right now.")

    outcome = asyncio.run(native_handler.run_native_agent_turn(
        message="Can you read that resource?",
        user_id="alice",
        turn_id="prompt-fresh-resource",
        llm_config=LLMConfig(model="fake"),
        tool_bindings=(_file_read_binding(read_calls),),
        completion=completion,
        trace_root=tmp_path,
    ))

    assert outcome.kind == "final_answer"
    assert "ALWAYS requires a fresh tool call in this turn" in captured
    assert "well-known or default content" in captured
    assert "similar resources were read before" in captured
    assert "memory, defaults or earlier turns" in captured
