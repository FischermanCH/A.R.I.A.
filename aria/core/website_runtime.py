from __future__ import annotations

from pathlib import Path
from typing import Any

from aria.core.connection_semantic_resolver import build_connection_aliases
from aria.core.connection_semantic_resolver import connection_label_match_score
from aria.core.connection_semantic_resolver import normalize_connection_alias
from aria.core.i18n import I18NStore

_WEBSITE_RUNTIME_I18N = I18NStore(Path(__file__).resolve().parents[1] / "i18n")


def _website_text(language: str | None, key: str, default: str = "", **values: object) -> str:
    template = _WEBSITE_RUNTIME_I18N.t(language or "de", f"website_runtime.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template
def normalize_website_rows(rows: dict[str, Any] | None) -> dict[str, dict[str, object]]:
    normalized: dict[str, dict[str, object]] = {}
    for ref, value in dict(rows or {}).items():
        clean_ref = str(ref or "").strip()
        if hasattr(value, "model_dump"):
            value = value.model_dump()
        if not clean_ref or not isinstance(value, dict):
            continue
        normalized[clean_ref] = {
            "url": str(value.get("url", "") or "").strip(),
            "group_name": str(value.get("group_name", "") or "").strip(),
            "title": str(value.get("title", "") or "").strip(),
            "description": str(value.get("description", "") or "").strip(),
            "tags": [str(item or "").strip() for item in list(value.get("tags", []) or []) if str(item or "").strip()],
            "aliases": [str(item or "").strip() for item in list(value.get("aliases", []) or []) if str(item or "").strip()],
        }
    return normalized


def website_aliases(ref: str, row: dict[str, object]) -> list[str]:
    aliases = build_connection_aliases("website", ref, row)
    url = str(row.get("url", "") or "").strip()
    if url:
        aliases.append(url)
    lower_blob = " ".join(
        str(row.get(field, "") or "").strip().lower()
        for field in ("title", "description", "group_name")
    )
    tag_blob = " ".join(str(item or "").strip().lower() for item in list(row.get("tags", []) or []))
    combined_blob = f"{lower_blob} {tag_blob}"
    if any(token in combined_blob for token in ("docs", "documentation", "dokumentation")):
        aliases.extend(["docs", "documentation", "dokumentation"])
    seen: list[str] = []
    for item in aliases:
        clean = normalize_connection_alias(item)
        if clean and clean not in seen:
            seen.append(clean)
    return seen


def find_website_matches(query: str, rows: dict[str, dict[str, object]]) -> list[tuple[int, str, dict[str, object]]]:
    clean_query = str(query or "").strip()
    candidates: list[tuple[int, str, dict[str, object]]] = []
    for ref, row in rows.items():
        best_score = 0
        for alias in website_aliases(ref, row):
            best_score = max(best_score, connection_label_match_score(clean_query, alias))
        if best_score <= 0:
            continue
        candidates.append((best_score, ref, row))
    candidates.sort(key=lambda item: (-item[0], item[1]))
    return candidates


def format_website_entry(ref: str, row: dict[str, object]) -> str:
    title = str(row.get("title", "") or "").strip() or ref
    url = str(row.get("url", "") or "").strip()
    group = str(row.get("group_name", "") or "").strip()
    description = str(row.get("description", "") or "").strip()
    tags = [str(item or "").strip() for item in list(row.get("tags", []) or []) if str(item or "").strip()]
    lines = [f"- {title} · `{ref}`{f' · {group}' if group else ''}"]
    if description:
        lines.append(f"  {description}")
    if tags:
        lines.append(f"  Tags: {', '.join(tags[:4])}")
    if url:
        lines.append(f"  {url}")
    lines.append(f"  `/config/connections/websites?website_ref={ref}#manage-existing`")
    return "\n".join(lines)


def find_matching_group_name(query: str, rows: dict[str, dict[str, object]]) -> str:
    best_group = ""
    best_score = 0
    grouped: dict[str, list[tuple[str, dict[str, object]]]] = {}
    for ref, row in rows.items():
        group_name = str(row.get("group_name", "") or "").strip()
        if not group_name:
            continue
        grouped.setdefault(group_name, []).append((ref, row))

    for group_name, items in grouped.items():
        score = connection_label_match_score(query, group_name)
        for ref, row in items:
            for alias in website_aliases(ref, row):
                score = max(score, connection_label_match_score(query, alias))
        if score > best_score:
            best_score = score
            best_group = group_name
    return best_group


def build_website_read_text(ref: str, row: dict[str, object], *, language: str = "de") -> str:
    title = str(row.get("title", "") or "").strip() or ref
    url = str(row.get("url", "") or "").strip()
    description = str(row.get("description", "") or "").strip()
    group = str(row.get("group_name", "") or "").strip()
    tags = [str(item or "").strip() for item in list(row.get("tags", []) or []) if str(item or "").strip()]
    if str(language or "").strip().lower().startswith("en"):
        lines = [f"Watched website: **{title}** · `{ref}`"]
        if group:
            lines.append(f"Group: `{group}`")
        if description:
            lines.append(description)
        if tags:
            lines.append(f"Tags: {', '.join(tags[:5])}")
        if url:
            lines.append(url)
        lines.append(f"`/config/connections/websites?website_ref={ref}#manage-existing`")
        return "\n\n".join(lines)
    lines = [_website_text(language, "read_header", "Watched website: **{title}** · `{ref}`", title=title, ref=ref)]
    if group:
        lines.append(_website_text(language, "group_line", "Group: `{group}`", group=group))
    if description:
        lines.append(description)
    if tags:
        lines.append(f"Tags: {', '.join(tags[:5])}")
    if url:
        lines.append(url)
    lines.append(f"`/config/connections/websites?website_ref={ref}#manage-existing`")
    return "\n\n".join(lines)


def build_website_list_text(
    rows: dict[str, dict[str, object]],
    *,
    group_name: str = "",
    language: str = "de",
) -> str:
    clean_group = str(group_name or "").strip()
    if clean_group:
        filtered = [
            (ref, row)
            for ref, row in rows.items()
            if str(row.get("group_name", "") or "").strip().lower() == clean_group.lower()
        ]
        if str(language or "").strip().lower().startswith("en"):
            if not filtered:
                return (
                    f"I could not find watched websites in `{clean_group}`.\n\n"
                    f"Open: `/config/connections/websites?mode=create#create-new`"
                )
            lines = [f"Watched websites in `{clean_group}`: {len(filtered)} entries."]
        else:
            if not filtered:
                return _website_text(
                    language,
                    "group_empty",
                    "I could not find watched websites in `{group}`.\n\nOpen: `/config/connections/websites?mode=create#create-new`",
                    group=clean_group,
                )
            lines = [_website_text(language, "group_list_header", "Watched websites in `{group}`: {count} entries.", group=clean_group, count=len(filtered))]
        for ref, row in filtered[:8]:
            lines.append(format_website_entry(ref, row))
        return "\n\n".join(lines)

    if str(language or "").strip().lower().startswith("en"):
        if not rows:
            return "You do not have watched websites yet. Create one: `/config/connections/websites?mode=create#create-new`"
        lines = [f"Your watched websites: {len(rows)} entries."]
    else:
        if not rows:
            return _website_text(language, "empty", "You do not have watched websites yet. Create one: `/config/connections/websites?mode=create#create-new`")
        lines = [_website_text(language, "list_header", "Your watched websites: {count} entries.", count=len(rows))]
    groups: dict[str, int] = {}
    for row in rows.values():
        group_name_value = str(row.get("group_name", "") or "").strip()
        if group_name_value:
            groups[group_name_value] = groups.get(group_name_value, 0) + 1
    if groups:
        prefix = _website_text(language, "groups_prefix", "Groups: ")
        lines.append(prefix + ", ".join(f"{name} ({count})" for name, count in sorted(groups.items())))
    for ref, row in list(rows.items())[:10]:
        lines.append(format_website_entry(ref, row))
    return "\n\n".join(lines)
