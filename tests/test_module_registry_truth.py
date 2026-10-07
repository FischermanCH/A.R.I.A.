from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path

from aria.modules import MODULE_MANIFESTS, external_boundary_ids
from aria.modules.boundary_contract import classify_external_boundary
from aria.modules.read_model import (
    module_external_boundary_diagnostics,
    module_python_ownership_diagnostics,
    module_reverse_dependencies,
    module_status_rows,
)
from aria.modules.validation import validate_module_repository_claims, validate_module_registry


ROOT = Path(__file__).resolve().parents[1]
LEGACY_FUNNEL_RING = {
    "turn_arbitration",
    "meta_catalog_routing",
    "module_dispatch",
    "action_planner",
    "agentic_context_runtime",
    "context_surfaces",
    "context_loader_runtime",
    "turn_decision",
    "command_operation_contract",
    "connection_inventory_contract",
}


def test_reverse_dependencies_are_derived_from_depends_on_only() -> None:
    reverse = module_reverse_dependencies()

    assert all("used_by" not in manifest for manifest in MODULE_MANIFESTS.values())
    for owner_id in MODULE_MANIFESTS:
        expected = tuple(
            sorted(
                module_id
                for module_id, manifest in MODULE_MANIFESTS.items()
                if owner_id in manifest.get("depends_on", ())
            )
        )
        assert reverse[owner_id] == expected


def test_status_rows_expose_derived_consumers_and_separate_claim_types() -> None:
    rows = {row["id"]: row for row in module_status_rows()}

    assert rows["action_contracts"]["used_by"] == module_reverse_dependencies()["action_contracts"]
    assert rows["action_contracts"]["python"] == tuple(
        MODULE_MANIFESTS["action_contracts"]["python"]
    )
    assert rows["action_contracts"]["integration_points"] == tuple(
        MODULE_MANIFESTS["action_contracts"].get("integration_points", ())
    )


def test_python_claims_are_existing_unique_python_file_owners() -> None:
    diagnostics = module_python_ownership_diagnostics()

    assert diagnostics["python_file_claim_count"] > 0
    assert diagnostics["integration_point_count"] > 0
    assert diagnostics["duplicate_python_owner_count"] == 0
    assert diagnostics["invalid_python_claim_count"] == 0
    assert diagnostics["invalid_integration_point_count"] == 0
    assert validate_module_repository_claims(ROOT, MODULE_MANIFESTS) == ()

    owners: dict[str, str] = {}
    for module_id, manifest in MODULE_MANIFESTS.items():
        for claim in manifest.get("python", ()):
            assert claim.endswith(".py")
            assert "::" not in claim
            assert "*" not in claim
            assert claim not in owners
            owners[claim] = module_id


def test_integration_points_reference_files_without_claiming_ownership() -> None:
    for manifest in MODULE_MANIFESTS.values():
        for point in manifest.get("integration_points", ()):
            file_path = point.split("::", 1)[0]
            assert file_path.endswith(".py")
            assert (ROOT / file_path).is_file()


def test_registry_validator_rejects_duplicate_python_ownership() -> None:
    base = {
        "name": "Demo",
        "status": "metadata_only",
        "lifecycle": "bootstrap_static",
        "risk": "low",
        "description": "Demo manifest.",
        "tests": [],
        "depends_on": [],
        "external_boundaries": [],
        "explicitly_excluded": [],
        "acceptance": ".codex/aria_acceptance/demo.json",
        "build_allowed": False,
        "runtime_access_allowed": False,
    }
    registry = {
        "left": {**base, "id": "left", "python": ["aria/modules/shared.py"]},
        "right": {**base, "id": "right", "python": ["aria/modules/shared.py"]},
    }

    issues = validate_module_registry(registry)

    assert any(issue.code == "python_ownership_conflict" for issue in issues)


