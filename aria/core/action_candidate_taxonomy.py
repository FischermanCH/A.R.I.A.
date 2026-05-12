from __future__ import annotations

from pathlib import Path

from aria.core.i18n import I18NStore
from aria.core.text_utils import is_german

_ACTION_CANDIDATE_I18N = I18NStore(Path(__file__).resolve().parents[1] / "i18n")


def _candidate_text(language: str | None, key: str, default: str = "") -> str:
    return _ACTION_CANDIDATE_I18N.t(language or "de", f"action_candidate_taxonomy.{key}", default or key)


TEMPLATE_CANDIDATE_KIND = "template"
RECIPE_CANDIDATE_KIND = "recipe"
LEGACY_SKILL_CANDIDATE_KIND = "skill"

TEMPLATE_CANDIDATE_ROLE = "template_candidate"
STORED_RECIPE_CANDIDATE_ROLE = "stored_recipe_candidate"
LEARNED_RECIPE_CANDIDATE_ROLE = "learned_recipe_candidate"

BUILT_IN_TEMPLATE_ORIGIN = "built_in_template_library"
STORED_RECIPE_MANIFEST_ORIGIN = "stored_recipe_manifest"
CUSTOM_SKILL_MANIFEST_ORIGIN = STORED_RECIPE_MANIFEST_ORIGIN
LEARNED_EXPERIENCE_ORIGIN = "learned_experience_store"


def _localized_text(language: str, *, de: str, en: str) -> str:
    return de if is_german(language) else en


def normalize_action_candidate_kind(kind: str) -> str:
    clean = str(kind or "").strip().lower()
    if clean == LEGACY_SKILL_CANDIDATE_KIND:
        return RECIPE_CANDIDATE_KIND
    if clean in {TEMPLATE_CANDIDATE_KIND, RECIPE_CANDIDATE_KIND}:
        return clean
    return clean


def is_recipe_candidate_kind(kind: str) -> bool:
    return normalize_action_candidate_kind(kind) == RECIPE_CANDIDATE_KIND


def candidate_role_priority(role: str) -> int:
    clean = str(role or "").strip().lower()
    if clean == TEMPLATE_CANDIDATE_ROLE:
        return 0
    if clean == STORED_RECIPE_CANDIDATE_ROLE:
        return 1
    if clean == LEARNED_RECIPE_CANDIDATE_ROLE:
        return 2
    return 9


def candidate_origin_priority(origin: str) -> int:
    clean = str(origin or "").strip().lower()
    if clean == BUILT_IN_TEMPLATE_ORIGIN:
        return 0
    if clean == STORED_RECIPE_MANIFEST_ORIGIN:
        return 1
    if clean == LEARNED_EXPERIENCE_ORIGIN:
        return 2
    return 9


def candidate_debug_label(role: str, language: str = "") -> str:
    clean = str(role or "").strip().lower()
    if clean == TEMPLATE_CANDIDATE_ROLE:
        return _localized_text(language, de="Template-Kandidat", en="Template candidate")
    if clean == STORED_RECIPE_CANDIDATE_ROLE:
        return _candidate_text(language, "stored_recipe_candidate", "Stored recipe candidate")
    if clean == LEARNED_RECIPE_CANDIDATE_ROLE:
        return _candidate_text(language, "learned_recipe_candidate", "Learned recipe candidate")
    return _localized_text(language, de="Aktions-Kandidat", en="Action candidate")


def candidate_kind_label(kind: str, *, role: str = "", language: str = "") -> str:
    clean_kind = normalize_action_candidate_kind(kind)
    clean_role = str(role or "").strip().lower()
    if clean_kind == TEMPLATE_CANDIDATE_KIND:
        return _localized_text(language, de="Template", en="Template")
    if clean_kind == RECIPE_CANDIDATE_KIND:
        if clean_role == LEARNED_RECIPE_CANDIDATE_ROLE:
            return _candidate_text(language, "learned_recipe", "Learned recipe")
        return _candidate_text(language, "recipe", "Recipe")
    return clean_kind
