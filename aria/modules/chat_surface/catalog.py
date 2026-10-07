from __future__ import annotations

from pathlib import Path
from typing import Any

from aria.modules.connections_profiles.admin import CONNECTION_CREATE_SPECS
from aria.modules.connections_profiles.admin import CONNECTION_UPDATE_SPECS
from aria.modules.connections_catalog.catalog import connection_chat_emoji
from aria.modules.connections_catalog.catalog import connection_example_ref
from aria.modules.connections_catalog.catalog import connection_insert_template
from aria.modules.connections_catalog.catalog import connection_kind_label
from aria.modules.platform_primitives.i18n import I18NStore
from aria.modules import module_route_path

_I18N = I18NStore(Path(__file__).resolve().parents[2] / "i18n")


def _toolbox_label(lang: str, key: str, default: str) -> str:
    return _I18N.t(lang, f"chat.{key}", default)


def _toolbox_insert(lang: str, key: str, default: str) -> str:
    value = _toolbox_label(lang, key, default)
    return value if value.endswith(" ") or not value else value + " "


def _chat_connection_kind_label(kind: str) -> str:
    return connection_kind_label(kind)


def _chat_connection_example_ref(kind: str, connection_catalog: dict[str, list[str]]) -> str:
    return connection_example_ref(kind, connection_catalog)


def _chat_connection_create_insert(lang: str, kind: str, ref: str) -> str:
    return connection_insert_template(kind, "create", ref, language=lang)


def _chat_connection_update_insert(lang: str, kind: str, ref: str) -> str:
    return connection_insert_template(kind, "update", ref, language=lang)


def _localize_connection_insert(lang: str, text: str) -> str:
    del lang
    return str(text or "")


def _chat_connection_kind_icon(kind: str) -> str:
    return connection_chat_emoji(kind)


def _memory_admin_path(route_path: str) -> str:
    resolved = module_route_path("memory_admin_ui", route_path)
    if resolved is None:
        raise RuntimeError(f"memory_admin_ui route is not registered: {route_path}")
    return resolved


