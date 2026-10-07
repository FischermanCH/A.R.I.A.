from __future__ import annotations

import asyncio
import base64
from contextlib import asynccontextmanager
import json
from pathlib import Path
from types import SimpleNamespace

from mcp.types import AudioContent, ImageContent, TextContent
import pytest

from aria.modules.configuration_foundations.config import AgenticLoopFeatureConfig, LLMConfig, MCPServerConfig
from aria.modules.mcp.runtime import MCPClientManager
from aria.modules.native_agent import handler as native_handler
from aria.modules.native_agent import pipeline_bridge
from aria.modules.sdk import NativeToolBinding, NativeToolContext, NativeToolContract, NativeToolResult


PNG = base64.b64encode(b"\x89PNG\r\n\x1a\naria-test-png").decode("ascii")
WEBP = base64.b64encode(b"RIFF\x10\x00\x00\x00WEBPVP8 aria-test-webp").decode("ascii")


def _response(*, content: str = "", tool_calls=(), finish_reason: str = "stop") -> SimpleNamespace:
    return SimpleNamespace(choices=[SimpleNamespace(
        message=SimpleNamespace(content=content, tool_calls=list(tool_calls)),
        finish_reason=finish_reason,
    )])


def _call(name: str, call_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments="{}"),
    )


def _binding(name: str, *, images: tuple[tuple[str, str], ...]) -> NativeToolBinding:
    async def execute(_context: NativeToolContext, _arguments) -> NativeToolResult:  # noqa: ANN001
        content = json.dumps({
            "status": "ok",
            "content": [
                {
                    "type": "image",
                    "mime_type": mime_type,
                    "omitted": True,
                    "note": "Image returned by the tool; it is NOT visible to you. Do not describe its contents.",
                }
                for mime_type, _data in images
            ],
        }, sort_keys=True)
        return NativeToolResult(content, name, images=images)

    return NativeToolBinding(NativeToolContract(
        owner_module_id="mcp", name=name, description="Return a test image.",
        input_schema={"type": "object", "properties": {}, "required": []},
        effect="read_only", confirmation_required=False,
        source_authority="mcp:test:tools/call", user_scoped=True,
        rollout_flag="native_agent_mcp_enabled",
    ), execute)


class _ImageSession:
    async def initialize(self) -> None:
        return None

    async def call_tool(self, _name: str, _arguments: dict) -> SimpleNamespace:
        oversized = "A" * (3_500_001)
        return SimpleNamespace(
            is_error=False,
            content=[
                TextContent(text="viewport"),
                ImageContent(data=PNG, mimeType="image/png"),
                ImageContent(data=WEBP, mimeType="image/webp"),
                ImageContent(data=PNG, mimeType="image/png"),
                ImageContent(data=PNG, mimeType="image/svg+xml"),
                ImageContent(data=oversized, mimeType="image/jpeg"),
                AudioContent(data=PNG, mimeType="audio/wav"),
            ],
            structured_content=None,
        )


@asynccontextmanager
async def _session_factory(_name: str, _config: MCPServerConfig):
    yield _ImageSession()


def test_mcp_result_projects_two_supported_images_and_placeholders_without_base64() -> None:
    manager = MCPClientManager({
        "blender": MCPServerConfig(url="https://invalid.test/sse", enabled=True),
    }, session_factory=_session_factory)

    result = asyncio.run(manager._call_remote("blender", "look", {}, intent="mcp__blender__look"))
    payload = json.loads(result.content)

    assert result.images == (("image/png", PNG), ("image/webp", WEBP))
    assert payload["content"][0] == {"text": "viewport", "type": "text"}
    assert sum(row.get("omitted") is True for row in payload["content"][1:]) == 6
    assert PNG not in result.content
    assert "image/svg+xml" not in result.content
    assert result.content.count('"mime_type":"image/png"') >= 2
    assert "audio/wav" in result.content


