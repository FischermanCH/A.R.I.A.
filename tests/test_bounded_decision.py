import asyncio
import json

from aria.modules.platform_primitives.bounded_decision import BoundedDecisionClient
from aria.modules.platform_primitives.bounded_decision import confidence_score


class FakeResponse:
    def __init__(self, content: str) -> None:
        self.content = content
        self.usage = {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5}


class FakeLLM:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls = []

    async def chat(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        return FakeResponse(self.content)


class StrictBehaviorLLM:
    def __init__(self, behavior: str, contents: list[str]) -> None:
        self.behavior = behavior
        self.contents = list(contents)
        self.calls = []

    async def chat(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        strict = kwargs.get("response_format", {}).get("json_schema", {}).get("strict")
        if self.behavior == "reject" and strict is True:
            raise RuntimeError("strict json_schema unsupported")
        return FakeResponse(self.contents.pop(0))


def strict_test_schema() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["route"],
        "properties": {"route": {"type": "string", "enum": ["chat"]}},
    }


def test_confidence_score_accepts_labels_and_numbers() -> None:
    assert confidence_score("high") > confidence_score("medium") > confidence_score("low")
    assert confidence_score("0.7") == 0.7
    assert confidence_score("nope") == 0.0


def test_bounded_decision_client_parses_json_and_usage() -> None:
    async def _run() -> None:
        llm = FakeLLM(json.dumps({"use_context": True, "confidence": "high"}))
        result = await BoundedDecisionClient(llm).decide_json(
            operation="unit_test_decision",
            system="Return JSON.",
            payload={"message": "hello"},
            source="test",
            user_id="u1",
            request_id="r1",
        )

        assert result.ok
        assert result.payload["use_context"] is True
        assert result.usage["total_tokens"] == 5
        assert result.diagnostics["payload_bytes"] == len('{"message":"hello"}'.encode("utf-8"))
        assert llm.calls[0][0][1]["content"] == '{"message":"hello"}'
        assert llm.calls[0][1]["operation"] == "unit_test_decision"

    asyncio.run(_run())


def test_bounded_decision_client_reports_invalid_json() -> None:
    async def _run() -> None:
        result = await BoundedDecisionClient(FakeLLM("not json")).decide_json(
            operation="unit_test_decision",
            system="Return JSON.",
            payload={"message": "hello"},
        )

        assert not result.ok
        assert result.error == "empty_or_invalid_response"

    asyncio.run(_run())


def test_bounded_decision_client_forwards_enforced_response_schema() -> None:
    async def _run() -> None:
        llm = FakeLLM(json.dumps({"module_dispatch": {"owner": "chat", "operation": "answer", "arguments": {}}}))
        response_schema = {
            "type": "object",
            "additionalProperties": False,
            "required": ["module_dispatch"],
            "properties": {
                "module_dispatch": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["owner", "operation", "arguments"],
                    "properties": {
                        "owner": {"type": "string"},
                        "operation": {"type": "string"},
                        "arguments": {"type": "object", "additionalProperties": False, "properties": {}},
                    },
                }
            },
        }

        result = await BoundedDecisionClient(llm).decide_json(
            operation="module_dispatch_test",
            system="Select one module operation.",
            payload={"message": "hello"},
            response_schema=response_schema,
        )

        assert result.ok
        assert llm.calls[0][1]["response_format"] == {
            "type": "json_schema",
            "json_schema": {
                "name": "module_dispatch_test",
                "strict": True,
                "schema": response_schema,
            },
        }

    asyncio.run(_run())


def test_bounded_decision_strict_provider_succeeds_in_one_call() -> None:
    async def _run() -> None:
        llm = StrictBehaviorLLM("support", ['{"route":"chat"}'])
        result = await BoundedDecisionClient(llm).decide_json(
            operation="strict_supported",
            system="Return JSON.",
            payload={},
            response_schema=strict_test_schema(),
            validate_payload=lambda payload: () if payload.get("route") == "chat" else ("unknown_route",),
            repair_once=True,
        )

        assert result.ok
        assert len(llm.calls) == 1
        assert llm.calls[0][1]["response_format"]["json_schema"]["strict"] is True

    asyncio.run(_run())


