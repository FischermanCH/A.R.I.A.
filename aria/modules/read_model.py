"""Read-only views over declarative ARIA module metadata."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from aria.modules.boundary_contract import (
    EXTERNAL_BOUNDARY_CATEGORIES,
    external_boundary_ids,
    external_boundary_records,
)
from aria.modules.legacy_aliases import DURABLE_LEGACY_MODULE_ALIASES, LEGACY_MODULE_ALIASES
from aria.modules.registry import MODULE_MANIFESTS
from aria.modules.validation import module_dependency_cycles, validate_module_registry

_REQUIRED_STATUS_FIELDS = (
    "id",
    "name",
    "status",
    "lifecycle",
    "risk",
    "parent",
    "build_allowed",
    "runtime_access_allowed",
    "acceptance",
)

def module_reverse_dependencies(
    manifests: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, tuple[str, ...]]:
    """Return the deterministic transpose of the internal dependency graph."""

    source = manifests if manifests is not None else MODULE_MANIFESTS
    reverse: dict[str, list[str]] = {str(module_id): [] for module_id in source}
    for consumer_id, manifest in source.items():
        for owner_id in manifest.get("depends_on", ()):
            owner_key = str(owner_id).strip()
            if owner_key in reverse:
                reverse[owner_key].append(str(consumer_id))
    return {module_id: tuple(sorted(consumers)) for module_id, consumers in sorted(reverse.items())}


def module_external_boundary_diagnostics(
    manifests: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return deterministic category totals for declared external boundaries."""

    source = manifests if manifests is not None else MODULE_MANIFESTS
    records = tuple(record for manifest in source.values() for record in external_boundary_records(manifest))
    categories = Counter(record["category"] for record in records)
    dispositions = Counter(record["disposition"] for record in records)
    return {
        "external_dependency_count": sum(categories.values()),
        "category_counts": dict(sorted(categories.items())),
        "disposition_counts": dict(sorted(dispositions.items())),
        "unclassified_count": sum(
            record["category"] not in EXTERNAL_BOUNDARY_CATEGORIES for record in records
        ),
    }


def module_python_ownership_diagnostics(
    manifests: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, int]:
    """Summarize exact file ownership and non-owning integration references."""

    source = manifests if manifests is not None else MODULE_MANIFESTS
    owners: Counter[str] = Counter()
    invalid_python = 0
    invalid_integration = 0
    integration_count = 0
    for manifest in source.values():
        for value in manifest.get("python", ()):
            clean = str(value).strip()
            owners[clean] += 1
            invalid_python += int(not clean.endswith(".py") or "::" in clean or "*" in clean)
        for value in manifest.get("integration_points", ()):
            clean = str(value).strip()
            file_path, separator, detail = clean.partition("::")
            integration_count += 1
            invalid_integration += int(
                not file_path.endswith(".py")
                or "*" in file_path
                or (bool(separator) and not detail.strip())
            )
    return {
        "python_file_claim_count": sum(owners.values()),
        "integration_point_count": integration_count,
        "duplicate_python_owner_count": sum(count > 1 for count in owners.values()),
        "invalid_python_claim_count": invalid_python,
        "invalid_integration_point_count": invalid_integration,
    }


def module_status_rows(manifests: Mapping[str, Mapping[str, Any]] | None = None) -> tuple[dict[str, Any], ...]:
    """Return a stable read-only status projection for module metadata."""

    source = manifests if manifests is not None else MODULE_MANIFESTS
    reverse_dependencies = module_reverse_dependencies(source)
    cycles = module_dependency_cycles(source)
    cycle_by_module = {
        module_id: cycle
        for cycle in cycles
        for module_id in cycle
    }
    rows: list[dict[str, Any]] = []
    for module_id in sorted(str(key) for key in source):
        manifest = source[module_id]
        row = {field: manifest.get(field) for field in _REQUIRED_STATUS_FIELDS}
        row["id"] = str(row.get("id") or module_id).strip()
        row["name"] = str(row.get("name") or row["id"]).strip()
        row["status"] = str(row.get("status") or "").strip()
        row["lifecycle"] = str(row.get("lifecycle") or "").strip()
        row["risk"] = str(row.get("risk") or "").strip()
        row["parent"] = str(row.get("parent") or "").strip()
        row["acceptance"] = str(row.get("acceptance") or "").strip()
        row["build_allowed"] = bool(row.get("build_allowed"))
        row["runtime_access_allowed"] = bool(row.get("runtime_access_allowed"))
        row["depends_on"] = tuple(str(item).strip() for item in manifest.get("depends_on", ()))
        boundary_records = external_boundary_records(manifest)
        row["external_boundaries"] = boundary_records
        row["external_dependencies"] = external_boundary_ids(manifest)
        row["external_boundary_categories"] = tuple(
            sorted(Counter(record["category"] for record in boundary_records).items())
        )
        row["external_boundary_dispositions"] = tuple(
            sorted(Counter(record["disposition"] for record in boundary_records).items())
        )
        row["python"] = tuple(str(item).strip() for item in manifest.get("python", ()))
        row["integration_points"] = tuple(
            str(item).strip() for item in manifest.get("integration_points", ())
        )
        row["used_by"] = reverse_dependencies.get(module_id, ())
        row["dependency_cycle"] = cycle_by_module.get(module_id, ())
        rows.append(row)
    return tuple(rows)


