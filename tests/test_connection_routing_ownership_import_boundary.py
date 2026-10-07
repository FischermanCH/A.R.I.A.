from __future__ import annotations

import importlib
from pathlib import Path

import aria.modules.connection_routing.pipeline_bridge as legacy_pipeline_bridge
import aria.modules.connection_routing.bounded_llm as legacy_bounded_llm
import aria.modules.connection_routing.admin as legacy_admin
import aria.modules.routing_hint_generation.hints as legacy_hints
import aria.modules.connection_routing.index as legacy_index
import aria.modules.connection_routing.resolver as legacy_resolver
from aria.modules.connection_routing import admin as canonical_admin
from aria.modules.connection_routing import bounded_llm as canonical_bounded_llm
from aria.modules.connection_routing import index as canonical_index
from aria.modules.connection_routing import pipeline_bridge as canonical_pipeline_bridge
from aria.modules.connection_routing import resolver as canonical_resolver
from aria.modules.routing_hint_generation import hints as canonical_hints


def test_connection_routing_legacy_modules_are_identity_aliases() -> None:
    assert legacy_index is canonical_index
    assert legacy_resolver is canonical_resolver
    assert legacy_bounded_llm is canonical_bounded_llm
    assert legacy_admin is canonical_admin
    assert legacy_pipeline_bridge is canonical_pipeline_bridge
    assert legacy_hints is canonical_hints


def test_connection_routing_legacy_imports_resolve_to_canonical_modules() -> None:
    pairs = (
        ("aria.modules.connection_routing.index", canonical_index),
        ("aria.modules.connection_routing.resolver", canonical_resolver),
        ("aria.modules.connection_routing.bounded_llm", canonical_bounded_llm),
        ("aria.modules.connection_routing.admin", canonical_admin),
        ("aria.modules.connection_routing.pipeline_bridge", canonical_pipeline_bridge),
        ("aria.modules.routing_hint_generation.hints", canonical_hints),
    )

    for legacy_name, canonical_module in pairs:
        assert importlib.import_module(legacy_name) is canonical_module


def test_production_code_uses_canonical_connection_routing_imports() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    forbidden_markers = ("from aria.core", "import aria.core", "from aria.web", "import aria.web")
    offenders = [
        str(path.relative_to(repository_root))
        for path in sorted((repository_root / "aria").rglob("*.py"))
        if path != repository_root / "aria" / "modules" / "legacy_aliases.py"
        and any(marker in path.read_text(encoding="utf-8") for marker in forbidden_markers)
    ]

    assert offenders == []