def test_bounded_decision_provider_ignores_strict_and_repair_stays_bounded() -> None:
    async def _run() -> None:
        llm = StrictBehaviorLLM("ignore", ['{"route":"almost"}', '{"route":"chat"}'])
        result = await BoundedDecisionClient(llm).decide_json(
            operation="strict_ignored",
            system="Return JSON.",
            payload={},
            response_schema=strict_test_schema(),
            validate_payload=lambda payload: () if payload.get("route") == "chat" else ("unknown_route",),
            repair_once=True,
        )

        assert result.ok
        assert len(llm.calls) == 2
        assert all(call[1]["response_format"]["json_schema"]["strict"] is True for call in llm.calls)
        assert result.diagnostics["repair_calls"] == 1

    asyncio.run(_run())


def test_bounded_decision_strict_rejection_falls_back_once_and_is_remembered() -> None:
    async def _run() -> None:
        llm = StrictBehaviorLLM("reject", ['{"route":"almost"}', '{"route":"chat"}', '{"route":"chat"}'])
        client = BoundedDecisionClient(llm)
        kwargs = {
            "system": "Return JSON.",
            "payload": {},
            "response_schema": strict_test_schema(),
            "validate_payload": lambda payload: () if payload.get("route") == "chat" else ("unknown_route",),
            "repair_once": True,
        }

        first = await client.decide_json(operation="strict_rejected_first", **kwargs)
        calls_after_first = len(llm.calls)
        second = await client.decide_json(operation="strict_rejected_second", **kwargs)

        assert first.ok and second.ok
        assert calls_after_first == 3
        assert len(llm.calls) == calls_after_first + 1
        assert llm.calls[0][1]["response_format"]["json_schema"]["strict"] is True
        assert all(call[1]["response_format"]["json_schema"]["strict"] is False for call in llm.calls[1:])
        assert first.diagnostics["strict_fallback_calls"] == 1
        assert second.diagnostics["strict_fallback_calls"] == 0

    asyncio.run(_run())


def test_bounded_decision_skips_strict_for_schema_with_optional_property() -> None:
    async def _run() -> None:
        llm = StrictBehaviorLLM("reject", ['{"route":"chat"}'])
        schema = strict_test_schema()
        schema["properties"]["reason"] = {"type": ["string", "null"]}
        result = await BoundedDecisionClient(llm).decide_json(
            operation="strict_incompatible",
            system="Return JSON.",
            payload={},
            response_schema=schema,
        )

        assert result.ok
        assert len(llm.calls) == 1
        assert llm.calls[0][1]["response_format"]["json_schema"]["strict"] is False

    asyncio.run(_run())


def test_bounded_decision_rejects_nonportable_schema_before_model_call() -> None:
    async def _run() -> None:
        llm = FakeLLM("{}")
        result = await BoundedDecisionClient(llm).decide_json(
            operation="module_dispatch_test",
            system="Select one module operation.",
            payload={"message": "hello"},
            response_schema={
                "type": "object",
                "minProperties": 1,
                "properties": {"value": {"oneOf": [{"type": "string"}, {"type": "number"}]}},
            },
        )

        assert result.error == "structured_output_schema_invalid"
        assert result.diagnostics["response_schema_transport_issues"] == 3
        assert llm.calls == []

    asyncio.run(_run())


def test_bounded_decision_rejects_excess_optional_schema_fields_before_model_call() -> None:
    async def _run() -> None:
        llm = FakeLLM("{}")
        result = await BoundedDecisionClient(llm).decide_json(
            operation="module_dispatch_test",
            system="Select one module operation.",
            payload={"message": "hello"},
            response_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {f"field_{index}": {"type": "string"} for index in range(25)},
            },
        )

        assert result.error == "structured_output_schema_invalid"
        assert result.diagnostics["response_schema_transport_issues"] == 1
        assert llm.calls == []

    asyncio.run(_run())


def test_bounded_decision_rejects_oversized_compiled_grammar_candidate_before_model_call() -> None:
    async def _run() -> None:
        llm = FakeLLM("{}")
        result = await BoundedDecisionClient(llm).decide_json(
            operation="module_dispatch_test",
            system="Select one module operation.",
            payload={"message": "hello"},
            response_schema={
                "type": "object",
                "additionalProperties": False,
                "required": ["value"],
                "properties": {"value": {"enum": ["x" * 9000]}},
            },
        )

        assert result.error == "structured_output_schema_invalid"
        assert result.diagnostics["response_schema_transport_issues"] == 1
        assert llm.calls == []

    asyncio.run(_run())
