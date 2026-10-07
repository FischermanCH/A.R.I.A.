from __future__ import annotations

import importlib
from pathlib import Path

import aria.modules.connections_mutations.admin_helpers as canonical_admin_helpers
import aria.modules.connections_mutations.handlers as canonical_handlers
import aria.modules.connections_mutations.routes as canonical_routes
import aria.modules.connections_mutations.support_helpers as canonical_support_helpers


MODULE_PAIRS = (
    ("aria.modules.connections_mutations.admin_helpers", canonical_admin_helpers),
    ("aria.modules.connections_mutations.handlers", canonical_handlers),
    ("aria.modules.connections_mutations.routes", canonical_routes),
    ("aria.modules.connections_mutations.support_helpers", canonical_support_helpers),
)


def test_legacy_connection_mutation_modules_are_canonical_module_objects() -> None:
    for legacy_name, canonical_module in MODULE_PAIRS:
        assert importlib.import_module(legacy_name) is canonical_module


def test_moved_connection_mutation_implementations_keep_data_roots() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    aria_root = repository_root / "aria"

    assert canonical_handlers._CONNECTION_MUTATION_I18N.base_dir == aria_root / "i18n"
    assert canonical_support_helpers._CONNECTION_SUPPORT_I18N.base_dir == aria_root / "i18n"
    assert canonical_support_helpers.SAMPLE_CONNECTIONS_DIR == repository_root / "samples" / "connections"
    assert canonical_support_helpers.SAMPLE_GUARDRAILS_DIR == repository_root / "samples" / "security"


def test_product_code_imports_canonical_connection_mutation_owner() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    forbidden_markers = ("from aria.core", "import aria.core", "from aria.web", "import aria.web")
    offenders = [
        str(path.relative_to(repository_root))
        for path in sorted((repository_root / "aria").rglob("*.py"))
        if path != repository_root / "aria" / "modules" / "legacy_aliases.py"
        and any(marker in path.read_text(encoding="utf-8") for marker in forbidden_markers)
    ]

    assert offenders == []



def test_config_composition_imports_canonical_connection_mutation_owner() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    source = (repository_root / "aria" / "modules" / "config_ui" / "routes.py").read_text(encoding="utf-8")

    assert "from aria.modules.connections_mutations.admin_helpers import" in source
    assert "from aria.modules.connections_mutations.handlers import" in source
    assert "from aria.modules.connections_mutations.routes import" in source
    assert "from aria.modules.connections_mutations.support_helpers import" in source
