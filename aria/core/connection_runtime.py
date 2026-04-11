from __future__ import annotations

import contextlib
import hashlib
import json
import imaplib
import socket
import smtplib
import ssl
import subprocess
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import Request as URLRequest, urlopen

from aria.core.connection_health import get_connection_health
from aria.core.connection_health import record_connection_health
from aria.core.connection_catalog import (
    connection_icon_name,
    connection_is_alpha,
    connection_kind_label,
    connection_kind_labels,
    normalize_connection_kind,
    ordered_connection_kinds,
)
from aria.core.config import resolve_searxng_base_url


CONNECTION_KIND_LABELS: dict[str, str] = connection_kind_labels()
_RSS_HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36 ARIA/1.0"
    ),
    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*;q=0.8",
}
_RSS_TEST_READ_BYTES = 256 * 1024
_RSS_ROOT_HINTS = ("<rss", "<feed", "<rdf:rdf")


def _msg(lang: str, de: str, en: str) -> str:
    return de if str(lang or "de").strip().lower().startswith("de") else en


def _searxng_rate_limit_hint(lang: str) -> str:
    return _msg(
        lang,
        "SearXNG-Test fehlgeschlagen: HTTP 429 Too Many Requests. Wahrscheinlich ist der SearXNG-Limiter aktiv. Fuer den internen ARIA-Stack `SEARXNG_LIMITER=false` setzen und den Stack neu deployen.",
        "SearXNG test failed: HTTP 429 Too Many Requests. The SearXNG limiter is likely still active. Set `SEARXNG_LIMITER=false` for the internal ARIA stack and redeploy the stack.",
    )


def _searxng_request_headers(base_url: str, *, user_agent: str = "ARIA/1.0") -> dict[str, str]:
    headers = {
        "User-Agent": user_agent,
        "Accept": "application/json",
    }
    host = str(urlparse(str(base_url or "").strip()).hostname or "").strip().lower()
    if host in {"searxng", "aria-searxng", "localhost", "127.0.0.1", "::1"}:
        headers["X-Forwarded-For"] = "127.0.0.1"
        headers["X-Real-IP"] = "127.0.0.1"
    return headers


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _value(row: Any, key: str, default: Any = "") -> Any:
    if isinstance(row, Mapping):
        return row.get(key, default)
    return getattr(row, key, default)


def _xml_name(tag: str) -> str:
    raw = str(tag or "").strip()
    if "}" in raw:
        raw = raw.split("}", 1)[1]
    if ":" in raw:
        raw = raw.split(":", 1)[1]
    return raw.lower()


def _extract_rss_preview_titles(xml_text: str, *, max_items: int = 3) -> tuple[str, list[str]]:
    feed_title = ""
    titles: list[str] = []
    root = ET.fromstring(str(xml_text or "").strip())
    root_name = _xml_name(root.tag)

    if root_name == "rss":
        channel = next((child for child in root if _xml_name(child.tag) == "channel"), None)
        if channel is not None:
            for child in channel:
                name = _xml_name(child.tag)
                if name == "title" and not feed_title:
                    feed_title = str(child.text or "").strip()
                    continue
                if name != "item":
                    continue
                title = next(
                    (str(node.text or "").strip() for node in child if _xml_name(node.tag) == "title" and str(node.text or "").strip()),
                    "",
                )
                if title:
                    titles.append(title)
                if len(titles) >= max_items:
                    break
    elif root_name == "feed":
        for child in root:
            name = _xml_name(child.tag)
            if name == "title" and not feed_title:
                feed_title = str(child.text or "").strip()
                continue
            if name != "entry":
                continue
            title = next(
                (str(node.text or "").strip() for node in child if _xml_name(node.tag) == "title" and str(node.text or "").strip()),
                "",
            )
            if title:
                titles.append(title)
            if len(titles) >= max_items:
                break
    elif root_name == "rdf":
        for child in root:
            name = _xml_name(child.tag)
            if name == "channel" and not feed_title:
                feed_title = next(
                    (str(node.text or "").strip() for node in child if _xml_name(node.tag) == "title" and str(node.text or "").strip()),
                    "",
                )
                continue
            if name != "item":
                continue
            title = next(
                (str(node.text or "").strip() for node in child if _xml_name(node.tag) == "title" and str(node.text or "").strip()),
                "",
            )
            if title:
                titles.append(title)
            if len(titles) >= max_items:
                break

    return feed_title, titles


def _resolve_local_runtime_path(base_dir: Path | None, value: str) -> Path:
    root = base_dir or _project_root()
    path = Path(str(value or "").strip()).expanduser()
    if not path.is_absolute():
        path = (root / path).resolve()
    return path


