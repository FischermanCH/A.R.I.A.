from pathlib import Path

from aria.modules.native_agent.handler import _MEMORY_QUESTION_WORDS, _memory_learning_prefilter


ROOT = Path(__file__).resolve().parents[1]


def test_first_token_question_word_skips_memory_learning_without_question_mark() -> None:
    assert _MEMORY_QUESTION_WORDS == {
        "was", "wie", "wer", "wen", "wem", "wessen", "wo", "wohin", "woher", "wann", "warum", "wieso",
        "weshalb", "welche", "welcher", "welches", "welchen", "welchem",
        "what", "how", "who", "whom", "where", "when", "why", "which",
    }
    assert _memory_learning_prefilter("was ist mein bevorzugter Antwort-Stil") is False
    assert _memory_learning_prefilter("which answer style works best for me") is False


def test_durable_first_person_statement_still_passes_memory_learning_prefilter() -> None:
    assert _memory_learning_prefilter("ich grille am liebsten mit Holzkohle") is True


def test_trailing_question_mark_still_skips_memory_learning() -> None:
    assert _memory_learning_prefilter("ich grille am liebsten mit Holzkohle?") is False


def test_chat_template_has_no_legacy_auto_memory_status_badge() -> None:
    template = (ROOT / "aria/templates/chat.html").read_text(encoding="utf-8")

    assert "auto-memory-indicator" not in template
    assert "memory_admin_auto_memory_path" not in template
    assert "chat.debug_auto_memory_learning" not in template
