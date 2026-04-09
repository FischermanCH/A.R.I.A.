from __future__ import annotations

import json
from pathlib import Path

from aria.core.capability_context import CapabilityContextStore


def test_capability_context_cache_refreshes_after_external_change(tmp_path: Path) -> None:
    target = tmp_path / "capability_context.json"
    target.write_text(
        json.dumps(
            {
                "demo": {
                    "capability": "search",
                    "connection_kind": "searxng",
                    "connection_ref": "web",
                    "path": "/updates",
                }
            }
        ),
        encoding="utf-8",
    )
    store = CapabilityContextStore(target)

    first = store.load_recent("demo")
    assert first["capability"] == "search"

    target.write_text(
        json.dumps(
            {
                "demo": {
                    "capability": "memory",
                    "connection_kind": "qdrant",
                    "connection_ref": "default",
                    "path": "/memories",
                }
            }
        ),
        encoding="utf-8",
    )

    second = store.load_recent("demo")
    assert second["capability"] == "memory"
    assert second["connection_kind"] == "qdrant"


def test_capability_context_load_recent_returns_copy(tmp_path: Path) -> None:
    store = CapabilityContextStore(tmp_path / "capability_context.json")
    store.remember_action(
        "demo",
        capability="search",
        connection_kind="searxng",
        connection_ref="web",
        path="/updates",
    )

    payload = store.load_recent("demo")
    payload["capability"] = "mutated"

    fresh = store.load_recent("demo")
    assert fresh["capability"] == "search"
