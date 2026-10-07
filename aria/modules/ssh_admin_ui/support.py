"""SSH administration support functions."""

from __future__ import annotations

import os
import shlex
import socket
import subprocess
from contextlib import suppress
from pathlib import Path
from typing import Any, Callable

from aria.modules.ssh_admin_ui.reader import read_ssh_connections


def ssh_keys_dir(base_dir: Path) -> Path:
    path = (base_dir / "data" / "ssh_keys").resolve()
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, 0o700)
    except OSError:
        pass
    return path


def ensure_ssh_keypair(base_dir: Path, ref: str, overwrite: bool = False) -> Path:
    key_dir = ssh_keys_dir(base_dir)
    key_path = key_dir / f"{ref}_ed25519"
    pub_path = key_path.with_suffix(".pub")
    key_exists = key_path.exists() or pub_path.exists()
    if key_exists and not overwrite:
        return key_path
    if key_exists and overwrite:
        with suppress(OSError):
            key_path.unlink()
        with suppress(OSError):
            pub_path.unlink()
    comment = f"aria-{ref}@{socket.gethostname()}"
    subprocess.run(
        ["ssh-keygen", "-t", "ed25519", "-N", "", "-f", str(key_path), "-C", comment],
        check=True,
        capture_output=True,
        text=True,
    )
    try:
        os.chmod(key_path, 0o600)
    except OSError:
        pass
    return key_path


def read_ssh_connection_profiles(
    read_raw_config: Callable[[], dict[str, Any]],
    sanitize_connection_name: Callable[[str | None], str],
    read_connection_metadata: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    return read_ssh_connections(
        read_raw_config=read_raw_config,
        sanitize_connection_name=sanitize_connection_name,
        read_connection_metadata=read_connection_metadata,
    )


def friendly_ssh_setup_error(lang: str, exc: Exception) -> str:
    is_de = str(lang or "de").strip().lower().startswith("de")
    if isinstance(exc, FileNotFoundError) and str(getattr(exc, "filename", "")).strip() == "ssh-keygen":
        if is_de:
            return (
                "ssh-keygen wurde auf diesem Host nicht gefunden. "
                "Bitte OpenSSH-Client/ssh-keygen installieren oder einen vorhandenen privaten Key manuell eintragen."
            )
        return (
            "ssh-keygen was not found on this host. "
            "Please install the OpenSSH client/ssh-keygen or enter an existing private key manually."
        )
    if isinstance(exc, ValueError):
        detail = str(exc).strip()
        if detail:
            return detail
    return "SSH-Key konnte nicht erzeugt werden." if is_de else "SSH key could not be generated."


def derive_matching_sftp_ref(ssh_ref: str) -> str:
    clean_ref = str(ssh_ref or "").strip()
    if not clean_ref:
        return "sftp-profile"
    for suffix in ("-ssh", "_ssh"):
        if clean_ref.endswith(suffix):
            return f"{clean_ref[:-len(suffix)]}{suffix[0]}sftp"
    return f"{clean_ref}-sftp"


def perform_ssh_key_exchange(
    base_dir: Path,
    *,
    ref: str,
    host: str,
    port: int,
    profile_user: str,
    login_user: str,
    login_password: str,
    connection_support_text: Callable[..., str],
) -> tuple[str, Path]:
    if not login_password.strip():
        raise ValueError("Passwort fehlt.")
    clean_host = str(host).strip()
    if not clean_host:
        raise ValueError("Host/IP fehlt im Connection-Profil.")
    clean_user = str(login_user or profile_user).strip()
    if not clean_user:
        raise ValueError("SSH-User fehlt (im Profil oder Formular).")

    key_path = ensure_ssh_keypair(base_dir, ref, overwrite=False)
    pub_path = key_path.with_suffix(".pub")
    if not pub_path.exists():
        raise ValueError("Public Key nicht gefunden.")
    pub_key = pub_path.read_text(encoding="utf-8").strip()
    if not pub_key:
        raise ValueError("Public Key ist leer.")

    try:
        import paramiko  # type: ignore[import-not-found]
    except Exception as exc:
        raise ValueError("Python-Modul 'paramiko' fehlt. Bitte installieren und ARIA neu starten.") from exc

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            hostname=clean_host,
            port=max(1, int(port)),
            username=clean_user,
            password=login_password,
            timeout=15,
            allow_agent=False,
            look_for_keys=False,
        )
        key_q = shlex.quote(pub_key)
        remote_cmd = (
            "umask 077; "
            "mkdir -p ~/.ssh; "
            "touch ~/.ssh/authorized_keys; "
            "chmod 700 ~/.ssh; "
            "chmod 600 ~/.ssh/authorized_keys; "
            f"grep -qxF {key_q} ~/.ssh/authorized_keys || echo {key_q} >> ~/.ssh/authorized_keys"
        )
        _, stdout, stderr = client.exec_command(remote_cmd, timeout=15)
        exit_code = stdout.channel.recv_exit_status()
        err = (stderr.read() or b"").decode("utf-8", errors="replace").strip()
        if exit_code != 0:
            raise ValueError(err or connection_support_text("authorized_keys_write_failed", "Remote error while writing authorized_keys."))
    finally:
        with suppress(Exception):
            client.close()
    return clean_user, key_path
