from __future__ import annotations

from pathlib import Path
from typing import Any
import re

from aria.core.doc_meta_catalog import DOC_META_PREFIX


def slug_user_id(user_id: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_-]", "_", str(user_id or "").strip().lower())
    clean = re.sub(r"_+", "_", clean).strip("_")
    return clean or "web"


def payload_user_matches(payload_user_id: Any, requested_user_id: str) -> bool:
    payload_user = str(payload_user_id or "").strip()
    if not payload_user:
        return False
    return slug_user_id(payload_user) == slug_user_id(requested_user_id)


def document_payload_name(payload: dict[str, Any] | None) -> str:
    data = payload or {}
    for key in (
        "document_name",
        "filename",
        "file_name",
        "original_filename",
        "source_name",
        "title",
        "name",
        "source_path",
        "path",
    ):
        raw = str(data.get(key, "") or "").strip()
        if not raw:
            continue
        if key in {"source_path", "path"}:
            return Path(raw).name or raw
        return raw
    return ""


def document_payload_id(payload: dict[str, Any] | None) -> str:
    data = payload or {}
    for key in ("document_id", "doc_id", "file_id", "upload_id", "source_id"):
        raw = str(data.get(key, "") or "").strip()
        if raw:
            return raw
    return ""


def document_collection_user_slug(collection: str, prefix: str) -> str:
    name = str(collection or "").strip().lower()
    clean_prefix = str(prefix or "").strip().lower().rstrip("_")
    marker = f"{clean_prefix}_"
    if not clean_prefix or not name.startswith(marker):
        return ""
    rest = name[len(marker) :].strip("_")
    return slug_user_id(rest) if rest else ""


def is_document_payload(payload: dict[str, Any] | None) -> bool:
    data = payload or {}
    source = str(data.get("source", "")).strip().lower()
    document_name = document_payload_name(data)
    document_id = document_payload_id(data)
    document_sources = {"rag_upload", "document_upload", "document", "uploaded_document"}
    return source in document_sources or source.startswith("rag_document") or bool(document_name) or bool(document_id)


def is_document_collection_name(collection: str) -> bool:
    return str(collection or "").strip().lower().startswith("aria_docs")


def is_document_guide_collection_name(collection: str, prefix: str) -> bool:
    return str(collection or "").strip().lower().startswith(str(prefix or "").strip().lower())


def is_document_meta_collection_name(collection: str) -> bool:
    return str(collection or "").strip().lower().startswith(DOC_META_PREFIX)
