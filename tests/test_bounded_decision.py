import asyncio
import json

from aria.core.bounded_decision import BoundedDecisionClient
from aria.core.bounded_decision import confidence_score


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