def friendly_discord_test_error_message(exc: Exception, *, lang: str = "de") -> str:
    raw = str(exc).strip() or _msg(lang, "Unbekannter Discord-Fehler.", "Unknown Discord error.")
    if isinstance(exc, HTTPError):
        code = int(getattr(exc, "code", 0) or 0)
        if code == 403:
            return _msg(
                lang,
                "Discord-Test fehlgeschlagen: Discord hat den Webhook mit 403 (Forbidden) abgelehnt. Bitte auf Discord prüfen, ob der Webhook noch existiert, zur richtigen Server-/Channel-Integration gehört und die URL exakt vollständig eingefügt wurde. In Discord: Servereinstellungen > Integrationen > Webhooks.",
                "Discord test failed: Discord rejected the webhook with 403 (Forbidden). Please verify in Discord that the webhook still exists, belongs to the correct server/channel integration, and that the URL was pasted completely. In Discord: Server Settings > Integrations > Webhooks.",
            )
        if code == 404:
            return _msg(
                lang,
                "Discord-Test fehlgeschlagen: Discord meldet 404 (Not Found). Der Webhook wurde auf Discord wahrscheinlich gelöscht oder die URL ist nicht korrekt.",
                "Discord test failed: Discord returned 404 (Not Found). The webhook was probably deleted in Discord or the URL is incorrect.",
            )
        if code == 401:
            return _msg(
                lang,
                "Discord-Test fehlgeschlagen: Discord meldet 401 (Unauthorized). Die Webhook-URL oder der Token-Teil scheint nicht mehr gültig zu sein.",
                "Discord test failed: Discord returned 401 (Unauthorized). The webhook URL or token part no longer seems to be valid.",
            )
        return _msg(lang, f"Discord-Test fehlgeschlagen: Discord meldet HTTP {code}.", f"Discord test failed: Discord returned HTTP {code}.")
    if "HTTP Error 403" in raw or ("403" in raw and "Forbidden" in raw):
        return _msg(
            lang,
            "Discord-Test fehlgeschlagen: Discord hat den Webhook mit 403 (Forbidden) abgelehnt. Bitte auf Discord prüfen, ob der Webhook noch existiert, zur richtigen Server-/Channel-Integration gehört und die URL exakt vollständig eingefügt wurde. In Discord: Servereinstellungen > Integrationen > Webhooks.",
            "Discord test failed: Discord rejected the webhook with 403 (Forbidden). Please verify in Discord that the webhook still exists, belongs to the correct server/channel integration, and that the URL was pasted completely. In Discord: Server Settings > Integrations > Webhooks.",
        )
    if "HTTP Error 404" in raw or ("404" in raw and "Not Found" in raw):
        return _msg(
            lang,
            "Discord-Test fehlgeschlagen: Discord meldet 404 (Not Found). Der Webhook wurde auf Discord wahrscheinlich gelöscht oder die URL ist nicht korrekt.",
            "Discord test failed: Discord returned 404 (Not Found). The webhook was probably deleted in Discord or the URL is incorrect.",
        )
    if "HTTP Error 401" in raw or ("401" in raw and "Unauthorized" in raw):
        return _msg(
            lang,
            "Discord-Test fehlgeschlagen: Discord meldet 401 (Unauthorized). Die Webhook-URL oder der Token-Teil scheint nicht mehr gültig zu sein.",
            "Discord test failed: Discord returned 401 (Unauthorized). The webhook URL or token part no longer seems to be valid.",
        )
    return _msg(lang, f"Discord-Test fehlgeschlagen: {raw}", f"Discord test failed: {raw}")


def _page_probe_timeout(row: Any, default_timeout: int) -> int:
    timeout = int(_value(row, "timeout_seconds", default_timeout) or default_timeout)
    return min(max(timeout, 5), 6)


def _ssh_target(row: Any) -> str:
    host = str(_value(row, "host", "")).strip() or "-"
    user = str(_value(row, "user", "")).strip() or "-"
    port = int(_value(row, "port", 22) or 22)
    return f"{user}@{host}:{port}"


def _discord_target(_row: Any) -> str:
    return "Discord Webhook"


def _sftp_target(row: Any) -> str:
    host = str(_value(row, "host", "")).strip() or "-"
    user = str(_value(row, "user", "")).strip() or "-"
    port = int(_value(row, "port", 22) or 22)
    return f"{user}@{host}:{port}"


def _smb_target(row: Any) -> str:
    host = str(_value(row, "host", "")).strip() or "-"
    share = str(_value(row, "share", "")).strip() or "-"
    user = str(_value(row, "user", "")).strip() or "-"
    return f"{user}@{host}/{share}"


def _webhook_target(row: Any) -> str:
    method = str(_value(row, "method", "POST")).strip().upper() or "POST"
    return f"{method} Webhook"


def _email_target(row: Any) -> str:
    host = str(_value(row, "smtp_host", "")).strip() or "-"
    user = str(_value(row, "user", "")).strip() or "-"
    port = int(_value(row, "port", 587) or 587)
    return f"{user}@{host}:{port}"


def _imap_target(row: Any) -> str:
    host = str(_value(row, "host", "")).strip() or "-"
    user = str(_value(row, "user", "")).strip() or "-"
    port = int(_value(row, "port", 993) or 993)
    mailbox = str(_value(row, "mailbox", "INBOX")).strip() or "INBOX"
    return f"{user}@{host}:{port}/{mailbox}"


def _http_api_target(row: Any) -> str:
    return str(_value(row, "base_url", "")).strip() or "HTTP API"


def _rss_target(row: Any) -> str:
    return str(_value(row, "feed_url", "")).strip() or "RSS Feed"


def _searxng_target(row: Any) -> str:
    return resolve_searxng_base_url(str(_value(row, "base_url", "")).strip())


def _mqtt_target(row: Any) -> str:
    host = str(_value(row, "host", "")).strip() or "-"
    user = str(_value(row, "user", "")).strip() or "-"
    port = int(_value(row, "port", 1883) or 1883)
    return f"{user}@{host}:{port}"


def _test_ssh_connection(ref: str, row: Any, *, timeout_override: int | None = None, base_dir: Path | None = None, page_probe: bool = False, lang: str = "de") -> str:
    del base_dir, page_probe
    host = str(_value(row, "host", "")).strip()
    user = str(_value(row, "user", "")).strip()
    port = int(_value(row, "port", 22) or 22)
    timeout_seconds = int(timeout_override or _value(row, "timeout_seconds", 20) or 20)
    strict_mode = str(_value(row, "strict_host_key_checking", "accept-new")).strip() or "accept-new"
    key_path_raw = str(_value(row, "key_path", "")).strip()
    if not host:
        raise ValueError(_msg(lang, "Host/IP fehlt im Profil.", "Host/IP is missing in the profile."))
    if not user:
        raise ValueError(_msg(lang, "User fehlt im Profil.", "User is missing in the profile."))
    if not key_path_raw:
        raise ValueError(_msg(lang, "Kein Key-Pfad im Profil. Erst Key-Exchange oder Key-Generierung durchführen.", "No key path configured in the profile. Run key exchange or key generation first."))
    key_path = Path(key_path_raw).expanduser()
    if not key_path.exists():
        raise ValueError(_msg(lang, f"Key-Datei nicht gefunden: {key_path}", f"Key file not found: {key_path}"))
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
        raise ValueError(_msg(lang, f"SSH-Test fehlgeschlagen: {detail}", f"SSH test failed: {detail}"))
    if "ARIA_SSH_OK" not in out:
        unclear = out or _msg(lang, "keine erwartete Antwort", "no expected response")
        raise ValueError(_msg(lang, f"SSH-Test unklar: {unclear}", f"SSH test inconclusive: {unclear}"))
    return _msg(lang, f"SSH-Test erfolgreich für {target} (Ref: {ref})", f"SSH test successful for {target} (Ref: {ref})")


