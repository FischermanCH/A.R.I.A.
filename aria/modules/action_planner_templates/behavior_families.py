from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from aria.modules.action_planner_templates.behavior_family_file_operation import FILE_OPERATION_BEHAVIOR_TO_MODE
from aria.modules.action_planner_templates.behavior_family_file_operation import FILE_OPERATION_PLAN_CLASS_TO_MODE
from aria.modules.platform_primitives.i18n import I18NStore

_BEHAVIOR_FAMILIES_I18N = I18NStore(Path(__file__).resolve().parents[2] / "i18n")


def _behavior_text(language: str | None, key: str, default: str = "", **values: object) -> str:
    template = _BEHAVIOR_FAMILIES_I18N.t(language or "de", f"behavior_families.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template


@dataclass(frozen=True, slots=True)
class BehaviorFamilySpec:
    family_id: str
    behavior_profiles: tuple[str, ...]
    plan_classes: tuple[str, ...]


BEHAVIOR_FAMILY_REGISTRY: dict[str, BehaviorFamilySpec] = {
    "file_operation": BehaviorFamilySpec(
        family_id="file_operation",
        behavior_profiles=tuple(FILE_OPERATION_BEHAVIOR_TO_MODE.keys()),
        plan_classes=tuple(FILE_OPERATION_PLAN_CLASS_TO_MODE.keys()),
    ),
    "source_lookup": BehaviorFamilySpec(
        family_id="source_lookup",
        behavior_profiles=("rss_read_feed", "website_read", "website_list"),
        plan_classes=("feed_digest", "website_reference", "website_listing"),
    ),
    "mailbox_access": BehaviorFamilySpec(
        family_id="mailbox_access",
        behavior_profiles=("imap_read_mailbox", "imap_search_mailbox"),
        plan_classes=("mailbox_read_basic", "mailbox_search_basic"),
    ),
    "request_target": BehaviorFamilySpec(
        family_id="request_target",
        behavior_profiles=("http_api_request",),
        plan_classes=("api_request_basic",),
    ),
}

SOURCE_LOOKUP_BEHAVIOR_TO_MODE: dict[str, str] = {
    "rss_read_feed": "digest",
    "website_read": "reference",
    "website_list": "listing",
}

SOURCE_LOOKUP_PLAN_CLASS_TO_MODE: dict[str, str] = {
    "feed_digest": "digest",
    "website_reference": "reference",
    "website_listing": "listing",
}

MAILBOX_ACCESS_BEHAVIOR_TO_MODE: dict[str, str] = {
    "imap_read_mailbox": "read",
    "imap_search_mailbox": "search",
}

MAILBOX_ACCESS_PLAN_CLASS_TO_MODE: dict[str, str] = {
    "mailbox_read_basic": "read",
    "mailbox_search_basic": "search",
}

REQUEST_TARGET_BEHAVIOR_TO_MODE: dict[str, str] = {
    "http_api_request": "request",
}

REQUEST_TARGET_PLAN_CLASS_TO_MODE: dict[str, str] = {
    "api_request_basic": "request",
}


def behavior_family_id_for(*, behavior_profile: str = "", plan_class: str = "") -> str:
    clean_profile = str(behavior_profile or "").strip().lower()
    clean_plan_class = str(plan_class or "").strip().lower()
    for family_id, spec in BEHAVIOR_FAMILY_REGISTRY.items():
        if clean_profile and clean_profile in spec.behavior_profiles:
            return family_id
        if clean_plan_class and clean_plan_class in spec.plan_classes:
            return family_id
    return ""


def source_lookup_mode(*, behavior_profile: str = "", plan_class: str = "") -> str:
    clean_profile = str(behavior_profile or "").strip().lower()
    clean_plan_class = str(plan_class or "").strip().lower()
    if clean_profile in SOURCE_LOOKUP_BEHAVIOR_TO_MODE:
        return SOURCE_LOOKUP_BEHAVIOR_TO_MODE[clean_profile]
    return SOURCE_LOOKUP_PLAN_CLASS_TO_MODE.get(clean_plan_class, "")


def source_lookup_behavior_profile_for(plan_class: str) -> str:
    mode = source_lookup_mode(plan_class=plan_class)
    for profile, profile_mode in SOURCE_LOOKUP_BEHAVIOR_TO_MODE.items():
        if profile_mode == mode:
            return profile
    return ""


def mailbox_access_mode(*, behavior_profile: str = "", plan_class: str = "") -> str:
    clean_profile = str(behavior_profile or "").strip().lower()
    clean_plan_class = str(plan_class or "").strip().lower()
    if clean_profile in MAILBOX_ACCESS_BEHAVIOR_TO_MODE:
        return MAILBOX_ACCESS_BEHAVIOR_TO_MODE[clean_profile]
    return MAILBOX_ACCESS_PLAN_CLASS_TO_MODE.get(clean_plan_class, "")


def mailbox_access_behavior_profile_for(plan_class: str) -> str:
    mode = mailbox_access_mode(plan_class=plan_class)
    for profile, profile_mode in MAILBOX_ACCESS_BEHAVIOR_TO_MODE.items():
        if profile_mode == mode:
            return profile
    return ""


def request_target_mode(*, behavior_profile: str = "", plan_class: str = "") -> str:
    clean_profile = str(behavior_profile or "").strip().lower()
    clean_plan_class = str(plan_class or "").strip().lower()
    if clean_profile in REQUEST_TARGET_BEHAVIOR_TO_MODE:
        return REQUEST_TARGET_BEHAVIOR_TO_MODE[clean_profile]
    return REQUEST_TARGET_PLAN_CLASS_TO_MODE.get(clean_plan_class, "")


def request_target_behavior_profile_for(plan_class: str) -> str:
    mode = request_target_mode(plan_class=plan_class)
    for profile, profile_mode in REQUEST_TARGET_BEHAVIOR_TO_MODE.items():
        if profile_mode == mode:
            return profile
    return ""


def build_source_lookup_preview(
    *,
    mode: str,
    language: str,
    group_name: str = "",
    fallback: str,
) -> str:
    clean_mode = str(mode or "").strip().lower()
    if clean_mode == "digest":
        return _behavior_text(language, "source_lookup_preview_digest", "Read recent feed entries")
    if clean_mode == "reference":
        return _behavior_text(language, "source_lookup_preview_reference", "Open watched website")
    if clean_mode == "listing":
        prefix = _behavior_text(language, "source_lookup_preview_listing_prefix", "Watched websites")
        return f"{prefix}: {group_name}" if str(group_name or "").strip() else fallback
    return fallback


def derive_source_lookup_inputs(
    *,
    mode: str,
    extract_website_group: Callable[[str], str],
    query: str,
) -> dict[str, str]:
    if str(mode or "").strip().lower() != "listing":
        return {}
    group = extract_website_group(query)
    return {"group_name": group} if group else {}


def build_source_lookup_draft(
    *,
    mode: str,
    query: str,
    extract_website_group: Callable[[str], str],
) -> tuple[str, str, str]:
    clean_mode = str(mode or "").strip().lower()
    if clean_mode == "digest":
        return "feed_read", "", "Read recent feed entries"
    if clean_mode == "reference":
        return "website_read", "", "Open watched website"
    if clean_mode == "listing":
        group = extract_website_group(query)
        return "website_list", group, "List watched websites"
    return "", "", ""


def build_mailbox_access_preview(*, mode: str, language: str, search_query: str = "", fallback: str) -> str:
    clean_mode = str(mode or "").strip().lower()
    is_de = str(language or "").strip().lower().startswith("de")
    if clean_mode == "read":
        return "Neueste E-Mails im Postfach lesen" if is_de else "Read the latest emails from the mailbox"
    if clean_mode == "search":
        prefix = "Mailbox-Suche" if is_de else "Mailbox search"
        return f"{prefix}: {search_query}" if str(search_query or "").strip() else fallback
    return fallback


def derive_mailbox_access_inputs(*, mode: str, search_query: str) -> dict[str, str]:
    if str(mode or "").strip().lower() != "search":
        return {}
    clean_search = str(search_query or "").strip()
    return {"search_query": clean_search} if clean_search else {}


def build_mailbox_access_draft(*, mode: str, search_query: str) -> tuple[str, str, str]:
    clean_mode = str(mode or "").strip().lower()
    if clean_mode == "read":
        return "mail_read", "", "Read latest mailbox entries"
    if clean_mode == "search":
        return "mail_search", str(search_query or "").strip(), (
            f"Mailbox search: {search_query}" if str(search_query or "").strip() else "Mailbox search query still missing"
        )
    return "", "", ""


def build_request_target_preview(*, mode: str, path: str, fallback: str) -> str:
    if str(mode or "").strip().lower() != "request":
        return fallback
    return f"HTTP request path: {path}" if str(path or "").strip() else "API path still missing"


def build_request_target_draft(*, mode: str, path: str) -> tuple[str, str]:
    if str(mode or "").strip().lower() != "request":
        return "", ""
    return "api_request", str(path or "").strip()
