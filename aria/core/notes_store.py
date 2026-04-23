from __future__ import annotations

import contextlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4
import re

import yaml


_FRONTMATTER_BOUNDARY = "---"


@dataclass(frozen=True)
class NoteRecord:
    note_id: str
    user_id: str
    title: str
    folder: str
    body: str
    path: Path
    relative_path: str
    created_at: str
    updated_at: str
    tags: list[str]

    @property
    def filename(self) -> str:
        return self.path.name

    @property
    def summary(self) -> str:
        text = re.sub(r"\s+", " ", self.body).strip()
        if len(text) <= 180:
            return text
        return text[:177].rstrip(" ,;:.!?") + "..."


class NotesStoreError(ValueError):
    """Raised when a note action cannot be completed."""


class NotesStore:
    def __init__(self, root_dir: Path):
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _slug_user_id(user_id: str) -> str:
        clean = re.sub(r"[^a-zA-Z0-9_-]", "_", str(user_id or "").strip().lower())
        clean = re.sub(r"_+", "_", clean).strip("_")
        return clean or "web"

    def _user_root(self, user_id: str) -> Path:
        root = self.root_dir / self._slug_user_id(user_id)
        root.mkdir(parents=True, exist_ok=True)
        return root

    @staticmethod
    def _normalize_title(value: str) -> str:
        title = re.sub(r"\s+", " ", str(value or "").strip())
        if not title:
            raise NotesStoreError("Bitte einen Notiz-Titel eingeben.")
        return title[:140].strip()

    @staticmethod
    def _normalize_body(value: str) -> str:
        body = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
        body = body.replace("\ufeff", "")
        body = re.sub(r"\n{3,}", "\n\n", body).strip()
        if not body:
            raise NotesStoreError("Bitte einen Notiz-Inhalt eingeben.")
        return body

    @staticmethod
    def _normalize_folder(value: str | None) -> str:
        raw = str(value or "").replace("\\", "/").strip().strip("/")
        if not raw:
            return ""
        parts: list[str] = []
        for part in raw.split("/"):
            clean = re.sub(r"\s+", " ", part).strip().strip(".")
            clean = re.sub(r"[^0-9A-Za-z _.-]", "-", clean)
            clean = re.sub(r"-{2,}", "-", clean).strip(" -")
            if not clean or clean in {"..", "."}:
                continue
            parts.append(clean[:80])
        return "/".join(parts[:8])

    @staticmethod
    def _normalize_tags(value: Any) -> list[str]:
        if isinstance(value, list):
            raw_items = value
        else:
            raw_items = re.split(r"[,;\n]+", str(value or ""))
        rows: list[str] = []
        seen: set[str] = set()
        for item in raw_items:
            clean = re.sub(r"\s+", " ", str(item or "").strip().lower()).strip(" -")
            clean = re.sub(r"[^0-9a-zA-ZäöüÄÖÜß _./+-]", "", clean)
            clean = clean[:24].strip()
            if len(clean) < 2 or clean in seen:
                continue
            seen.add(clean)
            rows.append(clean)
        return rows[:12]

    @staticmethod
    def _slugify(value: str) -> str:
        raw = str(value or "").strip().lower()
        raw = raw.encode("ascii", "ignore").decode("ascii")
        raw = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
        return raw[:80] or "note"

    @staticmethod
    def _split_frontmatter(content: str) -> tuple[dict[str, Any], str]:
        text = str(content or "")
        if not text.startswith(_FRONTMATTER_BOUNDARY + "\n"):
            return {}, text.strip()
        remainder = text[len(_FRONTMATTER_BOUNDARY) + 1 :]
        boundary = f"\n{_FRONTMATTER_BOUNDARY}\n"
        end = remainder.find(boundary)
        if end < 0:
            return {}, text.strip()
        raw_meta = remainder[:end]
        body = remainder[end + len(boundary) :].strip()
        try:
            meta = yaml.safe_load(raw_meta) or {}
        except yaml.YAMLError:
            meta = {}
        return meta if isinstance(meta, dict) else {}, body

    @staticmethod
    def _build_markdown(meta: dict[str, Any], body: str) -> str:
        safe_meta = {key: value for key, value in meta.items() if value not in (None, "", [], {})}
        frontmatter = yaml.safe_dump(safe_meta, sort_keys=False, allow_unicode=True).strip()
        body_text = str(body or "").strip() + "\n"
        return f"{_FRONTMATTER_BOUNDARY}\n{frontmatter}\n{_FRONTMATTER_BOUNDARY}\n\n{body_text}"

    def _iter_note_files(self, user_id: str) -> list[Path]:
        user_root = self._user_root(user_id)
        return sorted(path for path in user_root.rglob("*.md") if path.is_file())

    def _relative_folder_from_path(self, user_root: Path, path: Path) -> str:
        parent = path.parent.relative_to(user_root)
        value = str(parent).replace("\\", "/")
        return "" if value == "." else value

    def _load_note_from_path(self, user_id: str, path: Path) -> NoteRecord | None:
        user_root = self._user_root(user_id)
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            return None
        meta, body = self._split_frontmatter(raw)
        body = self._normalize_body(body or raw)
        title = self._normalize_title(meta.get("title") or path.stem.replace("-", " "))
        folder = self._normalize_folder(meta.get("folder") or self._relative_folder_from_path(user_root, path))
        created_at = str(meta.get("created_at") or self._now_iso()).strip()
        updated_at = str(meta.get("updated_at") or created_at).strip()
        tags = [str(item).strip() for item in list(meta.get("tags") or []) if str(item).strip()]
        note_id = str(meta.get("note_id") or "").strip() or str(uuid4())
        relative_path = str(path.relative_to(user_root)).replace("\\", "/")
        return NoteRecord(
            note_id=note_id,
            user_id=self._slug_user_id(user_id),
            title=title,
            folder=folder,
            body=body,
            path=path,
            relative_path=relative_path,
            created_at=created_at,
            updated_at=updated_at,
            tags=tags,
        )

    def list_notes(self, user_id: str) -> list[NoteRecord]:
        notes = [
            note
            for path in self._iter_note_files(user_id)
            if (note := self._load_note_from_path(user_id, path)) is not None
        ]
        notes.sort(key=lambda item: (item.folder.lower(), item.updated_at, item.title.lower()), reverse=False)
        notes.sort(key=lambda item: item.updated_at, reverse=True)
        return notes

    def list_folders(self, user_id: str) -> list[str]:
        folders = {""}
        user_root = self._user_root(user_id)
        for path in user_root.rglob("*"):
            if not path.is_dir():
                continue
            folder = str(path.relative_to(user_root)).replace("\\", "/")
            if folder and folder != ".":
                folders.add(folder)
        for note in self.list_notes(user_id):
            folders.add(note.folder)
        return sorted(item for item in folders if item != "")

    def get_note(self, user_id: str, note_id: str) -> NoteRecord | None:
        clean_id = str(note_id or "").strip()
        if not clean_id:
            return None
        for note in self.list_notes(user_id):
            if note.note_id == clean_id:
                return note
        return None

    def create_folder(self, user_id: str, folder: str) -> str:
        clean_folder = self._normalize_folder(folder)
        if not clean_folder:
            raise NotesStoreError("Bitte einen Ordnernamen eingeben.")
        target = self._user_root(user_id) / Path(clean_folder)
        target.mkdir(parents=True, exist_ok=True)
        return clean_folder

    def _target_path(self, user_id: str, folder: str, title: str, *, current_path: Path | None = None) -> Path:
        user_root = self._user_root(user_id)
        folder_path = user_root / Path(folder) if folder else user_root
        folder_path.mkdir(parents=True, exist_ok=True)
        slug = self._slugify(title)
        candidate = folder_path / f"{slug}.md"
        if current_path is not None and candidate == current_path:
            return candidate
        if not candidate.exists():
            return candidate
        index = 2
        while True:
            alt = folder_path / f"{slug}-{index}.md"
            if current_path is not None and alt == current_path:
                return alt
            if not alt.exists():
                return alt
            index += 1

    def save_note(
        self,
        user_id: str,
        *,
        title: str,
        body: str,
        folder: str = "",
        note_id: str = "",
        tags: Any = "",
    ) -> NoteRecord:
        clean_title = self._normalize_title(title)
        clean_body = self._normalize_body(body)
        clean_folder = self._normalize_folder(folder)
        clean_tags = self._normalize_tags(tags)
        existing = self.get_note(user_id, note_id)
        created_at = existing.created_at if existing else self._now_iso()
        updated_at = self._now_iso()
        actual_note_id = existing.note_id if existing else (str(note_id).strip() or str(uuid4()))
        target_path = self._target_path(user_id, clean_folder, clean_title, current_path=existing.path if existing else None)
        metadata = {
            "note_id": actual_note_id,
            "title": clean_title,
            "folder": clean_folder,
            "created_at": created_at,
            "updated_at": updated_at,
            "tags": clean_tags,
        }
        target_path.write_text(self._build_markdown(metadata, clean_body), encoding="utf-8")
        if existing and existing.path != target_path:
            with contextlib.suppress(OSError):
                existing.path.unlink()
            self._prune_empty_directories(existing.path.parent, stop_at=self._user_root(user_id))
        note = self._load_note_from_path(user_id, target_path)
        if note is None:
            raise NotesStoreError("Die Notiz konnte nicht gespeichert werden.")
        return note

    def delete_note(self, user_id: str, note_id: str) -> NoteRecord:
        note = self.get_note(user_id, note_id)
        if note is None:
            raise NotesStoreError("Die Notiz wurde nicht gefunden.")
        try:
            note.path.unlink()
        except OSError as exc:
            raise NotesStoreError("Die Notiz konnte nicht gelöscht werden.") from exc
        self._prune_empty_directories(note.path.parent, stop_at=self._user_root(user_id))
        return note

    def export_path(self, user_id: str, note_id: str) -> Path:
        note = self.get_note(user_id, note_id)
        if note is None:
            raise NotesStoreError("Die Notiz wurde nicht gefunden.")
        return note.path

    @staticmethod
    def _prune_empty_directories(path: Path, *, stop_at: Path) -> None:
        current = path
        stop = stop_at.resolve()
        while True:
            try:
                resolved = current.resolve()
            except OSError:
                break
            if resolved == stop:
                break
            try:
                current.rmdir()
            except OSError:
                break
            current = current.parent