def _test_discord_connection(ref: str, row: Any, *, timeout_override: int | None = None, base_dir: Path | None = None, page_probe: bool = False, lang: str = "de") -> str:
    del base_dir
    webhook = str(_value(row, "webhook_url", "")).strip()
    timeout_seconds = int(timeout_override or _value(row, "timeout_seconds", 10) or 10)
    send_test_messages = bool(_value(row, "send_test_messages", True)) and not page_probe
    if not webhook:
        raise ValueError(_msg(lang, "Keine Discord-Webhook-URL hinterlegt.", "No Discord webhook URL configured."))
    try:
        if send_test_messages:
            from datetime import datetime

            timestamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
            content = (
                "```text\n"
                "A.R.I.A // Discord uplink online\n"
                f"Ref: {ref}\n"
                "Status: GREEN\n"
                "Mode: webhook handshake established\n"
                f"Time: {timestamp}\n"
                "Checksum: OK\n"
                "```"
            )
            payload = json.dumps({"content": content}).encode("utf-8")
            req = URLRequest(
                webhook,
                data=payload,
                headers={"Content-Type": "application/json", "User-Agent": "ARIA/1.0"},
                method="POST",
            )
        else:
            req = URLRequest(webhook, headers={"User-Agent": "ARIA/1.0"}, method="GET")
        with urlopen(req, timeout=max(5, timeout_seconds)) as resp:  # noqa: S310
            _ = resp.read()
            status_code = int(getattr(resp, "status", 200) or 200)
    except HTTPError as exc:
        raise ValueError(friendly_discord_test_error_message(exc, lang=lang)) from exc
    except URLError as exc:
        raise ValueError(friendly_discord_test_error_message(exc, lang=lang)) from exc
    except Exception as exc:  # noqa: BLE001
        raise ValueError(friendly_discord_test_error_message(exc, lang=lang)) from exc
    if status_code >= 400:
        raise ValueError(friendly_discord_test_error_message(HTTPError(webhook, status_code, "", hdrs=None, fp=None), lang=lang))
    if send_test_messages:
        return _msg(lang, f"Discord-Test erfolgreich für {ref}", f"Discord test successful for {ref}")
    return _msg(lang, f"Discord-Test erfolgreich für {ref} (stille Prüfung ohne Testnachricht)", f"Discord test successful for {ref} (silent check without test message)")


def _test_sftp_connection(ref: str, row: Any, *, timeout_override: int | None = None, base_dir: Path | None = None, page_probe: bool = False, lang: str = "de") -> str:
    del page_probe
    host = str(_value(row, "host", "")).strip()
    user = str(_value(row, "user", "")).strip()
    port = int(_value(row, "port", 22) or 22)
    password = str(_value(row, "password", "")).strip()
    key_path = str(_value(row, "key_path", "")).strip()
    timeout_seconds = int(timeout_override or _value(row, "timeout_seconds", 10) or 10)
    root_path = str(_value(row, "root_path", "")).strip() or "."
    if not host:
        raise ValueError(_msg(lang, "Host/IP fehlt im Profil.", "Host/IP is missing in the profile."))
    if not user:
        raise ValueError(_msg(lang, "User fehlt im Profil.", "User is missing in the profile."))
    if not password and not key_path:
        raise ValueError(_msg(lang, "Keine SFTP-Authentisierung im Profil. Bitte Passwort oder Key-Pfad setzen.", "No SFTP authentication configured in the profile. Please set a password or key path."))
    try:
        import paramiko  # type: ignore[import-not-found]
    except Exception as exc:
        raise ValueError(_msg(lang, "Python-Modul 'paramiko' fehlt. Bitte installieren und ARIA neu starten.", "Python module 'paramiko' is missing. Please install it and restart ARIA.")) from exc
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
            raise ValueError(_msg(lang, f"SFTP-Key nicht gefunden: {key_path}", f"SFTP key not found: {key_path}"))
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
    except Exception as exc:  # noqa: BLE001
        raise ValueError(_msg(lang, f"SFTP-Test fehlgeschlagen: {exc}", f"SFTP test failed: {exc}")) from exc
    finally:
        try:
            client.close()
        except Exception:
            pass
    return _msg(lang, f"SFTP-Test erfolgreich für {user}@{host}:{port} (Ref: {ref})", f"SFTP test successful for {user}@{host}:{port} (Ref: {ref})")


def _test_smb_connection(ref: str, row: Any, *, timeout_override: int | None = None, base_dir: Path | None = None, page_probe: bool = False, lang: str = "de") -> str:
    del base_dir, page_probe
    host = str(_value(row, "host", "")).strip()
    share = str(_value(row, "share", "")).strip()
    user = str(_value(row, "user", "")).strip()
    password = str(_value(row, "password", "")).strip()
    port = int(_value(row, "port", 445) or 445)
    timeout_seconds = int(timeout_override or _value(row, "timeout_seconds", 10) or 10)
    root_path = str(_value(row, "root_path", "")).strip() or "/"
    if not host:
        raise ValueError(_msg(lang, "Host/IP fehlt im Profil.", "Host/IP is missing in the profile."))
    if not share:
        raise ValueError(_msg(lang, "Share fehlt im Profil.", "Share is missing in the profile."))
    if not user:
        raise ValueError(_msg(lang, "User fehlt im Profil.", "User is missing in the profile."))
    if not password:
        raise ValueError(_msg(lang, "Kein Passwort im Profil.", "No password configured in the profile."))
    try:
        from smb.SMBConnection import SMBConnection  # type: ignore[import-not-found]
    except Exception as exc:
        raise ValueError(_msg(lang, "Python-Modul 'pysmb' fehlt. Bitte installieren und ARIA neu starten.", "Python module 'pysmb' is missing. Please install it and restart ARIA.")) from exc
    conn = SMBConnection(user, password, "aria", host, use_ntlm_v2=True, is_direct_tcp=True)
    try:
        ok = conn.connect(host, max(1, port), timeout=max(5, timeout_seconds))
        if not ok:
            raise ValueError(_msg(lang, "SMB-Verbindung konnte nicht aufgebaut werden.", "SMB connection could not be established."))
        conn.listPath(share, root_path)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(_msg(lang, f"SMB-Test fehlgeschlagen: {exc}", f"SMB test failed: {exc}")) from exc
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return _msg(lang, f"SMB-Test erfolgreich für {user}@{host}/{share} (Ref: {ref})", f"SMB test successful for {user}@{host}/{share} (Ref: {ref})")


