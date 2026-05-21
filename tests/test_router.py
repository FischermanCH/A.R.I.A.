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


def test_router_delete_on_server_does_not_map_to_memory_forget() -> None:
    router = KeywordRouter(RoutingConfig())
    decision = router.classify("Lösche /tmp/test auf dem management server")
    assert decision.intents == ["chat"]


def test_router_webhook_payload_delete_does_not_map_to_memory_forget() -> None:
    router = KeywordRouter(RoutingConfig())
    decision = router.classify("sende an webhook : delete user record")
    assert decision.intents == ["chat"]


def test_router_recipe_status_intent() -> None:
    router = KeywordRouter(RoutingConfig())
    decision = router.classify("Kannst du deine Skills ueberpruefen und mir sagen was aktiv ist?")
    assert decision.intents == ["recipe_status"]


def test_router_recipe_status_intent_for_user_phrase() -> None:
    router = KeywordRouter(RoutingConfig())
    decision = router.classify("Was fuer skills hast du aktiv?")
    assert decision.intents == ["recipe_status"]


def test_router_recipe_status_intent_for_current_recipes_phrase() -> None:
    router = KeywordRouter(RoutingConfig())
    decision = router.classify("Was sind deine aktuellen Skills?")
    assert decision.intents == ["recipe_status"]


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


def test_router_english_recipe_status_intent() -> None:
    routing = RoutingConfig().for_language("en")
    router = KeywordRouter(routing)
    decision = router.classify("What skills are active right now?")
    assert decision.intents == ["recipe_status"]

def test_router_speicherplatz_is_not_memory_store() -> None:
    router = KeywordRouter(RoutingConfig())
    decision = router.classify("hab ich noch genug speicherplatz auf meinen servern ?")

    assert decision.intents == ["chat"]


def test_router_speicher_frei_disk_question_is_not_memory_store() -> None:
    router = KeywordRouter(RoutingConfig())
    decision = router.classify("hab ich auf all meinen server mehr als 10gb harddisk speicher frei ?")

    assert decision.intents == ["chat"]


def test_router_speichere_still_maps_to_memory_store() -> None:
    router = KeywordRouter(RoutingConfig())
    decision = router.classify("Speichere, dass mein NAS nachts Backups macht")

    assert decision.intents == ["memory_store"]
