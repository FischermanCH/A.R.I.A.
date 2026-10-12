"""Small UI-only action menu for the chat composer."""

from __future__ import annotations

from pathlib import Path

from aria.modules.platform_primitives.i18n import I18NStore


_CHAT_ACTIONS_I18N = I18NStore(Path(__file__).resolve().parents[2] / "i18n")


def build_chat_quick_actions(language: str) -> list[dict[str, str]]:
    lang = str(language or "de").lower()
    return [
        {
            "key": "new_chat",
            "label": _CHAT_ACTIONS_I18N.t(lang, "chat.quick_action_new_chat", "New chat"),
            "action": "clear",
            "icon": "＋",
        },
        {
            "key": "import_document",
            "label": _CHAT_ACTIONS_I18N.t(lang, "chat.quick_action_import_document", "Import document"),
            "href": "/memories/import#document-import",
            "icon": "⇧",
        },
        {
            "key": "save_chat_note",
            "label": _CHAT_ACTIONS_I18N.t(lang, "chat.quick_action_save_note", "Save chat as note"),
            "insert": "/chat note",
            "icon": "▣",
        },
        {
            "key": "open_notes",
            "label": _CHAT_ACTIONS_I18N.t(lang, "chat.quick_action_open_notes", "Open notes"),
            "href": "/notes",
            "icon": "↗",
        },
    ]
