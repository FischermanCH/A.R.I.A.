from __future__ import annotations

import copy
import importlib
import json
from pathlib import Path

import pytest

from aria.modules import MODULE_MANIFESTS, MODULE_MANIFEST_ISSUES, external_boundary_ids
from aria.modules.validation import (
    ModuleManifestValidationError,
    module_dependency_cycles,
    require_valid_module_registry,
    validate_module_manifest,
    validate_module_registry,
)


def _manifest(module_id: str, **updates: object) -> dict[str, object]:
    manifest: dict[str, object] = {
        "id": module_id,
        "name": module_id.replace("_", " ").title(),
        "status": "metadata_only",
        "lifecycle": "bootstrap_static",
        "risk": "low",
        "description": "Validation fixture.",
        "python": [f"aria/modules/{module_id}/manifest.py"],
        "tests": ["tests/test_module_manifest_validation.py"],
        "depends_on": [],
        "external_boundaries": [
            {
                "id": "kernel.config",
                "category": "kernel_platform",
                "disposition": "durable",
            }
        ],
        "explicitly_excluded": ["runtime_behavior"],
        "acceptance": ".codex/aria_acceptance/module-manifest-contract-hardening-alpha725.json",
        "build_allowed": False,
        "runtime_access_allowed": False,
    }
    manifest.update(updates)
    return manifest


def _issue_codes(manifest: dict[str, object], registry_key: str = "demo") -> set[str]:
    return {issue.code for issue in validate_module_manifest(registry_key, manifest)}


def _boundary(
    boundary_id: str,
    *,
    category: str = "library_service",
    disposition: str = "durable",
) -> dict[str, str]:
    return {"id": boundary_id, "category": category, "disposition": disposition}


def test_registered_module_manifests_pass_fail_closed_import_contract() -> None:
    assert len(MODULE_MANIFESTS) == 106
    assert MODULE_MANIFEST_ISSUES == ()
    assert validate_module_registry(MODULE_MANIFESTS) == ()
    assert require_valid_module_registry(MODULE_MANIFESTS) == ()


def test_every_manifest_module_is_imported_and_registered_under_its_directory_id() -> None:
    modules_dir = Path(__file__).resolve().parents[1] / "aria" / "modules"
    discovered = {path.parent.name for path in modules_dir.glob("*/manifest.py")}

    assert discovered == set(MODULE_MANIFESTS)
    for module_id in sorted(discovered):
        imported = importlib.import_module(f"aria.modules.{module_id}.manifest")
        assert imported.MODULE_MANIFEST is MODULE_MANIFESTS[module_id]
        assert imported.MODULE_MANIFEST["id"] == module_id


def test_every_registered_manifest_acceptance_exists_and_contains_valid_json() -> None:
    root = Path(__file__).resolve().parents[1]

    for module_id, manifest in sorted(MODULE_MANIFESTS.items()):
        acceptance = root / str(manifest["acceptance"])
        assert acceptance.is_file(), module_id
        assert isinstance(json.loads(acceptance.read_text(encoding="utf-8")), dict), module_id


@pytest.mark.parametrize(
    ("updates", "expected_code"),
    [
        ({"id": "Bad-ID"}, "module_id_format"),
        ({"routes": ["config"]}, "route_path"),
        ({"routes": ["/config?tab=x"]}, "route_path"),
        ({"routes_prefixes": ["/config/"]}, "route_prefix"),
        ({"public_path_prefixes": ["/static"]}, "public_path_prefix"),
        ({"templates": ["nested/page.html"]}, "template_name"),
        ({"static": ["../style.css"]}, "static_path"),
        ({"static_prefixes": ["nested/background-"]}, "static_prefix"),
        ({"prompts": ["prompts/recipes"]}, "prompt_prefix"),
        ({"python": ["../aria/main.py"]}, "repository_path"),
        ({"nav_node_ids": ["Invalid Node"]}, "nav_node_id"),
        ({"routes": ["/demo", "/demo"]}, "duplicate_item"),
        ({"tests": "tests/test_demo.py"}, "list_type"),
        ({"build_allowed": True}, "unsafe_registry_flag"),
        ({"runtime_access_allowed": "false"}, "safety_flag_type"),
        ({"lifecycle": "unknown"}, "lifecycle_class"),
        ({"lifecycle": "contract_only"}, "lifecycle_python_conflict"),
        ({"acceptance": "docs/acceptance.json"}, "acceptance_path"),
        ({"depends_on": ["demo"]}, "dependency_self"),
        ({"parent": "demo"}, "parent_self"),
    ],
)
def test_manifest_validator_rejects_malformed_authority_fields(updates: dict[str, object], expected_code: str) -> None:
    manifest = _manifest("demo", **updates)

    assert expected_code in _issue_codes(manifest)


