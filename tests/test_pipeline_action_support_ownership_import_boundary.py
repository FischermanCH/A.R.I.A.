from __future__ import annotations

import importlib
from pathlib import Path

from aria.modules.action_runtime_debug import routing as canonical_routing_debug
from aria.modules.pipeline_pending_action_contracts import contracts as canonical_pending


def test_pipeline_action_support_canonical_modules_are_importable() -> None:
    assert importlib.import_module("aria.modules.pipeline_pending_action_contracts.contracts") is canonical_pending
    assert importlib.import_module("aria.modules.action_runtime_debug.routing") is canonical_routing_debug


def test_production_code_uses_canonical_pipeline_action_support_imports() -> None:
    blocked = (
        "aria.core.pipeline_action_flow_helpers",
        "aria.core.pipeline_routing_debug_helpers",
    )
    offenders: list[str] = []

    for path in sorted(Path("aria").rglob("*.py")):
        if path == Path("aria/modules/legacy_aliases.py"):
            continue
        source = path.read_text(encoding="utf-8")
        for legacy_name in blocked:
            if legacy_name in source:
                offenders.append(f"{path}:{legacy_name}")

    assert offenders == []
