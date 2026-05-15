from __future__ import annotations

import re
from pathlib import Path

from aria.core.i18n import I18NStore
from aria.core.text_utils import is_english

_FILE_SUMMARY_I18N = I18NStore(Path(__file__).resolve().parents[2] / "i18n")


def _file_text(language: str | None, key: str, default: str = "", **values: object) -> str:
    template = _FILE_SUMMARY_I18N.t(language or "de", f"result_file_operation.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template


def _file_terms(key: str, fallback: tuple[str, ...]) -> tuple[str, ...]:
    raw_values = [
        _FILE_SUMMARY_I18N.t("de", f"result_file_operation.{key}", ""),
        _FILE_SUMMARY_I18N.t("en", f"result_file_operation.{key}", ""),
    ]
    terms: list[str] = []
    for raw in raw_values:
        for item in str(raw or "").split("|"):
            clean = item.strip()
            if clean and clean not in terms:
                terms.append(clean)
    return tuple(terms) or fallback


def _starts_with_any(value: str, prefixes: tuple[str, ...]) -> bool:
    lower = value.lower()
    return any(lower.startswith(prefix.lower()) for prefix in prefixes)


def _match_file_written(text: str) -> re.Match[str] | None:
    object_terms = "|".join(re.escape(item) for item in _file_terms("write_object_terms", ("file",)))
    action_terms = "|".join(re.escape(item) for item in _file_terms("write_action_terms", ("written",)))
    unit_terms = "|".join(re.escape(item) for item in _file_terms("char_unit_terms", ("chars?",)))
    return re.match(
        rf"^(?:SFTP|SMB)-(?:{object_terms})\s+(?:{action_terms}):\s+(.+?)\s+\((\d+)\s+(?:{unit_terms})\)$",
        text,
        re.IGNORECASE,
    )


def summarize_file_result_for_chat(
    text: str,
    *,
    connection_ref: str,
    connection_kind: str,
    capability: str,
    path: str,
    language: str | None = None,
) -> str:
    clean_text = str(text or "").strip()
    if not clean_text:
        return ""
    ref_label = f"`{connection_ref}`"
    path_label = str(path or "").strip() or "."
    _ = connection_kind

    if capability == "file_list":
        lines = [str(line or "").rstrip() for line in clean_text.splitlines() if str(line or "").strip()]
        if not lines:
            return ""
        first = lines[0].strip()
        if not _starts_with_any(first, _file_terms("list_header_prefixes", ("Contents of",))):
            return ""
        resolved_path = path_label
        if ":" in first:
            resolved_path = first.split(":", 1)[0].split(" ", 2)[-1].strip() or path_label
        entries: list[str] = []
        for line in lines[1:]:
            clean = line.strip()
            if not clean.startswith("- "):
                continue
            item = clean[2:].strip()
            if item:
                entries.append(item)
        if not entries:
            return ""
        folders = [item for item in entries if item.endswith("/")]
        files = [item for item in entries if not item.endswith("/")]
        if is_english(language):
            parts = [_file_text(language, "listing", "File listing for {ref} in `{path}`: {count} entries.", ref=ref_label, path=resolved_path, count=len(entries))]
            if folders:
                parts.append(_file_text(language, "folders", "Folders: {items}.", items=", ".join(folders[:5])))
            if files:
                parts.append(_file_text(language, "examples", "Examples: {items}.", items=", ".join(files[:5])))
        else:
            parts = [_file_text(language, "listing", "File listing for {ref} in `{path}`: {count} entries.", ref=ref_label, path=resolved_path, count=len(entries))]
            if folders:
                parts.append(_file_text(language, "folders", "Folders: {items}.", items=", ".join(folders[:5])))
            if files:
                parts.append(_file_text(language, "examples", "Examples: {items}.", items=", ".join(files[:5])))
        return " ".join(parts).strip()

    if capability == "file_write":
        write_match = _match_file_written(clean_text)
        if not write_match:
            return ""
        resolved_path = str(write_match.group(1) or "").strip() or path_label
        char_count = str(write_match.group(2) or "").strip()
        if is_english(language):
            return _file_text(language, "written", "File written via {ref}: `{path}` ({count} chars).", ref=ref_label, path=resolved_path, count=char_count)
        return _file_text(language, "written", "File written via {ref}: `{path}` ({count} chars).", ref=ref_label, path=resolved_path, count=char_count)

    return ""
