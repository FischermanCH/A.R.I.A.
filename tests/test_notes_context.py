from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import aria.modules.notes.context as notes_context
from aria.modules.notes.context import search_note_hits
from aria.modules.notes.store import NotesStore


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        memory=SimpleNamespace(enabled=True, backend="qdrant", qdrant_url="http://qdrant"),
        embeddings=SimpleNamespace(model="test-embedding"),
    )


class _EmptyNotesIndex:
    def __init__(self, *_args, **_kwargs):
        pass

    async def search_notes(self, **_kwargs):
        return []

    async def aclose(self):
        return None


class _OneHitNotesIndex:
    def __init__(self, *_args, **_kwargs):
        pass

    async def search_notes(self, **_kwargs):
        return [
            SimpleNamespace(
                note_id="qdrant-hit",
                title="Qdrant Pixel Axiom",
                folder="Pixel Axiom",
                relative_path="Pixel Axiom/qdrant.md",
                updated_at="2026-09-10T10:00:00+00:00",
                score=0.88,
                snippet="Semantic index hit.",
                chunk_index=1,
                chunk_total=1,
            )
        ]

    async def aclose(self):
        return None


def _store(tmp_path: Path) -> NotesStore:
    return NotesStore(tmp_path / "data" / "notes")


def _save_pixel_axiom_notes(tmp_path: Path, *, user_id: str = "tester") -> list[str]:
    store = _store(tmp_path)
    titles = [
        "Backlog PAE",
        "pixel-axiom.com // codex-briefing",
        "pixel-axiom.com // content-guide",
        "pixel-axiom.com // game-page-briefing",
        "pixel-axiom.com // ki-referenz",
        "pixel-axiom.com // README",
        "Death Pays Overtime Alpha-Testing",
    ]
    for title in titles:
        store.save_note(
            user_id,
            title=title,
            folder="Pixel Axiom",
            tags="pixel axiom, pae",
            body=f"{title} body for the Pixel Axiom project.",
        )
    return titles


@pytest.mark.anyio
async def test_search_note_hits_falls_back_to_markdown_folder_when_index_empty(monkeypatch, tmp_path: Path) -> None:
    titles = _save_pixel_axiom_notes(tmp_path)
    monkeypatch.setattr(notes_context, "NotesIndex", _EmptyNotesIndex)
    monkeypatch.setattr(notes_context, "build_notes_store", lambda _base_dir: _store(tmp_path))

    hits = await search_note_hits(
        base_dir=tmp_path,
        username="tester",
        settings=_settings(),
        query="pixel axiom",
        limit=8,
        allow_markdown_fallback=True,
    )

    assert {hit.title for hit in hits} == set(titles)
    assert {hit.folder for hit in hits} == {"Pixel Axiom"}
    assert {hit.source for hit in hits} == {"markdown"}


@pytest.mark.anyio
async def test_search_note_hits_prefers_qdrant_hits(monkeypatch, tmp_path: Path) -> None:
    _save_pixel_axiom_notes(tmp_path)
    monkeypatch.setattr(notes_context, "NotesIndex", _OneHitNotesIndex)

    hits = await search_note_hits(
        base_dir=tmp_path,
        username="tester",
        settings=_settings(),
        query="pixel axiom",
        limit=8,
        allow_markdown_fallback=True,
    )

    assert [hit.note_id for hit in hits] == ["qdrant-hit"]
    assert {hit.source for hit in hits} == {"qdrant"}


@pytest.mark.anyio
async def test_search_note_hits_markdown_fallback_keeps_user_scope(monkeypatch, tmp_path: Path) -> None:
    _save_pixel_axiom_notes(tmp_path, user_id="other")
    monkeypatch.setattr(notes_context, "NotesIndex", _EmptyNotesIndex)

    hits = await search_note_hits(
        base_dir=tmp_path,
        username="tester",
        settings=_settings(),
        query="pixel axiom",
        limit=8,
        allow_markdown_fallback=True,
    )

    assert hits == []


@pytest.mark.anyio
async def test_search_note_hits_markdown_fallback_returns_exact_title(monkeypatch, tmp_path: Path) -> None:
    _save_pixel_axiom_notes(tmp_path)
    monkeypatch.setattr(notes_context, "NotesIndex", _EmptyNotesIndex)

    hits = await search_note_hits(
        base_dir=tmp_path,
        username="tester",
        settings=_settings(),
        query="Backlog PAE",
        limit=8,
        allow_markdown_fallback=True,
    )

    assert [hit.title for hit in hits] == ["Backlog PAE"]
    assert {hit.source for hit in hits} == {"markdown"}


@pytest.mark.anyio
async def test_search_note_hits_markdown_fallback_unknown_source_label_empty(monkeypatch, tmp_path: Path) -> None:
    _save_pixel_axiom_notes(tmp_path)
    monkeypatch.setattr(notes_context, "NotesIndex", _EmptyNotesIndex)

    hits = await search_note_hits(
        base_dir=tmp_path,
        username="tester",
        settings=_settings(),
        query="Area 41",
        limit=8,
        allow_markdown_fallback=True,
    )

    assert hits == []
