from __future__ import annotations

import asyncio
import json

import aria.core.pipeline as pipeline_mod
from aria.core.config import Settings
from aria.core.pipeline import Pipeline
from aria.core.router import RouterDecision
from aria.core.turn_intent_arbitration import TurnIntentArbiter
from aria.skills.base import SkillResult


class _Response:
    def __init__(self, content: str) -> None:
        self.content = content
        self.usage = {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}


class _IntentLLM:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.operations: list[str] = []
        self.last_payload: dict | None = None

    async def chat(self, messages, **kwargs):
        operation = str(kwargs.get("operation") or "")
        self.operations.append(operation)
        if operation == "turn_intent_arbitration" and messages:
            self.last_payload = json.loads(messages[-1]["content"])
        if operation == "turn_intent_arbitration":
            return _Response(json.dumps(self.payload))
        return _Response("{}")


class _PromptLoader:
    def get_persona(self) -> str:
        return "Du bist ARIA"


def _settings() -> Settings:
    return Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "ui": {"debug_mode": True},
            "connections": {},
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )


def test_turn_intent_arbitration_can_override_keyword_signal_to_chat() -> None:
    llm = _IntentLLM(
        {
            "intents": ["chat"],
            "confidence": "high",
            "reason": "The user mentions search but asks for explanation, not web lookup.",
        }
    )

    result = asyncio.run(
        TurnIntentArbiter(llm).arbitrate(
            message="Erklaere mir, wie Internetsuche in ARIA funktioniert.",
            keyword_decision=RouterDecision(intents=["web_search"], level=1),
            available_intents={"chat", "web_search"},
            user_id="u1",
            request_id="req-1",
        )
    )

    assert result.decision.intents == ["chat"]
    assert result.decision.level == 2
    assert result.source == "turn_intent_arbitration"
    assert llm.operations == ["turn_intent_arbitration"]


def test_turn_intent_arbitration_falls_back_on_low_confidence() -> None:
    llm = _IntentLLM({"intents": ["chat"], "confidence": "low", "reason": "unsure"})

    result = asyncio.run(
        TurnIntentArbiter(llm).arbitrate(
            message="Websuche Mill WiFi Anleitung",
            keyword_decision=RouterDecision(intents=["web_search"], level=1),
            available_intents={"chat", "web_search"},
        )
    )

    assert result.decision.intents == ["web_search"]
    assert result.source == "keyword_router"
    assert result.reason == "arbiter_low_confidence"


def test_turn_intent_arbitration_passes_active_learning_hints_as_weak_signals() -> None:
    llm = _IntentLLM({"intents": ["web_search"], "confidence": "high", "reason": "source URL hint applies"})

    result = asyncio.run(
        TurnIntentArbiter(llm).arbitrate(
            message="Was steht auf https://example.test/page?",
            keyword_decision=RouterDecision(intents=["chat"], level=1),
            available_intents={"chat", "web_search"},
            active_learning_hints=[
                {
                    "source": "qdrant_learning_active_hint",
                    "collection": "aria_learning_active_hints_u1",
                    "text": "Active Learning Hint: concrete URLs should bias toward web_search",
                    "runtime_effect": "weak_signal_only",
                }
            ],
        )
    )

    assert result.decision.intents == ["web_search"]
    assert llm.last_payload is not None
    assert llm.last_payload["active_learning_hints"][0]["collection"] == "aria_learning_active_hints_u1"
    assert llm.last_payload["active_learning_hints"][0]["runtime_effect"] == "weak_signal_only"


def test_pipeline_agentic_routing_uses_turn_intent_arbitration() -> None:
    llm = _IntentLLM({"intents": ["chat"], "confidence": "high", "reason": "explanation request"})
    pipeline = Pipeline(settings=_settings(), prompt_loader=_PromptLoader(), llm_client=llm)

    decision = asyncio.run(
        pipeline._classify_routing_agentic(
            "Suche ist hier nur als Thema gemeint, erklaere mir die Funktion.",
            keyword_decision=RouterDecision(intents=["web_search"], level=1),
            user_id="u1",
            request_id="req-1",
        )
    )

    assert decision.intents == ["chat"]
    assert decision.level == 2


class _ActiveHintMemory:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def execute(self, query: str, params: dict) -> SkillResult:
        self.calls.append({"query": query, "params": dict(params)})
        return SkillResult(
            skill_name="memory",
            success=True,
            content="- [AKTIVER LERN-HINWEIS] Active Learning Hint: URL questions should use source lookup",
        )


def test_pipeline_agentic_routing_reads_active_learning_hints_from_qdrant() -> None:
    llm = _IntentLLM({"intents": ["web_search"], "confidence": "high", "reason": "active hint applies"})
    pipeline = Pipeline(settings=_settings(), prompt_loader=_PromptLoader(), llm_client=llm)
    pipeline.memory_skill = _ActiveHintMemory()  # type: ignore[assignment]
    pipeline.web_search_skill = object()  # type: ignore[assignment]

    decision = asyncio.run(
        pipeline._classify_routing_agentic(
            "Was steht auf https://example.test/page?",
            keyword_decision=RouterDecision(intents=["chat"], level=1),
            user_id="U 1",
            request_id="req-1",
        )
    )

    assert decision.intents == ["web_search"]
    assert pipeline.memory_skill.calls[-1]["params"]["collection"] == "aria_learning_active_hints_u_1"  # type: ignore[attr-defined]
    assert llm.last_payload is not None
    assert llm.last_payload["active_learning_hints"][0]["runtime_effect"] == "weak_signal_only"


def test_pipeline_records_active_learning_hint_outcome_after_turn(monkeypatch) -> None:
    captured: list[dict] = []

    async def fake_capture_learning_outcome(**kwargs):
        captured.append(dict(kwargs))
        return {"captured": True}

    async def _run() -> None:
        llm = _IntentLLM({"intents": ["chat"], "confidence": "high", "reason": "ordinary chat"})
        pipeline = Pipeline(settings=_settings(), prompt_loader=_PromptLoader(), llm_client=llm)
        pipeline.memory_skill = _ActiveHintMemory()  # type: ignore[assignment]
        monkeypatch.setattr(pipeline_mod, "capture_learning_outcome", fake_capture_learning_outcome)

        result = await pipeline.process(
            "Erklaere mir die URL-Frage nur kurz.",
            user_id="U 1",
            source="test",
            auto_memory_enabled=True,
        )
        await asyncio.sleep(0)

        assert result.intents == ["chat"]

    asyncio.run(_run())

    assert captured
    event = captured[0]["event"]
    assert event["source"] == "active_learning_hint_outcome"
    assert event["artifact_type"] == "routing_hint"
    assert event["evidence"]["active_hint_collections"] == ["aria_learning_active_hints_u_1"]
    assert event["evidence"]["final_intents"] == ["chat"]
