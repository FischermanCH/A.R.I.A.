from __future__ import annotations

from pathlib import Path
from typing import Any

from aria.core.i18n import I18NStore

_RECIPE_RUNTIME_STATUS_I18N = I18NStore(Path(__file__).resolve().parents[1] / "i18n")


def _status_text(language: str | None, key: str, default: str = "", **values: Any) -> str:
    template = _RECIPE_RUNTIME_STATUS_I18N.t(language or "de", f"recipe_runtime.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template


def build_recipe_status_text(settings: Any, runtime_recipes: list[dict[str, Any]], auto_memory_enabled: bool, *, language: str = "de") -> str:
    lines = [_status_text(language, "status_title", "Recipes (Runtime status):"), ""]
    searxng_rows = getattr(getattr(settings, "connections", object()), "searxng", {})
    core_rows = [
        ("Core", "Memory", bool(settings.memory.enabled), _status_text(language, "status_memory_purpose", "Stores and recalls knowledge via Qdrant.")),
        ("Core", "Auto-Memory", bool(auto_memory_enabled), _status_text(language, "status_auto_memory_purpose", "Extracts facts and preferences automatically from chat messages.")),
        (
            "Core",
            "Web Search",
            bool(isinstance(searxng_rows, dict) and searxng_rows),
            _status_text(language, "status_web_search_purpose", "Searches the web via SearXNG and returns sources directly in chat."),
        ),
    ]
    recipe_rows: list[tuple[str, str, bool, str]] = []
    for row in sorted(runtime_recipes, key=lambda item: str(item.get("name", "")).lower()):
        name = str(row.get("name", "")).strip() or str(row.get("id", "custom"))
        enabled = bool(row.get("enabled", False))
        description = str(row.get("description", "")).strip() or _status_text(language, "status_no_purpose", "No purpose stored.")
        connections = row.get("connections", [])
        if isinstance(connections, list) and connections:
            conn_text = ", ".join(str(item).strip() for item in connections if str(item).strip())
            if conn_text:
                description = f"{description} (Connections: {conn_text})"
        recipe_rows.append(("Custom", name, enabled, description))

    active_rows: list[tuple[str, str, str]] = []
    inactive_rows: list[tuple[str, str, str]] = []
    for kind, name, enabled, purpose in [*core_rows, *recipe_rows]:
        (active_rows if enabled else inactive_rows).append((kind, name, purpose))

    lines.append(_status_text(language, "status_active", "Active:"))
    if active_rows:
        for kind, name, purpose in active_rows:
            lines.append(f"- [{kind}] {name} — {purpose}")
    else:
        lines.append(_status_text(language, "status_no_active", "- No active recipes."))

    lines.append("")
    lines.append(_status_text(language, "status_disabled", "Disabled:"))
    if inactive_rows:
        for kind, name, purpose in inactive_rows:
            lines.append(f"- [{kind}] {name} — {purpose}")
    else:
        lines.append(_status_text(language, "status_no_disabled", "- No disabled recipes."))
    return "\n".join(lines)
