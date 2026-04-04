from aria.core.auto_memory import AutoMemoryExtractor


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
