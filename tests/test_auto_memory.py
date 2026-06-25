import asyncio
import json

from aria.core.auto_memory import AutoMemoryExtractor
from aria.core.config import Settings
from aria.skills.memory import MemorySkill


class _FakeLLMResponse:
    def __init__(self, content: str) -> None:
        self.content = content
        self.usage = {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18}


class _AutoMemoryLLM:
    def __init__(self) -> None:
        self.operations: list[str] = []

    async def chat(self, messages, **kwargs):
        self.operations.append(str(kwargs.get("operation") or ""))
        payload = json.loads(str(messages[1]["content"]))
        assert payload["max_facts"] == 3
        return _FakeLLMResponse(
            json.dumps(
                {
                    "recall_query": "pi-hole pruefen dns-node-01 dns health",
                    "facts": ["User phrase 'Pi-hole pruefen' means DNS health check on dns-node-01"],
                    "preferences": [],
                    "action_boundaries": [],
                    "should_persist_session": True,
                    "confidence": "high",
                    "reason": "durable user-specific operational convention",
                }
            )
        )


def test_auto_memory_extracts_preference() -> None:
    decision = AutoMemoryExtractor.decide("Ich bevorzuge direkte Antworten ohne Floskeln.")
    assert decision.preferences
    assert "direkte Antworten" in decision.preferences[0]


def test_auto_memory_extracts_fact_and_ip() -> None:
    decision = AutoMemoryExtractor.decide("Hostname: server-main, IP: 10.0.1.1")
    assert decision.facts
    assert any("10.0.1.1" in value for value in decision.facts)
    assert decision.should_persist_session is True


def test_auto_memory_skips_transient_questions_and_action_prompts() -> None:
    samples = [
        "was für news gibs auf heise",
        "wie lange braucht saturn bis er einmal um die sonne gekreist ist ?",
        "Ping von A.R.I.A (nach discord)",
        "brauchen meine linux server updates ?",
        "Erkläre mir Qdrant, Embeddings und semantische Suche so, dass ein Linux-Admin es in 10 Minuten versteht.",
    ]

    for message in samples:
        decision = AutoMemoryExtractor.decide(message)
        assert decision.facts == []
        assert decision.preferences == []
        assert decision.should_persist_session is False


def test_auto_memory_keeps_declarative_user_context() -> None:
    decision = AutoMemoryExtractor.decide("Mein NAS heisst atlas und läuft auf 10.0.10.100.")
    assert decision.should_persist_session is True
    assert decision.facts


def test_auto_memory_agentic_extractor_learns_user_behavior_convention() -> None:
    llm = _AutoMemoryLLM()
    decision = asyncio.run(
        AutoMemoryExtractor.decide_agentic(
            "Wenn ich Pi-hole pruefen schreibe, meine ich den DNS Health Check auf dns-node-01.",
            llm_client=llm,
            max_facts=3,
            enabled=True,
        )
    )

    assert llm.operations == ["auto_memory_extraction_decision"]
    assert decision.extraction_model == "agentic"
    assert decision.extraction_usage == {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18}
    assert decision.should_persist_session is True
    assert decision.facts == ["User phrase 'Pi-hole pruefen' means DNS health check on dns-node-01"]


def test_auto_memory_agentic_extractor_marks_action_sensitive_memory() -> None:
    class _BoundaryLLM(_AutoMemoryLLM):
        async def chat(self, messages, **kwargs):
            self.operations.append(str(kwargs.get("operation") or ""))
            return _FakeLLMResponse(
                json.dumps(
                    {
                        "recall_query": "public push approval boundary",
                        "facts": [],
                        "preferences": [],
                        "action_boundaries": [
                            "Do not push public releases until the user explicitly approves the release."
                        ],
                        "should_persist_session": True,
                        "confidence": "high",
                        "reason": "durable approval constraint",
                    }
                )
            )

    llm = _BoundaryLLM()
    decision = asyncio.run(
        AutoMemoryExtractor.decide_agentic(
            "Public push bitte erst machen, wenn ich den Release explizit freigebe.",
            llm_client=llm,
            max_facts=3,
            enabled=True,
        )
    )

    assert decision.action_boundaries == [
        "Do not push public releases until the user explicitly approves the release"
    ]
    assert decision.facts == [
        "Action boundary: Do not push public releases until the user explicitly approves the release"
    ]


def test_auto_memory_agentic_extractor_learns_from_user_feedback() -> None:
    class _FeedbackLLM(_AutoMemoryLLM):
        async def chat(self, messages, **kwargs):
            self.operations.append(str(kwargs.get("operation") or ""))
            payload = json.loads(str(messages[1]["content"]))
            assert "reflections" in payload["contract"]
            return _FakeLLMResponse(
                json.dumps(
                    {
                        "recall_query": "AREA41 official page snippets source quality",
                        "facts": [],
                        "preferences": [],
                        "reflections": [
                            "For concrete conference URL or anchor questions, prefer official page excerpts over search snippets and state clearly when the page is not readable."
                        ],
                        "action_boundaries": [],
                        "should_persist_session": True,
                        "confidence": "high",
                        "reason": "durable feedback about answer quality and source handling",
                    }
                )
            )

    llm = _FeedbackLLM()
    decision = asyncio.run(
        AutoMemoryExtractor.decide_agentic(
            "Das war meh: Beim AREA41-Fall darfst du nicht aus Such-Snippets raten, sondern musst die offizielle Seite wirklich lesen.",
            llm_client=llm,
            max_facts=3,
            enabled=True,
        )
    )

    assert decision.extraction_model == "agentic"
    assert decision.facts == []
    assert decision.preferences == []
    assert decision.reflections == [
        "For concrete conference URL or anchor questions, prefer official page excerpts over search snippets and state clearly when the page is not readable"
    ]


def test_memory_recall_targets_include_user_learning_reflections() -> None:
    async def _run() -> None:
        settings = Settings.model_validate(
                {
                    "llm": {"model": "fake"},
                    "memory": {"enabled": True},
                    "embeddings": {"provider": "openai", "model": "text-embedding-3-small"},
                }
        )
        skill = MemorySkill(memory=settings.memory, embeddings=settings.embeddings)

        async def fake_list_collection_names():
            return []

        skill._list_collection_names = fake_list_collection_names  # type: ignore[method-assign]
        targets = await skill._build_recall_targets(user_id="U 1", base_collection="aria_facts_u_1")

        learning = [target for target in targets if target["collection"] == "aria_learning_u_1"]
        assert learning == [
            {
                "type": "reflection",
                "label": "LERNEN",
                "collection": "aria_learning_u_1",
                "top_k": settings.memory.collections.knowledge.top_k,
            }
        ]

    asyncio.run(_run())
