from __future__ import annotations

from pathlib import Path
from typing import Any

from aria.modules.connections_semantic.resolver import normalize_connection_alias
from aria.modules.platform_primitives.i18n import I18NStore
from aria.modules.website_ui.links import website_create_path, website_manage_path

_WEBSITE_RUNTIME_I18N = I18NStore(Path(__file__).resolve().parents[2] / "i18n")


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
    lines.append(f"  `{website_manage_path(ref)}`")
    return "\n".join(lines)


def find_matching_group_name(query: str, rows: dict[str, dict[str, object]]) -> str:
    clean_query = normalize_connection_alias(query)
    matches: list[str] = []
    for row in rows.values():
        group_name = str(row.get("group_name", "") or "").strip()
        if group_name and normalize_connection_alias(group_name) == clean_query and group_name not in matches:
            matches.append(group_name)
    return matches[0] if len(matches) == 1 else ""


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
        lines.append(f"`{website_manage_path(ref)}`")
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
    lines.append(f"`{website_manage_path(ref)}`")
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
                    f"Open: `{website_create_path()}`"
                )
            lines = [f"Watched websites in `{clean_group}`: {len(filtered)} entries."]
        else:
            if not filtered:
                return _website_text(
                    language,
                    "group_empty",
                    "I could not find watched websites in `{group}`.\n\nOpen: `{create_url}`",
                    group=clean_group,
                    create_url=website_create_path(),
                )
            lines = [_website_text(language, "group_list_header", "Watched websites in `{group}`: {count} entries.", group=clean_group, count=len(filtered))]
        for ref, row in filtered[:8]:
            lines.append(format_website_entry(ref, row))
        return "\n\n".join(lines)

    if str(language or "").strip().lower().startswith("en"):
        if not rows:
            return f"You do not have watched websites yet. Create one: `{website_create_path()}`"
        lines = [f"Your watched websites: {len(rows)} entries."]
    else:
        if not rows:
            return _website_text(
                language,
                "empty",
                "You do not have watched websites yet. Create one: `{create_url}`",
                create_url=website_create_path(),
            )
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