def test_manifest_validator_reports_registry_key_mismatch() -> None:
    issues = validate_module_manifest("registry_key", _manifest("manifest_id"))

    assert any(issue.code == "module_id_mismatch" for issue in issues)


@pytest.mark.parametrize(
    ("left_field", "right_field", "value", "ownership_kind"),
    [
        ("routes", "api_routes", "/shared", "route"),
        ("routes_prefixes", "routes_prefixes", "/shared", "route_prefix"),
        ("templates", "templates", "shared.html", "template"),
        ("static", "static", "shared.css", "static"),
        ("static_prefixes", "static_prefixes", "background-", "static_prefix"),
        ("public_path_prefixes", "public_path_prefixes", "/static/", "public_path_prefix"),
        ("prompts", "prompts", "prompts/shared/", "prompt_prefix"),
        ("nav_node_ids", "nav_node_ids", "shared.node", "nav_node_id"),
    ],
)
def test_registry_validator_rejects_exclusive_cross_module_claims(
    left_field: str,
    right_field: str,
    value: str,
    ownership_kind: str,
) -> None:
    left = _manifest("left", **{left_field: [value]})
    right = _manifest("right", **{right_field: [value]})

    issues = validate_module_registry({"left": left, "right": right})

    assert any(
        issue.code == "ownership_conflict" and issue.field == ownership_kind and issue.value == value
        for issue in issues
    )


def test_registry_validator_allows_nonexclusive_test_references() -> None:
    registry = {
        "left": _manifest(
            "left",
            python=["aria/modules/left/service.py"],
            tests=["tests/test_shared.py"],
        ),
        "right": _manifest(
            "right",
            python=["aria/modules/right/service.py"],
            tests=["tests/test_shared.py"],
        ),
    }

    assert validate_module_registry(registry) == ()


def test_registry_validator_reports_missing_parent_and_parent_cycle() -> None:
    missing = validate_module_registry({"child": _manifest("child", parent="missing")})
    cyclic = validate_module_registry(
        {
            "left": _manifest("left", parent="right"),
            "right": _manifest("right", parent="left"),
        }
    )

    assert any(issue.code == "parent_missing" for issue in missing)
    assert sum(issue.code == "parent_cycle" for issue in cyclic) == 1


def test_registry_validator_rejects_missing_or_misclassified_dependencies() -> None:
    missing = validate_module_registry(
        {"demo": _manifest("demo", depends_on=["missing_module"])}
    )
    misclassified = validate_module_registry(
        {
            "left": _manifest("left", depends_on=[], external_boundaries=[_boundary("right")]),
            "right": _manifest("right", depends_on=[], external_boundaries=[]),
        }
    )

    assert any(issue.code == "dependency_missing" and issue.value == "missing_module" for issue in missing)
    assert any(
        issue.code == "dependency_registered_as_external" and issue.value == "right"
        for issue in misclassified
    )


def test_manifest_validator_rejects_dependency_class_conflict_and_bad_external_id() -> None:
    conflict = _manifest(
        "demo",
        depends_on=["other"],
        external_boundaries=[_boundary("other"), _boundary("Invalid Boundary")],
    )

    codes = _issue_codes(conflict)

    assert "dependency_class_conflict" in codes
    assert "external_boundary_id" in codes