def _test_webhook_connection(ref: str, row: Any, *, timeout_override: int | None = None, base_dir: Path | None = None, page_probe: bool = False, lang: str = "de") -> str:
    del base_dir, page_probe
    url = str(_value(row, "url", "")).strip()
    timeout_seconds = int(timeout_override or _value(row, "timeout_seconds", 10) or 10)
    method = str(_value(row, "method", "POST")).strip().upper() or "POST"
    content_type = str(_value(row, "content_type", "application/json")).strip() or "application/json"
    if not url:
        raise ValueError(_msg(lang, "Webhook-URL fehlt.", "Webhook URL is missing."))
    payload = json.dumps({"content": f"ARIA Webhook-Test ({ref})"}).encode("utf-8")
    req = URLRequest(url, data=payload if method != "GET" else None, headers={"Content-Type": content_type}, method=method)
    try:
        with urlopen(req, timeout=max(5, timeout_seconds)) as resp:  # noqa: S310
            _ = resp.read()
            status_code = int(getattr(resp, "status", 200) or 200)
    except URLError as exc:
        raise ValueError(_msg(lang, f"Webhook-Test fehlgeschlagen: {exc}", f"Webhook test failed: {exc}")) from exc
    except Exception as exc:  # noqa: BLE001
        raise ValueError(_msg(lang, f"Webhook-Test fehlgeschlagen: {exc}", f"Webhook test failed: {exc}")) from exc
    if status_code >= 400:
        raise ValueError(_msg(lang, f"Webhook-Test fehlgeschlagen: HTTP {status_code}", f"Webhook test failed: HTTP {status_code}"))
    return _msg(lang, f"Webhook-Test erfolgreich für {ref}", f"Webhook test successful for {ref}")


def _test_email_connection(ref: str, row: Any, *, timeout_override: int | None = None, base_dir: Path | None = None, page_probe: bool = False, lang: str = "de") -> str:
    del base_dir, page_probe
    host = str(_value(row, "smtp_host", "")).strip()
    user = str(_value(row, "user", "")).strip()
    password = str(_value(row, "password", "")).strip()
    port = int(_value(row, "port", 587) or 587)
    timeout_seconds = int(timeout_override or _value(row, "timeout_seconds", 10) or 10)
    use_ssl = bool(_value(row, "use_ssl", False))
    starttls = bool(_value(row, "starttls", True))
    if not host:
        raise ValueError(_msg(lang, "SMTP-Host fehlt.", "SMTP host is missing."))
    if not user:
        raise ValueError(_msg(lang, "SMTP-User fehlt.", "SMTP user is missing."))
    if not password:
        raise ValueError(_msg(lang, "SMTP-Passwort fehlt.", "SMTP password is missing."))
    try:
        if use_ssl:
            server = smtplib.SMTP_SSL(host, max(1, port), timeout=max(5, timeout_seconds), context=ssl.create_default_context())
        else:
            server = smtplib.SMTP(host, max(1, port), timeout=max(5, timeout_seconds))
        with server:
            server.ehlo()
            if starttls and not use_ssl:
                server.starttls(context=ssl.create_default_context())
                server.ehlo()
            server.login(user, password)
            server.noop()
    except Exception as exc:  # noqa: BLE001
        raise ValueError(_msg(lang, f"SMTP-Test fehlgeschlagen: {exc}", f"SMTP test failed: {exc}")) from exc
    return _msg(lang, f"SMTP-Test erfolgreich für {user}@{host}:{port} (Ref: {ref})", f"SMTP test successful for {user}@{host}:{port} (Ref: {ref})")


def _test_imap_connection(ref: str, row: Any, *, timeout_override: int | None = None, base_dir: Path | None = None, page_probe: bool = False, lang: str = "de") -> str:
    del base_dir, page_probe
    host = str(_value(row, "host", "")).strip()
    user = str(_value(row, "user", "")).strip()
    password = str(_value(row, "password", "")).strip()
    mailbox = str(_value(row, "mailbox", "INBOX")).strip() or "INBOX"
    port = int(_value(row, "port", 993) or 993)
    timeout_seconds = int(timeout_override or _value(row, "timeout_seconds", 10) or 10)
    use_ssl = bool(_value(row, "use_ssl", True))
    if not host:
        raise ValueError(_msg(lang, "IMAP-Host fehlt.", "IMAP host is missing."))
    if not user:
        raise ValueError(_msg(lang, "IMAP-User fehlt.", "IMAP user is missing."))
    if not password:
        raise ValueError(_msg(lang, "IMAP-Passwort fehlt.", "IMAP password is missing."))

    previous_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(max(5, timeout_seconds))
    try:
        if use_ssl:
            client = imaplib.IMAP4_SSL(host, max(1, port))
        else:
            client = imaplib.IMAP4(host, max(1, port))
        try:
            status, _ = client.login(user, password)
            if status != "OK":
                raise ValueError(_msg(lang, "IMAP-Login fehlgeschlagen.", "IMAP login failed."))
            status, _ = client.select(mailbox, readonly=True)
            if status != "OK":
                raise ValueError(_msg(lang, f"IMAP-Mailbox nicht erreichbar: {mailbox}", f"IMAP mailbox not reachable: {mailbox}"))
        finally:
            with contextlib.suppress(Exception):
                client.logout()
    except Exception as exc:  # noqa: BLE001
        raise ValueError(_msg(lang, f"IMAP-Test fehlgeschlagen: {exc}", f"IMAP test failed: {exc}")) from exc
    finally:
        socket.setdefaulttimeout(previous_timeout)
    return _msg(lang, f"IMAP-Test erfolgreich für {user}@{host}:{port}/{mailbox} (Ref: {ref})", f"IMAP test successful for {user}@{host}:{port}/{mailbox} (Ref: {ref})")


