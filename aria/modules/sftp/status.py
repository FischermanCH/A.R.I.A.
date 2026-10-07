"""SFTP connection status target and probe adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from aria.modules.platform_primitives.i18n import I18NStore

_SFTP_STATUS_I18N = I18NStore(Path(__file__).resolve().parents[2] / "i18n")


def _text(lang: str, key: str, default: str = "", **values: object) -> str:
    template = _SFTP_STATUS_I18N.t(lang or "de", f"connection_runtime.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template


def _value(row: Any, key: str, default: Any = "") -> Any:
    if isinstance(row, Mapping):
        return row.get(key, default)
    return getattr(row, key, default)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _resolve_local_runtime_path(base_dir: Path | None, value: str) -> Path:
    root = base_dir or _project_root()
    path = Path(str(value or "").strip()).expanduser()
    if not path.is_absolute():
        path = (root / path).resolve()
    return path


def sftp_target(row: Any) -> str:
    host = str(_value(row, "host", "")).strip() or "-"
    user = str(_value(row, "user", "")).strip() or "-"
    port = int(_value(row, "port", 22) or 22)
    return f"{user}@{host}:{port}"


def test_sftp_connection(
    ref: str,
    row: Any,
    *,
    timeout_override: int | None = None,
    base_dir: Path | None = None,
    page_probe: bool = False,
    lang: str = "de",
) -> str:
    del page_probe
    host = str(_value(row, "host", "")).strip()
    user = str(_value(row, "user", "")).strip()
    port = int(_value(row, "port", 22) or 22)
    password = str(_value(row, "password", "")).strip()
    key_path = str(_value(row, "key_path", "")).strip()
    timeout_seconds = int(timeout_override or _value(row, "timeout_seconds", 10) or 10)
    root_path = str(_value(row, "root_path", "")).strip() or "."
    if not host:
        raise ValueError(_text(lang, "message_572", "Host/IP is missing in the profile."))
    if not user:
        raise ValueError(_text(lang, "message_574", "User is missing in the profile."))
    if not password and not key_path:
        raise ValueError(_text(lang, "message_576", "No SFTP authentication configured in the profile. Please set a password or key path."))
    try:
        import paramiko  # type: ignore[import-not-found]
    except Exception as exc:
        raise ValueError(_text(lang, "message_580", "Python module 'paramiko' is missing. Please install it and restart ARIA.")) from exc
    connect_kwargs: dict[str, Any] = {
        "hostname": host,
        "port": max(1, port),
        "username": user,
        "timeout": max(5, timeout_seconds),
        "allow_agent": False,
        "look_for_keys": False,
    }
    if key_path:
        key_file = _resolve_local_runtime_path(base_dir, key_path)
        if not key_file.exists():
            raise ValueError(_text(lang, "message_592", "SFTP key not found: {key_path}", key_path=key_path))
        connect_kwargs["key_filename"] = str(key_file)
    else:
        connect_kwargs["password"] = password
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(**connect_kwargs)
        sftp = client.open_sftp()
        try:
            sftp.listdir(root_path)
        finally:
            try:
                sftp.close()
            except Exception:
                pass
    except Exception as exc:
        raise ValueError(_text(lang, "message_609", "SFTP test failed: {exc}", exc=exc)) from exc
    finally:
        try:
            client.close()
        except Exception:
            pass
    return _text(lang, "message_615", "SFTP test successful for {user}@{host}:{port} (Ref: {ref})", user=user, host=host, port=port, ref=ref)
