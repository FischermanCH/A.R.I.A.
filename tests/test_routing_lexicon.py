from aria.core.config import RoutingConfig
from aria.core.routing_lexicon import get_default_capability_lexicon
from aria.core.routing_lexicon import get_default_routing_languages
from aria.core.routing_lexicon import get_default_routing_profile


def test_default_german_routing_profile_is_deduplicated() -> None:
    profile = get_default_routing_profile("de")
    assert profile["memory_recall_keywords"].count("weisst du noch") == 1
    assert profile["memory_store_prefixes"].count("vergiss nicht ") == 1


def test_default_german_prefixes_keep_trailing_spaces() -> None:
    profile = get_default_routing_profile("de")
    assert "merk dir, dass " in profile["memory_store_prefixes"]
    assert "search the web " in profile["web_search_prefixes"]


def test_routing_config_ships_english_language_profile() -> None:
    routing = RoutingConfig()
    english = routing.for_language("en")
    assert "remember this" in english.memory_store_keywords
    assert "search the web" in english.web_search_keywords
    assert "what skills are active" in english.skill_status_keywords


def test_default_routing_languages_excludes_base_language() -> None:
    languages = get_default_routing_languages()
    assert "de" not in languages
    assert "en" in languages


def test_default_capability_lexicon_ships_english_web_terms() -> None:
    lexicon = get_default_capability_lexicon("en")
    assert "search the web" in lexicon.explicit_web_search_terms
    assert "show me the contents" in lexicon.read_terms
