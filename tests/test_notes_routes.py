from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.testclient import TestClient

from aria.core.notes_store import NotesStore
from aria.web.notes_routes import NotesRouteDeps, register_notes_routes


class _FakeNotesIndex:
    def __init__(self):
        self.reindexed: list[str] = []
        self.deleted: list[str] = []

    async def overview(self, _user_id: str):
        return SimpleNamespace(enabled=True, reachable=True, collection="aria_notes_tester", points=3)

    async def reindex_note(self, note):
        self.reindexed.append(note.note_id)
        return {"indexed": True, "chunk_count": 2, "collection": "aria_notes_tester"}

    async def delete_note(self, *, user_id: str, note_id: str):
        self.deleted.append(f"{user_id}:{note_id}")

    async def search_notes(self, *, user_id: str, query: str, limit: int = 8):
        _ = (user_id, limit)
        if "qdrant" not in query.lower():
            return []
        return [
            SimpleNamespace(
                note_id="note-1",
                title="Qdrant Migration",
                folder="Projekte/ARIA",
                relative_path="Projekte/ARIA/qdrant-migration.md",
                updated_at="2026-04-23T10:00:00+00:00",
                score=0.91,
                snippet="Migration, Collection-Namen und Reindex-Plan.",
                chunk_index=1,
                chunk_total=2,
            )
        ]


def _build_notes_app(tmp_path: Path) -> tuple[TestClient, _FakeNotesIndex]:
    app = FastAPI()
    templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "aria" / "templates"))
    templates.env.globals.setdefault("tr", lambda _request, _key, fallback="": fallback)
    templates.env.globals.setdefault("agent_name", lambda _request, fallback="ARIA": fallback)
    fake_index = _FakeNotesIndex()

    @app.middleware("http")
    async def _inject_state(request: Request, call_next):
        request.state.authenticated = True
        request.state.auth_user = "tester"
        request.state.auth_role = "admin"
        request.state.can_access_users = False
        request.state.can_access_advanced_config = True
        request.state.debug_mode = True
        request.state.lang = "de"
        request.state.cookie_names = {}
        request.state.csrf_token = "test-csrf"
        request.state.release_meta = {"label": "test"}
        request.state.update_status = SimpleNamespace(update_available=False)
        request.state.ui_theme = "matrix"
        request.state.ui_background = "grid"
        request.state.logical_back_url = ""
        return await call_next(request)

    register_notes_routes(
        app,
        NotesRouteDeps(
            templates=templates,
            base_dir=tmp_path,
            get_settings=lambda: SimpleNamespace(
                ui=SimpleNamespace(title="Notes Test"),
                memory=SimpleNamespace(enabled=True, backend="qdrant", qdrant_url="http://qdrant", qdrant_api_key=""),
                embeddings=SimpleNamespace(model="nomic-embed-text", api_base=None, api_key="", timeout_seconds=30),
            ),
            get_username_from_request=lambda _request: "tester",
            build_notes_store=lambda root_dir: NotesStore(root_dir),
            build_notes_index=lambda _settings: fake_index,
        ),
    )
    return TestClient(app), fake_index


def test_notes_page_renders_empty_state(tmp_path: Path) -> None:
    client, _index = _build_notes_app(tmp_path)

    response = client.get("/notes")

    assert response.status_code == 200
    assert "Notizen" in response.text
    assert "Noch keine Notizen vorhanden" in response.text
    assert 'class="notes-folder-tree"' in response.text
    assert 'class="notes-board"' in response.text
    assert 'class="notes-editor-form"' not in response.text
    assert "Memory Navigation" not in response.text
    assert "Qdrant-Index" not in response.text


def test_notes_page_opens_editor_only_when_requested(tmp_path: Path) -> None:
    client, _index = _build_notes_app(tmp_path)
    store = NotesStore(tmp_path / "data" / "notes")
    note = store.save_note("tester", title="Explorer Test", body="Board zuerst, Editor erst nach Klick.")

    board_response = client.get("/notes")
    edit_response = client.get(f"/notes?note={note.note_id}")
    create_response = client.get("/notes?new=1")

    assert board_response.status_code == 200
    assert 'class="notes-board"' in board_response.text
    assert 'class="notes-editor-form"' not in board_response.text

    assert edit_response.status_code == 200
    assert 'class="notes-editor-form"' in edit_response.text
    assert "Zurück zum Board" in edit_response.text
    assert "Explorer Test" in edit_response.text

    assert create_response.status_code == 200
    assert 'class="notes-editor-form"' in create_response.text


def test_notes_save_persists_markdown_and_reindexes(tmp_path: Path) -> None:
    client, index = _build_notes_app(tmp_path)

    response = client.post(
        "/notes/save",
        data={"title": "Projektideen", "folder": "Projekte/ARIA", "body": "Erste Idee\n\nMehr Kontext."},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/notes?folder=")
    assert "&note=" in response.headers["location"]
    saved_files = list((tmp_path / "data" / "notes" / "tester").rglob("*.md"))
    assert len(saved_files) == 1
    raw = saved_files[0].read_text(encoding="utf-8")
    assert "title: Projektideen" in raw
    assert "folder: Projekte/ARIA" in raw
    assert "Erste Idee" in raw
    assert len(index.reindexed) == 1


def test_notes_delete_removes_file_and_index_entry(tmp_path: Path) -> None:
    client, index = _build_notes_app(tmp_path)
    store = NotesStore(tmp_path / "data" / "notes")
    note = store.save_note("tester", title="Loesch mich", folder="Inbox", body="Temporär")

    response = client.post("/notes/delete", data={"note_id": note.note_id}, follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"].startswith("/notes?folder=__all__&info=")
    assert not note.path.exists()
    assert index.deleted == [f"tester:{note.note_id}"]


def test_notes_export_returns_markdown_file(tmp_path: Path) -> None:
    client, _index = _build_notes_app(tmp_path)
    store = NotesStore(tmp_path / "data" / "notes")
    note = store.save_note("tester", title="Exportierbar", body="## Hallo\n\nWelt")

    response = client.get(f"/notes/export/{note.note_id}.md")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "## Hallo" in response.text


def test_notes_page_can_show_search_results(tmp_path: Path) -> None:
    client, _index = _build_notes_app(tmp_path)
    store = NotesStore(tmp_path / "data" / "notes")
    store.save_note("tester", title="Qdrant Migration", folder="Projekte/ARIA", body="Reindex und Collections")

    response = client.get("/notes?q=qdrant migration")

    assert response.status_code == 200
    assert "Qdrant Migration" in response.text
    assert "Migration, Collection-Namen und Reindex-Plan." in response.text
    assert "Treffer für" in response.text


def test_notes_create_folder_redirects_into_visible_folder_context(tmp_path: Path) -> None:
    client, _index = _build_notes_app(tmp_path)

    redirect = client.post("/notes/folders/create", data={"folder": "Projekte/ARIA"}, follow_redirects=False)
    page = client.get(redirect.headers["location"])

    assert redirect.status_code == 303
    assert "folder=Projekte%2FARIA" in redirect.headers["location"]
    assert page.status_code == 200
    assert "Ordner Projekte/ARIA angelegt." in page.text
    assert 'class="notes-folder-link is-active"' in page.text
    assert ">ARIA<" in page.text
    assert 'class="notes-editor-form"' in page.text
