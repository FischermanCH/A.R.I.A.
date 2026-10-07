"""SSH connection status target and probe adapter."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Mapping

from aria.modules.platform_primitives.i18n import I18NStore

_SSH_STATUS_I18N = I18NStore(Path(__file__).resolve().parents[2] / "i18n")


def _text(lang: str, key: str, default: str = "", **values: object) -> str:
    template = _SSH_STATUS_I18N.t(lang or "de", f"connection_runtime.{key}", default or key)
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


def ssh_target(row: Any) -> str:
    host = str(_value(row, "host", "")).strip() or "-"
    user = str(_value(row, "user", "")).strip() or "-"
    port = int(_value(row, "port", 22) or 22)
    return f"{user}@{host}:{port}"


def test_ssh_connection(
    ref: str,
    row: Any,
    *,
    timeout_override: int | None = None,
    base_dir: Path | None = None,
    page_probe: bool = False,
    lang: str = "de",
) -> str:
    del base_dir, page_probe
    host = str(_value(row, "host", "")).strip()
    user = str(_value(row, "user", "")).strip()
    port = int(_value(row, "port", 22) or 22)
    timeout_seconds = int(timeout_override or _value(row, "timeout_seconds", 20) or 20)
    strict_mode = str(_value(row, "strict_host_key_checking", "accept-new")).strip() or "accept-new"
    key_path_raw = str(_value(row, "key_path", "")).strip()
    if not host:
        raise ValueError(_text(lang, "message_474", "Host/IP is missing in the profile."))
    if not user:
        raise ValueError(_text(lang, "message_476", "User is missing in the profile."))
    if not key_path_raw:
        raise ValueError(_text(lang, "message_478", "No key path configured in the profile. Run key exchange or key generation first."))
    key_path = Path(key_path_raw).expanduser()
    if not key_path.exists():
        raise ValueError(_text(lang, "message_481", "Key file not found: {key_path}", key_path=key_path))
    target = f"{user}@{host}"
    proc = subprocess.run(
        [
            "ssh",
            "-p",
            str(max(1, port)),
            "-o",
            "BatchMode=yes",
            "-o",
            f"ConnectTimeout={max(5, timeout_seconds)}",
            "-o",
            f"StrictHostKeyChecking={strict_mode}",
            "-i",
            str(key_path),
            target,
            "bash -lc 'echo ARIA_SSH_OK'",
        ],
        capture_output=True,
        text=True,
        timeout=max(8, timeout_seconds + 5),
        check=False,
    )
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    if proc.returncode != 0:
        detail = err or out or f"Exit Code {proc.returncode}"
        if "host key verification failed" in detail.lower() or "no ed25519 host key is known" in detail.lower():
            detail = _text(lang, "message_509", "{detail}", detail=detail)
        raise ValueError(_text(lang, "message_508", "SSH test failed: {detail}", detail=detail))
    if "ARIA_SSH_OK" not in out:
        unclear = out or _text(lang, "message_510", "no expected response")
        raise ValueError(_text(lang, "message_511", "SSH test inconclusive: {unclear}", unclear=unclear))
    return _text(lang, "message_512", "SSH test successful for {target} (Ref: {ref})", target=target, ref=ref)