def test_manifest_validator_rejects_legacy_or_incomplete_external_boundary_authority() -> None:
    legacy = _manifest("demo", external_dependencies=["kernel.config"])
    incomplete = _manifest("demo", external_boundaries=[{"id": "yaml"}])

    assert "legacy_external_dependencies" in _issue_codes(legacy)
    assert "external_boundary_fields" in _issue_codes(incomplete)
    assert "external_boundary_category" in _issue_codes(incomplete)
    assert "external_boundary_disposition" in _issue_codes(incomplete)


def test_dependency_cycle_diagnostics_are_deterministic_and_ignore_external_boundaries() -> None:
    registry = {
        "alpha": _manifest("alpha", depends_on=["beta"]),
        "beta": _manifest("beta", depends_on=["alpha"], external_boundaries=[_boundary("legacy.chat")]),
        "gamma": _manifest("gamma", depends_on=["alpha"], external_boundaries=[]),
    }

    assert module_dependency_cycles(registry) == (("alpha", "beta"),)
    assert module_dependency_cycles(dict(reversed(tuple(registry.items())))) == (("alpha", "beta"),)


def test_current_registry_dependencies_are_fully_classified() -> None:
    module_ids = set(MODULE_MANIFESTS)

    for module_id, manifest in MODULE_MANIFESTS.items():
        internal = set(manifest["depends_on"])
        external = set(external_boundary_ids(manifest))
        assert "external_dependencies" not in manifest, module_id
        assert internal <= module_ids, module_id
        assert not external & module_ids, module_id
        assert not internal & external, module_id

    assert module_dependency_cycles(MODULE_MANIFESTS) == ()

    assert "memory_export" in MODULE_MANIFESTS["config_backup"]["depends_on"]
    assert "config_backup" not in MODULE_MANIFESTS["memory_export"]["depends_on"]


def test_connections_umbrella_delegates_python_and_provider_dependencies_to_submodules() -> None:
    umbrella = MODULE_MANIFESTS["connections"]

    assert umbrella["python"] == []
    assert umbrella["depends_on"] == ["auth_ui", "config_ui", "navigation_shell"]
    assert MODULE_MANIFESTS["connections_runtime_status"]["python"] == [
        "aria/modules/connections_runtime_status/runtime.py",
        "aria/modules/connections_runtime_status/inventory_source.py",
        "aria/modules/connections_runtime_status/native_tools.py",
    ]
    assert MODULE_MANIFESTS["connections_provider_manifest"]["python"] == [
        "aria/modules/connections_provider_manifest/projection.py",
    ]
    assert MODULE_MANIFESTS["connections_mutations"]["python"] == [
        "aria/modules/connections_mutations/admin_helpers.py",
        "aria/modules/connections_mutations/handlers.py",
        "aria/modules/connections_mutations/routes.py",
        "aria/modules/connections_mutations/support_helpers.py",
    ]
    assert "connections_runtime_status" in MODULE_MANIFESTS["connections_profiles"]["depends_on"]
    assert "connections_runtime_status" in MODULE_MANIFESTS["connections_ui_readonly"]["depends_on"]
    assert "connections_runtime_status" not in external_boundary_ids(MODULE_MANIFESTS["connections_profiles"])
    assert "connections_runtime_status" not in external_boundary_ids(MODULE_MANIFESTS["connections_ui_readonly"])


def test_recipes_umbrella_delegates_product_claims_to_submodules() -> None:
    umbrella = MODULE_MANIFESTS["recipes"]

    assert umbrella["python"] == []
    assert umbrella["templates"] == []
    assert umbrella["prompts"] == []
    assert umbrella["routes_prefixes"] == []
    assert umbrella["depends_on"] == ["auth_ui", "navigation_shell"]
    assert MODULE_MANIFESTS["recipe_store"]["prompts"] == ["prompts/recipes/"]
    assert MODULE_MANIFESTS["recipe_legacy_skill_compat"]["prompts"] == ["prompts/skills/"]
    assert MODULE_MANIFESTS["recipe_legacy_skill_compat"]["routes_prefixes"] == ["/skills"]
    assert "aria/modules/recipe_runtime/runtime.py" in MODULE_MANIFESTS["recipe_runtime"]["python"]
    assert "recipe_learning" not in MODULE_MANIFESTS


