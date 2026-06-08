from aria.core.chat_freshness import chat_freshness_candidate
from aria.core.chat_freshness import explicitly_requests_web_research


def test_explicit_web_research_is_freshness_candidate() -> None:
    message = "ich suche ein cyberdeck zum selbst bauen, kannst du mal im internet recherchieren was es so gibt"

    assert explicitly_requests_web_research(message)
    assert chat_freshness_candidate(message, intents=["chat"])


def test_explicit_local_context_does_not_become_web_research() -> None:
    message = "suche in meinen notizen nach cyberdeck"

    assert not explicitly_requests_web_research(message)
    assert not chat_freshness_candidate(message, intents=["chat"])
