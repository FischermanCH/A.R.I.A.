from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from aria.modules.notes.magic import WebNoteSource
import aria.modules.notes.chat_flows as chat_notes_flows
from aria.modules.notes.chat_flows import handle_chat_notes_flow


class _Response:
    def __init__(self, content: str) -> None:
        self.content = content
        self.usage = {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}


class _NotesLLM:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.operations: list[str] = []

    async def chat(self, messages, **kwargs):
        import json

        _ = messages
        operation = str(kwargs.get("operation") or "")
        self.operations.append(operation)
        if operation == "notes_action_arbitration":
            return _Response(json.dumps(self.payload))
        return _Response("{}")


async def _run_open(base_dir: Path):
    return await handle_chat_notes_flow(
        clean_message="open notes",
        username="neo",
        base_dir=base_dir,
        settings=SimpleNamespace(memory=SimpleNamespace(enabled=False, backend="memory"), embeddings=SimpleNamespace()),
    )


async def _run_create(base_dir: Path):
    return await handle_chat_notes_flow(
        clean_message="create note: Ideen\nErste Zeile\n\nMehr Text",
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


def test_chat_notes_flow_does_not_infer_tags_from_canonical_note_contract(tmp_path: Path):
    import asyncio

    outcome = asyncio.run(
        handle_chat_notes_flow(
            clean_message=(
                "create note: Google Calendar OAuth\n"
                "Google Calendar OAuth braucht Audience, Test users und OAuth Playground"
            ),
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
    assert "Tags:" not in outcome.assistant_text
    saved_files = list((tmp_path / "data" / "notes" / "neo").rglob("*.md"))
    assert len(saved_files) == 1
    raw = saved_files[0].read_text(encoding="utf-8")
    assert "tags:" not in raw
    assert "oauth" in raw.lower()


def test_chat_notes_flow_does_not_use_lexical_search_when_semantic_index_is_disabled(tmp_path: Path):
    import asyncio

    store = chat_notes_flows._store(tmp_path)
    store.save_note("neo", title="Qdrant Plan", folder="Projekte/ARIA", body="Reindex und Chunking fuer Notes")

    outcome = asyncio.run(
        handle_chat_notes_flow(
            clean_message="search notes: qdrant",
            username="neo",
            base_dir=tmp_path,
            settings=SimpleNamespace(memory=SimpleNamespace(enabled=False, backend="memory"), embeddings=SimpleNamespace()),
        )
    )

    assert outcome is not None
    assert outcome.handled is True
    assert "nichts Passendes gefunden" in outcome.assistant_text
    assert "`/notes`" in outcome.assistant_text
    assert outcome.badge_duration is not None
    assert any("notes_flow handled=true" in row for row in outcome.badge_details)


def test_chat_notes_flow_agentic_arbiter_does_not_add_lexical_search_fallback(tmp_path: Path) -> None:
    import asyncio

    store = chat_notes_flows._store(tmp_path)
    store.save_note("neo", title="ARIA Agentic Plan", folder="Projekte/ARIA", body="Agentic-first statt Regex-first")
    llm = _NotesLLM(
        {
            "action": "search_notes",
            "canonical_command": "search notes: agentic",
            "confidence": "high",
            "reason": "The user asks to search notes.",
        }
    )

    outcome = asyncio.run(
        handle_chat_notes_flow(
            clean_message="kannst du in meinen notizen nach dem agentic plan schauen?",
            username="neo",
            base_dir=tmp_path,
            settings=SimpleNamespace(memory=SimpleNamespace(enabled=False, backend="memory"), embeddings=SimpleNamespace()),
            llm_client=llm,
        )
    )

    assert outcome is not None
    assert outcome.handled is True
    assert "nichts Passendes gefunden" in outcome.assistant_text
    assert llm.operations == ["notes_action_arbitration"]


def test_chat_notes_flow_agentic_no_action_blocks_regex_fallback(tmp_path: Path) -> None:
    import asyncio

    llm = _NotesLLM(
        {
            "action": "no_action",
            "canonical_command": "",
            "confidence": "high",
            "reason": "The user asks for an explanation about notes, not a notes action.",
        }
    )

    outcome = asyncio.run(
        handle_chat_notes_flow(
            clean_message="öffne notizen",
            username="neo",
            base_dir=tmp_path,
            settings=SimpleNamespace(memory=SimpleNamespace(enabled=False, backend="memory"), embeddings=SimpleNamespace()),
            llm_client=llm,
        )
    )

    assert outcome is None
    assert llm.operations == ["notes_action_arbitration"]


def test_chat_notes_flow_can_list_note_folders(tmp_path: Path):
    import asyncio

    store = chat_notes_flows._store(tmp_path)
    store.save_note("neo", title="Qdrant Plan", folder="Projekte/ARIA", body="Reindex")

    outcome = asyncio.run(
        handle_chat_notes_flow(
            clean_message="list note folders",
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
            clean_message="list notes in folder: Projekte/ARIA",
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
            clean_message="list notes in folder: area41",
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
            clean_message="list notes in folder: area41",
            username="neo",
            base_dir=tmp_path,
            settings=SimpleNamespace(memory=SimpleNamespace(enabled=False, backend="memory"), embeddings=SimpleNamespace()),
        )
    )

    assert outcome is not None
    assert outcome.handled is True
    assert "/notes?folder=Area41" in outcome.assistant_text
    assert "Area41 Status" in outcome.assistant_text


def test_chat_notes_flow_does_not_guess_note_by_title_when_semantic_search_is_unavailable(tmp_path: Path):
    import asyncio

    store = chat_notes_flows._store(tmp_path)
    store.save_note("neo", title="Qdrant Plan", folder="Projekte/ARIA", body="Reindex und Chunking fuer Notes")

    outcome = asyncio.run(
        handle_chat_notes_flow(
            clean_message="open note: qdrant",
            username="neo",
            base_dir=tmp_path,
            settings=SimpleNamespace(memory=SimpleNamespace(enabled=False, backend="memory"), embeddings=SimpleNamespace()),
        )
    )

    assert outcome is not None
    assert outcome.handled is True
    assert "keine Notiz gefunden" in outcome.assistant_text
    assert "/notes?q=qdrant" in outcome.assistant_text


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
            clean_message="save web source: https://example.org/google-oauth",
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
    assert "Ordner: Inbox" in outcome.assistant_text
    saved_files = list((tmp_path / "data" / "notes" / "neo").rglob("*.md"))
    assert len(saved_files) == 1
    raw = saved_files[0].read_text(encoding="utf-8")
    assert "Quelle: https://example.org/google-oauth" in raw
    assert "google" in raw.lower()
