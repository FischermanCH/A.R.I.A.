from __future__ import annotations

import importlib
import sys

from aria.modules import MODULE_MANIFESTS
from aria.modules.authority_chain_audit.audit import authority_chain_boundary_map


def test_authority_chain_audit_legacy_import_is_identity_alias() -> None:
    legacy = importlib.import_module("aria.modules.authority_chain_audit.audit")
    canonical = importlib.import_module("aria.modules.authority_chain_audit.audit")

    assert legacy is canonical
    assert sys.modules["aria.modules.authority_chain_audit.audit"] is canonical


def test_authority_chain_audit_manifest_is_static_and_non_runtime() -> None:
    manifest = MODULE_MANIFESTS["authority_chain_audit"]

    assert manifest["status"] == "import_boundary_active"
    assert manifest["build_allowed"] is False
    assert manifest["runtime_access_allowed"] is False
    assert "runtime_dependency" in manifest["explicitly_excluded"]
    assert "source_authority_behavior" in manifest["explicitly_excluded"]


def test_authority_chain_audit_boundary_ids_are_preserved() -> None:
    assert tuple(authority_chain_boundary_map()) == (
        "connection_target_selection",
        "memory_retrieval_failure",
    )
