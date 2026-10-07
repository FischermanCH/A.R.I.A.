"""One isolated native Tool-Calling roundtrip with a deterministic dummy tool."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from importlib import import_module
import json
from typing import Any, Awaitable, Callable

from aria.modules.configuration_foundations.config import LLMConfig
from aria.modules.model_gateway_clients.native_tools import field as _field
from aria.modules.model_gateway_clients.native_tools import first_choice as _first_choice
from aria.modules.model_gateway_clients.native_tools import parse_tool_calls
from aria.modules.model_gateway_clients.parameter_compat import call_with_model_parameter_compat

Completion = Callable[..., Awaitable[Any]]


@dataclass(frozen=True)
class NativeToolcallDiagnostics:
    native_tool_call_emitted: bool
    tool_name: str
    arguments: dict[str, Any]
    tool_result: int | None
    final_answer: str
    final_answer_correct: bool
    finish_reason: str
    response_source: str
    provider_calls: int
    provider_error: str
    tool_payload: list[dict[str, Any]]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _parse_first_tool_call(message: Any) -> tuple[str, str, dict[str, Any]]:
    tool_calls = parse_tool_calls(message)
    if not tool_calls:
        raise RuntimeError("native_toolcall_missing")
    tool_call = tool_calls[0]
    return tool_call.call_id, tool_call.name, dict(tool_call.arguments)


def _add_numbers(arguments: dict[str, Any]) -> int:
    if set(arguments) != {"a", "b"}:
        raise RuntimeError("native_toolcall_arguments_invalid")
    a, b = arguments["a"], arguments["b"]
    if isinstance(a, bool) or isinstance(b, bool) or not isinstance(a, int) or not isinstance(b, int):
        raise RuntimeError("native_toolcall_arguments_invalid")
    return a + b


def _is_provider_bad_request(exc: Exception) -> bool:
    return any(cls.__name__ == "BadRequestError" for cls in type(exc).__mro__)


async def run_native_toolcall_selftest(config: LLMConfig, *, completion: Completion | None = None) -> NativeToolcallDiagnostics:
    if completion is None:
        completion = getattr(import_module("litellm"), "acompletion")
    tools = [{
        "name": "add_numbers",
        "description": "Add two integers and return their sum.",
        "input_schema": {
            "type": "object",
            "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
            "required": ["a", "b"],
        },
    }]
    messages: list[dict[str, Any]] = [{"role": "user", "content": "What is 7+5? Use the add_numbers tool. After the tool result, reply with exactly 12."}]
    kwargs = {
        "model": config.model, "messages": messages, "api_base": config.api_base,
        "api_key": config.api_key or None, "temperature": config.temperature,
        "max_tokens": config.max_tokens, "timeout": config.timeout_seconds,
        "tools": tools, "tool_choice": "auto",
    }
    try:
        first = await call_with_model_parameter_compat(completion, kwargs)
    except Exception as exc:
        if not _is_provider_bad_request(exc):
            raise
        return NativeToolcallDiagnostics(
            False, "", {}, None, "", False, "", "provider_error", 1, str(exc), tools,
        )
    first_message, finish_reason = _first_choice(first)
    tool_call_id, tool_name, arguments = _parse_first_tool_call(first_message)
    if tool_name != "add_numbers":
        raise RuntimeError("native_toolcall_name_mismatch")
    result = _add_numbers(arguments)
    messages.extend([
        {"role": "assistant", "content": "", "tool_calls": [{"id": tool_call_id, "type": "function", "function": {"name": tool_name, "arguments": json.dumps(arguments)}}]},
        {"role": "tool", "tool_call_id": tool_call_id, "content": str(result)},
    ])
    final = await call_with_model_parameter_compat(completion, {**kwargs, "messages": messages})
    final_message, _ = _first_choice(final)
    final_text = str(_field(final_message, "content", "") or "").strip()
    return NativeToolcallDiagnostics(
        True, tool_name, arguments, result, final_text, final_text == "12",
        finish_reason, "tool_calls", 2, "", tools,
    )
