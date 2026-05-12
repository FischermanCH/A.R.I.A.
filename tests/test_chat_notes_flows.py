from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from aria.core.notes_magic import WebNoteSource
import aria.web.chat_notes_flows as chat_notes_flows
from aria.web.chat_notes_flows import handle_chat_notes_flow


async def _run_open(base_dir: Path):
    return await handle_chat_notes_flow(
        clean_message="öffne notizen",
        username="neo",
        base_dir=base_dir,
        settings=SimpleNamespace(memory=SimpleNamespace(enabled=False, backend="memory"), embeddings=SimpleNamespace()),
    )


async def _run_create(base_dir: Path):
    return await handle_chat_notes_flow(
        clean_message="erstelle notiz Ideen: Erste Zeile\n\nMehr Text",
        username="neo",
        base_dir=base_dir,
        settings=SimpleNamespace(
            memory=SimpleNamespace(enabled=False, backend="memory"),
            embeddings=SimpleNamespace(model="", api_base="", api_key="", timeout_seconds=30),
        ),
    )


def test_chat_notes_flow_can_open_notes(tmp_path: Path):
    import asyncio

    outcome = asyncio.run(_run_open(tmp_path))

    assert outcome is not None
    assert outcome.handled is True
    assert "/notes" in outcome.assistant_text


def test_chat_notes_flow_can_create_note_without_qdrant(tmp_path: Path):
    import asyncio

    outcome = asyncio.run(_run_create(tmp_path))

    assert outcome is not None
    assert outcome.handled is True
    assert "Notiz gespeichert" in outcome.assistant_text
    saved_files = list((tmp_path / "data" / "notes" / "neo").rglob("*.md"))
    assert len(saved_files) == 1
    assert "Erste Zeile" in saved_files[0].read_text(encoding="utf-8")


def test_chat_notes_flow_can_create_natural_note_with_tags(tmp_path: Path):
    import asyncio

    outcome = asyncio.run(
        handle_chat_notes_flow(
            clean_message="halte fest Google Calendar OAuth braucht Audience, Test users und OAuth Playground",
            username="neo",
            base_dir=tmp_path,
            settings=SimpleNamespace(
                memory=SimpleNamespace(enabled=False, backend="memory"),
                embeddings=SimpleNamespace(model="", api_base="", api_key="", timeout_seconds=30),
            ),
        )
    )

    assert outcome is not None
    assert outcome.handled is True
    assert "Tags:" in outcome.assistant_text
    saved_files = list((tmp_path / "data" / "notes" / "neo").rglob("*.md"))
    assert len(saved_files) == 1
    raw = saved_files[0].read_text(encoding="utf-8")
    assert "tags:" in raw
    assert "oauth" in raw.lower()


def test_chat_notes_flow_can_search_notes(tmp_path: Path):
    import asyncio

    store = chat_notes_flows._store(tmp_path)
    store.save_note("neo", title="Qdrant Plan", folder="Projekte/ARIA", body="Reindex und Chunking fuer Notes")

    outcome = asyncio.run(
        handle_chat_notes_flow(
            clean_message="suche in notizen nach qdrant",
            username="neo",
            base_dir=tmp_path,
            settings=SimpleNamespace(memory=SimpleNamespace(enabled=False, backend="memory"), embeddings=SimpleNamespace()),
        )
    )

    assert outcome is not None
    assert outcome.handled is True
    assert "Qdrant Plan" in outcome.assistant_text
    assert "/notes?note=" in outcome.assistant_text


def test_chat_notes_flow_can_list_note_folders(tmp_path: Path):
    import asyncio

    store = chat_notes_flows._store(tmp_path)
    store.save_note("neo", title="Qdrant Plan", folder="Projekte/ARIA", body="Reindex")

    outcome = asyncio.run(
        handle_chat_notes_flow(
            clean_message="zeige ordner in notizen",
            username="neo",
            base_dir=tmp_path,
            settings=SimpleNamespace(memory=SimpleNamespace(enabled=False, backend="memory"), embeddings=SimpleNamespace()),
        )
    )

    assert outcome is not None
    assert outcome.handled is True
    assert "Projekte/ARIA" in outcome.assistant_text


def test_chat_notes_flow_can_list_notes_in_folder(tmp_path: Path):
    import asyncio

    store = chat_notes_flows._store(tmp_path)
    store.save_note("neo", title="Qdrant Plan", folder="Projekte/ARIA", body="Reindex")
    store.save_note("neo", title="Other", folder="Inbox", body="Else")

    outcome = asyncio.run(
        handle_chat_notes_flow(
            clean_message="zeige notizen in Projekte/ARIA",
            username="neo",
            base_dir=tmp_path,
            settings=SimpleNamespace(memory=SimpleNamespace(enabled=False, backend="memory"), embeddings=SimpleNamespace()),
        )
    )

    assert outcome is not None
    assert outcome.handled is True
    assert "Qdrant Plan" in outcome.assistant_text
    assert "Other" not in outcome.assistant_text