def _test_http_api_connection(ref: str, row: Any, *, timeout_override: int | None = None, base_dir: Path | None = None, page_probe: bool = False, lang: str = "de") -> str:
    del base_dir, page_probe
    base_url = str(_value(row, "base_url", "")).strip()
    health_path = str(_value(row, "health_path", "/")).strip() or "/"
    auth_token = str(_value(row, "auth_token", "")).strip()
    timeout_seconds = int(timeout_override or _value(row, "timeout_seconds", 10) or 10)
    method = str(_value(row, "method", "GET")).strip().upper() or "GET"
    if not base_url:
        raise ValueError(_msg(lang, "Base URL fehlt.", "Base URL is missing."))
    target_url = urljoin(base_url.rstrip("/") + "/", health_path.lstrip("/"))
    headers: dict[str, str] = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    req = URLRequest(target_url, headers=headers, method=method)
    try:
        with urlopen(req, timeout=max(5, timeout_seconds)) as resp:  # noqa: S310
            _ = resp.read()
            status_code = int(getattr(resp, "status", 200) or 200)
    except URLError as exc:
        raise ValueError(_msg(lang, f"HTTP-API-Test fehlgeschlagen: {exc}", f"HTTP API test failed: {exc}")) from exc
    except Exception as exc:  # noqa: BLE001
        raise ValueError(_msg(lang, f"HTTP-API-Test fehlgeschlagen: {exc}", f"HTTP API test failed: {exc}")) from exc
    if status_code >= 400:
        raise ValueError(_msg(lang, f"HTTP-API-Test fehlgeschlagen: HTTP {status_code}", f"HTTP API test failed: HTTP {status_code}"))
    return _msg(lang, f"HTTP-API-Test erfolgreich für {ref}", f"HTTP API test successful for {ref}")


def _test_rss_connection(ref: str, row: Any, *, timeout_override: int | None = None, base_dir: Path | None = None, page_probe: bool = False, lang: str = "de") -> str:
    del base_dir, page_probe
    feed_url = str(_value(row, "feed_url", "")).strip()
    timeout_seconds = int(timeout_override or _value(row, "timeout_seconds", 10) or 10)
    if not feed_url:
        raise ValueError(_msg(lang, "Feed-URL fehlt.", "Feed URL is missing."))
    req = URLRequest(feed_url, headers=_RSS_HTTP_HEADERS, method="GET")
    try:
        with urlopen(req, timeout=max(5, timeout_seconds)) as resp:  # noqa: S310
            payload = resp.read(_RSS_TEST_READ_BYTES)
            status_code = int(getattr(resp, "status", 200) or 200)
    except URLError as exc:
        raise ValueError(_msg(lang, f"RSS-Test fehlgeschlagen: {exc}", f"RSS test failed: {exc}")) from exc
    except Exception as exc:  # noqa: BLE001
        raise ValueError(_msg(lang, f"RSS-Test fehlgeschlagen: {exc}", f"RSS test failed: {exc}")) from exc
    if status_code >= 400:
        raise ValueError(_msg(lang, f"RSS-Test fehlgeschlagen: HTTP {status_code}", f"RSS test failed: HTTP {status_code}"))
    text = payload.decode("utf-8", errors="replace").strip()
    lower_text = text.lower()
    if text.startswith("{") or text.startswith("["):
        raise ValueError(
            _msg(
                lang,
                "RSS-Test fehlgeschlagen: Diese URL liefert JSON statt RSS/Atom-XML. Bitte als HTTP-API-Connection anlegen.",
                "RSS test failed: This URL returns JSON instead of RSS/Atom XML. Please create it as an HTTP API connection.",
            )
        )
    if not any(marker in lower_text for marker in _RSS_ROOT_HINTS):
        try:
            ET.fromstring(text)
        except Exception as exc:  # noqa: BLE001
            raise ValueError(_msg(lang, f"RSS-Test fehlgeschlagen: ungültiges XML ({exc})", f"RSS test failed: invalid XML ({exc})")) from exc
    try:
        feed_title, preview_titles = _extract_rss_preview_titles(text, max_items=3)
    except Exception:
        feed_title, preview_titles = "", []
    if preview_titles:
        joined_titles = " | ".join(preview_titles)
        if feed_title:
            return _msg(
                lang,
                f"Feed geladen: {feed_title} · Neueste Artikel: {joined_titles}",
                f"Feed loaded: {feed_title} · Latest articles: {joined_titles}",
            )
        return _msg(
            lang,
            f"Neueste Artikel: {joined_titles}",
            f"Latest articles: {joined_titles}",
        )
    return _msg(lang, f"RSS-Test erfolgreich für {ref}", f"RSS test successful for {ref}")


