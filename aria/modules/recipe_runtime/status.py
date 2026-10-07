from __future__ import annotations

from pathlib import Path
from string import Formatter
from typing import Any

from aria.modules.platform_primitives.i18n import I18NStore

_RECIPE_RUNTIME_STATUS_I18N = I18NStore(Path(__file__).resolve().parents[2] / "i18n")


def _status_text(language: str | None, key: str, default: str = "", **values: Any) -> str:
    template = _RECIPE_RUNTIME_STATUS_I18N.t(language or "de", f"recipe_runtime.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template


def build_recipe_status_text(settings: Any, runtime_recipes: list[dict[str, Any]], *, language: str = "de") -> str:
    lines = [_status_text(language, "status_title", "Recipes (Runtime status):"), ""]
    core_rows = [
        ("Core", "Memory", bool(settings.memory.enabled), _status_text(language, "status_memory_purpose", "Stores and recalls knowledge via Qdrant.")),
        (
            "Core",
            "Web Search",
            True,
            _status_text(language, "status_web_search_purpose", "Searches the web through ARIA's managed service and returns sources directly in chat."),
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


def _enabled_recipe_rows(runtime_recipes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        (
            row
            for row in runtime_recipes
            if isinstance(row, dict)
            and bool(row.get("enabled", False))
            and str(row.get("id") or "").strip()
        ),
        key=lambda row: str(row.get("id") or ""),
    )


def _template_inputs(value: Any) -> list[str]:
    fields: list[str] = []
    try:
        parsed = Formatter().parse(str(value or ""))
        for _literal, field_name, _format_spec, _conversion in parsed:
            clean = str(field_name or "").strip()
            if clean and clean not in fields:
                fields.append(clean)
    except (ValueError, TypeError):
        return []
    return fields


def _recipe_step_lines(row: dict[str, Any], *, include_inputs: bool, language: str) -> list[str]:
    lines: list[str] = []
    input_names: list[str] = []
    for index, step in enumerate(list(row.get("steps") or []), start=1):
        if not isinstance(step, dict):
            continue
        step_name = str(step.get("name") or step.get("id") or step.get("type") or index).strip()
        step_type = str(step.get("type") or "").strip()
        lines.append(f"{index}. **{step_name}** (`{step_type}`)")
        params = step.get("params")
        if not isinstance(params, dict):
            continue
        for key, value in params.items():
            clean_key = str(key or "").strip()
            if not clean_key:
                continue
            clean_value = str(value or "").strip()
            lines.append(f"   - `{clean_key}`: `{clean_value}`")
            for field_name in _template_inputs(clean_value):
                if field_name not in input_names:
                    input_names.append(field_name)
    if include_inputs:
        lines.extend(
            [
                "",
                f"**{_status_text(language, 'presentation_inputs', 'Inputs')}**: "
                + (", ".join(f"`{name}`" for name in input_names) if input_names else _status_text(language, "presentation_no_inputs", "No unresolved inputs")),
            ]
        )
    return lines


def render_recipe_turn(
    operation: str,
    recipe_id: str,
    runtime_recipes: list[dict[str, Any]],
    *,
    language: str = "de",
) -> str:
    rows = _enabled_recipe_rows(runtime_recipes)
    if operation == "inventory":
        if not rows:
            return _status_text(language, "presentation_empty", "No enabled stored recipes are available.")
        lines = [f"## {_status_text(language, 'presentation_inventory_title', 'Stored recipes')}"]
        for row in rows:
            current_id = str(row.get("id") or "").strip()
            name = str(row.get("name") or current_id).strip()
            purpose = str(row.get("description") or "").strip() or _status_text(
                language,
                "status_no_purpose",
                "No purpose stored.",
            )
            connections = ", ".join(
                str(item).strip()
                for item in list(row.get("connections") or [])
                if str(item).strip()
            ) or _status_text(language, "presentation_no_connections", "None declared")
            lines.extend(
                [
                    "",
                    f"### {name}",
                    f"- **ID:** `{current_id}`",
                    f"- **{_status_text(language, 'presentation_purpose', 'Purpose')}:** {purpose}",
                    f"- **{_status_text(language, 'presentation_connections', 'Connections')}:** {connections}",
                ]
            )
        lines.extend(["", _status_text(language, "presentation_not_executed", "Nothing was executed.")])
        return "\n".join(lines)

    selected = next((row for row in rows if str(row.get("id") or "").strip() == recipe_id), None)
    if selected is None:
        return _status_text(language, "presentation_not_found", "No matching enabled stored recipe was found.")

    name = str(selected.get("name") or recipe_id).strip()
    description = str(selected.get("description") or "").strip() or _status_text(
        language,
        "status_no_purpose",
        "No purpose stored.",
    )
    connections = ", ".join(
        str(item).strip()
        for item in list(selected.get("connections") or [])
        if str(item).strip()
    ) or _status_text(language, "presentation_no_connections", "None declared")
    title_key = "presentation_preview_title" if operation == "preview" else "presentation_explain_title"
    title_default = "Recipe preview" if operation == "preview" else "Stored recipe"
    lines = [
        f"## {_status_text(language, title_key, title_default)}: {name}",
        "",
        f"- **ID:** `{recipe_id}`",
        f"- **{_status_text(language, 'presentation_purpose', 'Purpose')}:** {description}",
        f"- **{_status_text(language, 'presentation_connections', 'Connections')}:** {connections}",
        "",
        f"### {_status_text(language, 'presentation_steps', 'Steps')}",
        *_recipe_step_lines(selected, include_inputs=operation == "preview", language=language),
    ]
    if operation == "preview":
        lines.extend(
            [
                "",
                f"**{_status_text(language, 'presentation_confirmation', 'Confirmation')}**: "
                + _status_text(language, "presentation_confirmation_required", "Required before execution"),
            ]
        )
    lines.extend(["", _status_text(language, "presentation_not_executed", "Nothing was executed.")])
    return "\n".join(lines)
