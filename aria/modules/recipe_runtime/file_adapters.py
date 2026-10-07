from __future__ import annotations

import contextlib
import io
import posixpath
from pathlib import Path
from typing import Any, Callable

RecipeText = Callable[..., str]


class RecipeFileRuntime:
    def __init__(
        self,
        *,
        get_connection_profile: Callable[[str, str], Any],
        resolve_local_path: Callable[[str], Path],
        enforce_file_guardrail: Callable[..., None],
        format_directory_listing: Callable[..., str],
        truncate_text: Callable[[str, int], str],
        recipe_text: RecipeText,
    ) -> None:
        self.get_connection_profile = get_connection_profile
        self.resolve_local_path = resolve_local_path
        self.enforce_file_guardrail = enforce_file_guardrail
        self.format_directory_listing = format_directory_listing
        self.truncate_text = truncate_text
        self.recipe_text = recipe_text

    def _text(self, key: str, default: str, **values: Any) -> str:
        return self.recipe_text("de", key, default, **values)

    def _build_sftp_connect_kwargs(self, connection: Any) -> dict[str, Any]:
        host = str(getattr(connection, "host", "")).strip()
        user = str(getattr(connection, "user", "")).strip()
        password = str(getattr(connection, "password", "")).strip()
        key_path = str(getattr(connection, "key_path", "")).strip()
        port = int(getattr(connection, "port", 22) or 22)
        timeout_seconds = int(getattr(connection, "timeout_seconds", 10) or 10)

        if not host:
            raise ValueError(self._text("sftp_host_missing", "SFTP host is missing in the profile."))
        if not user:
            raise ValueError(self._text("sftp_user_missing", "SFTP user is missing in the profile."))

        connect_kwargs: dict[str, Any] = {
            "hostname": host,
            "port": max(1, port),
            "username": user,
            "timeout": max(5, timeout_seconds),
            "allow_agent": False,
            "look_for_keys": False,
        }
        if key_path:
            key_file = self.resolve_local_path(key_path)
            if not key_file.exists():
                raise ValueError(self._text("sftp_key_not_found", "SFTP key not found: {key_path}", key_path=key_path))
            connect_kwargs["key_filename"] = str(key_file)
        elif password:
            connect_kwargs["password"] = password
        else:
            raise ValueError(self._text("sftp_auth_missing", "SFTP authentication is missing in the profile."))
        return connect_kwargs

    @staticmethod
    def _resolve_sftp_target_path(connection: Any, remote_path: str) -> str:
        root_path = str(getattr(connection, "root_path", "")).strip()
        clean_remote_path = str(remote_path).strip()
        if not clean_remote_path:
            return ""
        if clean_remote_path.startswith("/"):
            return posixpath.normpath(clean_remote_path)
        if root_path:
            return posixpath.normpath(posixpath.join(root_path, clean_remote_path))
        return posixpath.normpath(clean_remote_path)

    def _build_smb_connection(self, connection: Any) -> tuple[Any, str]:
        host = str(getattr(connection, "host", "")).strip()
        share = str(getattr(connection, "share", "")).strip()
        user = str(getattr(connection, "user", "")).strip()
        password = str(getattr(connection, "password", "")).strip()
        port = int(getattr(connection, "port", 445) or 445)
        timeout_seconds = int(getattr(connection, "timeout_seconds", 10) or 10)

        if not host:
            raise ValueError(self._text("smb_host_missing", "SMB host is missing in the profile."))
        if not share:
            raise ValueError(self._text("smb_share_missing", "SMB share is missing in the profile."))
        if not user:
            raise ValueError(self._text("smb_user_missing", "SMB user is missing in the profile."))
        if not password:
            raise ValueError(self._text("smb_password_missing", "SMB password is missing in the profile."))

        try:
            from smb.SMBConnection import SMBConnection  # type: ignore[import-not-found]
        except Exception as exc:  # noqa: BLE001
            raise ValueError(self._text("pysmb_missing", "Python module 'pysmb' is missing. Please install it and restart ARIA.")) from exc

        conn = SMBConnection(user, password, "aria", host, use_ntlm_v2=True, is_direct_tcp=True)
        ok = conn.connect(host, max(1, port), timeout=max(5, timeout_seconds))
        if not ok:
            raise ValueError(self._text("smb_connection_failed", "SMB connection could not be established."))
        return conn, share

    @staticmethod
    def _resolve_smb_target_path(connection: Any, remote_path: str) -> str:
        root_path = str(getattr(connection, "root_path", "")).strip()
        clean_remote_path = str(remote_path).strip()
        base_path = root_path or "/"
        if clean_remote_path and clean_remote_path.startswith("/"):
            return posixpath.normpath(clean_remote_path)
        if clean_remote_path:
            return posixpath.normpath(posixpath.join(base_path, clean_remote_path))
        return posixpath.normpath(base_path)

    def execute_sftp_read(self, connection_ref: str, remote_path: str) -> str:
        connection = self.get_connection_profile("sftp", connection_ref)
        connect_kwargs = self._build_sftp_connect_kwargs(connection)
        resolved_path = self._resolve_sftp_target_path(connection, remote_path)

        if not resolved_path:
            raise ValueError(self._text("sftp_file_path_missing", "SFTP file path is missing."))
        self.enforce_file_guardrail(connection=connection, operation="read", resolved_path=resolved_path)

        try:
            import paramiko  # type: ignore[import-not-found]
        except Exception as exc:  # noqa: BLE001
            raise ValueError(self._text("paramiko_missing", "Python module 'paramiko' is missing. Please install it and restart ARIA.")) from exc

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(**connect_kwargs)
            sftp = client.open_sftp()
            try:
                with sftp.open(resolved_path, "r") as handle:
                    payload = handle.read()
            finally:
                with contextlib.suppress(Exception):
                    sftp.close()
        finally:
            with contextlib.suppress(Exception):
                client.close()

        text = payload.decode("utf-8", errors="replace") if isinstance(payload, bytes) else str(payload)
        return self.truncate_text(text.strip(), 1400)

    def execute_sftp_write(self, connection_ref: str, remote_path: str, content: str) -> str:
        connection = self.get_connection_profile("sftp", connection_ref)
        connect_kwargs = self._build_sftp_connect_kwargs(connection)
        resolved_path = self._resolve_sftp_target_path(connection, remote_path)

        if not resolved_path:
            raise ValueError(self._text("sftp_file_path_missing", "SFTP file path is missing."))
        self.enforce_file_guardrail(connection=connection, operation="write", resolved_path=resolved_path, content=content)

        try:
            import paramiko  # type: ignore[import-not-found]
        except Exception as exc:  # noqa: BLE001
            raise ValueError(self._text("paramiko_missing", "Python module 'paramiko' is missing. Please install it and restart ARIA.")) from exc

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(**connect_kwargs)
            sftp = client.open_sftp()
            try:
                current_path = ""
                parent_dir = posixpath.dirname(resolved_path)
                for part in [item for item in parent_dir.split("/") if item]:
                    current_path = f"{current_path}/{part}" if current_path else f"/{part}"
                    try:
                        sftp.stat(current_path)
                    except Exception:
                        sftp.mkdir(current_path)
                with sftp.open(resolved_path, "w") as handle:
                    handle.write(content)
            finally:
                with contextlib.suppress(Exception):
                    sftp.close()
        finally:
            with contextlib.suppress(Exception):
                client.close()

        return self._text("sftp_file_written", "SFTP file written: {resolved_path} ({length} characters)", resolved_path=resolved_path, length=len(content))

    def execute_sftp_list(self, connection_ref: str, remote_path: str, *, language: str = "de") -> str:
        connection = self.get_connection_profile("sftp", connection_ref)
        connect_kwargs = self._build_sftp_connect_kwargs(connection)
        resolved_path = self._resolve_sftp_target_path(connection, remote_path or ".")
        self.enforce_file_guardrail(connection=connection, operation="list", resolved_path=resolved_path)

        try:
            import paramiko  # type: ignore[import-not-found]
        except Exception as exc:  # noqa: BLE001
            raise ValueError(self._text("paramiko_missing", "Python module 'paramiko' is missing. Please install it and restart ARIA.")) from exc

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(**connect_kwargs)
            sftp = client.open_sftp()
            try:
                entries = sftp.listdir_attr(resolved_path)
            finally:
                with contextlib.suppress(Exception):
                    sftp.close()
        finally:
            with contextlib.suppress(Exception):
                client.close()

        names: list[str] = []
        for entry in entries[:40]:
            filename = str(getattr(entry, "filename", "")).strip()
            if not filename:
                continue
            if hasattr(entry, "st_mode") and int(getattr(entry, "st_mode", 0) or 0) & 0o040000:
                names.append(filename + "/")
            else:
                names.append(filename)
        return self.format_directory_listing("SFTP", resolved_path, names, language=language)

    def execute_smb_read(self, connection_ref: str, remote_path: str) -> str:
        connection = self.get_connection_profile("smb", connection_ref)
        resolved_path = self._resolve_smb_target_path(connection, remote_path)
        if not resolved_path:
            raise ValueError(self._text("smb_file_path_missing", "SMB file path is missing."))
        self.enforce_file_guardrail(connection=connection, operation="read", resolved_path=resolved_path)

        conn, share = self._build_smb_connection(connection)
        buffer = io.BytesIO()
        try:
            conn.retrieveFile(share, resolved_path, buffer)
        finally:
            with contextlib.suppress(Exception):
                conn.close()

        text = buffer.getvalue().decode("utf-8", errors="replace")
        return self.truncate_text(text.strip(), 1400)

    def execute_smb_write(self, connection_ref: str, remote_path: str, content: str) -> str:
        connection = self.get_connection_profile("smb", connection_ref)
        resolved_path = self._resolve_smb_target_path(connection, remote_path)
        if not resolved_path:
            raise ValueError(self._text("smb_file_path_missing", "SMB file path is missing."))
        self.enforce_file_guardrail(connection=connection, operation="write", resolved_path=resolved_path, content=content)

        conn, share = self._build_smb_connection(connection)
        try:
            parent_dir = posixpath.dirname(resolved_path)
            current_path = ""
            for part in [item for item in parent_dir.split("/") if item]:
                current_path = f"{current_path}/{part}" if current_path else f"/{part}"
                with contextlib.suppress(Exception):
                    conn.createDirectory(share, current_path)
            conn.storeFile(share, resolved_path, io.BytesIO(content.encode("utf-8")))
        finally:
            with contextlib.suppress(Exception):
                conn.close()

        return self._text("smb_file_written", "SMB file written: {resolved_path} ({length} characters)", resolved_path=resolved_path, length=len(content))

    def execute_smb_list(self, connection_ref: str, remote_path: str, *, language: str = "de") -> str:
        connection = self.get_connection_profile("smb", connection_ref)
        resolved_path = self._resolve_smb_target_path(connection, remote_path or ".")
        self.enforce_file_guardrail(connection=connection, operation="list", resolved_path=resolved_path)
        conn, share = self._build_smb_connection(connection)
        try:
            entries = conn.listPath(share, resolved_path)
        finally:
            with contextlib.suppress(Exception):
                conn.close()

        names: list[str] = []
        for entry in entries[:40]:
            filename = str(getattr(entry, "filename", "")).strip()
            if not filename or filename in {".", ".."}:
                continue
            if bool(getattr(entry, "isDirectory", False)):
                names.append(filename + "/")
            else:
                names.append(filename)
        return self.format_directory_listing("SMB", resolved_path, names, language=language)
