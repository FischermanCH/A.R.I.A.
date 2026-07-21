import asyncio

from aria.core.chat_freshness import chat_freshness_candidate
from aria.core.chat_freshness import decide_chat_freshness
from aria.core.chat_freshness import explicitly_requests_web_research


def test_explicit_web_research_is_freshness_candidate() -> None:
    message = "ich suche ein cyberdeck zum selbst bauen, kannst du mal im internet recherchieren was es so gibt"

    assert explicitly_requests_web_research(message)
    assert chat_freshness_candidate(message, intents=["chat"])


def test_explicit_local_context_does_not_become_web_research() -> None:
    message = "suche in meinen notizen nach cyberdeck"

    assert not explicitly_requests_web_research(message)
    assert not chat_freshness_candidate(message, intents=["chat"])


def test_explicit_url_is_freshness_candidate() -> None:
    message = "lies diese Seite wirklich aus: https://area41.io/#speakers"

    assert chat_freshness_candidate(message, intents=["chat"])


def test_current_product_semantics_need_llm_not_freshness_fallback() -> None:
    decision = asyncio.run(
        decide_chat_freshness(
            message="was ist der neuste amazon kindle",
            intents=["chat"],
            llm_client=None,
        )
    )

    assert decision.needs_fresh_context is False
    assert decision.source == "none"
    assert decision.query == ""
    assert "LLM freshness arbiter unavailable" in decision.reason


def test_recent_weeks_product_update_is_freshness_candidate() -> None:
    message = "gibts vom rabbit r1 ein update das in den letzten wochen rausgekommen ist"

    assert chat_freshness_candidate(message, intents=["chat"])


def test_freshness_fallback_without_llm_allows_explicit_web_research() -> None:
    decision = asyncio.run(
        decide_chat_freshness(
            message="suche im internet nach dem neusten amazon kindle",
            intents=["chat"],
            llm_client=None,
        )
    )

    assert decision.needs_fresh_context is True
    assert decision.source == "explicit_fallback"
    assert "amazon kindle" in decision.query.lower()
