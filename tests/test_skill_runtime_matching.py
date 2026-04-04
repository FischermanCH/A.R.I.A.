import asyncio

from aria.core.skill_runtime import match_custom_skill_intents, resolve_custom_skill_intent_with_llm


def test_match_custom_skill_intents_handles_natural_reordered_phrase() -> None:
    intents = match_custom_skill_intents(
        "machst du mir ein update auf dem server",
        [
            {
                "id": "server-update-2nodes",
                "name": "Server Update 2 Nodes",
                "description": "Fuehrt apt Update/Upgrade auf zwei Servern aus und fasst das Ergebnis zusammen.",
                "keywords": ["server update starten", "apt update auf beiden servern"],
                "connections": ["ssh", "llm"],
                "enabled": True,
            }
        ],
    )
    assert intents == ["custom_skill:server-update-2nodes"]


def test_match_custom_skill_intents_handles_real_manifest_style_update_prompt() -> None:
    intents = match_custom_skill_intents(
        "machst du mir ein update auf dem server",
        [
            {
                "id": "server-update-2nodes",
                "name": "server-update-2nodes",
                "description": "Fuehrt apt Update/Upgrade auf server-main und server-alert aus und fasst das Ergebnis zusammen.",
                "keywords": [
                    "server update starten",
                    "server upgrade durchführen",
                    "apt update auf beiden servern",
                ],
                "connections": ["ssh", "llm"],
                "enabled": True,
            }
        ],
    )
    assert intents == ["custom_skill:server-update-2nodes"]


def test_match_custom_skill_intents_ignores_unrelated_prompt() -> None:
    intents = match_custom_skill_intents(
        "was ist neu im heise online feed",
        [
            {
                "id": "server-update-2nodes",
                "name": "Server Update 2 Nodes",
                "description": "Fuehrt apt Update/Upgrade auf zwei Servern aus und fasst das Ergebnis zusammen.",
                "keywords": ["server update starten", "apt update auf beiden servern"],
                "connections": ["ssh", "llm"],
                "enabled": True,
            }
        ],
    )
    assert intents == []


def test_resolve_custom_skill_intent_with_llm_returns_valid_skill_only() -> None:
    class FakeLLMResponse:
        def __init__(self, content: str) -> None:
            self.content = content

    class FakeLLMClient:
        async def chat(self, _messages):
            return FakeLLMResponse('{"id":"server-update-2nodes","confidence":"high","reason":"passt"}')

    intents = asyncio.run(
        resolve_custom_skill_intent_with_llm(
            "machst du mir ein update auf dem server",
            [
                {
                    "id": "server-update-2nodes",
                    "name": "Server Update 2 Nodes",
                    "description": "Fuehrt apt Update/Upgrade auf zwei Servern aus und fasst das Ergebnis zusammen.",
                    "keywords": ["server update starten"],
                    "connections": ["ssh", "llm"],
                    "enabled": True,
                }
            ],
            FakeLLMClient(),
        )
    )
    assert intents == ["custom_skill:server-update-2nodes"]


def test_resolve_custom_skill_intent_with_llm_rejects_unknown_skill() -> None:
    class FakeLLMResponse:
        def __init__(self, content: str) -> None:
            self.content = content

    class FakeLLMClient:
        async def chat(self, _messages):
            return FakeLLMResponse('{"id":"does-not-exist","confidence":"high","reason":"falsch"}')

    intents = asyncio.run(
        resolve_custom_skill_intent_with_llm(
            "machst du mir ein update auf dem server",
            [
                {
                    "id": "server-update-2nodes",
                    "name": "Server Update 2 Nodes",
                    "description": "Fuehrt apt Update/Upgrade auf zwei Servern aus und fasst das Ergebnis zusammen.",
                    "keywords": ["server update starten"],
                    "connections": ["ssh", "llm"],
                    "enabled": True,
                }
            ],
            FakeLLMClient(),
        )
    )
    assert intents == []
