"""Registry-backed links owned by the Notes module."""

from __future__ import annotations

from urllib.parse import quote_plus

from aria.modules import module_route_path


def notes_path() -> str:
    resolved = module_route_path("notes", "/notes")
    if resolved is None:
        raise RuntimeError("notes route is not registered: /notes")
    return resolved


def note_editor_path(note_id: str | None) -> str:
    clean_note_id = str(note_id or "").strip()
    if not clean_note_id:
        return notes_path()
    return f"{notes_path()}?note={quote_plus(clean_note_id)}#note-editor"


def notes_folder_path(folder: str | None) -> str:
    clean_folder = str(folder or "").strip()
    if not clean_folder:
        return notes_path()
    return f"{notes_path()}?folder={quote_plus(clean_folder)}"


__all__ = ["note_editor_path", "notes_folder_path", "notes_path"]
