from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from aria.modules.configuration_foundations.config import LLMConfig
from aria.modules.mcp.runtime import _project_tool_content
from aria.modules.native_agent.handler import run_native_agent_turn
from aria.modules.pipeline_contracts.result import PipelineResult
from aria.modules.pipeline_orchestrator.agent_jobs import AgentJobStore
from aria.modules.pipeline_orchestrator.pipeline import Pipeline
import aria.modules.pipeline_orchestrator.pipeline as pipeline_module
from aria.modules.sdk import NativeToolBinding, NativeToolContext, NativeToolContract, NativeToolResult
from e2e.strict_anthropic import validate_anthropic_request


IMAGE_BYTES = {
    "image/png": b"\x89PNG\r\n\x1a\n" + b"png-payload",
    "image/jpeg": b"\xff\xd8\xff" + b"jpeg-payload",
    "image/gif": b"GIF89a" + b"gif-payload",
    "image/webp": b"RIFF\x10\x00\x00\x00WEBPVP8 " + b"webp-payload",
}


def _encoded(mime_type: str) -> str:
    return base64.b64encode(IMAGE_BYTES[mime_type]).decode("ascii")


@pytest.mark.parametrize("mime_type", tuple(IMAGE_BYTES))
def test_mcp_image_projection_sniffs_each_supported_magic_type(mime_type: str) -> None:
    data = _encoded(mime_type)
    projected, images = _project_tool_content(({
        "type": "image", "mimeType": mime_type, "data": data,
    },))

    assert images == ((mime_type, data),)
    assert projected[0]["mime_type"] == mime_type


def test_mcp_image_projection_corrects_exact_live_webp_declared_as_png() -> None:
    data = _encoded("image/webp")
    projected, images = _project_tool_content(({
        "type": "image", "mimeType": "image/png", "data": data,
    },))

    assert images == (("image/webp", data),)
    assert projected == [{
        "type": "image",
        "mime_type": "image/webp",
        "omitted": True,
        "note": "Image returned by the tool; it is NOT visible to you. Do not describe its contents.",
    }]


def test_mcp_image_projection_unknown_bytes_stay_placeholder_only() -> None:
    data = base64.b64encode(b"not-a-supported-image").decode("ascii")
    projected, images = _project_tool_content(({
        "type": "image", "mimeType": "image/png", "data": data,
    },))

    assert images == ()
    assert projected[0]["omitted"] is True
    assert projected[0]["mime_type"] == "image/png"


def _response(*, content: str = "", tool_calls: tuple[object, ...] = ()) -> SimpleNamespace:
    return SimpleNamespace(choices=[SimpleNamespace(
        message=SimpleNamespace(content=content, tool_calls=list(tool_calls)),
        finish_reason="tool_use" if tool_calls else "stop",
    )])


def _call(name: str, call_id: str = "call-image") -> SimpleNamespace:
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments="{}"),
    )


def _image_binding() -> NativeToolBinding:
    data = _encoded("image/webp")

    async def execute(_context: NativeToolContext, _arguments: object) -> NativeToolResult:
        content = json.dumps({
            "status": "ok",
            "content": [{
                "type": "image", "mime_type": "image/webp", "omitted": True,
                "note": "Image returned by the tool; it is NOT visible to you. Do not describe its contents.",
            }],
        }, sort_keys=True)
        return NativeToolResult(content, "mcp__blender__search_assets", images=(("image/webp", data),))

    return NativeToolBinding(
        NativeToolContract(
            owner_module_id="mcp",
            name="mcp__blender__search_assets",
            description="Search Poly Haven assets.",
            input_schema={"type": "object", "properties": {}, "required": []},
            effect="read_only",
            confirmation_required=False,
            source_authority="mcp:blender:tools/call",
            user_scoped=True,
            rollout_flag="native_agent_mcp_enabled",
        ),
        execute,
    )


class _Provider400(RuntimeError):
    status_code = 400


LIVE_IMAGE_ERROR = (
    "messages.4.content.1.tool_result.content.1.image.source.base64: "
    "The image was specified using the image/png media type, but the image appears to be a image/webp image"
)


def _has_image(messages: object) -> bool:
    return "image_url" in json.dumps(messages, sort_keys=True)


def test_image_400_retries_same_call_once_without_images_and_completes(tmp_path: Path) -> None:
    requests: list[list[dict]] = []

    async def completion(**kwargs):  # noqa: ANN003, ANN202
        rows = list(kwargs["messages"])
        requests.append(rows)
        if len(requests) == 1:
            return _response(tool_calls=(_call("mcp__blender__search_assets"),))
        if len(requests) == 2:
            assert _has_image(rows)
            raise _Provider400(LIVE_IMAGE_ERROR)
        assert not _has_image(rows)
        return _response(content="Asset search completed without visual inspection.")

    outcome = asyncio.run(run_native_agent_turn(
        message="Search Poly Haven.", user_id="alice", turn_id="image-retry",
        llm_config=LLMConfig(model="claude-sonnet-4-5"),
        tool_bindings=(_image_binding(),), completion=completion, trace_root=tmp_path,
    ))

    assert outcome.kind == "final_answer"
    assert outcome.provider_calls == 3
    assert outcome.mcp_vision_degraded is True
    assert len(requests) == 3


