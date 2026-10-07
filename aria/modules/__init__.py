"""Declarative ARIA module metadata.

This package is intentionally passive for now. Importing it must not register
routes, change dispatch behavior, or start runtime work.
"""

from __future__ import annotations

from aria.modules.boundary_contract import (
    EXTERNAL_BOUNDARY_CATEGORIES,
    EXTERNAL_BOUNDARY_DISPOSITIONS,
    classify_external_boundary,
    external_boundary_disposition,
    external_boundary_ids,
    external_boundary_record,
    external_boundary_records,
)
from aria.modules.read_model import (
    module_asset_path,
    module_catalog_entries,
    module_external_boundary_diagnostics,
    module_lifecycle_diagnostics,
    module_lifecycle_rows,
    module_nav_node_id,
    module_prompt_path,
    module_python_ownership_diagnostics,
    module_public_path_prefix,
    module_registry_diagnostics,
    module_reverse_dependencies,
    module_route_path,
    module_route_prefix_path,
    module_static_asset_path,
    module_static_asset_prefix_path,
    module_status_rows,
    module_template_name,
)
from aria.modules.registry import MODULE_MANIFESTS, MODULE_MANIFEST_ISSUES, get_module_manifest
from aria.modules.loader import (
    ENTRY_POINT_GROUP,
    PLUGIN_PATH_ENV,
    build_module_registry,
    configured_plugin_paths,
    discover_entry_point_manifests,
    discover_module_registry,
    discover_plugin_path_manifests,
)
from aria.modules.sdk import SDK_API_VERSION
from aria.modules.validation import (
    ModuleManifestIssue,
    ModuleManifestValidationError,
    module_dependency_cycles,
    require_valid_module_registry,
    validate_module_manifest,
    validate_module_repository_claims,
    validate_module_registry,
)

__all__ = [
    "MODULE_MANIFESTS",
    "MODULE_MANIFEST_ISSUES",
    "ModuleManifestIssue",
    "ModuleManifestValidationError",
    "ENTRY_POINT_GROUP",
    "EXTERNAL_BOUNDARY_CATEGORIES",
    "EXTERNAL_BOUNDARY_DISPOSITIONS",
    "PLUGIN_PATH_ENV",
    "SDK_API_VERSION",
    "build_module_registry",
    "classify_external_boundary",
    "external_boundary_disposition",
    "external_boundary_ids",
    "external_boundary_record",
    "external_boundary_records",
    "configured_plugin_paths",
    "discover_entry_point_manifests",
    "discover_module_registry",
    "discover_plugin_path_manifests",
    "get_module_manifest",
    "module_asset_path",
    "module_catalog_entries",
    "module_dependency_cycles",
    "module_external_boundary_diagnostics",
    "module_lifecycle_diagnostics",
    "module_lifecycle_rows",
    "module_nav_node_id",
    "module_prompt_path",
    "module_python_ownership_diagnostics",
    "module_public_path_prefix",
    "module_registry_diagnostics",
    "module_reverse_dependencies",
    "module_route_path",
    "module_route_prefix_path",
    "module_static_asset_path",
    "module_static_asset_prefix_path",
    "module_status_rows",
    "module_template_name",
    "require_valid_module_registry",
    "validate_module_manifest",
    "validate_module_repository_claims",
    "validate_module_registry",
]
