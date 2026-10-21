#!/usr/bin/env python3
"""Add the fictitious demo states the website feature screenshots need.

Runs after seed.py on the generated demo seed: offline LLM stub, a guardrail
profile attached to demo SSH connections, connection metadata, a mixed live
status cache and a prepared «update available» state. No real hosts or data.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
from typing import Any

import yaml


GUARDRAIL_REF = "demo-safe-maintenance"
FAILING = {"ssh:workshop", "smb:library", "rss:feed-07", "rss:feed-19", "mqtt:sensors"}


def _write_json(target: Path, payload: Any) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _seed_config(config_path: Path) -> dict[str, Any]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    config.setdefault("llm", {}).update({
        "model": "openai/demo-offline",
        "api_base": "http://llm-stub:8099/v1",
        "api_key": "demo-offline",
    })
    config.setdefault("security", {}).setdefault("guardrails", {})[GUARDRAIL_REF] = {
        "kind": "ssh_command",
        "title": "Sichere Wartung",
        "description": "Erlaubt nur lesende Diagnosebefehle und blockiert Neustarts, Löschbefehle und Root-Rechte.",
        "connection_kinds": ["ssh"],
        "allow_terms": ["uptime", "df -h", "docker ps", "systemctl status"],
        "deny_terms": ["sudo", "rm -rf", "reboot", "shutdown"],
        "allow_recipe_ids": [],
    }
    ssh = config.setdefault("connections", {}).setdefault("ssh", {})
    ssh["observatory"].update({
        "description": "Fiktive Sternwarte mit Wetterstation und Kamera-Archiv.",
        "aliases": ["sternwarte", "observatory-host"],
        "tags": ["linux", "kamera", "demo"],
        "guardrail_ref": GUARDRAIL_REF,
    })
    ssh["workshop"].update({"guardrail_ref": GUARDRAIL_REF})
    config_path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return config


def _seed_connection_health(data: Path, config: dict[str, Any], now: datetime) -> None:
    rows: dict[str, Any] = {}
    for index, (kind, refs) in enumerate(sorted(config.get("connections", {}).items())):
        for offset, ref in enumerate(sorted(refs)):
            key = f"{kind}:{ref}"
            checked = (now - timedelta(minutes=3 + index + offset)).isoformat()
            failing = key in FAILING
            rows[key] = {
                "last_checked_at": checked,
                "last_status": "error" if failing else "ok",
                "last_target": "",
                "last_message": "Demo: Zeitüberschreitung beim Verbindungsaufbau" if failing else "Demo: Verbindung erfolgreich geprüft",
                "last_success_at": (now - timedelta(days=2)).isoformat() if failing else checked,
            }
    _write_json(data / "runtime" / "connection_health.json", {"connections": rows})


def _seed_update_status(data: Path, root: Path, now: datetime) -> None:
    env = (root / "demo" / "generated" / ".env").read_text(encoding="utf-8")
    image = os.environ.get("ARIA_DEMO_IMAGE") or re.search(r"^ARIA_DEMO_IMAGE=(.+)$", env, re.M).group(1)
    match = re.search(r"(\d+\.\d+\.\d+)-alpha\.?(\d+)$", image.strip())
    if not match:
        raise SystemExit(f"Cannot derive demo version from image tag: {image}")
    current = f"{match.group(1)}-alpha{match.group(2)}"
    latest = f"{match.group(1)}-alpha{int(match.group(2)) + 1}"
    _write_json(data / "runtime" / "update_status.json", {
        "current_label": current,
        "latest_label": latest,
        "latest_tag": f"v{latest.replace('-alpha', '-alpha.')}",
        "update_available": True,
        "checked_at": now.isoformat(),
        "source": "github-tags",
        "release_notes": f"## {latest}\n\n- Demo: fiktive neue Version für die Update-Ansicht.",
        "release_notes_source": "",
        "recent_releases": [],
        "error": "",
    })


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    generated = args.root / "demo" / "generated"
    now = datetime.now(timezone.utc).replace(microsecond=0)
    config = _seed_config(generated / "config" / "config.yaml")
    _seed_connection_health(generated / "data", config, now)
    _seed_update_status(generated / "data", args.root, now)


if __name__ == "__main__":
    main()
