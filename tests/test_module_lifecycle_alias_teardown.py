from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

from aria.modules import MODULE_MANIFESTS, module_lifecycle_diagnostics, module_lifecycle_rows
from aria.modules.compatibility import LegacyModuleAliasFinder, install_legacy_module_aliases
from aria.modules.legacy_aliases import DURABLE_LEGACY_MODULE_ALIASES, LEGACY_MODULE_ALIASES


def test_lifecycle_projection_keeps_acceptance_flags_separate_from_activation() -> None:
    rows = module_lifecycle_rows()
    diagnostics = module_lifecycle_diagnostics()

    assert len(rows) == len(MODULE_MANIFESTS) == 106
    assert {row["id"] for row in rows} == set(MODULE_MANIFESTS)
    assert sum(row["activation_owner"] == "application_bootstrap" for row in rows) == 88
    assert sum(row["activation_owner"] == "none" for row in rows) == 18
    assert all(row["activation_configurable"] is False for row in rows)
    assert diagnostics == {
        "module_count": 106,
        "bootstrap_owned_count": 88,
        "contract_only_count": 18,
        "declarative_activation_count": 0,
        "unclassified_lifecycle_count": 0,
        "build_allowed_count": 0,
        "runtime_access_allowed_count": 0,
        "legacy_alias_count": 2,
        "acceptance_flags_are_activation_controls": False,
    }


def test_lifecycle_projection_respects_explicit_registry_without_activating_it() -> None:
    manifests = {
        "demo": {
            "lifecycle": "declarative_runtime",
            "build_allowed": True,
            "runtime_access_allowed": True,
        }
    }

    assert module_lifecycle_rows(manifests) == (
        {
            "id": "demo",
            "lifecycle": "declarative_runtime",
            "activation_owner": "module_registry",
            "activation_configurable": True,
            "build_allowed": True,
            "runtime_access_allowed": True,
        },
    )
    assert module_lifecycle_diagnostics(manifests)["declarative_activation_count"] == 1


def test_lifecycle_classes_are_explicit_and_match_python_ownership() -> None:
    assert {manifest["lifecycle"] for manifest in MODULE_MANIFESTS.values()} == {
        "bootstrap_static",
        "contract_only",
    }
    assert all(
        manifest["lifecycle"] == ("bootstrap_static" if manifest["python"] else "contract_only")
        for manifest in MODULE_MANIFESTS.values()
    )


def test_legacy_alias_inventory_is_exact_and_centralized() -> None:
    assert len(LEGACY_MODULE_ALIASES) == 2
    assert len(set(LEGACY_MODULE_ALIASES.values())) == 2
    assert set(LEGACY_MODULE_ALIASES) == {
        "aria.skills.base",
        "aria.skills.memory",
    }
    assert DURABLE_LEGACY_MODULE_ALIASES == frozenset(LEGACY_MODULE_ALIASES)
    assert all(target.startswith("aria.modules.") for target in LEGACY_MODULE_ALIASES.values())


def test_legacy_alias_finder_installation_is_idempotent_and_lazy() -> None:
    loaded_targets_before = set(LEGACY_MODULE_ALIASES.values()) & set(sys.modules)

    first = install_legacy_module_aliases()
    second = install_legacy_module_aliases()

    assert first is second
    assert sum(isinstance(finder, LegacyModuleAliasFinder) for finder in sys.meta_path) == 1
    assert set(LEGACY_MODULE_ALIASES.values()) & set(sys.modules) == loaded_targets_before


@pytest.mark.parametrize(("legacy_name", "canonical_name"), sorted(LEGACY_MODULE_ALIASES.items()))
def test_every_legacy_module_name_resolves_to_exact_canonical_identity(
    legacy_name: str,
    canonical_name: str,
) -> None:
    assert importlib.import_module(legacy_name) is importlib.import_module(canonical_name)


@pytest.mark.parametrize("unknown_name", ["aria.core.not_registered", "aria.web.not_registered"])
def test_unknown_legacy_module_names_still_fail(unknown_name: str) -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(unknown_name)


def test_private_legacy_trees_have_no_python_compatibility_files() -> None:
    root = Path(__file__).resolve().parents[1]

    assert sorted((root / "aria" / "core").rglob("*.py")) == []
    assert sorted((root / "aria" / "web").rglob("*.py")) == []


@pytest.mark.parametrize("removed_name", ["aria.core.config", "aria.core.pipeline", "aria.web.stats_routes"])
def test_removed_private_legacy_names_fail(removed_name: str) -> None:
    sys.modules.pop(removed_name, None)
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(removed_name)
