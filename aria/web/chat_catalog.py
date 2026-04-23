from __future__ import annotations

from pathlib import Path
from typing import Any

from aria.core.connection_admin import CONNECTION_CREATE_SPECS
from aria.core.connection_admin import CONNECTION_UPDATE_SPECS
from aria.core.connection_catalog import connection_chat_emoji
from aria.core.connection_catalog import connection_example_ref
from aria.core.connection_catalog import connection_insert_template
from aria.core.connection_catalog import connection_kind_label
from aria.core.connection_catalog import connection_toolbox_keywords
from aria.core.connection_catalog import normalize_connection_kind
from aria.core.i18n import I18NStore

_I18N = I18NStore(Path(__file__).resolve().parents[1] / "i18n")


def _toolbox_label(lang: str, key: str, default: str) -> str:
    return _I18N.t(lang, f"chat.{key}", default)


def _toolbox_insert(lang: str, key: str, default: str) -> str:
    value = _toolbox_label(lang, key, default)
    return value if value.endswith(" ") or not value else value + " "


def _chat_connection_kind_label(kind: str) -> str:
    return connection_kind_label(kind)


def _chat_connection_example_ref(kind: str, connection_catalog: dict[str, list[str]]) -> str:
    return connection_example_ref(kind, connection_catalog)


def _chat_connection_create_insert(kind: str, ref: str) -> str:
    return connection_insert_template(kind, "create", ref)


def _chat_connection_update_insert(kind: str, ref: str) -> str:
    return connection_insert_template(kind, "update", ref)


def _localize_connection_insert(lang: str, text: str) -> str:
    if str(lang or "").strip().lower() == "de":
        return text
    localized = str(text or "")
    replacements = (
        ("erstelle ", "create "),
        ("aktualisiere ", "update "),
        ("ändere ", "update "),
        ("aendere ", "update "),
        ("lösche ", "delete "),
        ("loesche ", "delete "),
        (" titel ", " title "),
        (" pfad ", " path "),
        (" passwort ", " password "),
        (" schluesselpfad ", " key "),
        (" keypfad ", " key "),
        (" beschreibung ", " description "),
        (" aliase ", " aliases "),
        (" sprache ", " language "),
        (" zeitraum ", " time_range "),
        (" jugendschutz ", " safe_search "),
        (" kategorien ", " categories "),
        (" suchmaschinen ", " engines "),
    )
    for source, target in replacements:
        localized = localized.replace(source, target)
    return localized


def _connection_toolbox_keywords(kind: str, refs: list[str]) -> list[str]:
    return connection_toolbox_keywords(kind, refs)


def _chat_connection_kind_icon(kind: str) -> str:
    return connection_chat_emoji(kind)


def _score_chat_command_entry(
    entry: dict[str, Any],
    *,
    recent_text: str,
) -> int:
    haystack = str(recent_text or "").strip().lower()
    if not haystack:
        return 0
    score = 0
    for keyword in entry.get("keywords", []):
        value = str(keyword or "").strip().lower()
        if not value or len(value) < 2:
            continue
        if value in haystack:
            score += 3 if len(value) >= 6 else 2
    label = str(entry.get("label", "")).strip().lower()
    hint = str(entry.get("hint", "")).strip().lower()
    if label and label in haystack:
        score += 2
    elif hint and hint in haystack:
        score += 1
    return score


def _build_suggested_toolbox_group(
    lang: str,
    entries: list[dict[str, Any]],
    recent_messages: list[str] | None,
) -> dict[str, Any] | None:
    recent_text = " \n".join(str(row or "").strip().lower() for row in (recent_messages or [])[-8:] if str(row or "").strip())
    if not recent_text:
        return None
    scored: list[tuple[int, dict[str, Any]]] = []
    seen_inserts: set[str] = set()
    for entry in entries:
        insert = str(entry.get("insert", "")).strip()
        if not insert:
            continue
        score = _score_chat_command_entry(entry, recent_text=recent_text)
        if score <= 0:
            continue
        if insert in seen_inserts:
            continue
        seen_inserts.add(insert)
        scored.append((score, entry))
    if not scored:
        return None
    scored.sort(key=lambda item: (-item[0], str(item[1].get("group", "")), str(item[1].get("label", ""))))
    return {
        "key": "suggested",
        "title": _toolbox_label(lang, "slash_suggested", "Passend jetzt"),
        "items": [row for _, row in scored[:5]],
    }


