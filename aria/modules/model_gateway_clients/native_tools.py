"""Provider-neutral parsing for LiteLLM-normalized native tool calls."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any


def field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


@dataclass(frozen=True)
class NativeToolCall:
    call_id: str
    name: str
    arguments: dict[str, Any]

    def as_message_payload(self) -> dict[str, Any]:
        return {
            "id": self.call_id,
            "type": "function",
            "function": {"name": self.name, "arguments": json.dumps(self.arguments)},
        }


def first_choice(response: Any) -> tuple[Any, str]:
    choices = field(response, "choices", ()) or ()
    if not choices:
        raise RuntimeError("native_toolcall_no_choice")
    choice = choices[0]
    return field(choice, "message", None), str(field(choice, "finish_reason", "") or "")


def parse_tool_calls(message: Any) -> tuple[NativeToolCall, ...]:
    parsed: list[NativeToolCall] = []
    for index, raw_call in enumerate(field(message, "tool_calls", ()) or ()):
        function = field(raw_call, "function", None)
        name = str(field(function, "name", "") or "").strip()
        raw_arguments = field(function, "arguments", None)
        if isinstance(raw_arguments, str):
            try:
                arguments = json.loads(raw_arguments)
            except json.JSONDecodeError as exc:
                raise RuntimeError("native_toolcall_arguments_invalid") from exc
        elif isinstance(raw_arguments, dict):
            arguments = dict(raw_arguments)
        else:
            raise RuntimeError("native_toolcall_arguments_invalid")
        if not name or not isinstance(arguments, dict):
            raise RuntimeError("native_toolcall_arguments_invalid")
        parsed.append(NativeToolCall(str(field(raw_call, "id", "") or f"tool-call-{index + 1}"), name, arguments))
    return tuple(parsed)