def test_documents_umbrella_delegates_product_claims_to_submodules() -> None:
    umbrella = MODULE_MANIFESTS["documents"]

    assert umbrella["python"] == []
    assert umbrella["routes"] == []
    assert umbrella["routes_prefixes"] == []
    assert umbrella["templates"] == []
    assert umbrella["depends_on"] == []
    assert MODULE_MANIFESTS["notes"]["routes_prefixes"] == ["/notes"]
    assert "notes.html" in MODULE_MANIFESTS["notes"]["templates"]
    assert MODULE_MANIFESTS["document_ingest"]["python"] == [
        "aria/modules/document_ingest/ingest.py",
    ]
    assert "aria/modules/document_memory/service.py" in MODULE_MANIFESTS["document_memory"]["python"]


def test_memory_umbrella_delegates_learning_bridge_and_overlapping_files() -> None:
    memory_python = set(MODULE_MANIFESTS["memory"]["python"])

    assert MODULE_MANIFESTS["memory"]["depends_on"] == [
        "configuration_foundations",
        "platform_primitives",
        "qdrant_gateway",
        "system_diagnostics",
        "chat_history_storage",
    ]
    assert "aria/core/qdrant_collection_classifier.py" not in memory_python
    assert "aria/core/qdrant_storage_diagnostics.py" not in memory_python
    assert "aria/core/auto_memory.py" not in memory_python
    assert "aria/core/document_memory_*.py" not in memory_python
    assert "aria/core/memory_*.py" not in memory_python
    assert "aria/core/procedure_skill_memory.py" not in memory_python
    assert MODULE_MANIFESTS["memory_learning_bridge"]["python"] == [
        "aria/modules/memory_learning_bridge/skill.py",
    ]
    assert MODULE_MANIFESTS["memory_learning_bridge"]["depends_on"] == [
        "system_diagnostics",
        "qdrant_gateway",
        "skill_contracts",
    ]
    assert "aria/modules/memory/admin_query.py" in memory_python


def test_actions_umbrella_delegates_all_python_claims_to_submodules() -> None:
    assert MODULE_MANIFESTS["actions"]["python"] == []
    assert MODULE_MANIFESTS["actions"]["depends_on"] == ["runtime_guardrails"]
    assert "action_planner" not in MODULE_MANIFESTS
    assert "action_planner" not in MODULE_MANIFESTS["actions"]["candidate_submodules"]
    assert "aria/modules/action_planner_templates/planner.py" in MODULE_MANIFESTS["action_planner_templates"]["python"]
    assert MODULE_MANIFESTS["action_draft_policy"]["python"] == [
        "aria/modules/action_draft_policy/contracts.py",
        "aria/modules/action_draft_policy/guardrail_drafts.py",
    ]
    assert "chat_pending_tokens" not in MODULE_MANIFESTS
    assert "chat_pending_tokens" not in MODULE_MANIFESTS["actions"]["candidate_submodules"]


