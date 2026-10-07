from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from aria.modules.website_runtime.runtime import normalize_website_rows
from aria.modules.website_ui.links import websites_config_path


@dataclass(frozen=True)
class ChatWebsitesOutcome:
    handled: bool
    assistant_text: str
    icon: str = "🔗"
    intent_label: str = "websites"


def _read_website_connections(base_dir: Path) -> dict[str, dict[str, object]]:
    config_path = Path(base_dir) / "config" / "config.yaml"
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    connections = raw.get("connections", {}) if isinstance(raw, dict) else {}
    websites = connections.get("website", {}) if isinstance(connections, dict) else {}
    if not isinstance(websites, dict):
        return {}
    return normalize_website_rows(websites)


async def handle_chat_websites_flow(
    *,
    clean_message: str,
    base_dir: Path,
) -> ChatWebsitesOutcome | None:
    del clean_message
    rows = _read_website_connections(base_dir)
    return ChatWebsitesOutcome(
        handled=True,
        assistant_text=(
            f"Deine beobachteten Webseiten liegen hier: `{websites_config_path()}`\n\n"
            f"Aktuell vorhanden: {len(rows)}"
        ),
    )
