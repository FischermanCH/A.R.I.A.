from __future__ import annotations

from typing import Any, Callable

from aria.modules.connections_catalog.catalog import normalize_connection_kind


FILE_OPERATION_BEHAVIOR_TO_MODE: dict[str, str] = {
    "remote_list_files": "list",
    "remote_read_file": "read",
    "remote_write_file": "write",
}

FILE_OPERATION_PLAN_CLASS_TO_MODE: dict[str, str] = {
    "file_list_basic": "list",
    "file_read_basic": "read",
    "file_write_basic": "write",
}

_FILE_OPERATION_KIND_COPY: dict[str, dict[str, dict[str, str]]] = {
    "sftp": {
        "list": {
            "title": "SFTP List Files",
            "summary": "Lists files or directories on the target system.",
            "preview": "List remote files via SFTP",
            "base_preview_de": "Dateien via SFTP anzeigen",
            "base_preview_en": "List files via SFTP",
        },
        "read": {
            "title": "SFTP Read File",
            "summary": "Reads a remote file from the target system.",
            "preview": "Read remote file via SFTP",
            "base_preview_de": "Remote-Datei via SFTP lesen",
            "base_preview_en": "Read remote file via SFTP",
        },
        "write": {
            "title": "SFTP Write File",
            "summary": "Writes prepared content back to a remote file on the target system.",
            "preview": "Write remote file via SFTP",
            "base_preview_de": "Remote-Datei via SFTP schreiben",
            "base_preview_en": "Write remote file via SFTP",
        },
    },
    "smb": {
        "list": {
            "title": "SMB List Files",
            "summary": "Lists files or directories on an SMB share.",
            "preview": "List remote files via SMB",
            "base_preview_de": "Dateien via SMB anzeigen",
            "base_preview_en": "List files via SMB",
        },
        "read": {
            "title": "SMB Read File",
            "summary": "Reads a file from an SMB share.",
            "preview": "Read remote file via SMB",
            "base_preview_de": "Remote-Datei via SMB lesen",
            "base_preview_en": "Read remote file via SMB",
        },
        "write": {
            "title": "SMB Write File",
            "summary": "Writes a file to an SMB share.",
            "preview": "Write remote file via SMB",
            "base_preview_de": "Remote-Datei via SMB schreiben",
            "base_preview_en": "Write remote file via SMB",
        },
    },
}

_FILE_OPERATION_DRAFT_LABELS: dict[str, dict[str, tuple[str, str]]] = {
    "sftp": {
        "list": ("List remote path", "Remote-Pfad anzeigen"),
        "read": ("Read remote path", "Remote-Pfad lesen"),
        "write": ("Write remote path", "Remote-Pfad schreiben"),
    },
    "smb": {
        "list": ("List share path", "Share-Pfad anzeigen"),
        "read": ("Read share path", "Share-Pfad lesen"),
        "write": ("Write share path", "Share-Pfad schreiben"),
    },
}


def file_operation_mode(*, behavior_profile: str = "", plan_class: str = "") -> str:
    clean_profile = str(behavior_profile or "").strip().lower()
    clean_plan_class = str(plan_class or "").strip().lower()
    if clean_profile in FILE_OPERATION_BEHAVIOR_TO_MODE:
        return FILE_OPERATION_BEHAVIOR_TO_MODE[clean_profile]
    return FILE_OPERATION_PLAN_CLASS_TO_MODE.get(clean_plan_class, "")


def file_operation_behavior_profile_for(plan_class: str) -> str:
    mode = file_operation_mode(plan_class=plan_class)
    for profile, profile_mode in FILE_OPERATION_BEHAVIOR_TO_MODE.items():
        if profile_mode == mode:
            return profile
    return ""


def build_file_operation_templates(connection_kind: str) -> list[dict[str, Any]]:
    clean_kind = normalize_connection_kind(connection_kind)
    copy = _FILE_OPERATION_KIND_COPY.get(clean_kind, {})
    if not copy:
        return []
    rows: list[dict[str, Any]] = []
    for mode in ("list", "read", "write"):
        mode_copy = copy.get(mode, {})
        candidate_id = f"{clean_kind}_{mode}_files" if mode == "list" else f"{clean_kind}_{mode}_file"
        rows.append(
            {
                "candidate_id": candidate_id,
                "plan_class": f"file_{mode}_basic",
                "behavior_profile": f"remote_{mode}_file" if mode != "list" else "remote_list_files",
                "title": mode_copy.get("title", ""),
                "summary": mode_copy.get("summary", ""),
                "intent": f"{mode}_file" if mode != "list" else "list_files",
                "capability": "file_list" if mode == "list" else ("file_read" if mode == "read" else "file_write"),
                "preview": mode_copy.get("preview", ""),
                "base_preview_de": mode_copy.get("base_preview_de", ""),
                "base_preview_en": mode_copy.get("base_preview_en", ""),
                "required_inputs": [] if mode == "list" else ["remote_path"],
            }
        )
    return rows


def build_file_operation_preview(
    *,
    mode: str,
    connection_kind: str,
    language: str,
    path: str,
    fallback: str,
) -> str:
    clean_kind = normalize_connection_kind(connection_kind)
    clean_mode = str(mode or "").strip().lower()
    labels = _FILE_OPERATION_DRAFT_LABELS.get(clean_kind, {})
    localized = labels.get(clean_mode)
    if not localized:
        return fallback
    en_label, de_label = localized
    prefix = de_label if str(language or "").strip().lower().startswith("de") else en_label
    if clean_mode == "list":
        return f"{prefix}: {path or '.'}"
    return f"{prefix}: {path}" if str(path or "").strip() else fallback


def derive_file_operation_inputs(
    *,
    mode: str,
    query: str,
    extract_remote_path: Callable[[str], str],
) -> dict[str, str]:
    clean_mode = str(mode or "").strip().lower()
    if clean_mode not in {"list", "read", "write"}:
        return {}
    path = extract_remote_path(query)
    return {"remote_path": path} if path else {}


def build_file_operation_draft(
    *,
    mode: str,
    connection_kind: str,
    query: str,
    extract_path: Callable[[str], str],
    extract_content: Callable[[str], str],
) -> tuple[str, str, str, str]:
    clean_mode = str(mode or "").strip().lower()
    clean_kind = normalize_connection_kind(connection_kind)
    labels = _FILE_OPERATION_DRAFT_LABELS.get(clean_kind, {})
    localized = labels.get(clean_mode, ("Remote path", "Remote-Pfad"))
    en_label, _de_label = localized
    path = ""
    content = ""
    capability = ""
    if clean_mode == "list":
        capability = "file_list"
        path = extract_path(query) or "."
        preview = f"{en_label}: {path}"
        return capability, path, content, preview
    if clean_mode == "read":
        capability = "file_read"
        path = extract_path(query)
        preview = f"{en_label}: {path}" if path else f"{en_label} still missing"
        return capability, path, content, preview
    if clean_mode == "write":
        capability = "file_write"
        path = extract_path(query)
        content = extract_content(query)
        preview = f"{en_label}: {path}" if path else f"{en_label} still missing"
        return capability, path, content, preview
    return capability, path, content, ""