def test_provider_umbrellas_delegate_product_claims_to_submodules() -> None:
    for module_id in ("http_api", "rss"):
        assert MODULE_MANIFESTS[module_id]["python"] == []
    assert MODULE_MANIFESTS["ssh"]["python"] == ["aria/modules/ssh/profile_admin.py"]

    assert MODULE_MANIFESTS["ssh"]["depends_on"] == ["runtime_guardrails"]
    assert MODULE_MANIFESTS["sftp"]["depends_on"] == ["connections", "action_contracts", "platform_primitives", "runtime_guardrails"]
    assert MODULE_MANIFESTS["http_api"]["depends_on"] == ["runtime_guardrails"]
    assert MODULE_MANIFESTS["rss"]["depends_on"] == ["platform_primitives"]

    assert MODULE_MANIFESTS["ssh_admin_ui"]["routes_prefixes"] == ["/config/connections/ssh"]
    assert MODULE_MANIFESTS["sftp_admin_ui"]["routes_prefixes"] == ["/config/connections/sftp"]
    assert MODULE_MANIFESTS["sftp_admin_ui"]["templates"] == ["config_connections_sftp.html"]
    assert MODULE_MANIFESTS["http_api_admin_ui"]["templates"] == [
        "config_connections_http_api.html",
        "config_connections_webhook.html",
    ]
    assert MODULE_MANIFESTS["ssh_policy"]["python"] == [
        "aria/modules/ssh_policy/guardrail_commands.py",
        "aria/modules/ssh_policy/policy.py",
    ]
    assert MODULE_MANIFESTS["http_api_policy"]["python"] == [
        "aria/modules/http_api_policy/policy.py",
    ]
    assert MODULE_MANIFESTS["rss_digest"]["python"] == [
        "aria/modules/rss_digest/options.py",
        "aria/modules/rss_digest/execution_policy.py",
        "aria/modules/rss_digest/grouping.py",
    ]
    assert MODULE_MANIFESTS["rss_opml"]["python"] == [
        "aria/modules/rss_opml/opml.py",
    ]


def test_legacy_learning_and_auto_memory_modules_are_absent() -> None:
    removed = {
        "learning",
        "learning_admin_ui",
        "learning_artifacts",
        "learning_candidates",
        "learning_feedback",
        "learning_governance",
        "learning_runtime",
        "prepared_artifacts",
        "recipe_learning",
        "auto_memory",
    }

    assert not removed & set(MODULE_MANIFESTS)


def test_registry_validator_is_deterministic_and_does_not_mutate_input() -> None:
    registry = {
        "right": _manifest("right", templates=["shared.html"]),
        "left": _manifest("left", templates=["shared.html"]),
    }
    before = copy.deepcopy(registry)

    first = validate_module_registry(registry)
    second = validate_module_registry(registry)

    assert first == second
    assert registry == before
    assert list(first) == sorted(first)


def test_require_valid_module_registry_raises_with_structured_issues() -> None:
    registry = {"demo": _manifest("demo", public_path_prefixes=["/static"])}

    with pytest.raises(ModuleManifestValidationError) as exc_info:
        require_valid_module_registry(registry)

    assert exc_info.value.issues
    assert exc_info.value.issues[0].code == "public_path_prefix"
    assert "public_path_prefix:demo:public_path_prefixes:/static" in str(exc_info.value)


def test_narrow_modules_exclusively_own_split_surface_metadata() -> None:
    assert MODULE_MANIFESTS["ui_admin"].get("routes_prefixes") == []
    assert MODULE_MANIFESTS["ui_admin"].get("static") == []
    assert MODULE_MANIFESTS["connections"].get("templates") == []
    assert MODULE_MANIFESTS["recipes"].get("routes_prefixes") == []
    assert "_config_nav.html" not in MODULE_MANIFESTS["navigation_shell"].get("templates", [])
    assert "config_connections_rss.html" not in MODULE_MANIFESTS["rss"].get("templates", [])
    assert "config_memory.html" not in MODULE_MANIFESTS["memory"].get("templates", [])
    assert "learning" not in MODULE_MANIFESTS
    assert "memories_learning_candidate_apply_preview.html" not in MODULE_MANIFESTS["memory_admin_ui"].get("templates", [])
    assert "config_backup.html" not in MODULE_MANIFESTS["memory_export"].get("templates", [])

    assert "/config" in MODULE_MANIFESTS["config_ui"].get("routes_prefixes", [])
    assert "/recipes" in MODULE_MANIFESTS["recipes_ui"].get("routes_prefixes", [])
    assert "/skills" in MODULE_MANIFESTS["recipe_legacy_skill_compat"].get("routes_prefixes", [])
    assert "style.css" in MODULE_MANIFESTS["navigation_shell"].get("static", [])
    assert "config_connections_rss.html" in MODULE_MANIFESTS["rss_ui"].get("templates", [])
    assert "config_memory.html" in MODULE_MANIFESTS["memory_admin_ui"].get("templates", [])
    assert "config_backup.html" in MODULE_MANIFESTS["config_backup"].get("templates", [])
