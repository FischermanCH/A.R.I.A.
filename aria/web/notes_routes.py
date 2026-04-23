from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from fastapi import FastAPI, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from aria.core.notes_context import search_note_hits
from aria.core.notes_index import NotesIndex
from aria.core.notes_store import NoteRecord, NotesStore, NotesStoreError


SettingsGetter = Callable[[], Any]
UsernameResolver = Callable[[Request], str]
NotesStoreFactory = Callable[[Path], NotesStore]
NotesIndexFactory = Callable[[Any], NotesIndex]


@dataclass(frozen=True)
class NotesRouteDeps:
    templates: Jinja2Templates
    base_dir: Path
    get_settings: SettingsGetter
    get_username_from_request: UsernameResolver
    build_notes_store: NotesStoreFactory
    build_notes_index: NotesIndexFactory


_ALL_FOLDER_TOKEN = "__all__"
_ROOT_FOLDER_TOKEN = "__root__"


def _folder_token(folder: str) -> str:
    clean = str(folder or "").strip()
    return clean or _ROOT_FOLDER_TOKEN


def _folder_matches(note: NoteRecord, selected_folder: str) -> bool:
    if selected_folder == _ALL_FOLDER_TOKEN:
        return True
    if selected_folder == _ROOT_FOLDER_TOKEN:
        return not bool(note.folder)
    clean_folder = str(note.folder or "").strip()
    return clean_folder == selected_folder or clean_folder.startswith(f"{selected_folder}/")


def _folder_rows(notes: list[NoteRecord], folders: list[str]) -> list[dict[str, Any]]:
    exact_counts: dict[str, int] = {}
    branch_counts: dict[str, int] = {_ALL_FOLDER_TOKEN: len(notes), _ROOT_FOLDER_TOKEN: 0}
    for note in notes:
        folder = str(note.folder or "").strip()
        if not folder:
            branch_counts[_ROOT_FOLDER_TOKEN] = branch_counts.get(_ROOT_FOLDER_TOKEN, 0) + 1
            continue
        exact_counts[folder] = exact_counts.get(folder, 0) + 1
        parts = folder.split("/")
        branch = ""
        for part in parts:
            branch = f"{branch}/{part}" if branch else part
            branch_counts[branch] = branch_counts.get(branch, 0) + 1
    rows = [
        {
            "token": _ALL_FOLDER_TOKEN,
            "folder": "",
            "label": "Alle Notizen",
            "depth": 0,
            "count": branch_counts.get(_ALL_FOLDER_TOKEN, 0),
            "is_special": True,
        },
        {
            "token": _ROOT_FOLDER_TOKEN,
            "folder": "",
            "label": "Inbox",
            "depth": 0,
            "count": branch_counts.get(_ROOT_FOLDER_TOKEN, 0),
            "is_special": True,
        },
    ]
    for folder in sorted({str(item or "").strip() for item in folders if str(item or "").strip()}, key=lambda value: value.lower()):
        rows.append(
            {
                "token": folder,
                "folder": folder,
                "label": folder.split("/")[-1],
                "depth": folder.count("/") + 1,
                "count": branch_counts.get(folder, exact_counts.get(folder, 0)),
                "is_special": False,
            }
        )
    return rows


def _board_notes(
    notes: list[NoteRecord],
    *,
    selected_folder: str,
    selected_note_id: str,
    search_results: list[dict[str, Any]] | None = None,
) -> tuple[list[NoteRecord], NoteRecord | None]:
    notes_by_id = {note.note_id: note for note in notes}
    selected_note = notes_by_id.get(selected_note_id)
    if search_results:
        rows: list[NoteRecord] = []
        seen: set[str] = set()
        for result in search_results:
            note_id = str(result.get("note_id", "")).strip()
            note = notes_by_id.get(note_id)
            if note is None or note.note_id in seen:
                continue
            seen.add(note.note_id)
            rows.append(note)
        return rows, selected_note
    rows = [note for note in notes if _folder_matches(note, selected_folder)]
    rows.sort(key=lambda item: item.updated_at, reverse=True)
    return rows, selected_note