def module_registry_diagnostics(
    manifests: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return passive validation and dependency summary data for operators."""

    source = manifests if manifests is not None else MODULE_MANIFESTS
    issues = validate_module_registry(source)
    cycles = module_dependency_cycles(source)
    internal_dependencies = sum(len(manifest.get("depends_on", ())) for manifest in source.values())
    external_dependencies = sum(len(external_boundary_records(manifest)) for manifest in source.values())
    external_boundary_diagnostics = module_external_boundary_diagnostics(source)
    python_ownership_diagnostics = module_python_ownership_diagnostics(source)
    legacy_alias_migration_candidates = set(LEGACY_MODULE_ALIASES) - DURABLE_LEGACY_MODULE_ALIASES
    return {
        "module_count": len(source),
        "validation_issue_count": len(issues),
        "internal_dependency_count": internal_dependencies,
        "external_dependency_count": external_dependencies,
        "external_boundary_category_counts": external_boundary_diagnostics["category_counts"],
        "external_boundary_disposition_counts": external_boundary_diagnostics["disposition_counts"],
        "external_boundary_unclassified_count": external_boundary_diagnostics["unclassified_count"],
        **python_ownership_diagnostics,
        "dependency_cycle_count": len(cycles),
        "dependency_cycle_module_count": len({module_id for cycle in cycles for module_id in cycle}),
        "dependency_cycles": cycles,
        "legacy_alias_count": len(LEGACY_MODULE_ALIASES),
        "legacy_alias_durable_count": len(DURABLE_LEGACY_MODULE_ALIASES),
        "legacy_alias_migration_candidate_count": len(legacy_alias_migration_candidates),
        "legacy_alias_canonical_target_count": len(set(LEGACY_MODULE_ALIASES.values())),
        "legacy_manifest_reference_count": sum(
            value.startswith(("aria/core/", "aria/web/"))
            for manifest in source.values()
            for field in ("python", "integration_points")
            for value in manifest.get(field, ())
            if isinstance(value, str)
        ),
        "legacy_alias_removal_ready": not legacy_alias_migration_candidates,
    }


def module_lifecycle_rows(
    manifests: Mapping[str, Mapping[str, Any]] | None = None,
) -> tuple[dict[str, Any], ...]:
    """Describe registry activation authority without activating modules."""

    source = manifests if manifests is not None else MODULE_MANIFESTS
    activation_owners = {
        "bootstrap_static": "application_bootstrap",
        "declarative_runtime": "module_registry",
        "contract_only": "none",
    }
    rows = []
    for module_id in sorted(str(key) for key in source):
        lifecycle = str(source[module_id].get("lifecycle") or "").strip()
        rows.append(
            {
                "id": module_id,
                "lifecycle": lifecycle,
                "activation_owner": activation_owners.get(lifecycle, "unclassified"),
                "activation_configurable": lifecycle == "declarative_runtime",
                "build_allowed": bool(source[module_id].get("build_allowed")),
                "runtime_access_allowed": bool(source[module_id].get("runtime_access_allowed")),
            }
        )
    return tuple(rows)


def module_lifecycle_diagnostics(
    manifests: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, int | bool]:
    """Return passive counts that keep acceptance authority separate from activation."""

    rows = module_lifecycle_rows(manifests)
    lifecycle_class_counts = Counter(str(row["lifecycle"]) for row in rows)
    return {
        "module_count": len(rows),
        "bootstrap_owned_count": sum(row["activation_owner"] == "application_bootstrap" for row in rows),
        "contract_only_count": lifecycle_class_counts["contract_only"],
        "declarative_activation_count": sum(bool(row["activation_configurable"]) for row in rows),
        "unclassified_lifecycle_count": lifecycle_class_counts[""],
        "build_allowed_count": sum(bool(row["build_allowed"]) for row in rows),
        "runtime_access_allowed_count": sum(bool(row["runtime_access_allowed"]) for row in rows),
        "legacy_alias_count": len(LEGACY_MODULE_ALIASES),
        "acceptance_flags_are_activation_controls": False,
    }


def module_static_asset_path(
    module_id: str,
    asset_name: str,
    base_dir: Path,
    *,
    manifests: Mapping[str, Mapping[str, Any]] | None = None,
) -> Path | None:
    """Return the local path for a static asset explicitly owned by a module."""

    module_key = str(module_id or "").strip()
    asset_key = str(asset_name or "").strip()
    if not module_key or not asset_key or "\\" in asset_key:
        return None
    relative = Path(asset_key)
    if relative.is_absolute() or ".." in relative.parts:
        return None
    source = manifests or MODULE_MANIFESTS
    manifest = source.get(module_key)
    if not manifest:
        return None
    registered_assets = {str(item or "").strip() for item in manifest.get("static", [])}
    if asset_key not in registered_assets:
        return None
    static_root = (Path(base_dir) / "aria" / "static").resolve()
    candidate = (static_root / relative).resolve()
    try:
        candidate.relative_to(static_root)
    except ValueError:
        return None
    return candidate


def module_static_asset_prefix_path(
    module_id: str,
    asset_name: str,
    base_dir: Path,
    *,
    manifests: Mapping[str, Mapping[str, Any]] | None = None,
) -> Path | None:
    """Return a static asset path when a module explicitly owns its filename prefix."""

    module_key = str(module_id or "").strip()
    asset_key = str(asset_name or "").strip()
    if not module_key or not asset_key or "/" in asset_key or "\\" in asset_key:
        return None
    source = manifests or MODULE_MANIFESTS
    manifest = source.get(module_key)
    if not manifest:
        return None
    prefixes = tuple(str(item or "").strip() for item in manifest.get("static_prefixes", []))
    if not any(prefix and asset_key.startswith(prefix) for prefix in prefixes):
        return None
    static_root = (Path(base_dir) / "aria" / "static").resolve()
    candidate = (static_root / asset_key).resolve()
    try:
        candidate.relative_to(static_root)
    except ValueError:
        return None
    return candidate


def module_prompt_path(
    module_id: str,
    prompt_path: str,
    base_dir: Path,
    *,
    manifests: Mapping[str, Mapping[str, Any]] | None = None,
) -> Path | None:
    """Return a repository prompt path covered by module-owned prompt prefixes."""

    module_key = str(module_id or "").strip()
    prompt_key = str(prompt_path or "").strip()
    if not module_key or not prompt_key or "\\" in prompt_key:
        return None
    relative = Path(prompt_key)
    if relative.is_absolute() or ".." in relative.parts:
        return None
    source = manifests or MODULE_MANIFESTS
    manifest = source.get(module_key)
    if not manifest:
        return None
    prefixes = tuple(str(item or "").strip().rstrip("/") for item in manifest.get("prompts", []))
    if not any(prefix and prompt_key.startswith(prefix + "/") for prefix in prefixes):
        return None
    root = Path(base_dir).resolve()
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


def module_public_path_prefix(
    module_id: str,
    route_path: str,
    *,
    manifests: Mapping[str, Mapping[str, Any]] | None = None,
) -> str | None:
    """Return a path covered by an explicitly public module-owned prefix."""

    module_key = str(module_id or "").strip()
    route_key = str(route_path or "").strip()
    if (
        not module_key
        or not route_key.startswith("/")
        or route_key.startswith("//")
        or "\\" in route_key
        or ".." in Path(route_key).parts
    ):
        return None
    source = manifests or MODULE_MANIFESTS
    manifest = source.get(module_key)
    if not manifest:
        return None
    prefixes = tuple(
        str(item or "").strip()
        for item in manifest.get("public_path_prefixes", [])
        if str(item or "").strip().startswith("/")
        and not str(item or "").strip().startswith("//")
        and str(item or "").strip().endswith("/")
    )
    if any(prefix and route_key.startswith(prefix) for prefix in prefixes):
        return route_key
    return None


def module_asset_path(
    module_id: str,
    asset_name: str,
    base_dir: Path,
    *,
    asset_field: str = "assets",
    manifests: Mapping[str, Mapping[str, Any]] | None = None,
) -> Path | None:
    """Return a local file path for an asset explicitly owned by a module."""

    module_key = str(module_id or "").strip()
    asset_key = str(asset_name or "").strip()
    field_key = str(asset_field or "").strip()
    if not module_key or not asset_key or not field_key or "/" in asset_key or "\\" in asset_key:
        return None
    source = manifests or MODULE_MANIFESTS
    manifest = source.get(module_key)
    if not manifest:
        return None
    raw_assets = manifest.get(field_key, {})
    if not isinstance(raw_assets, Mapping):
        return None
    relative_path = str(raw_assets.get(asset_key) or "").strip()
    if not relative_path:
        return None
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        return None
    root = Path(base_dir).resolve()
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


def module_catalog_entries(
    module_id: str,
    catalog_field: str,
    *,
    require_path: bool = True,
    manifests: Mapping[str, Mapping[str, Any]] | None = None,
) -> tuple[dict[str, Any], ...]:
    """Return catalog entries explicitly owned by a module."""

    module_key = str(module_id or "").strip()
    field_key = str(catalog_field or "").strip()
    if not module_key or not field_key:
        return ()
    source = manifests or MODULE_MANIFESTS
    manifest = source.get(module_key)
    if not manifest:
        return ()
    raw_entries = manifest.get(field_key, ())
    if not isinstance(raw_entries, (list, tuple)):
        return ()
    entries: list[dict[str, Any]] = []
    for raw_entry in raw_entries:
        if not isinstance(raw_entry, Mapping):
            continue
        entry = dict(raw_entry)
        entry["id"] = str(entry.get("id") or "").strip()
        if "path" in entry or require_path:
            entry["path"] = str(entry.get("path") or "").strip()
        if not entry["id"] or (require_path and not entry.get("path")):
            continue
        entries.append(entry)
    return tuple(entries)


def module_template_name(
    module_id: str,
    template_name: str,
    *,
    manifests: Mapping[str, Mapping[str, Any]] | None = None,
) -> str | None:
    """Return a template name explicitly owned by a module."""

    module_key = str(module_id or "").strip()
    template_key = str(template_name or "").strip()
    if not module_key or not template_key or "/" in template_key or "\\" in template_key:
        return None
    source = manifests or MODULE_MANIFESTS
    manifest = source.get(module_key)
    if not manifest:
        return None
    registered_templates = {str(item or "").strip() for item in manifest.get("templates", [])}
    if template_key not in registered_templates:
        return None
    return template_key


def module_route_path(
    module_id: str,
    route_path: str,
    *,
    manifests: Mapping[str, Mapping[str, Any]] | None = None,
) -> str | None:
    """Return a route path explicitly owned by a module."""

    module_key = str(module_id or "").strip()
    route_key = str(route_path or "").strip()
    if not module_key or not route_key.startswith("/") or route_key.startswith("//"):
        return None
    source = manifests or MODULE_MANIFESTS
    manifest = source.get(module_key)
    if not manifest:
        return None
    registered_routes = {str(item or "").strip() for item in manifest.get("routes", [])}
    registered_routes.update(str(item or "").strip() for item in manifest.get("api_routes", []))
    if route_key not in registered_routes:
        return None
    return route_key


def module_route_prefix_path(
    module_id: str,
    route_path: str,
    *,
    manifests: Mapping[str, Mapping[str, Any]] | None = None,
) -> str | None:
    """Return a local route path covered by a module-owned route prefix."""

    module_key = str(module_id or "").strip()
    route_key = str(route_path or "").strip()
    if not module_key or not route_key.startswith("/") or route_key.startswith("//"):
        return None
    source = manifests or MODULE_MANIFESTS
    manifest = source.get(module_key)
    if not manifest:
        return None
    prefixes = tuple(str(item or "").strip().rstrip("/") or "/" for item in manifest.get("routes_prefixes", []))
    for prefix in prefixes:
        if prefix == "/":
            return route_key
        if route_key == prefix or route_key.startswith(prefix + "/"):
            return route_key
    return None


def module_nav_node_id(
    module_id: str,
    nav_node_id: str,
    *,
    available_node_ids: set[str] | frozenset[str] | tuple[str, ...] | list[str] | None = None,
    manifests: Mapping[str, Mapping[str, Any]] | None = None,
) -> str | None:
    """Return a navigation node id explicitly owned by a module."""

    module_key = str(module_id or "").strip()
    node_key = str(nav_node_id or "").strip()
    if not module_key or not node_key:
        return None
    source = manifests or MODULE_MANIFESTS
    manifest = source.get(module_key)
    if not manifest:
        return None
    registered_node_ids = {str(item or "").strip() for item in manifest.get("nav_node_ids", [])}
    if node_key not in registered_node_ids:
        return None
    if available_node_ids is not None and node_key not in {str(item or "").strip() for item in available_node_ids}:
        return None
    return node_key
