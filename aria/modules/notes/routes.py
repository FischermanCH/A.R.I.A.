from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from fastapi import FastAPI, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from aria.modules.platform_primitives.i18n import I18NStore
from aria.modules.notes.context import search_note_hits
from aria.modules.notes.index import NotesIndex
from aria.modules.notes.store import NoteRecord, NotesStore, NotesStoreError
from aria.modules import module_route_path, module_template_name


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
_NOTES_ROUTES_I18N = I18NStore(Path(__file__).resolve().parents[2] / "i18n")


def _documents_template_name(template_name: str) -> str:
    resolved = module_template_name("notes", template_name)
    if resolved is None:
        raise RuntimeError(f"notes template is not registered: {template_name}")
    return resolved


def _documents_route(route_path: str = "/notes") -> str:
    resolved = module_route_path("notes", route_path)
    if resolved is None:
        raise RuntimeError(f"notes route is not registered: {route_path}")
    return resolved


def _notes_redirect_url(**params: str) -> str:
    base = _documents_route("/notes")
    clean = [(key, str(value or "").strip()) for key, value in params.items() if str(value or "").strip()]
    if not clean:
        return base
    return f"{base}?{'&'.join(f'{key}={value}' for key, value in clean)}"


def _notes_route_text(language: str, key: str, default: str = "", **values: object) -> str:
    template = _NOTES_ROUTES_I18N.t(language, f"notes_routes.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template


def _folder_token(folder: str) -> str:
    clean = str(folder or "").strip()
    return clean or _ROOT_FOLDER_TOKEN


def _notes_view(value: str) -> str:
    return "list" if str(value or "").strip().lower() == "list" else "cards"


def _folder_matches(note: NoteRecord, selected_folder: str) -> bool:
    if selected_folder == _ALL_FOLDER_TOKEN:
        return True
    if selected_folder == _ROOT_FOLDER_TOKEN:
        return not bool(note.folder)
    clean_folder = str(note.folder or "").strip()
    return clean_folder == selected_folder or clean_folder.startswith(f"{selected_folder}/")


def _folder_rows(notes: list[NoteRecord], folders: list[str], *, language: str = "de") -> list[dict[str, Any]]:
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
            "label": _notes_route_text(language, "all_notes", "All notes"),
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


def _replace_note(notes: list[NoteRecord], replacement: NoteRecord) -> list[NoteRecord]:
    rows: list[NoteRecord] = []
    replaced = False
    for note in notes:
        if note.note_id == replacement.note_id:
            rows.append(replacement)
            replaced = True
        else:
            rows.append(note)
    if not replaced:
        rows.append(replacement)
    return rows


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
        store: NotesStore | None = None,
        notes: list[NoteRecord] | None = None,
        folders: list[str] | None = None,
        selected_note: NoteRecord | None = None,
        notes_view: str = "cards",
    ) -> HTMLResponse:
        settings = deps.get_settings()
        username = deps.get_username_from_request(request) or "web"
        lang = str(getattr(request.state, "lang", "de") or "de")
        store = store or _store()
        notes = notes if notes is not None else store.list_notes(username, preview_only=True)
        folders = folders if folders is not None else store.list_folders(username, notes=notes)
        if selected_note is None and not create_mode and selected_note_id:
            selected_note = store.get_note(username, selected_note_id)
            if selected_note is not None:
                notes = _replace_note(notes, selected_note)
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
            name=_documents_template_name("notes.html"),
            context={
                "title": settings.ui.title,
                "username": username,
                "notes_nav": "notes",
                "notes": notes,
                "note_folder_rows": _folder_rows(notes, folders, language=lang),
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
                "notes_view": _notes_view(notes_view),
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
        view: str = "cards",
    ) -> HTMLResponse:
        username = deps.get_username_from_request(request) or "web"
        selected = str(note or "").strip()
        selected_folder = str(folder or _ALL_FOLDER_TOKEN).strip() or _ALL_FOLDER_TOKEN
        store = _store()
        known_notes = store.list_notes(username, preview_only=True)
        folders = store.list_folders(username, notes=known_notes)
        if selected_folder not in {_ALL_FOLDER_TOKEN, _ROOT_FOLDER_TOKEN}:
            selected_folder = store.resolve_folder_name(username, selected_folder, folders=folders)
        search_query = str(q or "").strip()
        info_message = str(info or "").strip()
        error_message = str(error or "").strip()
        search_results: list[dict[str, Any]] = []
        known_note_ids = {item.note_id for item in known_notes}
        known_note_ids_by_title = {item.title.strip().lower(): item.note_id for item in known_notes if item.title.strip()}
        selected_note = None if bool(new) or not selected else store.get_note(username, selected)
        if selected_note is not None:
            known_notes = _replace_note(known_notes, selected_note)
            known_note_ids.add(selected_note.note_id)
            if selected_note.title.strip():
                known_note_ids_by_title[selected_note.title.strip().lower()] = selected_note.note_id
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
            store=store,
            notes=known_notes,
            folders=folders,
            selected_note=selected_note,
            notes_view=view,
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
        lang = str(getattr(request.state, "lang", "de") or "de")
        store = _store()
        try:
            note = store.save_note(username, note_id=note_id, title=title, folder=folder, tags=tags, body=body)
        except NotesStoreError as exc:
            return RedirectResponse(url=_notes_redirect_url(error=quote_plus(str(exc))), status_code=303)
        info_message = _notes_route_text(lang, "note_saved", "Note saved.")
        notes_index = _index()
        try:
            result = await notes_index.reindex_note(note)
            if result.get("indexed"):
                info_message = _notes_route_text(
                    lang,
                    "note_saved_indexed",
                    "Note saved. Qdrant index updated ({chunk_count} chunks).",
                    chunk_count=int(result.get("chunk_count", 0) or 0),
                )
        except Exception as exc:
            info_message = _notes_route_text(
                lang,
                "note_saved_index_failed",
                "Note saved. Qdrant index could not be updated: {error}",
                error=exc,
            )
        finally:
            close = getattr(notes_index, "aclose", None)
            if callable(close):
                await close()
        folder_token = quote_plus(_folder_token(note.folder))
        return RedirectResponse(
            url=_notes_redirect_url(folder=folder_token, note=quote_plus(note.note_id), info=quote_plus(info_message)),
            status_code=303,
        )

    @app.post("/notes/delete")
    async def notes_delete(request: Request, note_id: str = Form("")) -> RedirectResponse:
        username = deps.get_username_from_request(request) or "web"
        lang = str(getattr(request.state, "lang", "de") or "de")
        store = _store()
        try:
            note = store.delete_note(username, note_id)
        except NotesStoreError as exc:
            return RedirectResponse(url=_notes_redirect_url(error=quote_plus(str(exc))), status_code=303)
        info_message = _notes_route_text(lang, "note_deleted", "Note deleted.")
        notes_index = _index()
        try:
            await notes_index.delete_note(user_id=username, note_id=note.note_id)
            info_message = _notes_route_text(lang, "note_deleted_index_cleaned", "Note deleted. Qdrant index cleaned.")
        except Exception as exc:
            info_message = _notes_route_text(
                lang,
                "note_deleted_index_failed",
                "Note deleted. Qdrant index could not be cleaned: {error}",
                error=exc,
            )
        finally:
            close = getattr(notes_index, "aclose", None)
            if callable(close):
                await close()
        return RedirectResponse(
            url=_notes_redirect_url(folder=quote_plus(_ALL_FOLDER_TOKEN), info=quote_plus(info_message)),
            status_code=303,
        )

    @app.post("/notes/move")
    async def notes_move(
        request: Request,
        note_id: str = Form(""),
        target_folder: str = Form(""),
    ) -> RedirectResponse:
        username = deps.get_username_from_request(request) or "web"
        lang = str(getattr(request.state, "lang", "de") or "de")
        store = _store()
        folders = store.list_folders(username)
        clean_target = store.resolve_folder_name(username, target_folder, folders=folders) if str(target_folder or "").strip() else ""
        try:
            note = store.move_note(username, note_id, folder=clean_target)
        except NotesStoreError as exc:
            return RedirectResponse(url=_notes_redirect_url(error=quote_plus(str(exc))), status_code=303)
        info_message = _notes_route_text(
            lang,
            "note_moved",
            "Note moved to {folder}.",
            folder=note.folder or "Inbox",
        )
        notes_index = _index()
        try:
            result = await notes_index.reindex_note(note)
            if result.get("indexed"):
                info_message = _notes_route_text(
                    lang,
                    "note_moved_indexed",
                    "Note moved to {folder}. Qdrant index updated ({chunk_count} chunks).",
                    folder=note.folder or "Inbox",
                    chunk_count=int(result.get("chunk_count", 0) or 0),
                )
        except Exception as exc:
            info_message = _notes_route_text(
                lang,
                "note_moved_index_failed",
                "Note moved to {folder}. Qdrant index could not be updated: {error}",
                folder=note.folder or "Inbox",
                error=exc,
            )
        finally:
            close = getattr(notes_index, "aclose", None)
            if callable(close):
                await close()
        return RedirectResponse(
            url=_notes_redirect_url(
                folder=quote_plus(_folder_token(note.folder)),
                note=quote_plus(note.note_id),
                info=quote_plus(info_message),
            ),
            status_code=303,
        )

    @app.post("/notes/bulk/move")
    async def notes_bulk_move(request: Request) -> RedirectResponse:
        username = deps.get_username_from_request(request) or "web"
        lang = str(getattr(request.state, "lang", "de") or "de")
        form = await request.form()
        note_ids = [str(item or "").strip() for item in form.getlist("note_ids") if str(item or "").strip()]
        target_folder = str(form.get("target_folder") or "").strip()
        selected_folder = str(form.get("selected_folder") or _ALL_FOLDER_TOKEN).strip() or _ALL_FOLDER_TOKEN
        store = _store()
        folders = store.list_folders(username)
        clean_target = store.resolve_folder_name(username, target_folder, folders=folders) if target_folder else ""
        if not note_ids:
            info_message = _notes_route_text(lang, "bulk_move_no_selection", "Please select at least one note.")
            return RedirectResponse(
                url=_notes_redirect_url(folder=quote_plus(selected_folder), view="list", error=quote_plus(info_message)),
                status_code=303,
            )
        moved_notes: list[NoteRecord] = []
        try:
            for note_id in note_ids:
                moved_notes.append(store.move_note(username, note_id, folder=clean_target))
        except NotesStoreError as exc:
            return RedirectResponse(
                url=_notes_redirect_url(folder=quote_plus(selected_folder), view="list", error=quote_plus(str(exc))),
                status_code=303,
            )
        info_message = _notes_route_text(
            lang,
            "bulk_notes_moved",
            "{count} notes moved to {folder}.",
            count=len(moved_notes),
            folder=clean_target or "Inbox",
        )
        notes_index = _index()
        indexed_count = 0
        try:
            for note in moved_notes:
                result = await notes_index.reindex_note(note)
                if result.get("indexed"):
                    indexed_count += 1
            info_message = _notes_route_text(
                lang,
                "bulk_notes_moved_indexed",
                "{count} notes moved to {folder}. Qdrant index updated for {indexed_count} notes.",
                count=len(moved_notes),
                folder=clean_target or "Inbox",
                indexed_count=indexed_count,
            )
        except Exception as exc:
            info_message = _notes_route_text(
                lang,
                "bulk_notes_moved_index_failed",
                "{count} notes moved to {folder}. Qdrant index could not be fully updated: {error}",
                count=len(moved_notes),
                folder=clean_target or "Inbox",
                error=exc,
            )
        finally:
            close = getattr(notes_index, "aclose", None)
            if callable(close):
                await close()
        return RedirectResponse(
            url=_notes_redirect_url(folder=quote_plus(_folder_token(clean_target)), view="list", info=quote_plus(info_message)),
            status_code=303,
        )

    @app.post("/notes/folders/create")
    async def notes_create_folder(request: Request, folder: str = Form("")) -> RedirectResponse:
        username = deps.get_username_from_request(request) or "web"
        lang = str(getattr(request.state, "lang", "de") or "de")
        store = _store()
        try:
            created = store.create_folder(username, folder)
        except NotesStoreError as exc:
            return RedirectResponse(url=_notes_redirect_url(error=quote_plus(str(exc))), status_code=303)
        info_message = _notes_route_text(lang, "folder_created", "Folder {folder} created.", folder=created)
        return RedirectResponse(
            url=_notes_redirect_url(folder=quote_plus(created), new="1", info=quote_plus(info_message)),
            status_code=303,
        )

    @app.post("/notes/folders/rename")
    async def notes_rename_folder(
        request: Request,
        folder: str = Form(""),
        new_folder: str = Form(""),
    ) -> RedirectResponse:
        username = deps.get_username_from_request(request) or "web"
        lang = str(getattr(request.state, "lang", "de") or "de")
        store = _store()
        try:
            renamed = store.rename_folder(username, folder=folder, new_folder=new_folder)
        except NotesStoreError as exc:
            fallback_folder = str(folder or _ALL_FOLDER_TOKEN).strip() or _ALL_FOLDER_TOKEN
            return RedirectResponse(
                url=_notes_redirect_url(folder=quote_plus(fallback_folder), error=quote_plus(str(exc))),
                status_code=303,
            )
        info_message = _notes_route_text(lang, "folder_renamed", "Folder renamed: {folder}", folder=renamed)
        return RedirectResponse(
            url=_notes_redirect_url(folder=quote_plus(renamed), info=quote_plus(info_message)),
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
            return RedirectResponse(url=_notes_redirect_url(error=quote_plus(str(exc))), status_code=303)
        filename = export_path.name if note is None else f"{note.title}.md"
        return FileResponse(export_path, media_type="text/markdown; charset=utf-8", filename=filename)
