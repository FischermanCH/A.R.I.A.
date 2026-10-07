"""SFTP action-resolution boundary helpers."""

from __future__ import annotations


def supports_sftp_file_operation(connection_kind: str) -> bool:
    return str(connection_kind or "").strip().lower() == "sftp"
