from __future__ import annotations

import importlib
from pathlib import Path

import aria.modules.inbound_event_storage.routes as canonical_inbound_routes
import aria.modules.runtime_bootstrap.manager as canonical_runtime_manager
import aria.modules.runtime_bootstrap.memory_helpers as canonical_memory_helpers
import aria.modules.runtime_bootstrap.support_helpers as canonical_support_helpers


MODULE_PAIRS = (
    ("aria.modules.runtime_bootstrap.manager", canonical_runtime_manager),
    ("aria.modules.runtime_bootstrap.support_helpers", canonical_support_helpers),
    ("aria.modules.runtime_bootstrap.memory_helpers", canonical_memory_helpers),
    ("aria.modules.inbound_event_storage.routes", canonical_inbound_routes),
)


def test_legacy_runtime_and_inbound_modules_are_canonical_module_objects() -> None:
    for legacy_name, canonical_module in MODULE_PAIRS:
        assert importlib.import_module(legacy_name) is canonical_module


def test_product_code_imports_canonical_runtime_and_inbound_owners() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    forbidden_markers = ("from aria.core", "import aria.core", "from aria.web", "import aria.web")
    offenders = [
        str(path.relative_to(repository_root))
        for path in sorted((repository_root / "aria").rglob("*.py"))
        if path != repository_root / "aria" / "modules" / "legacy_aliases.py"
        and any(marker in path.read_text(encoding="utf-8") for marker in forbidden_markers)
    ]

    assert offenders == []



def test_main_composition_imports_canonical_runtime_and_inbound_owners() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    main_source = (repository_root / "aria" / "main.py").read_text(encoding="utf-8")

    assert "import aria.modules.runtime_bootstrap.manager as runtime_manager" in main_source
    assert "from aria.modules.runtime_bootstrap.support_helpers import MainRuntimeSupportDeps" in main_source
    assert "from aria.modules.runtime_bootstrap.memory_helpers import MemoryRuntimeHelperDeps" in main_source
    assert "from aria.modules.inbound_event_storage.routes import InboundEventRouteDeps" in main_source