def _build_admin_chat_command_entries(lang: str, connection_catalog: dict[str, list[str]]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []

    for kind in sorted(CONNECTION_CREATE_SPECS.keys()):
        label_kind = _chat_connection_kind_label(kind)
        example_ref = _chat_connection_example_ref(kind, connection_catalog)
        entries.append(
            {
                "group": "admin",
                "kind": kind,
                "icon": _chat_connection_kind_icon(kind),
                "label": f"{_toolbox_label(lang, 'tool_create_connection', 'Create connection')} · {label_kind}",
                "insert": _localize_connection_insert(lang, _chat_connection_create_insert(lang, kind, example_ref)),
                "hint": _toolbox_label(
                    lang,
                    "tool_create_connection_hint",
                    "Erstellt eine einfache Connection per Chat mit Confirm-Step.",
                ),
            }
        )

    for kind in sorted(CONNECTION_UPDATE_SPECS.keys()):
        label_kind = _chat_connection_kind_label(kind)
        example_ref = _chat_connection_example_ref(kind, connection_catalog)
        entries.append(
            {
                "group": "admin",
                "kind": kind,
                "icon": _chat_connection_kind_icon(kind),
                "label": f"{_toolbox_label(lang, 'tool_update_connection', 'Update connection')} · {label_kind}",
                "insert": _localize_connection_insert(lang, _chat_connection_update_insert(lang, kind, example_ref)),
                "hint": _toolbox_label(
                    lang,
                    "tool_update_connection_hint",
                    "Aktualisiert einfache Connections oder nur Metadaten per Chat.",
                ),
            }
        )

    delete_kind = ""
    delete_ref = ""
    for kind in sorted(connection_catalog.keys()):
        refs = connection_catalog.get(kind, [])
        if refs:
            delete_kind = kind
            delete_ref = refs[0]
            break
    if not delete_kind:
        delete_kind = "rss"
        delete_ref = _chat_connection_example_ref(delete_kind, connection_catalog)
    entries.append(
        {
            "group": "admin",
            "icon": _chat_connection_kind_icon(delete_kind),
            "kind": delete_kind,
            "label": f"{_toolbox_label(lang, 'tool_delete_connection', 'Delete connection')} · {_chat_connection_kind_label(delete_kind)}",
            "insert": _toolbox_insert(lang, "tool_delete_connection_insert", "delete {kind} {ref} ").format(kind=delete_kind, ref=delete_ref),
            "hint": _toolbox_label(
                lang,
                "tool_delete_connection_hint",
                "Deletes a connection profile with a confirmation step.",
            ),
        }
    )
    return entries


def _build_system_chat_command_entries(lang: str, *, advanced_mode: bool) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    general_entries: list[dict[str, Any]] = [
        {
            "group": "commands",
            "icon": "📝",
            "label": _toolbox_label(lang, "tool_notes_open", "Open notes"),
            "insert": _toolbox_insert(lang, "tool_notes_open_insert", "open notes"),
            "hint": _toolbox_label(lang, "tool_notes_open_hint", "Opens notes management directly from chat."),
        },
        {
            "group": "documents",
            "icon": "📄",
            "label": _toolbox_label(lang, "tool_document_import", "Import document"),
            "href": f"{_memory_admin_path('/memories/import')}#document-import",
            "hint": _toolbox_label(lang, "tool_document_import_hint", "Opens document import with collection selection."),
        },
        {
            "group": "commands",
            "icon": "🗒️",
            "label": _toolbox_label(lang, "tool_notes_create", "Create note"),
            "insert": _toolbox_insert(lang, "tool_notes_create_insert", "erstelle notiz "),
            "hint": _toolbox_label(lang, "tool_notes_create_hint", "Quickly create a note in the format Title: Content."),
        },
        {
            "group": "commands",
            "icon": "💬",
            "label": _toolbox_label(lang, "tool_chat_save_note", "Save chat as note"),
            "insert": _toolbox_insert(lang, "tool_chat_save_note_insert", "/chat note"),
            "hint": _toolbox_label(lang, "tool_chat_save_note_hint", "Saves the current chat as a Markdown note and indexes it for note search."),
        },
        {
            "group": "commands",
            "icon": "✍️",
            "label": _toolbox_label(lang, "tool_notes_capture", "Capture free note"),
            "insert": _toolbox_insert(lang, "tool_notes_capture_insert", "halte fest "),
            "hint": _toolbox_label(lang, "tool_notes_capture_hint", "Stores a free-form note and automatically adds title, folder, and tags."),
        },
        {
            "group": "commands",
            "icon": "🔗",
            "label": _toolbox_label(lang, "tool_notes_from_url", "Web source as note"),
            "insert": _toolbox_insert(lang, "tool_notes_from_url_insert", "speichere webseite https:// als notiz"),
            "hint": _toolbox_label(lang, "tool_notes_from_url_hint", "Extracts title and summary from a URL and creates a note from it."),
        },
        {
            "group": "commands",
            "icon": "🔎",
            "label": _toolbox_label(lang, "tool_notes_search", "Search notes"),
            "insert": _toolbox_insert(lang, "tool_notes_search_insert", "suche in notizen nach "),
            "hint": _toolbox_label(lang, "tool_notes_search_hint", "Searches your notes semantically or lexically."),
        },
        {
            "group": "commands",
            "icon": "🗂️",
            "label": _toolbox_label(lang, "tool_notes_folders", "Show note folders"),
            "insert": _toolbox_insert(lang, "tool_notes_folders_insert", "zeige ordner in notizen"),
            "hint": _toolbox_label(lang, "tool_notes_folders_hint", "Lists existing note folders directly in chat."),
        },
        {
            "group": "commands",
            "icon": "📂",
            "label": _toolbox_label(lang, "tool_notes_in_folder", "Notes in folder"),
            "insert": _toolbox_insert(lang, "tool_notes_in_folder_insert", "zeige notizen in "),
            "hint": _toolbox_label(lang, "tool_notes_in_folder_hint", "Lists notes from a specific folder."),
        },
        {
            "group": "commands",
            "icon": "🌐",
            "label": _toolbox_label(lang, "tool_web_search_with_notes", "Web search with notes"),
            "insert": _toolbox_insert(lang, "tool_web_search_with_notes_insert", "suche im internet nach  mit meinen notizen"),
            "hint": _toolbox_label(lang, "tool_web_search_with_notes_hint", "Combines web search with matching note context."),
        },
        {
            "group": "commands",
            "icon": "🔗",
            "label": _toolbox_label(lang, "tool_websites_open", "Open watched websites"),
            "insert": _toolbox_insert(lang, "tool_websites_open_insert", "open watched websites"),
            "hint": _toolbox_label(lang, "tool_websites_open_hint", "Opens the watched websites directly from chat."),
        },
        {
            "group": "commands",
            "icon": "📋",
            "label": _toolbox_label(lang, "tool_websites_list", "Beobachtete Webseiten zeigen"),
            "insert": _toolbox_insert(lang, "tool_websites_list_insert", "zeige beobachtete webseiten"),
            "hint": _toolbox_label(lang, "tool_websites_list_hint", "Listet die aktuell gespeicherten Webseiten im Chat."),
        },
        {
            "group": "commands",
            "icon": "✏️",
            "label": _toolbox_label(lang, "tool_websites_edit", "Beobachtete Webseite bearbeiten"),
            "insert": _toolbox_insert(lang, "tool_websites_edit_insert", "edit watched website "),
            "hint": _toolbox_label(lang, "tool_websites_edit_hint", "Updates title, group, or URL of a watched website through the confirmation flow."),
        },
        {
            "group": "commands",
            "icon": "➕",
            "label": _toolbox_label(lang, "tool_websites_watch", "Webseite beobachten"),
            "insert": _toolbox_insert(lang, "tool_websites_watch_insert", "beobachte https://"),
            "hint": _toolbox_label(lang, "tool_websites_watch_hint", "Legt eine beobachtete Webseite per Chat an und nutzt den bestehenden Confirm-Step."),
        },
        {
            "group": "commands",
            "icon": "🌐",
            "label": _toolbox_label(lang, "tool_web_search", "Web search"),
            "insert": _toolbox_insert(lang, "tool_web_search_insert", "suche im internet nach "),
            "hint": _toolbox_label(lang, "tool_web_search_hint", "Startet eine explizite Websuche mit Quellen."),
        },
        {
            "group": "commands",
            "icon": "📊",
            "label": _toolbox_label(lang, "tool_open_stats", "Open stats"),
            "insert": _toolbox_insert(lang, "tool_open_stats_insert", "zeige stats"),
            "hint": _toolbox_label(lang, "tool_open_stats_hint", "Shows statistics and status pages directly from chat."),
        },
        {
            "group": "commands",
            "icon": "🧾",
            "label": _toolbox_label(lang, "tool_open_activities", "Open activities"),
            "insert": _toolbox_insert(lang, "tool_open_activities_insert", "show activities"),
            "hint": _toolbox_label(lang, "tool_open_activities_hint", "Opens Activities & Runs directly from chat."),
        },
    ]
    admin_entries: list[dict[str, Any]] = [
        {
            "group": "admin",
            "icon": "🚀",
            "label": _toolbox_label(lang, "tool_update_run", "Kontrolliertes Update starten"),
            "insert": _toolbox_insert(lang, "tool_update_run_insert", "starte update"),
            "hint": _toolbox_label(lang, "tool_update_run_hint", "Starts the configured update path with a confirmation code."),
        },
        {
            "group": "admin",
            "icon": "🩺",
            "label": _toolbox_label(lang, "tool_update_status", "Check update status"),
            "insert": _toolbox_insert(lang, "tool_update_status_insert", "zeige update status"),
            "hint": _toolbox_label(lang, "tool_update_status_hint", "Fragt den GUI-Update-Helper direkt aus dem Chat ab."),
        },
    ]
    if advanced_mode:
        admin_entries.extend(
            [
                {
                    "group": "admin",
                    "icon": "📦",
                    "label": _toolbox_label(lang, "tool_backup_export", "Config-Backup exportieren"),
                    "insert": _toolbox_insert(lang, "tool_backup_export_insert", "exportiere config backup"),
                    "hint": _toolbox_label(lang, "tool_backup_export_hint", "Creates a download link for the current configuration backup."),
                },
                {
                    "group": "admin",
                    "icon": "♻️",
                    "label": _toolbox_label(lang, "tool_backup_import", "Config-Backup importieren"),
                    "insert": _toolbox_insert(lang, "tool_backup_import_insert", "importiere config backup"),
                    "hint": _toolbox_label(lang, "tool_backup_import_hint", "Opens the restore path for an existing configuration backup."),
                },
            ]
        )
    return general_entries, admin_entries


def build_chat_command_catalog(
    *,
    lang: str,
    auth_role: str,
    advanced_mode: bool,
    recall_templates: list[str],
    store_templates: list[str],
    recipe_trigger_hints: list[str],
    recipe_toolbox_rows: list[dict[str, Any]] | None = None,
    connection_catalog: dict[str, list[str]] | None = None,
    recent_messages: list[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, str], list[dict[str, Any]]]:
    del recent_messages
    system_entries, admin_system_entries = _build_system_chat_command_entries(lang, advanced_mode=advanced_mode)
    entries: list[dict[str, Any]] = [
        {
            "group": "commands",
            "icon": "⌨",
            "label": "/cls",
            "insert": "/cls",
            "hint": _toolbox_label(lang, "slash_cls_hint", "Delete local chat history"),
        },
        {
            "group": "commands",
            "icon": "⌨",
            "label": "/clear",
            "insert": "/clear",
            "hint": _toolbox_label(lang, "slash_cls_hint", "Delete local chat history"),
        },
        *system_entries,
    ]

    seen_read_inserts: set[str] = set()
    for item in recall_templates:
        value = str(item or "").strip()
        if not value:
            continue
        display_insert = _toolbox_insert(lang, "tool_memory_read_insert", "what do you know about ")
        if display_insert in seen_read_inserts:
            continue
        seen_read_inserts.add(display_insert)
        entries.append(
            {
                "group": "read",
                "icon": "📖",
                "label": _toolbox_label(lang, "slash_read_cmd", "/lesen"),
                "insert": display_insert,
                "hint": display_insert.strip(),
            }
        )
    seen_store_inserts: set[str] = set()
    for item in store_templates:
        value = str(item or "").strip()
        if not value:
            continue
        display_insert = _toolbox_insert(lang, "tool_memory_store_insert", "merk dir ")
        if display_insert in seen_store_inserts:
            continue
        seen_store_inserts.add(display_insert)
        entries.append(
            {
                "group": "store",
                "icon": "💾",
                "label": _toolbox_label(lang, "slash_store_cmd", "/merken"),
                "insert": display_insert,
                "hint": display_insert.strip(),
            }
        )
    if recipe_toolbox_rows:
        for row in recipe_toolbox_rows[:40]:
            insert_text = str(row.get("insert", "") or "").strip()
            label = str(row.get("label", "") or "").strip()
            hint = str(row.get("hint", "") or "").strip()
            if not insert_text:
                insert_text = label or hint
            if not label:
                label = insert_text or _toolbox_label(lang, "slash_skill_cmd", "/recipe")
            if not hint:
                hint = insert_text or label
            if not insert_text:
                continue
            entries.append(
                {
                    "group": "recipes",
                    "icon": "🧩",
                    "label": label,
                    "badge": _toolbox_label(lang, "slash_skill_cmd", "/recipe"),
                    "insert": insert_text if insert_text.endswith(" ") else insert_text + " ",
                    "hint": hint,
                }
            )
    else:
        for value in recipe_trigger_hints[:40]:
            hint = str(value or "").strip()
            if not hint:
                continue
            entries.append(
                {
                    "group": "recipes",
                    "icon": "🧩",
                    "label": hint,
                    "badge": _toolbox_label(lang, "slash_skill_cmd", "/recipe"),
                    "insert": hint if hint.endswith(" ") else hint + " ",
                    "hint": _toolbox_label(lang, "slash_skill_cmd", "/recipe"),
                }
            )

    if auth_role == "admin":
        entries.extend(admin_system_entries)
        entries.extend(_build_admin_chat_command_entries(lang, connection_catalog or {}))

    group_titles = {
        "commands": _toolbox_label(lang, "slash_commands", "Commands"),
        "documents": _toolbox_label(lang, "slash_documents", "Dokumente"),
        "read": _toolbox_label(lang, "slash_read", "Memory lesen"),
        "store": _toolbox_label(lang, "slash_store", "Memory speichern"),
        "recipes": _toolbox_label(lang, "slash_skills", "Recipes"),
        "admin": _toolbox_label(lang, "slash_admin", "Admin"),
    }
    group_icons = {
        "commands": "⌨",
        "documents": "📄",
        "read": "📖",
        "store": "💾",
        "recipes": "🧩",
        "admin": "🛠",
    }

    grouped: dict[str, list[dict[str, Any]]] = {key: [] for key in group_titles.keys()}
    for row in entries:
        grouped.setdefault(str(row.get("group", "commands")), []).append(row)

    order = ["commands", "documents", "read", "store", "recipes", "admin"]
    toolbox_groups: list[dict[str, Any]] = []
    for group_key in order:
        rows = grouped.get(group_key, [])
        if not rows:
            continue
        limit = 16 if group_key == "commands" else 6 if group_key in {"recipes", "read", "store"} else 12
        toolbox_groups.append(
            {
                "key": group_key,
                "title": group_titles.get(group_key, group_key),
                "icon": group_icons.get(group_key, "•"),
                "items": rows[:limit],
            }
        )
    return entries, group_titles, toolbox_groups
