from __future__ import annotations

import importlib
from pathlib import Path

import pytest


MODULE_PAIRS = (
    ("aria.modules.runtime_guardrails.guardrails", "aria.modules.runtime_guardrails.guardrails"),
    ("aria.modules.ssh_runtime.runtime", "aria.modules.ssh_runtime.runtime"),
    ("aria.modules.memory.personal", "aria.modules.memory.personal"),
    ("aria.modules.memory.assist", "aria.modules.memory.assist"),
    ("aria.modules.memory.admin_query", "aria.modules.memory.admin_query"),
    ("aria.modules.memory.recall_sources", "aria.modules.memory.recall_sources"),
    ("aria.modules.qdrant_gateway.client", "aria.modules.qdrant_gateway.client"),
)


def test_runtime_memory_kernel_legacy_modules_are_identity_aliases() -> None:
    for legacy_name, canonical_name in MODULE_PAIRS:
        assert importlib.import_module(legacy_name) is importlib.import_module(canonical_name)


def test_production_code_uses_canonical_runtime_memory_kernel_imports() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    forbidden_markers = ("from aria.core", "import aria.core", "from aria.web", "import aria.web")
    offenders = [
        str(path.relative_to(repository_root))
        for path in sorted((repository_root / "aria").rglob("*.py"))
        if path != repository_root / "aria" / "modules" / "legacy_aliases.py"
        and any(marker in path.read_text(encoding="utf-8") for marker in forbidden_markers)
    ]

    assert offenders == []



def test_qdrant_gateway_constructs_only_the_injected_client(monkeypatch: pytest.MonkeyPatch) -> None:
    gateway = importlib.import_module("aria.modules.qdrant_gateway.client")
    calls: list[dict[str, object]] = []

    class FakeClient:
        def __init__(self, **kwargs: object) -> None:
            calls.append(dict(kwargs))

    monkeypatch.setattr(gateway, "AsyncQdrantClient", FakeClient)

    client = gateway.create_async_qdrant_client(
        url="http://qdrant:6333",
        api_key="secret",
        timeout=7,
    )

    assert isinstance(client, FakeClient)
    assert calls == [{"url": "http://qdrant:6333", "api_key": "secret", "timeout": 7}]
