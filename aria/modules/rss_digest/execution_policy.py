from __future__ import annotations

import json
from typing import Any

from aria.modules.rss_digest.options import build_rss_digest_options_note
from aria.modules.rss_digest.options import infer_rss_digest_options


RSS_GROUP_BUNDLE_PREFIX = "__rss_group_bundle__:"


def build_rss_group_bundle_note(group_name: str, refs: list[str]) -> str:
    payload = {
        "group": str(group_name or "").strip(),
        "refs": [str(item or "").strip() for item in list(refs or []) if str(item or "").strip()],
    }
    return RSS_GROUP_BUNDLE_PREFIX + json.dumps(payload, ensure_ascii=True, separators=(",", ":"))


def parse_rss_group_bundle_note(notes: list[str] | tuple[str, ...] | None) -> tuple[str, list[str]] | None:
    for item in list(notes or []):
        text = str(item or "").strip()
        if not text.startswith(RSS_GROUP_BUNDLE_PREFIX):
            continue
        try:
            payload = json.loads(text[len(RSS_GROUP_BUNDLE_PREFIX) :])
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        group_name = str(payload.get("group", "") or "").strip()
        refs = [str(ref or "").strip() for ref in list(payload.get("refs", []) or []) if str(ref or "").strip()]
        if group_name and refs:
            return group_name, refs
    return None


async def rss_digest_options_note_for_query(message: str, *, llm_client: Any | None, language: str = "") -> str:
    options = await infer_rss_digest_options(message, llm_client=llm_client, language=language)
    return build_rss_digest_options_note(options)


class RssActionSelectionPolicy:
    def __init__(self, *, settings: Any, llm_client: Any | None) -> None:
        _ = settings
        self._llm_client = llm_client

    @staticmethod
    def parse_group_bundle_note(notes: list[str] | tuple[str, ...] | None) -> tuple[str, list[str]] | None:
        return parse_rss_group_bundle_note(notes)

    async def digest_options_note_for_query(self, message: str, *, language: str = "") -> str:
        return await rss_digest_options_note_for_query(
            message,
            llm_client=self._llm_client,
            language=language,
        )