def _build_admin_chat_command_entries(lang: str, connection_catalog: dict[str, list[str]]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []

    for kind in sorted(CONNECTION_CREATE_SPECS.keys()):
        label_kind = _chat_connection_kind_label(kind)
        example_ref = _chat_connection_example_ref(kind, connection_catalog)
        refs = connection_catalog.get(normalize_connection_kind(kind), [])
        entries.append(
            {
                "group": "admin",
                "kind": kind,
                "icon": _chat_connection_kind_icon(kind),
                "label": f"{_toolbox_label(lang, 'tool_create_connection', 'Verbindung erstellen')} · {label_kind}",
                "insert": _localize_connection_insert(lang, _chat_connection_create_insert(kind, example_ref)),
                "hint": _toolbox_label(
                    lang,
                    "tool_create_connection_hint",
                    "Erstellt eine einfache Connection per Chat mit Confirm-Step.",
                ),
                "keywords": _connection_toolbox_keywords(kind, refs),
            }
        )

    for kind in sorted(CONNECTION_UPDATE_SPECS.keys()):
        label_kind = _chat_connection_kind_label(kind)
        example_ref = _chat_connection_example_ref(kind, connection_catalog)
        refs = connection_catalog.get(normalize_connection_kind(kind), [])
        entries.append(
            {
                "group": "admin",
                "kind": kind,
                "icon": _chat_connection_kind_icon(kind),
                "label": f"{_toolbox_label(lang, 'tool_update_connection', 'Verbindung aktualisieren')} · {label_kind}",
                "insert": _localize_connection_insert(lang, _chat_connection_update_insert(kind, example_ref)),
                "hint": _toolbox_label(
                    lang,
                    "tool_update_connection_hint",
                    "Aktualisiert einfache Connections oder nur Metadaten per Chat.",
                ),
                "keywords": _connection_toolbox_keywords(kind, refs),
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
            "label": f"{_toolbox_label(lang, 'tool_delete_connection', 'Verbindung löschen')} · {_chat_connection_kind_label(delete_kind)}",
            "insert": _localize_connection_insert(lang, f"lösche {delete_kind} {delete_ref} "),
            "hint": _toolbox_label(
                lang,
                "tool_delete_connection_hint",
                "Löscht ein Connection-Profil mit Confirm-Step.",
            ),
            "keywords": _connection_toolbox_keywords(delete_kind, [delete_ref]),
        }
    )
    return entries


def _build_system_chat_command_entries(lang: str, *, advanced_mode: bool) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    general_entries: list[dict[str, Any]] = [
        {
            "group": "commands",
            "icon": "📝",
            "label": _toolbox_label(lang, "tool_notes_open", "Notizen öffnen"),
            "insert": _toolbox_insert(lang, "tool_notes_open_insert", "öffne notizen"),
            "hint": _toolbox_label(lang, "tool_notes_open_hint", "Öffnet die Notizenverwaltung direkt über den Chat."),
            "keywords": ["notizen", "notes", "markdown", "wissen", "memo"],
        },
        {
            "group": "commands",
            "icon": "🗒️",
            "label": _toolbox_label(lang, "tool_notes_create", "Notiz anlegen"),
            "insert": _toolbox_insert(lang, "tool_notes_create_insert", "erstelle notiz "),
            "hint": _toolbox_label(lang, "tool_notes_create_hint", "Lege schnell eine Notiz im Format Titel: Inhalt an."),
            "keywords": ["notiz", "note", "merken", "memo", "markdown"],
        },
        {
            "group": "commands",
            "icon": "✍️",
            "label": _toolbox_label(lang, "tool_notes_capture", "Freie Notiz festhalten"),
            "insert": _toolbox_insert(lang, "tool_notes_capture_insert", "halte fest "),
            "hint": _toolbox_label(lang, "tool_notes_capture_hint", "Speichert eine freie Notiz und ergänzt Titel, Ordner und Tags automatisch."),
            "keywords": ["notiz", "note", "festhalten", "capture", "merken", "quick note"],
        },
        {
            "group": "commands",
            "icon": "🔗",
            "label": _toolbox_label(lang, "tool_notes_from_url", "Webquelle als Notiz"),
            "insert": _toolbox_insert(lang, "tool_notes_from_url_insert", "speichere webseite https:// als notiz"),
            "hint": _toolbox_label(lang, "tool_notes_from_url_hint", "Zieht Titel und Kurztext aus einer URL und legt daraus eine Notiz an."),
            "keywords": ["url", "link", "webseite", "website", "quelle", "source", "notiz"],
        },
        {
            "group": "commands",
            "icon": "🔎",
            "label": _toolbox_label(lang, "tool_notes_search", "Notizen durchsuchen"),
            "insert": _toolbox_insert(lang, "tool_notes_search_insert", "suche in notizen nach "),
            "hint": _toolbox_label(lang, "tool_notes_search_hint", "Durchsucht deine Notizen semantisch oder lexikalisch."),
            "keywords": ["notizen", "notes", "suche", "search", "wissen"],
        },
        {
            "group": "commands",
            "icon": "🌐",
            "label": _toolbox_label(lang, "tool_web_search_with_notes", "Websuche mit Notizen"),
            "insert": _toolbox_insert(lang, "tool_web_search_with_notes_insert", "suche im internet nach  mit meinen notizen"),
            "hint": _toolbox_label(lang, "tool_web_search_with_notes_hint", "Kombiniert Websuche mit passendem Notiz-Kontext."),
            "keywords": ["web", "internet", "notizen", "notes", "recherche", "search"],
        },
        {
            "group": "commands",
            "icon": "🌐",
            "label": _toolbox_label(lang, "tool_web_search", "Web search"),
            "insert": _toolbox_insert(lang, "tool_web_search_insert", "suche im internet nach "),
            "hint": _toolbox_label(lang, "tool_web_search_hint", "Startet eine explizite Websuche mit Quellen."),
            "keywords": ["internet", "web", "search", "websuche", "news", "neuigkeiten", "recherche"],
        },
        {
            "group": "commands",
            "icon": "📊",
            "label": _toolbox_label(lang, "tool_open_stats", "Stats öffnen"),
            "insert": _toolbox_insert(lang, "tool_open_stats_insert", "zeige stats"),
            "hint": _toolbox_label(lang, "tool_open_stats_hint", "Zeigt Statistik- und Statusseiten direkt über den Chat an."),
            "keywords": ["stats", "statistik", "statistiken", "status", "metrics"],
        },
        {
            "group": "commands",
            "icon": "🧾",
            "label": _toolbox_label(lang, "tool_open_activities", "Aktivitäten öffnen"),
            "insert": _toolbox_insert(lang, "tool_open_activities_insert", "zeige aktivitäten"),
            "hint": _toolbox_label(lang, "tool_open_activities_hint", "Öffnet Aktivitäten & Runs direkt aus dem Chat."),
            "keywords": ["aktivitäten", "aktivitaeten", "activities", "runs", "logs"],
        },
    ]
    admin_entries: list[dict[str, Any]] = [
        {
            "group": "admin",
            "icon": "🚀",
            "label": _toolbox_label(lang, "tool_update_run", "Kontrolliertes Update starten"),
            "insert": _toolbox_insert(lang, "tool_update_run_insert", "starte update"),
            "hint": _toolbox_label(lang, "tool_update_run_hint", "Startet den konfigurierten Update-Pfad mit Bestätigungscode."),
            "keywords": ["update", "upgrade", "release", "deploy", "helper"],
        },
        {
            "group": "admin",
            "icon": "🩺",
            "label": _toolbox_label(lang, "tool_update_status", "Update-Status prüfen"),
            "insert": _toolbox_insert(lang, "tool_update_status_insert", "zeige update status"),
            "hint": _toolbox_label(lang, "tool_update_status_hint", "Fragt den GUI-Update-Helper direkt aus dem Chat ab."),
            "keywords": ["update", "status", "helper", "deploy"],
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
                    "hint": _toolbox_label(lang, "tool_backup_export_hint", "Erstellt einen Download-Link für das aktuelle Konfigurations-Backup."),
                    "keywords": ["backup", "export", "config", "konfig", "restore"],
                },
                {
                    "group": "admin",
                    "icon": "♻️",
                    "label": _toolbox_label(lang, "tool_backup_import", "Config-Backup importieren"),
                    "insert": _toolbox_insert(lang, "tool_backup_import_insert", "importiere config backup"),
                    "hint": _toolbox_label(lang, "tool_backup_import_hint", "Öffnet den Restore-Weg für ein vorhandenes Config-Backup."),
                    "keywords": ["backup", "import", "restore", "config", "konfig"],
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
    skill_trigger_hints: list[str],
    skill_toolbox_rows: list[dict[str, Any]] | None = None,
    connection_catalog: dict[str, list[str]] | None = None,
    recent_messages: list[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, str], list[dict[str, Any]]]:
    system_entries, admin_system_entries = _build_system_chat_command_entries(lang, advanced_mode=advanced_mode)
    entries: list[dict[str, Any]] = [
        {
            "group": "commands",
            "icon": "⌨",
            "label": "/cls",
            "insert": "/cls",
            "hint": _toolbox_label(lang, "slash_cls_hint", "Lokalen Chatverlauf löschen"),
            "keywords": ["clear", "cls", "chat löschen", "verlauf löschen", "chat reset"],
        },
        {
            "group": "commands",
            "icon": "⌨",
            "label": "/clear",
            "insert": "/clear",
            "hint": _toolbox_label(lang, "slash_cls_hint", "Lokalen Chatverlauf löschen"),
            "keywords": ["clear", "cls", "chat löschen", "verlauf löschen", "chat reset"],
        },
        *system_entries,
    ]

    seen_read_inserts: set[str] = set()
    for item in recall_templates:
        value = str(item or "").strip()
        if not value:
            continue
        display_insert = _toolbox_insert(lang, "tool_memory_read_insert", "was weißt du über ")
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
                "keywords": [value, display_insert.strip(), "lesen", "erinnern", "memory", "wissen"],
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
                "keywords": [value, display_insert.strip(), "merken", "speichern", "memory", "wissen"],
            }
        )
    if skill_toolbox_rows:
        for row in skill_toolbox_rows[:40]:
            insert_text = str(row.get("insert", "") or "").strip()
            label = str(row.get("label", "") or "").strip()
            hint = str(row.get("hint", "") or "").strip()
            keywords = [str(item or "").strip().lower() for item in row.get("keywords", []) if str(item or "").strip()]
            if not insert_text:
                insert_text = label or hint
            if not label:
                label = insert_text or _toolbox_label(lang, "slash_skill_cmd", "/skill")
            if not hint:
                hint = insert_text or label
            if not insert_text:
                continue
            entries.append(
                {
                    "group": "skills",
                    "icon": "🧩",
                    "label": label,
                    "badge": _toolbox_label(lang, "slash_skill_cmd", "/skill"),
                    "insert": insert_text if insert_text.endswith(" ") else insert_text + " ",
                    "hint": hint,
                    "keywords": list(
                        dict.fromkeys(keywords + [label.lower(), hint.lower(), insert_text.lower(), "skill", "automation", "aktion"])
                    ),
                }
            )
    else:
        for value in skill_trigger_hints[:40]:
            hint = str(value or "").strip()
            if not hint:
                continue
            entries.append(
                {
                    "group": "skills",
                    "icon": "🧩",
                    "label": hint,
                    "badge": _toolbox_label(lang, "slash_skill_cmd", "/skill"),
                    "insert": hint if hint.endswith(" ") else hint + " ",
                    "hint": _toolbox_label(lang, "slash_skill_cmd", "/skill"),
                    "keywords": [hint, "skill", "automation", "aktion"],
                }
            )

    if auth_role == "admin":
        entries.extend(admin_system_entries)
        entries.extend(_build_admin_chat_command_entries(lang, connection_catalog or {}))

    group_titles = {
        "suggested": _toolbox_label(lang, "slash_suggested", "Passend jetzt"),
        "commands": _toolbox_label(lang, "slash_commands", "Commands"),
        "read": _toolbox_label(lang, "slash_read", "Memory lesen"),
        "store": _toolbox_label(lang, "slash_store", "Memory speichern"),
        "skills": _toolbox_label(lang, "slash_skills", "Skills"),
        "admin": _toolbox_label(lang, "slash_admin", "Admin"),
    }
    group_icons = {
        "suggested": "✨",
        "commands": "⌨",
        "read": "📖",
        "store": "💾",
        "skills": "🧩",
        "admin": "🛠",
    }

    grouped: dict[str, list[dict[str, Any]]] = {key: [] for key in group_titles.keys()}
    for row in entries:
        grouped.setdefault(str(row.get("group", "commands")), []).append(row)

    order = ["commands", "read", "store", "skills", "admin"]
    toolbox_groups: list[dict[str, Any]] = []
    suggested_group = _build_suggested_toolbox_group(lang, entries, recent_messages)
    if suggested_group:
        suggested_group["icon"] = group_icons["suggested"]
        toolbox_groups.append(suggested_group)
    for group_key in order:
        rows = grouped.get(group_key, [])
        if not rows:
            continue
        limit = 6 if group_key in {"skills", "read", "store"} else 12
        toolbox_groups.append(
            {
                "key": group_key,
                "title": group_titles.get(group_key, group_key),
                "icon": group_icons.get(group_key, "•"),
                "items": rows[:limit],
            }
        )
    return entries, group_titles, toolbox_groups