def test_external_boundary_taxonomy_classifies_every_reference_once() -> None:
    diagnostics = module_external_boundary_diagnostics()
    expected = sum(len(manifest["external_boundaries"]) for manifest in MODULE_MANIFESTS.values())

    assert expected == 62
    assert diagnostics["external_dependency_count"] == expected
    assert sum(diagnostics["category_counts"].values()) == expected
    assert diagnostics["unclassified_count"] == 0
    assert diagnostics["disposition_counts"] == {"durable": 62}
    assert set(diagnostics["category_counts"]) == {
        "data_boundary",
        "kernel_platform",
        "library_service",
        "runtime_callback",
    }


def test_registry_has_no_provisional_metadata_statuses() -> None:
    provisional_markers = (
        "metadata_only",
        "needs_split",
        "needs_subsplit",
        "readpoint_prepared",
        "active_needs_split",
    )

    assert not {
        module_id: manifest["status"]
        for module_id, manifest in MODULE_MANIFESTS.items()
        if any(marker in str(manifest.get("status", "")) for marker in provisional_markers)
    }


def test_every_non_python_module_has_concrete_contract_evidence() -> None:
    reverse_consumers = {module_id: set() for module_id in MODULE_MANIFESTS}
    for consumer_id, manifest in MODULE_MANIFESTS.items():
        for dependency_id in manifest.get("depends_on", []):
            if dependency_id in reverse_consumers:
                reverse_consumers[dependency_id].add(consumer_id)

    evidence_fields = (
        "routes",
        "routes_prefixes",
        "templates",
        "static",
        "assets",
        "prompts",
        "catalogs",
        "nav_node_ids",
        "integration_points",
        "candidate_submodules",
    )
    unproven = {
        module_id
        for module_id, manifest in MODULE_MANIFESTS.items()
        if not manifest.get("python")
        and not reverse_consumers[module_id]
        and not any(manifest.get(field) for field in evidence_fields)
    }

    assert unproven == set()


def test_external_boundary_classifier_is_deterministic_for_known_classes() -> None:
    examples = {
        "kernel.templates": "kernel_platform",
        "pipeline.owner_contract": "composition_contract",
        "filesystem.caller_supplied_paths": "data_boundary",
        "request_cookie_callbacks": "runtime_callback",
        "yaml": "library_service",
    }

    assert {value: classify_external_boundary(value) for value in examples} == examples
    counts = Counter(
        classify_external_boundary(dependency)
        for manifest in MODULE_MANIFESTS.values()
        for dependency in external_boundary_ids(manifest)
    )
    assert dict(sorted(counts.items())) == module_external_boundary_diagnostics()["category_counts"]


def test_external_boundary_records_are_the_only_manifest_authority() -> None:
    for module_id, manifest in MODULE_MANIFESTS.items():
        assert "external_dependencies" not in manifest, module_id
        for record in manifest["external_boundaries"]:
            assert set(record) == {"id", "category", "disposition"}, module_id
            assert record["category"] == classify_external_boundary(record["id"]), module_id
            assert record["disposition"] in {"durable", "transitional"}, module_id


def test_retained_runtime_has_no_import_or_directory_from_legacy_funnel_ring() -> None:
    findings: list[str] = []
    for path in sorted((ROOT / "aria").rglob("*.py")):
        relative = path.relative_to(ROOT)
        owner = relative.parts[2] if relative.parts[:2] == ("aria", "modules") else ""
        if owner in LEGACY_FUNNEL_RING or relative == Path("aria/modules/registry.py"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(relative))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            elif isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            for name in names:
                parts = name.split(".")
                if len(parts) >= 3 and parts[:2] == ["aria", "modules"] and parts[2] in LEGACY_FUNNEL_RING:
                    findings.append(f"{relative}:{node.lineno}: {name}")

    assert findings == []
    assert all(not (ROOT / "aria" / "modules" / module_id).exists() for module_id in LEGACY_FUNNEL_RING)