@pytest.mark.parametrize("second_error", [LIVE_IMAGE_ERROR, "invalid_request_error: unrelated schema field"])
def test_provider_400_is_not_retried_twice_or_when_unrelated(
    tmp_path: Path, second_error: str,
) -> None:
    calls = 0

    async def completion(**_kwargs):  # noqa: ANN003, ANN202
        nonlocal calls
        calls += 1
        if calls == 1:
            return _response(tool_calls=(_call("mcp__blender__search_assets"),))
        raise _Provider400(second_error)

    outcome = asyncio.run(run_native_agent_turn(
        message="Search Poly Haven.", user_id="alice", turn_id="image-no-loop",
        llm_config=LLMConfig(model="claude-sonnet-4-5"),
        tool_bindings=(_image_binding(),), completion=completion, trace_root=tmp_path,
    ))

    assert outcome.kind == "infra_error"
    assert calls == (3 if second_error == LIVE_IMAGE_ERROR else 2)


def test_strict_fake_rejects_exact_live_webp_declared_as_png() -> None:
    payload = {
        "model": "claude-e2e",
        "max_tokens": 100,
        "messages": [{
            "role": "user",
            "content": [{
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": _encoded("image/webp"),
                },
            }],
        }],
    }

    violations = validate_anthropic_request(payload)
    assert len(violations) == 1
    assert violations[0].message == (
        "The image was specified using the image/png media type, "
        "but the image appears to be a image/webp image"
    )


def _pipeline(tmp_path: Path) -> Pipeline:
    pipeline = Pipeline.__new__(Pipeline)
    pipeline.settings = SimpleNamespace(
        agentic_loop=SimpleNamespace(async_agent_job_sync_budget_seconds=0.01),
    )
    pipeline._project_root = tmp_path
    pipeline._agent_job_store = None
    pipeline._agent_job_store_path = None
    pipeline._agent_job_tasks = set()
    pipeline._routing_debug_enabled = lambda: False
    pipeline._native_pending_store = None
    return pipeline


def _await_pipeline_tasks(pipeline: Pipeline) -> None:
    async def wait() -> None:
        for _index in range(30):
            tasks = tuple(pipeline._agent_job_tasks)
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            if not pipeline._agent_job_tasks:
                return
            await asyncio.sleep(0)

    asyncio.run(wait())


def test_confirmation_resume_exception_becomes_terminal_error_and_notice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipeline = _pipeline(tmp_path)
    notices: list[dict] = []

    async def notifier(_user_id: str, **kwargs):  # noqa: ANN003
        notices.append(dict(kwargs))

    pipeline._agent_job_notifier = notifier
    store = pipeline.get_agent_job_store()
    store.create(job_id="job-confirm-fail", user_id="alice", goal="build", status="detached")
    assert store.set_awaiting_confirmation("job-confirm-fail", {
        "messages": [], "pending_token": "na-token", "pending_call_id": "call-1",
        "pending_tool_name": "mcp__review__execute", "pending_preview": "Run code",
        "pending_deferred_calls": [], "original_message": "build", "language": "en",
        "auth_role": "admin", "turn_id": "turn-confirm-fail",
    })

    async def fail_resume(*_args, **_kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError("post-confirm resume exploded")

    monkeypatch.setattr(pipeline_module, "run_native_agent_first_stage", fail_resume)
    assert asyncio.run(pipeline.resolve_agent_job_confirmation(
        "alice", "job-confirm-fail", approve=True,
    )) == "started"
    _await_pipeline_tasks(pipeline)

    record = store.get("job-confirm-fail")
    assert record is not None
    assert record.status == "error"
    assert record.resume_state is None
    assert "post-confirm resume exploded" in record.result
    assert len(notices) == 1
    assert notices[0]["badge_intent"] == "agent_job_error"


def test_terminal_notice_uses_total_wall_duration_and_reports_last_segment(
    tmp_path: Path,
) -> None:
    pipeline = _pipeline(tmp_path)
    notices: list[dict] = []

    async def notifier(_user_id: str, **kwargs):  # noqa: ANN003
        notices.append(dict(kwargs))

    pipeline._agent_job_notifier = notifier
    store = AgentJobStore(tmp_path / "duration.sqlite3")
    store.create(job_id="job-duration", user_id="alice", goal="long build", now=100.0)
    store.set_terminal("job-duration", status="done", result="complete", now=220.0)
    result = PipelineResult(
        request_id="segment", text="complete", usage={}, intents=["chat"], skill_errors=[],
        router_level=2, duration_ms=5600, detail_lines=[],
    )

    asyncio.run(pipeline._notify_agent_job_terminal(
        store=store, job_id="job-duration", user_id="alice", language="en",
        status="done", result="complete", terminal_result=result,
    ))

    assert notices[0]["badge_duration"] == "120.0"
    assert "Routing Debug: agent_job_duration total_ms=120000 segment_ms=5600" in notices[0]["badge_details"]
