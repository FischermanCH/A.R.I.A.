from aria.core.config import RoutingConfig
from aria.core.router import KeywordRouter


def test_router_store_intent() -> None:
    router = KeywordRouter(RoutingConfig())
    decision = router.classify("Merk dir, dass mein NAS 10.0.10.100 hat")
    assert "memory_store" in decision.intents
    assert decision.level == 1


def test_router_recall_intent() -> None:
    router = KeywordRouter(RoutingConfig())
    decision = router.classify("Erinnerst du dich an mein NAS?")
    assert "memory_recall" in decision.intents


def test_router_chat_fallback() -> None:
    router = KeywordRouter(RoutingConfig())
    decision = router.classify("Wie ist das Wetter heute?")
    assert decision.intents == ["chat"]


def test_router_web_search_intent() -> None:
    router = KeywordRouter(RoutingConfig())
    decision = router.classify("Websuche Mill WiFi Anleitung")
    assert "web_search" in decision.intents


def test_router_internet_search_phrase_maps_to_web_search() -> None:
    router = KeywordRouter(RoutingConfig())
    decision = router.classify("Suche in Internet nach den letzten News über den aibi bot")
    assert "web_search" in decision.intents


def test_router_vergiss_nicht_maps_to_store_not_forget() -> None:
    router = KeywordRouter(RoutingConfig())
    decision = router.classify("Vergiss nicht, dass mein NAS 10.0.10.100 hat")
    assert decision.intents == ["memory_store"]


def test_router_forget_intent_is_exclusive() -> None:
    router = KeywordRouter(RoutingConfig())
    decision = router.classify("Vergiss die alte IP-Adresse")
    assert decision.intents == ["memory_forget"]


def test_router_skill_status_intent() -> None:
    router = KeywordRouter(RoutingConfig())
    decision = router.classify("Kannst du deine Skills ueberpruefen und mir sagen was aktiv ist?")
    assert decision.intents == ["skill_status"]


def test_router_skill_status_intent_for_user_phrase() -> None:
    router = KeywordRouter(RoutingConfig())
    decision = router.classify("Was fuer skills hast du aktiv?")
    assert decision.intents == ["skill_status"]


def test_router_skill_status_intent_for_current_skills_phrase() -> None:
    router = KeywordRouter(RoutingConfig())
    decision = router.classify("Was sind deine aktuellen Skills?")
    assert decision.intents == ["skill_status"]


def test_router_cls_stays_chat_intent() -> None:
    router = KeywordRouter(RoutingConfig())
    assert router.classify("cls").intents == ["chat"]
    assert router.classify("/cls").intents == ["chat"]
    assert router.classify("clear").intents == ["chat"]
    assert router.classify("/clear").intents == ["chat"]


def test_router_english_memory_store_intent() -> None:
    routing = RoutingConfig().for_language("en")
    router = KeywordRouter(routing)
    decision = router.classify("Remember this: my NAS has the new backup share")
    assert "memory_store" in decision.intents


def test_router_english_web_search_intent() -> None:
    routing = RoutingConfig().for_language("en")
    router = KeywordRouter(routing)
    decision = router.classify("Search the web for the latest rabbit r1 news")
    assert "web_search" in decision.intents


def test_router_english_skill_status_intent() -> None:
    routing = RoutingConfig().for_language("en")
    router = KeywordRouter(routing)
    decision = router.classify("What skills are active right now?")
    assert decision.intents == ["skill_status"]
