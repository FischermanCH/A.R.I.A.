from __future__ import annotations

from aria.core.qdrant_collection_classifier import classify_qdrant_collection
from aria.core.qdrant_collection_classifier import is_notes_qdrant_collection
from aria.core.qdrant_collection_classifier import is_recipe_experience_qdrant_collection
from aria.core.qdrant_collection_classifier import is_routing_qdrant_collection


def test_recipe_experience_collection_is_system_learning_memory() -> None:
    row = classify_qdrant_collection("aria_recipe_experience_demo_user")

    assert row.kind == "recipe_experience"
    assert row.group == "system"
    assert row.is_system is True
    assert row.is_user_memory is False
    assert is_recipe_experience_qdrant_collection("aria_recipe_experience_demo_user") is True


def test_future_aria_collection_remains_visible_as_system() -> None:
    row = classify_qdrant_collection("aria_future_signal_demo_user")

    assert row.kind == "system"
    assert row.group == "system"
    assert row.is_system is True


def test_user_memory_collections_are_not_generic_system_collections() -> None:
    assert classify_qdrant_collection("aria_docs_demo_user_manuals").kind == "document"
    assert classify_qdrant_collection("aria_facts_demo_user").kind == "fact"
    assert classify_qdrant_collection("aria_preferences_demo_user").kind == "preference"
    assert classify_qdrant_collection("aria_sessions_demo_user_260513").kind == "session"
    assert classify_qdrant_collection("aria_context-mem_demo_user").kind == "knowledge"

    for name in (
        "aria_docs_demo_user_manuals",
        "aria_facts_demo_user",
        "aria_preferences_demo_user",
        "aria_sessions_demo_user_260513",
        "aria_context-mem_demo_user",
    ):
        assert classify_qdrant_collection(name).is_user_memory is True
        assert classify_qdrant_collection(name).is_system is False


def test_notes_and_routing_helpers_keep_scope_boundaries() -> None:
    assert is_notes_qdrant_collection("aria_notes_demo_user", username="demo_user") is True
    assert is_notes_qdrant_collection("aria_notes_other", username="demo_user") is False
    assert is_routing_qdrant_collection("aria_routing_connections_aria_8800") is True


def test_prefix_matching_avoids_accidental_partial_names() -> None:
    assert is_recipe_experience_qdrant_collection("aria_recipe_experience_demo_user") is True
    assert is_recipe_experience_qdrant_collection("aria_recipe_experiencefoo") is False
