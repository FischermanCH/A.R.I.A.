from __future__ import annotations

import pytest

from aria.modules.notes import links as document_link_readpoints


def test_notes_paths_use_notes_registry_readpoint(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    def fake_module_route_path(owner: str, path: str) -> str:
        calls.append((owner, path))
        return "/workspace/notes"

    monkeypatch.setattr(document_link_readpoints, "module_route_path", fake_module_route_path)

    assert document_link_readpoints.notes_path() == "/workspace/notes"
    assert document_link_readpoints.note_editor_path("note/1") == "/workspace/notes?note=note%2F1#note-editor"
    assert document_link_readpoints.notes_folder_path("Projekte/ARIA") == "/workspace/notes?folder=Projekte%2FARIA"
    assert calls == [("notes", "/notes"), ("notes", "/notes"), ("notes", "/notes")]


def test_notes_paths_fail_closed_without_notes_route_owner(monkeypatch) -> None:
    monkeypatch.setattr(document_link_readpoints, "module_route_path", lambda *_args, **_kwargs: None)

    with pytest.raises(RuntimeError, match="notes route is not registered: /notes"):
        document_link_readpoints.notes_path()
