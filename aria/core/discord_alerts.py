from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request as URLRequest, urlopen

from aria.core.runtime_endpoint import _host_port_url


ALERT_CATEGORY_FLAGS = {
    "skill_errors": "alert_skill_errors",
    "safe_fix": "alert_safe_fix",
    "connection_changes": "alert_connection_changes",
    "system_events": "alert_system_events",
}


def _iter_matching_discord_profiles(settings: Any, category: str) -> list[tuple[str, Any]]:
    flag_name = ALERT_CATEGORY_FLAGS.get(str(category).strip().lower(), "")
    if not flag_name:
        return []
    rows: list[tuple[str, Any]] = []
    connections = getattr(getattr(settings, "connections", object()), "discord", {})
    if not isinstance(connections, dict):
        return rows
    for ref in sorted(connections.keys()):
        connection = connections.get(ref)
        if connection is None:
            continue
        webhook = str(getattr(connection, "webhook_url", "")).strip()
        if not webhook:
            continue
        if not bool(getattr(connection, flag_name, False)):
            continue
        rows.append((ref, connection))
    return rows


def _render_alert_message(*, category: str, title: str, lines: list[str], level: str = "info") -> str:
    now = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    category_text = str(category or "event").strip().upper()
    level_text = str(level or "info").strip().upper()
    body = "\n".join(f"- {line}" for line in lines if str(line).strip())
    payload = [
        "```text",
        "A.R.I.A // event bus",
        f"Category: {category_text}",
        f"Level: {level_text}",
        f"Time: {now}",
        f"Title: {title}",
    ]
    if body:
        payload.extend(["Details:", body])
    payload.append("```")
    return "\n".join(payload)[:1900]


def _post_webhook_message(webhook_url: str, content: str, timeout_seconds: int) -> None:
    payload = json.dumps({"content": content}).encode("utf-8")
    req = URLRequest(
        webhook_url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "ARIA/1.0",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=max(5, timeout_seconds)) as resp:  # noqa: S310
            _ = resp.read()
            status_code = int(getattr(resp, "status", 200) or 200)
    except (HTTPError, URLError):
        return
    except Exception:
        return
    if status_code >= 400:
        return


def send_discord_alerts(
    settings: Any,
    *,
    category: str,
    title: str,
    lines: list[str] | None = None,
    level: str = "info",
) -> int:
    rows = _iter_matching_discord_profiles(settings, category)
    if not rows:
        return 0
    content = _render_alert_message(
        category=category,
        title=str(title).strip() or "ARIA Event",
        lines=list(lines or []),
        level=level,
    )
    sent = 0
    for _ref, connection in rows:
        webhook = str(getattr(connection, "webhook_url", "")).strip()
        timeout_seconds = int(getattr(connection, "timeout_seconds", 10) or 10)
        if not webhook:
            continue
        _post_webhook_message(webhook, content, timeout_seconds)
        sent += 1
    return sent


def runtime_host_line(settings: Any) -> str:
    aria_cfg = getattr(settings, "aria", object())
    public_url = str(getattr(aria_cfg, "public_url", "") or "").strip()
    if public_url:
        return f"Host: {public_url.rstrip('/')}"

    host = str(getattr(aria_cfg, "host", "") or "").strip()
    port = int(getattr(aria_cfg, "port", 8800) or 8800)
    if host and host not in {"0.0.0.0", "::"}:
        return f"Host: {_host_port_url('http', host, port)}"

    return "Host: Public URL nicht konfiguriert (setze ARIA_PUBLIC_URL)"