def _test_searxng_connection(ref: str, row: Any, *, timeout_override: int | None = None, base_dir: Path | None = None, page_probe: bool = False, lang: str = "de") -> str:
    del base_dir, page_probe
    base_url = resolve_searxng_base_url(str(_value(row, "base_url", "")).strip())
    timeout_seconds = int(timeout_override or _value(row, "timeout_seconds", 10) or 10)
    language = str(_value(row, "language", "")).strip()
    safe_search = int(_value(row, "safe_search", 1) or 1)
    params = {
        "q": "aria health check",
        "format": "json",
        "pageno": 1,
        "safesearch": max(0, min(safe_search, 2)),
    }
    if language:
        params["language"] = language
    target_url = f"{base_url.rstrip('/')}/search?{urlencode(params)}"
    req = URLRequest(
        target_url,
        headers=_searxng_request_headers(base_url),
        method="GET",
    )
    try:
        with urlopen(req, timeout=max(5, timeout_seconds)) as resp:  # noqa: S310
            payload = resp.read()
            status_code = int(getattr(resp, "status", 200) or 200)
    except HTTPError as exc:
        if int(getattr(exc, "code", 0) or 0) == 429:
            raise ValueError(_searxng_rate_limit_hint(lang)) from exc
        raise ValueError(_msg(lang, f"SearXNG-Test fehlgeschlagen: {exc}", f"SearXNG test failed: {exc}")) from exc
    except URLError as exc:
        raise ValueError(_msg(lang, f"SearXNG-Test fehlgeschlagen: {exc}", f"SearXNG test failed: {exc}")) from exc
    except Exception as exc:  # noqa: BLE001
        raise ValueError(_msg(lang, f"SearXNG-Test fehlgeschlagen: {exc}", f"SearXNG test failed: {exc}")) from exc
    if status_code >= 400:
        raise ValueError(_msg(lang, f"SearXNG-Test fehlgeschlagen: HTTP {status_code}", f"SearXNG test failed: HTTP {status_code}"))
    try:
        data = json.loads(payload.decode("utf-8", errors="replace"))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(_msg(lang, f"SearXNG-Test lieferte kein JSON: {exc}", f"SearXNG test did not return JSON: {exc}")) from exc
    if not isinstance(data, dict) or "results" not in data:
        raise ValueError(_msg(lang, "SearXNG-Test lieferte kein erwartetes Search-JSON.", "SearXNG test did not return the expected search JSON."))
    return _msg(lang, f"SearXNG-Test erfolgreich für {ref}", f"SearXNG test successful for {ref}")


def probe_searxng_stack_service(*, lang: str = "de", timeout_seconds: int = 4) -> dict[str, Any]:
    base_url = resolve_searxng_base_url("")
    params = {
        "q": "aria stack health",
        "format": "json",
        "pageno": 1,
        "safesearch": 1,
    }
    target_url = f"{base_url.rstrip('/')}/search?{urlencode(params)}"
    req = URLRequest(
        target_url,
        headers=_searxng_request_headers(base_url),
        method="GET",
    )
    try:
        with urlopen(req, timeout=max(3, timeout_seconds)) as resp:  # noqa: S310
            payload = resp.read()
            status_code = int(getattr(resp, "status", 200) or 200)
    except HTTPError as exc:
        status_code = int(getattr(exc, "code", 0) or 0)
        if status_code == 429:
            return {
                "available": True,
                "status": "warn",
                "target": base_url,
                "message": _searxng_rate_limit_hint(lang),
            }
        if status_code == 403:
            return {
                "available": True,
                "status": "warn",
                "target": base_url,
                "message": _msg(
                    lang,
                    "SearXNG-Stackdienst antwortet, lehnt die JSON-Probe aber mit HTTP 403 ab. Das bedeutet meist: `format=json` ist im SearXNG-Setup nicht freigeschaltet oder eine Access-/Limiter-Regel blockiert die Anfrage. Bitte `search.formats` inkl. `json` und die Limiter-/Zugriffsregeln pruefen.",
                    "SearXNG stack service responds, but rejects the JSON probe with HTTP 403. This usually means `format=json` is not enabled in the SearXNG setup or an access/limiter rule blocks the request. Please check `search.formats` includes `json` and review limiter/access rules.",
                ),
            }
        return {
            "available": False,
            "status": "error",
            "target": base_url,
            "message": _msg(lang, f"SearXNG-Stackdienst nicht erreichbar: {exc}", f"SearXNG stack service is not reachable: {exc}"),
        }
    except URLError as exc:
        return {
            "available": False,
            "status": "error",
            "target": base_url,
            "message": _msg(lang, f"SearXNG-Stackdienst nicht erreichbar: {exc}", f"SearXNG stack service is not reachable: {exc}"),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "available": False,
            "status": "error",
            "target": base_url,
            "message": _msg(lang, f"SearXNG-Stackdienst nicht erreichbar: {exc}", f"SearXNG stack service is not reachable: {exc}"),
        }
    if status_code >= 400:
        return {
            "available": False,
            "status": "error",
            "target": base_url,
            "message": _msg(lang, f"SearXNG-Stackdienst antwortete mit HTTP {status_code}.", f"SearXNG stack service returned HTTP {status_code}."),
        }
    try:
        data = json.loads(payload.decode("utf-8", errors="replace"))
    except Exception as exc:  # noqa: BLE001
        return {
            "available": False,
            "status": "error",
            "target": base_url,
            "message": _msg(lang, f"SearXNG-Stackdienst liefert kein JSON: {exc}", f"SearXNG stack service did not return JSON: {exc}"),
        }
    if not isinstance(data, dict) or "results" not in data:
        return {
            "available": False,
            "status": "error",
            "target": base_url,
            "message": _msg(lang, "SearXNG-Stackdienst liefert noch keine erwartete JSON-Suche.", "SearXNG stack service does not return the expected JSON search yet."),
        }
    return {
        "available": True,
        "status": "ok",
        "target": base_url,
        "message": _msg(lang, "SearXNG-Stackdienst ist erreichbar.", "SearXNG stack service is reachable."),
    }


