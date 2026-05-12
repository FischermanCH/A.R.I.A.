from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re

import yaml

from aria.core.website_runtime import normalize_website_rows


@dataclass(frozen=True)
class ChatWebsitesOutcome:
    handled: bool
    assistant_text: str
    icon: str = "🔗"
    intent_label: str = "websites"


_CHAT_WEBSITES_LEXICON_PATH = Path(__file__).resolve().parents[1] / "lexicons" / "chat_websites.json"


def _load_pattern_group(name: str) -> tuple[re.Pattern[str], ...]:
    try:
        raw = json.loads(_CHAT_WEBSITES_LEXICON_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not load chat websites lexicon: {_CHAT_WEBSITES_LEXICON_PATH}") from exc
    patterns = raw.get("patterns", {}).get(name, []) if isinstance(raw, dict) else []
    if not isinstance(patterns, list):
        return ()
    return tuple(re.compile(str(pattern), re.IGNORECASE) for pattern in patterns if str(pattern).strip())


_OPEN_WEBSITES_PATTERNS = _load_pattern_group("open_websites")
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
    text = str(clean_message or "").strip()
    if not text:
        return None

    for pattern in _OPEN_WEBSITES_PATTERNS:
        if pattern.match(text):
            rows = _read_website_connections(base_dir)
            return ChatWebsitesOutcome(
                handled=True,
                assistant_text=(
                    f"Deine beobachteten Webseiten liegen hier: `/config/connections/websites`\n\n"
                    f"Aktuell vorhanden: {len(rows)}"
                ),
            )

    return None
