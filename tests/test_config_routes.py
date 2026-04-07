from aria.web.config_routes import (
    EMBEDDING_SWITCH_CONFIRM_PHRASE,
    _embedding_fingerprint_for_values,
    _embedding_switch_requires_confirmation,
    _memory_point_totals,
    _resolve_embedding_model_label,
    _short_fingerprint,
)


def test_embedding_switch_requires_confirmation_only_with_existing_memory() -> None:
    current = _embedding_fingerprint_for_values("nomic-embed-text", "http://localhost:11434")
    new = _embedding_fingerprint_for_values("text-embedding-3-small", "https://api.openai.com/v1")

    assert _embedding_switch_requires_confirmation(current, new, 12) is True
    assert _embedding_switch_requires_confirmation(current, current, 12) is False
    assert _embedding_switch_requires_confirmation(current, new, 0) is False


def test_memory_point_totals_sums_points_and_collections() -> None:
    total_points, total_collections = _memory_point_totals(
        [{"name": "a", "points": 4}, {"name": "b", "points": 7}]
    )

    assert total_points == 11
    assert total_collections == 2


def test_embedding_helpers_normalize_expected_values() -> None:
    assert _resolve_embedding_model_label("text-embedding-3-small", "https://api.openai.com/v1") == "openai/text-embedding-3-small"
    assert len(_short_fingerprint("abcdef1234567890")) == 12
    assert EMBEDDING_SWITCH_CONFIRM_PHRASE == "EMBEDDINGS WECHSELN"