def test_native_loop_attaches_real_images_with_turn_bound_and_keeps_observability_clean(
    tmp_path: Path,
) -> None:
    calls: list[dict] = []
    bindings = tuple(
        _binding(f"mcp__test__image_{index}", images=(("image/png", PNG), ("image/webp", WEBP)))
        for index in range(3)
    )

    async def completion(**kwargs):  # noqa: ANN003, ANN202
        calls.append(kwargs)
        if len(calls) == 1:
            return _response(
                tool_calls=tuple(_call(binding.contract.name, f"call-{index}") for index, binding in enumerate(bindings)),
                finish_reason="tool_use",
            )
        return _response(content="I can see the attached viewport images.")

    checkpoints: list[str] = []

    async def checkpoint(_index: int, _tools, summary: str) -> None:  # noqa: ANN001
        checkpoints.append(summary)

    outcome = asyncio.run(native_handler.run_native_agent_turn(
        message="Look at the viewport.", user_id="alice", turn_id="vision-turn",
        llm_config=LLMConfig(model="claude-sonnet-4-5"), tool_bindings=bindings,
        completion=completion, trace_root=tmp_path, step_callback=checkpoint,
        mcp_vision_enabled=True,
    ))

    tool_messages = [row for row in calls[1]["messages"] if row.get("role") == "tool"]
    image_blocks = [
        block
        for row in tool_messages
        for block in row["content"] if isinstance(row["content"], list)
        if block.get("type") == "image_url"
    ]
    assert len(image_blocks) == 4
    assert all(block["image_url"]["url"].startswith("data:image/") for block in image_blocks)
    text_blocks = [
        row["content"][0]["text"] if isinstance(row["content"], list) else row["content"]
        for row in tool_messages
    ]
    assert all(PNG not in text and WEBP not in text for text in text_blocks)
    assert sum(text.count('"attached": true') for text in text_blocks) == 4
    assert outcome.mcp_vision_images == 4
    assert outcome.mcp_vision_bytes == 2 * len(PNG) + 2 * len(WEBP)
    assert all(PNG not in summary and WEBP not in summary for summary in checkpoints)
    trace_text = (tmp_path / "vision-turn.jsonl").read_text(encoding="utf-8")
    assert PNG not in trace_text
    assert WEBP not in trace_text


def test_vision_flag_and_model_gate_keep_placeholder_path(tmp_path: Path) -> None:
    async def run(model: str, enabled: bool) -> list[dict]:
        calls: list[dict] = []

        async def completion(**kwargs):  # noqa: ANN003, ANN202
            calls.append(kwargs)
            if len(calls) == 1:
                return _response(tool_calls=(_call("mcp__test__look", "look"),), finish_reason="tool_use")
            return _response(content="No image claim.")

        outcome = await native_handler.run_native_agent_turn(
            message="Look.", user_id="alice", turn_id=f"gate-{model}-{enabled}",
            llm_config=LLMConfig(model=model),
            tool_bindings=(_binding("mcp__test__look", images=(("image/png", PNG),)),),
            completion=completion, trace_root=tmp_path, mcp_vision_enabled=enabled,
        )
        assert outcome.mcp_vision_images == 0
        return calls

    for model, enabled in (("gpt-test", True), ("claude-sonnet-4-5", False)):
        calls = asyncio.run(run(model, enabled))
        tool_message = next(row for row in calls[1]["messages"] if row.get("role") == "tool")
        rendered = json.dumps(tool_message["content"], sort_keys=True)
        assert "image_url" not in rendered
        assert "NOT visible" in rendered
        assert PNG not in rendered


def test_cacheable_request_marks_text_not_image_and_keeps_three_breakpoints() -> None:
    messages, tools = native_handler._cacheable_request(
        model="claude-sonnet-4-5",
        messages=(
            {"role": "system", "content": "system"},
            {"role": "tool", "tool_call_id": "call", "content": [
                {"type": "text", "text": "result"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,aA=="}},
            ]},
        ),
        tools=({"name": "tool", "description": "tool", "input_schema": {"type": "object"}},),
    )

    assert messages[-1]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}
    assert "cache_control" not in messages[-1]["content"][0]
    assert "cache_control" not in messages[-1]["content"][1]

    def count(value) -> int:  # noqa: ANN001
        if isinstance(value, dict):
            return int("cache_control" in value) + sum(count(item) for item in value.values())
        if isinstance(value, (list, tuple)):
            return sum(count(item) for item in value)
        return 0

    assert count(messages) + count(tools) == 3


