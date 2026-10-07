"""Strict, scripted Anthropic Messages fake used only by the E2E harness."""

from __future__ import annotations

import argparse
import asyncio
import base64
import binascii
from copy import deepcopy
from dataclasses import dataclass
import itertools
import hashlib
from typing import Any, Mapping

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn


ALLOWED_IMAGE_MEDIA_TYPES = frozenset({"image/png", "image/jpeg", "image/gif", "image/webp"})
ALPHA972_CACHE_CONTROL_ERROR = "cache_control may not be specified within tool_result.content"


@dataclass(frozen=True, slots=True)
class AnthropicViolation:
    message: str
    path: str


def _image_mime_type(payload: bytes) -> str:
    if payload.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if payload.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if payload.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(payload) >= 12 and payload.startswith(b"RIFF") and payload[8:12] == b"WEBP":
        return "image/webp"
    return ""


def _content_blocks(value: Any) -> list[Mapping[str, Any]]:
    if isinstance(value, str):
        return [{"type": "text", "text": value}]
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _walk_cache_control(value: Any, path: str = "request") -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            child = f"{path}.{key}"
            if key == "cache_control":
                found.append(child)
            found.extend(_walk_cache_control(item, child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(_walk_cache_control(item, f"{path}[{index}]"))
    return found


def validate_anthropic_request(payload: Mapping[str, Any]) -> tuple[AnthropicViolation, ...]:
    """Validate the subset of Anthropic's contract that previously escaped unit tests."""

    violations: list[AnthropicViolation] = []
    messages = payload.get("messages")
    if not isinstance(messages, list) or not messages:
        return (AnthropicViolation("messages must be a non-empty array", "messages"),)

    cache_paths = _walk_cache_control(payload)
    if len(cache_paths) > 4:
        violations.append(AnthropicViolation("At most 4 cache_control blocks are allowed", "request"))

    tools = payload.get("tools")
    tools_defined = isinstance(tools, list) and bool(tools)
    pending_tool_uses: set[str] = set()
    saw_tool_blocks = False
    expected_role = "user"

    for message_index, message in enumerate(messages):
        path = f"messages[{message_index}]"
        if not isinstance(message, Mapping):
            violations.append(AnthropicViolation("message must be an object", path))
            continue
        role = str(message.get("role") or "")
        if role != expected_role:
            violations.append(AnthropicViolation(
                "Messages must start with user and strictly alternate user/assistant roles", f"{path}.role",
            ))
        expected_role = "assistant" if role == "user" else "user"
        blocks = _content_blocks(message.get("content"))
        if not blocks and message.get("content") != "":
            violations.append(AnthropicViolation("message content must be text or content blocks", f"{path}.content"))

        tool_results_here: set[str] = set()
        tool_uses_here: set[str] = set()
        for block_index, block in enumerate(blocks):
            block_path = f"{path}.content[{block_index}]"
            block_type = str(block.get("type") or "")
            if block_type == "text" and not str(block.get("text") or "").strip():
                violations.append(AnthropicViolation("text blocks must not be empty", f"{block_path}.text"))
            elif block_type == "image":
                source = block.get("source")
                media_type = str(source.get("media_type") or "") if isinstance(source, Mapping) else ""
                data = str(source.get("data") or "") if isinstance(source, Mapping) else ""
                if media_type not in ALLOWED_IMAGE_MEDIA_TYPES:
                    violations.append(AnthropicViolation("invalid image media_type", f"{block_path}.source.media_type"))
                decoded = b""
                try:
                    if not data:
                        raise ValueError("empty")
                    decoded = base64.b64decode(data, validate=True)
                except (ValueError, binascii.Error):
                    violations.append(AnthropicViolation("invalid image base64 data", f"{block_path}.source.data"))
                actual_media_type = _image_mime_type(decoded)
                if decoded and actual_media_type and media_type != actual_media_type:
                    violations.append(AnthropicViolation(
                        "The image was specified using the "
                        f"{media_type} media type, but the image appears to be a "
                        f"{actual_media_type} image",
                        f"{block_path}.source.base64",
                    ))
            elif block_type == "tool_use":
                saw_tool_blocks = True
                tool_id = str(block.get("id") or "")
                if tool_id:
                    tool_uses_here.add(tool_id)
            elif block_type == "tool_result":
                saw_tool_blocks = True
                tool_id = str(block.get("tool_use_id") or "")
                tool_results_here.add(tool_id)
                nested_cache = _walk_cache_control(block.get("content"), f"{block_path}.content")
                if nested_cache:
                    violations.append(AnthropicViolation(ALPHA972_CACHE_CONTROL_ERROR, nested_cache[0]))

        if role == "user":
            for tool_id in sorted(tool_results_here):
                if not tool_id or tool_id not in pending_tool_uses:
                    violations.append(AnthropicViolation(
                        "tool_result must reference a tool_use from the preceding assistant message",
                        f"{path}.content",
                    ))
            if pending_tool_uses and tool_results_here != pending_tool_uses:
                violations.append(AnthropicViolation(
                    "Every tool_use must be answered by exactly one tool_result in the next user turn",
                    f"{path}.content",
                ))
            pending_tool_uses.clear()
        elif role == "assistant":
            pending_tool_uses = tool_uses_here

    if pending_tool_uses:
        violations.append(AnthropicViolation(
            "Every tool_use must be answered by a tool_result in the next user turn", "messages[-1].content",
        ))
    if saw_tool_blocks and not tools_defined:
        violations.append(AnthropicViolation("Tool blocks require a non-empty tools definition", "tools"))
    return tuple(violations)


def _sanitize(value: Any, *, depth: int = 0) -> Any:
    if depth > 8:
        return "[depth-limited]"
    if isinstance(value, Mapping):
        if value.get("type") == "image" and isinstance(value.get("source"), Mapping):
            source = dict(value["source"])
            data = str(source.get("data") or "")
            source["data"] = f"[base64 omitted; {len(data)} chars]"
            return {
                str(key)[:120]: _sanitize(source if key == "source" else item, depth=depth + 1)
                for key, item in value.items()
            }
        return {
            str(key)[:120]: "[redacted]" if str(key).lower() in {"api_key", "authorization", "x-api-key"}
            else _sanitize(item, depth=depth + 1)
            for key, item in list(value.items())[:200]
        }
    if isinstance(value, list):
        return [_sanitize(item, depth=depth + 1) for item in value[:200]]
    if isinstance(value, str):
        return value[:12000]
    return value


class ScriptedAnthropicState:
    def __init__(self) -> None:
        self.scenario = "default"
        self.steps: list[dict[str, Any]] = []
        self.requests: list[dict[str, Any]] = []
        self.violations: list[dict[str, Any]] = []
        self.scenarios: list[dict[str, Any]] = []
        self._ids = itertools.count(1)
        self.litellm_proxy_compatibility = False
        self.temperature_free_models: set[str] = set()
        self.embedding_requests: list[dict[str, Any]] = []

    def reset(
        self, scenario: str, steps: list[Mapping[str, Any]], *,
        litellm_proxy_compatibility: bool = False,
        temperature_free_models: list[str] | None = None,
    ) -> None:
        if self.requests or self.violations or self.scenario != "default":
            self.scenarios.append({
                "scenario": self.scenario,
                "requests": deepcopy(self.requests),
                "violations": deepcopy(self.violations),
                "queued": len(self.steps),
            })
        self.scenario = str(scenario or "default")[:80]
        self.steps = [deepcopy(dict(item)) for item in steps]
        self.requests = []
        self.violations = []
        self.litellm_proxy_compatibility = bool(litellm_proxy_compatibility)
        self.temperature_free_models = {
            str(model or "").strip()
            for model in (temperature_free_models or [])
            if str(model or "").strip()
        }
        self.embedding_requests = []

    def next_step(self) -> dict[str, Any]:
        if self.steps:
            return self.steps.pop(0)
        return {"type": "text", "text": "E2E scripted response queue exhausted."}

    def response(self, step: Mapping[str, Any], model: str) -> dict[str, Any]:
        step_type = str(step.get("type") or "text")
        if step_type == "tool_use":
            content = [{
                "type": "tool_use",
                "id": str(step.get("id") or f"toolu_e2e_{next(self._ids)}"),
                "name": str(step.get("name") or ""),
                "input": deepcopy(dict(step.get("input") or {})),
            }]
            stop_reason = "tool_use"
        else:
            text = step.get("text") if "text" in step else "E2E response"
            content = [{"type": "text", "text": str(text or "")}]
            stop_reason = str(step.get("stop_reason") or "end_turn")
        return {
            "id": f"msg_e2e_{next(self._ids)}",
            "type": "message",
            "role": "assistant",
            "model": str(model or "claude-e2e"),
            "content": content,
            "stop_reason": stop_reason,
            "stop_sequence": None,
            "usage": {
                "input_tokens": int(step.get("input_tokens") or 17),
                "output_tokens": int(step.get("output_tokens") or 9),
                "cache_creation_input_tokens": int(step.get("cache_creation_input_tokens") or 3),
                "cache_read_input_tokens": int(step.get("cache_read_input_tokens") or 7),
            },
        }


def create_app(state: ScriptedAnthropicState | None = None) -> FastAPI:
    state = state or ScriptedAnthropicState()
    app = FastAPI(title="ARIA strict fake Anthropic")

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {"ok": True, "scenario": state.scenario}

    @app.post("/__control/reset")
    async def reset(request: Request) -> dict[str, Any]:
        payload = await request.json()
        state.reset(
            str(payload.get("scenario") or "default"), list(payload.get("steps") or []),
            litellm_proxy_compatibility=bool(payload.get("litellm_proxy_compatibility", False)),
            temperature_free_models=list(payload.get("temperature_free_models") or []),
        )
        return {"ok": True, "scenario": state.scenario, "queued": len(state.steps)}

    @app.get("/__control/logs")
    async def logs() -> dict[str, Any]:
        return {
            "scenario": state.scenario,
            "requests": deepcopy(state.requests),
            "violations": deepcopy(state.violations),
            "scenarios": [*deepcopy(state.scenarios), {
                "scenario": state.scenario,
                "requests": deepcopy(state.requests),
                "violations": deepcopy(state.violations),
                "queued": len(state.steps),
            }],
            "queued": len(state.steps),
            "embedding_requests": deepcopy(state.embedding_requests),
        }

    @app.post("/embeddings")
    @app.post("/v1/embeddings")
    async def embeddings(request: Request) -> JSONResponse:
        payload = await request.json()
        raw_input = payload.get("input", [])
        inputs = raw_input if isinstance(raw_input, list) else [raw_input]
        rows: list[dict[str, Any]] = []
        for index, item in enumerate(inputs):
            text = str(item or "")
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            vector = [round((byte - 127.5) / 127.5, 8) for byte in digest]
            rows.append({"object": "embedding", "index": index, "embedding": vector})
        state.embedding_requests.append({
            "model": str(payload.get("model") or ""),
            "count": len(inputs),
        })
        return JSONResponse({
            "object": "list",
            "data": rows,
            "model": str(payload.get("model") or "text-embedding-e2e"),
            "usage": {
                "prompt_tokens": sum(max(1, len(str(item or "")) // 4) for item in inputs),
                "total_tokens": sum(max(1, len(str(item or "")) // 4) for item in inputs),
            },
        })

    @app.post("/v1/messages")
    async def messages(request: Request) -> JSONResponse:
        payload = await request.json()
        violations = validate_anthropic_request(payload)
        request_row = {"scenario": state.scenario, "payload": _sanitize(payload), "accepted": False}
        state.requests.append(request_row)
        if state.litellm_proxy_compatibility and payload.get("tool_choice") == {"type": "none"}:
            return JSONResponse(
                status_code=500,
                content={"type": "error", "error": {
                    "type": "internal_server_error",
                    "message": "Incompatible tool choice param submitted - {'type': 'none'}",
                }},
            )
        if (
            str(payload.get("model") or "").strip() in state.temperature_free_models
            and "temperature" in payload
        ):
            return JSONResponse(
                status_code=400,
                content={"type": "error", "error": {
                    "type": "invalid_request_error",
                    "message": "`temperature` is deprecated for this model.",
                }},
            )
        if violations:
            rows = [{"message": item.message, "path": item.path} for item in violations]
            state.violations.extend(rows)
            return JSONResponse(
                status_code=400,
                content={"type": "error", "error": {"type": "invalid_request_error", "message": rows[0]["message"]}},
            )
        request_row["accepted"] = True
        step = state.next_step()
        delay = max(0.0, min(120.0, float(step.get("delay_seconds") or 0.0)))
        if delay:
            await asyncio.sleep(delay)
        if str(step.get("type") or "") == "error":
            status = int(step.get("status") or 529)
            return JSONResponse(
                status_code=status,
                content={"type": "error", "error": {
                    "type": str(step.get("error_type") or "overloaded_error"),
                    "message": str(step.get("message") or "Overloaded"),
                }},
            )
        return JSONResponse(state.response(step, str(payload.get("model") or "claude-e2e")))

    return app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=9000)
    args = parser.parse_args()
    uvicorn.run(create_app(), host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
