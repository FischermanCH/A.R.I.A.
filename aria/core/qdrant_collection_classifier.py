from __future__ import annotations

from dataclasses import dataclass
import re


ARIA_COLLECTION_PREFIX = "aria_"
RECIPE_EXPERIENCE_PREFIX = "aria_recipe_experience"
ROUTING_PREFIX = "aria_routing"
NOTES_PREFIX = "aria_notes"
DOCUMENT_PREFIX = "aria_docs"
FACTS_PREFIX = "aria_facts"
PREFERENCES_PREFIX = "aria_preferences"
PREFERENCES_LEGACY_PREFIX = "aria_prefs"
SESSIONS_PREFIX = "aria_sessions"
CONTEXT_PREFIX = "aria_context-mem"
MEMORY_LEGACY_PREFIX = "aria_memory"


@dataclass(frozen=True, slots=True)
class QdrantCollectionClassification:
    name: str
    kind: str
    group: str
    is_aria: bool
    is_user_memory: bool
    is_system: bool


def _clean_name(name: str) -> str:
    return str(name or "").strip().lower()


def _slug_user_id(user_id: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_-]", "_", str(user_id or "").strip().lower())
    clean = re.sub(r"_+", "_", clean).strip("_")
    return clean or "web"


def _matches_prefix(name: str, prefix: str) -> bool:
    clean = _clean_name(name)
    clean_prefix = _clean_name(prefix)
    return bool(clean and clean_prefix) and (clean == clean_prefix or clean.startswith(f"{clean_prefix}_"))


def classify_qdrant_collection(name: str, *, username: str = "") -> QdrantCollectionClassification:
    clean = _clean_name(name)
    is_aria = clean.startswith(ARIA_COLLECTION_PREFIX)
    if not is_aria:
        return QdrantCollectionClassification(
            name=str(name or "").strip(),
            kind="external",
            group="external",
            is_aria=False,
            is_user_memory=False,
            is_system=False,
        )

    if _matches_prefix(clean, RECIPE_EXPERIENCE_PREFIX):
        return QdrantCollectionClassification(clean, "recipe_experience", "system", True, False, True)
    if _matches_prefix(clean, ROUTING_PREFIX):
        return QdrantCollectionClassification(clean, "routing", "system", True, False, True)
    if _matches_prefix(clean, NOTES_PREFIX):
        if username and clean != f"{NOTES_PREFIX}_{_slug_user_id(username)}":
            return QdrantCollectionClassification(clean, "notes", "system", True, False, False)
        return QdrantCollectionClassification(clean, "notes", "system", True, False, True)
    if _matches_prefix(clean, DOCUMENT_PREFIX):
        return QdrantCollectionClassification(clean, "document", "user_memory", True, True, False)
    if _matches_prefix(clean, FACTS_PREFIX):
        return QdrantCollectionClassification(clean, "fact", "user_memory", True, True, False)
    if _matches_prefix(clean, PREFERENCES_PREFIX) or _matches_prefix(clean, PREFERENCES_LEGACY_PREFIX):
        return QdrantCollectionClassification(clean, "preference", "user_memory", True, True, False)
    if _matches_prefix(clean, SESSIONS_PREFIX):
        return QdrantCollectionClassification(clean, "session", "user_memory", True, True, False)
    if _matches_prefix(clean, CONTEXT_PREFIX):
        return QdrantCollectionClassification(clean, "knowledge", "user_memory", True, True, False)
    if _matches_prefix(clean, MEMORY_LEGACY_PREFIX):
        return QdrantCollectionClassification(clean, "legacy_memory", "user_memory", True, True, False)
    return QdrantCollectionClassification(clean, "system", "system", True, False, True)


def is_recipe_experience_qdrant_collection(name: str) -> bool:
    return classify_qdrant_collection(name).kind == "recipe_experience"


def is_routing_qdrant_collection(name: str) -> bool:
    return classify_qdrant_collection(name).kind == "routing"


def is_notes_qdrant_collection(name: str, *, username: str = "") -> bool:
    classification = classify_qdrant_collection(name, username=username)
    return classification.kind == "notes" and (not username or classification.is_system)