def register_notes_routes(app: FastAPI, deps: NotesRouteDeps) -> None:
    def _store() -> NotesStore:
        return deps.build_notes_store(deps.base_dir / "data" / "notes")

    def _index() -> NotesIndex:
        return deps.build_notes_index(deps.get_settings())

    def _render_notes_page(
        request: Request,
        *,
        info_message: str = "",
        error_message: str = "",
        selected_note_id: str = "",
        selected_folder: str = _ALL_FOLDER_TOKEN,
        create_mode: bool = False,
        search_query: str = "",
        search_results: list[dict[str, Any]] | None = None,
    ) -> HTMLResponse:
        settings = deps.get_settings()
        username = deps.get_username_from_request(request) or "web"
        store = _store()
        notes = store.list_notes(username)
        folders = store.list_folders(username)
        selected_note = None if create_mode else (store.get_note(username, selected_note_id) if selected_note_id else None)
        if selected_note is not None and selected_folder == _ALL_FOLDER_TOKEN:
            selected_folder = _folder_token(selected_note.folder)
        board_notes, selected_note = _board_notes(
            notes,
            selected_folder=selected_folder,
            selected_note_id=selected_note_id,
            search_results=search_results,
        )
        return deps.templates.TemplateResponse(
            request=request,
            name="notes.html",
            context={
                "title": settings.ui.title,
                "username": username,
                "notes_nav": "notes",
                "notes": notes,
                "note_folder_rows": _folder_rows(notes, folders),
                "board_notes": board_notes,
                "note_folders": folders,
                "selected_note": selected_note,
                "selected_folder": selected_folder,
                "create_mode": create_mode,
                "notes_count": len(notes),
                "folder_count": len(folders),
                "info_message": info_message,
                "error_message": error_message,
                "note_search_query": search_query,
                "note_search_results": list(search_results or []),
                "note_search_result_map": {
                    str(item.get("note_id", "")).strip(): item for item in list(search_results or []) if str(item.get("note_id", "")).strip()
                },
            },
        )

    @app.get("/notes", response_class=HTMLResponse)
    async def notes_page(
        request: Request,
        note: str = "",
        folder: str = _ALL_FOLDER_TOKEN,
        q: str = "",
        info: str = "",
        error: str = "",
        new: int = 0,
    ) -> HTMLResponse:
        username = deps.get_username_from_request(request) or "web"
        selected = str(note or "").strip()
        selected_folder = str(folder or _ALL_FOLDER_TOKEN).strip() or _ALL_FOLDER_TOKEN
        search_query = str(q or "").strip()
        info_message = str(info or "").strip()
        error_message = str(error or "").strip()
        search_results: list[dict[str, Any]] = []
        known_notes = _store().list_notes(username)
        known_note_ids = {item.note_id for item in known_notes}
        known_note_ids_by_title = {item.title.strip().lower(): item.note_id for item in known_notes if item.title.strip()}
        if search_query:
            notes_index = _index()
            try:
                raw_hits = await notes_index.search_notes(user_id=username, query=search_query, limit=8)
                search_results = [
                    {
                        "note_id": hit.note_id,
                        "title": hit.title,
                        "folder": hit.folder,
                        "relative_path": hit.relative_path,
                        "updated_at": hit.updated_at,
                        "score": hit.score,
                        "snippet": hit.snippet,
                        "chunk_index": hit.chunk_index,
                        "chunk_total": hit.chunk_total,
                        "source": "qdrant",
                    }
                    for hit in raw_hits
                ]
                for item in search_results:
                    note_id = str(item.get("note_id", "")).strip()
                    if note_id in known_note_ids:
                        continue
                    title_key = str(item.get("title", "")).strip().lower()
                    mapped_note_id = known_note_ids_by_title.get(title_key, "")
                    if mapped_note_id:
                        item["note_id"] = mapped_note_id
            except Exception:
                pass
            finally:
                close = getattr(notes_index, "aclose", None)
                if callable(close):
                    await close()
        if search_query and (
            not search_results or not any(str(item.get("note_id", "")).strip() in known_note_ids for item in search_results)
        ):
            raw_hits = await search_note_hits(
                base_dir=deps.base_dir,
                username=username,
                settings=deps.get_settings(),
                query=search_query,
                limit=8,
            )
            search_results = [
                {
                    "note_id": hit.note_id,
                    "title": hit.title,
                    "folder": hit.folder,
                    "relative_path": hit.relative_path,
                    "updated_at": hit.updated_at,
                    "score": hit.score,
                    "snippet": hit.snippet,
                    "chunk_index": hit.chunk_index,
                    "chunk_total": hit.chunk_total,
                    "source": hit.source,
                }
                for hit in raw_hits
            ]
        return _render_notes_page(
            request,
            selected_note_id=selected,
            selected_folder=selected_folder,
            create_mode=bool(new),
            info_message=info_message,
            error_message=error_message,
            search_query=search_query,
            search_results=search_results,
        )

    @app.post("/notes/save")
    async def notes_save(
        request: Request,
        note_id: str = Form(""),
        title: str = Form(""),
        folder: str = Form(""),
        tags: str = Form(""),
        body: str = Form(""),
    ) -> RedirectResponse:
        username = deps.get_username_from_request(request) or "web"
        store = _store()
        try:
            note = store.save_note(username, note_id=note_id, title=title, folder=folder, tags=tags, body=body)
        except NotesStoreError as exc:
            return RedirectResponse(url=f"/notes?error={quote_plus(str(exc))}", status_code=303)
        info_message = "Notiz gespeichert."
        notes_index = _index()
        try:
            result = await notes_index.reindex_note(note)
            if result.get("indexed"):
                info_message = f"Notiz gespeichert. Qdrant-Index aktualisiert ({int(result.get('chunk_count', 0) or 0)} Chunks)."
        except Exception as exc:
            info_message = f"Notiz gespeichert. Qdrant-Index konnte nicht aktualisiert werden: {exc}"
        finally:
            close = getattr(notes_index, "aclose", None)
            if callable(close):
                await close()
        folder_token = quote_plus(_folder_token(note.folder))
        return RedirectResponse(
            url=f"/notes?folder={folder_token}&note={quote_plus(note.note_id)}&info={quote_plus(info_message)}",
            status_code=303,
        )

    @app.post("/notes/delete")
    async def notes_delete(request: Request, note_id: str = Form("")) -> RedirectResponse:
        username = deps.get_username_from_request(request) or "web"
        store = _store()
        try:
            note = store.delete_note(username, note_id)
        except NotesStoreError as exc:
            return RedirectResponse(url=f"/notes?error={quote_plus(str(exc))}", status_code=303)
        info_message = "Notiz gelöscht."
        notes_index = _index()
        try:
            await notes_index.delete_note(user_id=username, note_id=note.note_id)
            info_message = "Notiz gelöscht. Qdrant-Index bereinigt."
        except Exception as exc:
            info_message = f"Notiz gelöscht. Qdrant-Index konnte nicht bereinigt werden: {exc}"
        finally:
            close = getattr(notes_index, "aclose", None)
            if callable(close):
                await close()
        return RedirectResponse(url=f"/notes?folder={quote_plus(_ALL_FOLDER_TOKEN)}&info={quote_plus(info_message)}", status_code=303)

    @app.post("/notes/folders/create")
    async def notes_create_folder(request: Request, folder: str = Form("")) -> RedirectResponse:
        username = deps.get_username_from_request(request) or "web"
        store = _store()
        try:
            created = store.create_folder(username, folder)
        except NotesStoreError as exc:
            return RedirectResponse(url=f"/notes?error={quote_plus(str(exc))}", status_code=303)
        return RedirectResponse(
            url=f"/notes?folder={quote_plus(created)}&new=1&info={quote_plus(f'Ordner {created} angelegt.')}",
            status_code=303,
        )

    @app.get("/notes/export/{note_id}.md", response_model=None)
    async def notes_export(request: Request, note_id: str) -> Response:
        username = deps.get_username_from_request(request) or "web"
        store = _store()
        try:
            export_path = store.export_path(username, note_id)
            note = store.get_note(username, note_id)
        except NotesStoreError as exc:
            return RedirectResponse(url=f"/notes?error={quote_plus(str(exc))}", status_code=303)
        filename = export_path.name if note is None else f"{note.title}.md"
        return FileResponse(export_path, media_type="text/markdown; charset=utf-8", filename=filename)