def test_pipeline_vision_details_footer_dedupe_and_history_strip(monkeypatch, tmp_path: Path) -> None:
    footer = "⚠️ Der MCP-Server blender ist gerade nicht erreichbar (TimeoutError). [Neu verbinden](/config/connections/mcp)"
    captured_history: list[dict] = []

    class DownManager:
        async def discover_all(self, **_kwargs):  # noqa: ANN202
            return {"blender": ()}

        def statuses(self):  # noqa: ANN201
            return (SimpleNamespace(server_name="blender", connected=False, tool_count=0, error="TimeoutError"),)

    async def fake_turn(**kwargs):  # noqa: ANN003, ANN202
        captured_history.extend(kwargs["recent_history"])
        assert kwargs["mcp_vision_enabled"] is True
        return native_handler.NativeAgentOutcome(
            "final_answer", f"Nicht erreichbar.\n\n{footer}", 1,
            mcp_vision_images=1, mcp_vision_bytes=8, mcp_vision_degraded=True,
        )

    owner = SimpleNamespace(
        settings=SimpleNamespace(
            agentic_loop=SimpleNamespace(
                enabled=True, native_agent_mcp_enabled=True,
                native_agent_mcp_vision_enabled=True, native_tool_selector_top_k=16,
                native_agent_max_steps=16, native_agent_max_provider_calls=16,
                native_agent_memory_learn_enabled=False, native_web_debug_details=False,
            ),
            llm=SimpleNamespace(model="claude-sonnet-4-5"), _aria_usage_meter=None,
        ),
        _native_mcp_client=DownManager(), _native_tool_relevance_selector=None,
        _native_agent_completion=None, _project_root=tmp_path,
        _load_stored_recipe_runtime=lambda: (), usage_meter=None, embedding_client=None,
    )
    monkeypatch.setattr(pipeline_bridge, "assemble_native_tools", lambda *_args, **_kwargs: ())
    monkeypatch.setattr(pipeline_bridge, "filter_tools_by_configured_connections", lambda rows, _settings: rows)
    monkeypatch.setattr(pipeline_bridge, "run_native_agent_turn", fake_turn)

    result = asyncio.run(pipeline_bridge.run_native_agent_first_stage(
        owner, message="Blender prüfen", user_id="alice", request_id="vision-detail",
        source="test", start=0.0, language="de",
        recent_history=[
            {"role": "user", "text": "Blender prüfen"},
            {"role": "assistant", "text": f"Keine Verbindung.\n\n{footer}"},
        ],
    ))

    assert result is not None
    assert result.text.count("⚠️ Der MCP-Server blender") == 1
    assert all("⚠️ Der MCP-Server" not in row["text"] for row in captured_history if row["role"] == "assistant")
    assert "Routing Debug: mcp_vision images=1 live=0 replaced=0 bytes=8" in result.detail_lines
    assert "Routing Debug: mcp_vision degraded=provider_rejected_image" in result.detail_lines


def test_recap_anchors_history_support_and_negation_scope(tmp_path: Path) -> None:
    assert native_handler._looks_like_unsourced_action_claim(
        "Ich habe einen blauen Würfel erstellt, keine weiteren Änderungen."
    ) is True
    assert native_handler._looks_like_unsourced_action_claim("Ich habe den Würfel nicht erstellt.") is False
    assert native_handler._looks_like_unsourced_action_claim("Ich konnte den Würfel nicht erstellen.") is False
    assert native_handler._looks_like_unsourced_action_claim("In diesem Chat habe ich einen Würfel erstellt.") is False

    answers = iter((
        "Ich habe einen roten Würfel gebaut.",
        "Ich habe einen roten Würfel gebaut.",
    ))
    calls: list[dict] = []

    async def completion(**kwargs):  # noqa: ANN003, ANN202
        calls.append(kwargs)
        return _response(content=next(answers))

    outcome = asyncio.run(native_handler.run_native_agent_turn(
        message="Was hast du gebaut?", user_id="alice", turn_id="history-recap",
        llm_config=LLMConfig(model="fake"),
        tool_bindings=(_binding("mcp__test__noop", images=()),),
        recent_history=[
            {"role": "user", "text": "Baue einen roten Würfel."},
            {"role": "assistant", "text": "Der rote Würfel wurde erstellt."},
        ],
        completion=completion, trace_root=tmp_path,
    ))

    assert len(calls) == 2
    assert "literal word 'Vorhin'" in str(calls[1]["messages"][-1]["content"])
    assert outcome.message == "Ich habe einen roten Würfel gebaut."
    assert outcome.reason == "native_agent_action_claim_retry"

    unsupported_answers = iter((
        "Ich habe einen blauen Würfel gebaut.",
        "Ich habe einen blauen Würfel gebaut.",
    ))

    async def unsupported(**_kwargs):  # noqa: ANN003, ANN202
        return _response(content=next(unsupported_answers))

    blocked = asyncio.run(native_handler.run_native_agent_turn(
        message="Baue einen blauen Würfel?", user_id="alice", turn_id="unsupported-recap",
        llm_config=LLMConfig(model="fake"),
        tool_bindings=(_binding("mcp__test__noop", images=()),),
        recent_history=[
            {"role": "user", "text": "Baue einen roten Würfel."},
            {"role": "assistant", "text": "Der rote Würfel wurde erstellt."},
        ],
        completion=unsupported, trace_root=tmp_path,
    ))
    assert blocked.reason == "native_agent_action_claim_blocked"
    assert "NICHT ausgeführt" in blocked.message


@pytest.mark.parametrize("anchor", [
    "in diesem Chat", "in diesem Gespräch", "in unserem Gespräch", "bisher", "bislang",
    "heute", "insgesamt", "in den letzten Schritten", "in this chat", "in this conversation",
    "so far", "today", "in total",
])
def test_recap_anchor_vocabulary_is_not_treated_as_current_turn_claim(anchor: str) -> None:
    assert native_handler._looks_like_unsourced_action_claim(
        f"{anchor} habe ich einen Würfel erstellt."
    ) is False


def test_vision_flag_defaults_true() -> None:
    assert AgenticLoopFeatureConfig().native_agent_mcp_vision_enabled is True