def _cached_rss_connection_status(ref: str, row: Any, *, lang: str = "de") -> dict[str, str] | None:
    poll_interval = int(_value(row, "poll_interval_minutes", 60) or 60)
    poll_interval = max(1, min(poll_interval, 10080))
    poll_interval_seconds = poll_interval * 60
    cached = get_connection_health(f"rss:{ref}")
    last_checked_at = str(cached.get("last_checked_at", "")).strip()
    if not last_checked_at:
        return None
    try:
        checked_ts = datetime.fromisoformat(last_checked_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    age_seconds = max(0.0, datetime.now(timezone.utc).timestamp() - checked_ts.timestamp())
    if age_seconds > poll_interval_seconds + _rss_poll_phase_offset_seconds(ref, row, poll_interval_seconds):
        return None
    status = str(cached.get("last_status", "")).strip().lower()
    if status not in {"ok", "error"}:
        return None
    title = str(_value(row, "title", "")).strip()
    tags_raw = _value(row, "tags", [])
    tags = [str(item).strip() for item in tags_raw if str(item).strip()] if isinstance(tags_raw, list) else []
    return {
        "kind_key": "rss",
        "kind": connection_kind_label("rss"),
        "kind_icon": connection_icon_name("rss"),
        "kind_alpha": connection_is_alpha("rss"),
        "ref": ref,
        "display_name": title or ref,
        "title": title,
        "group_name": str(_value(row, "group_name", "")).strip(),
        "tags": tags,
        "target": _rss_target(row),
        "status": status,
        "message": str(cached.get("last_message", "")).strip()
        or _msg(lang, "RSS-Status aus Cache.", "RSS status from cache."),
        "last_success_at": str(cached.get("last_success_at", "")).strip(),
    }


def _rss_poll_phase_offset_seconds(ref: str, row: Any, poll_interval_seconds: int) -> int:
    if poll_interval_seconds <= 1:
        return 0
    seed = f"{str(ref or '').strip()}|{str(_value(row, 'feed_url', '')).strip()}"
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % poll_interval_seconds


def _last_rss_connection_status(ref: str, row: Any, *, lang: str = "de") -> dict[str, str]:
    cached = get_connection_health(f"rss:{ref}")
    status = str(cached.get("last_status", "")).strip().lower()
    if status not in {"ok", "error"}:
        status = "error"
    title = str(_value(row, "title", "")).strip()
    tags_raw = _value(row, "tags", [])
    tags = [str(item).strip() for item in tags_raw if str(item).strip()] if isinstance(tags_raw, list) else []
    return {
        "kind_key": "rss",
        "kind": connection_kind_label("rss"),
        "kind_icon": connection_icon_name("rss"),
        "kind_alpha": connection_is_alpha("rss"),
        "ref": ref,
        "display_name": title or ref,
        "title": title,
        "group_name": str(_value(row, "group_name", "")).strip(),
        "tags": tags,
        "target": _rss_target(row),
        "status": status,
        "message": str(cached.get("last_message", "")).strip()
        or _msg(
            lang,
            "Noch kein RSS-Status im Cache. Nutze 'Jetzt pingen' für eine Live-Prüfung.",
            "No RSS status cached yet. Use 'Ping now' for a live check.",
        ),
        "last_success_at": str(cached.get("last_success_at", "")).strip(),
    }


def _cached_connection_status_row(kind: str, ref: str, row: Any, *, lang: str = "de") -> dict[str, Any]:
    normalized_kind = normalize_connection_kind(kind)
    if normalized_kind == "rss":
        return _last_rss_connection_status(ref, row, lang=lang)

    target = _CONNECTION_TARGETS[normalized_kind](row)
    title = str(_value(row, "title", "")).strip()
    tags_raw = _value(row, "tags", [])
    tags = [str(item).strip() for item in tags_raw if str(item).strip()] if isinstance(tags_raw, list) else []
    cached = get_connection_health(f"{normalized_kind}:{ref}")
    status = str(cached.get("last_status", "")).strip().lower()
    if status not in {"ok", "error"}:
        status = "warn"
    message = str(cached.get("last_message", "")).strip()
    if not message:
        message = _msg(
            lang,
            "Noch kein Status im Cache. Nutze den Test-Button fuer eine Live-Pruefung.",
            "No cached status yet. Use the test button for a live check.",
        )
    return {
        "kind_key": normalized_kind,
        "kind": connection_kind_label(normalized_kind),
        "kind_icon": connection_icon_name(normalized_kind),
        "kind_alpha": connection_is_alpha(normalized_kind),
        "ref": ref,
        "display_name": title or ref,
        "title": title,
        "group_name": str(_value(row, "group_name", "")).strip() if normalized_kind == "rss" else "",
        "tags": tags,
        "target": target,
        "status": status,
        "message": message,
        "last_success_at": str(cached.get("last_success_at", "")).strip(),
    }


def _test_mqtt_connection(ref: str, row: Any, *, timeout_override: int | None = None, base_dir: Path | None = None, page_probe: bool = False, lang: str = "de") -> str:
    del base_dir, page_probe
    host = str(_value(row, "host", "")).strip()
    user = str(_value(row, "user", "")).strip()
    password = str(_value(row, "password", "")).strip()
    port = int(_value(row, "port", 1883) or 1883)
    timeout_seconds = int(timeout_override or _value(row, "timeout_seconds", 10) or 10)
    if not host:
        raise ValueError(_msg(lang, "Host/IP fehlt im Profil.", "Host/IP is missing in the profile."))
    if not user:
        raise ValueError(_msg(lang, "MQTT-User fehlt im Profil.", "MQTT user is missing in the profile."))
    if not password:
        raise ValueError(_msg(lang, "MQTT-Passwort fehlt.", "MQTT password is missing."))
    try:
        import paho.mqtt.client as mqtt  # type: ignore[import-not-found]
    except Exception as exc:
        raise ValueError(_msg(lang, "Python-Modul 'paho-mqtt' fehlt. Bitte installieren und ARIA neu starten.", "Python module 'paho-mqtt' is missing. Please install it and restart ARIA.")) from exc
    result: dict[str, Any] = {"rc": None}
    client = mqtt.Client()
    client.username_pw_set(user, password)
    if bool(_value(row, "use_tls", False)):
        client.tls_set()

    def _on_connect(_client: Any, _userdata: Any, _flags: Any, rc: int, _properties: Any = None) -> None:
        result["rc"] = rc
        try:
            _client.disconnect()
        except Exception:
            pass

    client.on_connect = _on_connect
    try:
        client.connect(host, max(1, port), keepalive=max(5, timeout_seconds))
        client.loop_start()
        deadline = time.time() + max(5, timeout_seconds)
        while result["rc"] is None and time.time() < deadline:
            time.sleep(0.1)
        client.loop_stop()
        if result["rc"] is None:
            raise ValueError(_msg(lang, "MQTT-Timeout beim Verbindungsaufbau.", "MQTT timeout during connection setup."))
        if int(result["rc"]) != 0:
            raise ValueError(_msg(lang, f"MQTT-Connect fehlgeschlagen (rc={result['rc']}).", f"MQTT connect failed (rc={result['rc']})."))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(_msg(lang, f"MQTT-Test fehlgeschlagen: {exc}", f"MQTT test failed: {exc}")) from exc
    finally:
        try:
            client.disconnect()
        except Exception:
            pass
    return _msg(lang, f"MQTT-Test erfolgreich für {user}@{host}:{port} (Ref: {ref})", f"MQTT test successful for {user}@{host}:{port} (Ref: {ref})")


_CONNECTION_TESTERS = {
    "ssh": _test_ssh_connection,
    "discord": _test_discord_connection,
    "sftp": _test_sftp_connection,
    "smb": _test_smb_connection,
    "webhook": _test_webhook_connection,
    "email": _test_email_connection,
    "imap": _test_imap_connection,
    "http_api": _test_http_api_connection,
    "rss": _test_rss_connection,
    "searxng": _test_searxng_connection,
    "mqtt": _test_mqtt_connection,
}

_CONNECTION_TARGETS = {
    "ssh": _ssh_target,
    "discord": _discord_target,
    "sftp": _sftp_target,
    "smb": _smb_target,
    "webhook": _webhook_target,
    "email": _email_target,
    "imap": _imap_target,
    "http_api": _http_api_target,
    "rss": _rss_target,
    "searxng": _searxng_target,
    "mqtt": _mqtt_target,
}


def test_connection(kind: str, ref: str, row: Any, *, page_probe: bool = False, base_dir: Path | None = None, lang: str = "de") -> str:
    normalized_kind = str(kind or "").strip().lower().replace("-", "_")
    tester = _CONNECTION_TESTERS.get(normalized_kind)
    if tester is None:
        raise ValueError(_msg(lang, f"Unbekannter Connection-Typ: {kind}", f"Unknown connection type: {kind}"))
    timeout_override = None
    if page_probe:
        default_timeout = 20 if normalized_kind == "ssh" else 10
        timeout_override = _page_probe_timeout(row, default_timeout)
    return tester(ref, row, timeout_override=timeout_override, base_dir=base_dir, page_probe=page_probe, lang=lang)


def build_connection_status_row(
    kind: str,
    ref: str,
    row: Any,
    *,
    page_probe: bool = False,
    cached_only: bool = False,
    base_dir: Path | None = None,
    lang: str = "de",
) -> dict[str, str]:
    normalized_kind = normalize_connection_kind(kind)
    if normalized_kind not in _CONNECTION_TESTERS:
        raise ValueError(_msg(lang, f"Unbekannter Connection-Typ: {kind}", f"Unknown connection type: {kind}"))
    if cached_only:
        return _cached_connection_status_row(normalized_kind, ref, row, lang=lang)
    if normalized_kind == "rss" and page_probe:
        cached_row = _cached_rss_connection_status(ref, row, lang=lang)
        if cached_row is not None:
            return cached_row
        return _last_rss_connection_status(ref, row, lang=lang)
    target = _CONNECTION_TARGETS[normalized_kind](row)
    title = str(_value(row, "title", "")).strip()
    tags_raw = _value(row, "tags", [])
    tags = [str(item).strip() for item in tags_raw if str(item).strip()] if isinstance(tags_raw, list) else []
    try:
        message = test_connection(normalized_kind, ref, row, page_probe=page_probe, base_dir=base_dir, lang=lang)
        health_entry = record_connection_health(f"{normalized_kind}:{ref}", status="ok", target=target, message=message)
        status = "ok"
    except Exception as exc:  # noqa: BLE001
        message = str(exc)
        health_entry = record_connection_health(f"{normalized_kind}:{ref}", status="error", target=target, message=message)
        status = "error"
    return {
        "kind_key": normalized_kind,
        "kind": connection_kind_label(normalized_kind),
        "kind_icon": connection_icon_name(normalized_kind),
        "kind_alpha": connection_is_alpha(normalized_kind),
        "ref": ref,
        "display_name": title or ref,
        "title": title,
        "group_name": str(_value(row, "group_name", "")).strip() if normalized_kind == "rss" else "",
        "tags": tags,
        "target": target,
        "status": status,
        "message": message,
        "last_success_at": str(health_entry.get("last_success_at", "")).strip(),
    }


def build_connection_status_rows(
    kind: str,
    rows_by_ref: Mapping[str, Any],
    *,
    selected_ref: str = "",
    page_probe: bool = False,
    cached_only: bool = False,
    base_dir: Path | None = None,
    lang: str = "de",
) -> list[dict[str, Any]]:
    normalized_kind = normalize_connection_kind(kind)
    rows: list[dict[str, Any]] = []
    for ref in sorted(rows_by_ref.keys()):
        row = rows_by_ref.get(ref)
        if row is None:
            continue
        rows.append(
            {
                **build_connection_status_row(
                    normalized_kind,
                    ref,
                    row,
                    page_probe=page_probe,
                    cached_only=cached_only,
                    base_dir=base_dir,
                    lang=lang,
                ),
                "selected": ref == selected_ref,
            }
        )
    return rows


def build_settings_connection_status_rows(
    settings: Any,
    *,
    page_probe: bool = True,
    cached_only_threshold: int | None = None,
    base_dir: Path | None = None,
    lang: str = "de",
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    connections = getattr(settings, "connections", None)
    if connections is None:
        return rows
    for kind in ordered_connection_kinds():
        items = getattr(connections, kind, {})
        if not isinstance(items, Mapping):
            try:
                items = dict(items)
            except Exception:
                items = {}
        refs = sorted(items.keys())
        use_cached_only = bool(page_probe) and cached_only_threshold is not None and len(refs) >= max(1, int(cached_only_threshold))
        for ref in refs:
            row = items.get(ref)
            if row is None:
                continue
            rows.append(
                build_connection_status_row(
                    kind,
                    ref,
                    row,
                    page_probe=page_probe and not use_cached_only,
                    cached_only=use_cached_only,
                    base_dir=base_dir,
                    lang=lang,
                )
            )
    return rows