def test_chat_notes_flow_can_open_notes_folder_without_falling_through(tmp_path: Path):
    import asyncio

    store = chat_notes_flows._store(tmp_path)
    store.save_note("neo", title="Area41 Status", folder="area41", body="Nur Notes, kein SFTP.")

    outcome = asyncio.run(
        handle_chat_notes_flow(
            clean_message="öffne notizen in ordner area41",
            username="neo",
            base_dir=tmp_path,
            settings=SimpleNamespace(memory=SimpleNamespace(enabled=False, backend="memory"), embeddings=SimpleNamespace()),
        )
    )

    assert outcome is not None
    assert outcome.handled is True
    assert "/notes?folder=area41" in outcome.assistant_text
    assert "Area41 Status" in outcome.assistant_text


def test_chat_notes_flow_resolves_folder_case_insensitively(tmp_path: Path):
    import asyncio

    store = chat_notes_flows._store(tmp_path)
    store.save_note("neo", title="Area41 Status", folder="Area41", body="Nur Notes, kein SFTP.")

    outcome = asyncio.run(
        handle_chat_notes_flow(
            clean_message="öffne notizen in ordner area41",
            username="neo",
            base_dir=tmp_path,
            settings=SimpleNamespace(memory=SimpleNamespace(enabled=False, backend="memory"), embeddings=SimpleNamespace()),
        )
    )

    assert outcome is not None
    assert outcome.handled is True
    assert "/notes?folder=Area41" in outcome.assistant_text
    assert "Area41 Status" in outcome.assistant_text


def test_chat_notes_flow_can_open_note_by_query(tmp_path: Path):
    import asyncio

    store = chat_notes_flows._store(tmp_path)
    store.save_note("neo", title="Qdrant Plan", folder="Projekte/ARIA", body="Reindex und Chunking fuer Notes")

    outcome = asyncio.run(
        handle_chat_notes_flow(
            clean_message="öffne notiz qdrant",
            username="neo",
            base_dir=tmp_path,
            settings=SimpleNamespace(memory=SimpleNamespace(enabled=False, backend="memory"), embeddings=SimpleNamespace()),
        )
    )

    assert outcome is not None
    assert outcome.handled is True
    assert "Qdrant Plan" in outcome.assistant_text
    assert "/notes?note=" in outcome.assistant_text


def test_chat_notes_flow_can_use_notes_as_web_context(tmp_path: Path, monkeypatch):
    import asyncio

    store = chat_notes_flows._store(tmp_path)
    store.save_note("neo", title="Google OAuth", folder="Recherche", body="Audience, Test users und OAuth Playground")

    class _FakeWebSearch:
        def __init__(self, *, settings):
            self.settings = settings

        async def execute(self, query: str, params: dict):
            _ = params
            return SimpleNamespace(content=f"[Web Search]\\nSuche: {query}\\n- Treffer")

    monkeypatch.setattr(chat_notes_flows, "WebSearchSkill", _FakeWebSearch)

    outcome = asyncio.run(
        handle_chat_notes_flow(
            clean_message="suche im internet nach google calendar oauth mit meinen notizen zu google oauth",
            username="neo",
            base_dir=tmp_path,
            settings=SimpleNamespace(memory=SimpleNamespace(enabled=False, backend="memory"), embeddings=SimpleNamespace()),
        )
    )

    assert outcome is not None
    assert outcome.handled is True
    assert "Notiz-Kontext" in outcome.assistant_text
    assert "Google OAuth" in outcome.assistant_text
    assert "[Web Search]" in outcome.assistant_text


def test_chat_notes_flow_can_capture_web_source_as_note(tmp_path: Path, monkeypatch):
    import asyncio

    monkeypatch.setattr(
        chat_notes_flows,
        "fetch_web_note_source",
        lambda url: WebNoteSource(
            url=url,
            title="Google OAuth Setup",
            description="Audience, Test users und Playground.",
            snippet="OAuth Client, Redirect URI und Refresh-Token.",
            tags=["google", "oauth", "calendar"],
        ),
    )

    outcome = asyncio.run(
        handle_chat_notes_flow(
            clean_message="speichere webseite https://example.org/google-oauth als notiz",
            username="neo",
            base_dir=tmp_path,
            settings=SimpleNamespace(
                memory=SimpleNamespace(enabled=False, backend="memory"),
                embeddings=SimpleNamespace(model="", api_base="", api_key="", timeout_seconds=30),
            ),
        )
    )

    assert outcome is not None
    assert outcome.handled is True
    assert "Webquelle als Notiz gespeichert" in outcome.assistant_text
    assert "Recherche" in outcome.assistant_text
    saved_files = list((tmp_path / "data" / "notes" / "neo").rglob("*.md"))
    assert len(saved_files) == 1
    raw = saved_files[0].read_text(encoding="utf-8")
    assert "Quelle: https://example.org/google-oauth" in raw
    assert "google" in raw.lower()
