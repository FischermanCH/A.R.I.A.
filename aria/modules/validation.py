"""Pure validation contracts for passive ARIA module manifests."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from aria.modules.boundary_contract import (
    EXTERNAL_BOUNDARY_CATEGORIES,
    EXTERNAL_BOUNDARY_DISPOSITIONS,
    external_boundary_ids,
)

_MODULE_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_NAV_NODE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]*$")
_REQUIRED_TEXT_FIELDS = ("id", "name", "status", "lifecycle", "risk", "description", "acceptance")
_LIFECYCLE_CLASSES = frozenset({"bootstrap_static", "declarative_runtime", "contract_only"})
_REQUIRED_LIST_FIELDS = (
    "python",
    "tests",
    "depends_on",
    "external_boundaries",
    "explicitly_excluded",
)
_STRING_LIST_FIELDS = (
    "api_routes",
    "candidate_submodules",
    "depends_on",
    "docs",
    "explicitly_excluded",
    "integration_points",
    "nav_node_ids",
    "notes",
    "prompts",
    "public_path_prefixes",
    "python",
    "routes",
    "routes_prefixes",
    "scripts",
    "static",
    "static_prefixes",
    "templates",
    "tests",
)
_REPOSITORY_PATH_FIELDS = ("docs", "integration_points", "python", "scripts", "tests")
_EXCLUSIVE_OWNERSHIP_GROUPS: Mapping[str, tuple[str, ...]] = {
    "route": ("routes", "api_routes"),
    "route_prefix": ("routes_prefixes",),
    "template": ("templates",),
    "static": ("static",),
    "static_prefix": ("static_prefixes",),
    "public_path_prefix": ("public_path_prefixes",),
    "prompt_prefix": ("prompts",),
    "nav_node_id": ("nav_node_ids",),
}


@dataclass(frozen=True, order=True)
class ModuleManifestIssue:
    """One deterministic module-manifest contract violation."""

    code: str
    module_id: str
    field: str
    value: str
    detail: str


class ModuleManifestValidationError(ValueError):
    """Raised when a registry cannot safely serve as readpoint authority."""

    def __init__(self, issues: Sequence[ModuleManifestIssue]) -> None:
        self.issues = tuple(issues)
        summary = "; ".join(
            f"{issue.code}:{issue.module_id}:{issue.field}:{issue.value}" for issue in self.issues
        )
        super().__init__(f"invalid module registry: {summary}")


def _issue(code: str, module_id: str, field: str, value: object, detail: str) -> ModuleManifestIssue:
    return ModuleManifestIssue(code, module_id, field, str(value), detail)


def _string_items(manifest: Mapping[str, Any], field: str) -> tuple[str, ...]:
    raw = manifest.get(field, ())
    if not isinstance(raw, (list, tuple)):
        return ()
    return tuple(str(item).strip() for item in raw if isinstance(item, str) and str(item).strip())


def _is_safe_route(value: str) -> bool:
    return (
        value.startswith("/")
        and not value.startswith("//")
        and "\\" not in value
        and "?" not in value
        and "#" not in value
        and ".." not in PurePosixPath(value).parts
    )


def _is_safe_repository_path(value: str) -> bool:
    path_value = value.split("::", 1)[0]
    relative = PurePosixPath(path_value)
    return bool(path_value) and not relative.is_absolute() and "\\" not in path_value and ".." not in relative.parts


def validate_module_manifest(registry_key: str, manifest: Mapping[str, Any]) -> tuple[ModuleManifestIssue, ...]:
    """Validate one manifest without importing runtime code or mutating metadata."""

    module_key = str(registry_key or "").strip()
    issues: list[ModuleManifestIssue] = []
    if not isinstance(manifest, Mapping):
        return (_issue("manifest_type", module_key, "manifest", type(manifest).__name__, "manifest must be a mapping"),)

    for field in _REQUIRED_TEXT_FIELDS:
        value = manifest.get(field)
        if not isinstance(value, str) or not value.strip():
            issues.append(_issue("required_text", module_key, field, value, "required non-empty string"))

    manifest_id = str(manifest.get("id") or "").strip()
    if manifest_id and not _MODULE_ID_RE.fullmatch(manifest_id):
        issues.append(_issue("module_id_format", module_key, "id", manifest_id, "invalid module id"))
    if manifest_id and manifest_id != module_key:
        issues.append(_issue("module_id_mismatch", module_key, "id", manifest_id, "registry key and id differ"))

    lifecycle = str(manifest.get("lifecycle") or "").strip()
    python_claims = _string_items(manifest, "python")
    if lifecycle and lifecycle not in _LIFECYCLE_CLASSES:
        issues.append(
            _issue("lifecycle_class", module_key, "lifecycle", lifecycle, "unknown lifecycle class")
        )
    elif lifecycle == "contract_only" and python_claims:
        issues.append(
            _issue(
                "lifecycle_python_conflict",
                module_key,
                "lifecycle",
                lifecycle,
                "contract-only modules cannot own executable Python files",
            )
        )
    elif lifecycle in {"bootstrap_static", "declarative_runtime"} and not python_claims:
        issues.append(
            _issue(
                "lifecycle_python_conflict",
                module_key,
                "lifecycle",
                lifecycle,
                "executable lifecycle classes require a Python owner",
            )
        )

    for field in _REQUIRED_LIST_FIELDS:
        if field not in manifest:
            issues.append(_issue("required_list", module_key, field, "missing", "required list field"))

    for field in _STRING_LIST_FIELDS:
        if field not in manifest:
            continue
        raw = manifest.get(field)
        if not isinstance(raw, (list, tuple)):
            issues.append(_issue("list_type", module_key, field, type(raw).__name__, "field must be a list or tuple"))
            continue
        seen: set[str] = set()
        for item in raw:
            if not isinstance(item, str) or not item.strip():
                issues.append(_issue("list_item", module_key, field, item, "items must be non-empty strings"))
                continue
            clean = item.strip()
            if clean in seen:
                issues.append(_issue("duplicate_item", module_key, field, clean, "duplicate item in manifest"))
            seen.add(clean)

    raw_boundaries = manifest.get("external_boundaries")
    if raw_boundaries is not None:
        if not isinstance(raw_boundaries, (list, tuple)):
            issues.append(
                _issue(
                    "list_type",
                    module_key,
                    "external_boundaries",
                    type(raw_boundaries).__name__,
                    "field must be a list or tuple",
                )
            )
        else:
            seen_boundary_ids: set[str] = set()
            for index, record in enumerate(raw_boundaries):
                if not isinstance(record, Mapping):
                    issues.append(
                        _issue(
                            "external_boundary_record",
                            module_key,
                            "external_boundaries",
                            index,
                            "boundary record must be a mapping",
                        )
                    )
                    continue
                if set(record) != {"id", "category", "disposition"}:
                    issues.append(
                        _issue(
                            "external_boundary_fields",
                            module_key,
                            "external_boundaries",
                            index,
                            "boundary record fields must be id, category and disposition",
                        )
                    )
                boundary_id = str(record.get("id") or "").strip()
                category = str(record.get("category") or "").strip()
                disposition = str(record.get("disposition") or "").strip()
                if not _NAV_NODE_ID_RE.fullmatch(boundary_id):
                    issues.append(
                        _issue(
                            "external_boundary_id",
                            module_key,
                            "external_boundaries",
                            boundary_id,
                            "invalid external boundary id",
                        )
                    )
                if boundary_id in seen_boundary_ids:
                    issues.append(
                        _issue(
                            "duplicate_item",
                            module_key,
                            "external_boundaries",
                            boundary_id,
                            "duplicate boundary id in manifest",
                        )
                    )
                seen_boundary_ids.add(boundary_id)
                if category not in EXTERNAL_BOUNDARY_CATEGORIES:
                    issues.append(
                        _issue(
                            "external_boundary_category",
                            module_key,
                            "external_boundaries",
                            category,
                            "unknown external boundary category",
                        )
                    )
                if disposition not in EXTERNAL_BOUNDARY_DISPOSITIONS:
                    issues.append(
                        _issue(
                            "external_boundary_disposition",
                            module_key,
                            "external_boundaries",
                            disposition,
                            "unknown external boundary disposition",
                        )
                    )

    if "external_dependencies" in manifest:
        issues.append(
            _issue(
                "legacy_external_dependencies",
                module_key,
                "external_dependencies",
                "present",
                "external_boundaries is the only stored boundary authority",
            )
        )

    for field in ("build_allowed", "runtime_access_allowed"):
        value = manifest.get(field)
        if not isinstance(value, bool):
            issues.append(_issue("safety_flag_type", module_key, field, value, "safety flag must be boolean"))
        elif value:
            issues.append(_issue("unsafe_registry_flag", module_key, field, value, "passive registry flags must remain false"))

    acceptance = str(manifest.get("acceptance") or "").strip()
    if acceptance and (
        not acceptance.startswith(".codex/aria_acceptance/")
        or not acceptance.endswith(".json")
        or not _is_safe_repository_path(acceptance)
    ):
        issues.append(_issue("acceptance_path", module_key, "acceptance", acceptance, "invalid acceptance path"))

    for field in ("routes", "api_routes"):
        for value in _string_items(manifest, field):
            if not _is_safe_route(value):
                issues.append(_issue("route_path", module_key, field, value, "invalid route path"))

    for value in _string_items(manifest, "routes_prefixes"):
        if not _is_safe_route(value) or (value != "/" and value.endswith("/")):
            issues.append(_issue("route_prefix", module_key, "routes_prefixes", value, "invalid route prefix boundary"))

    for value in _string_items(manifest, "public_path_prefixes"):
        if not _is_safe_route(value) or not value.endswith("/"):
            issues.append(
                _issue("public_path_prefix", module_key, "public_path_prefixes", value, "public prefix must end with /" )
            )

    for field in _REPOSITORY_PATH_FIELDS:
        for value in _string_items(manifest, field):
            if not _is_safe_repository_path(value):
                issues.append(_issue("repository_path", module_key, field, value, "unsafe repository-relative path"))

    for value in _string_items(manifest, "python"):
        if not value.endswith(".py") or "::" in value or "*" in value:
            issues.append(
                _issue(
                    "python_ownership_path",
                    module_key,
                    "python",
                    value,
                    "python ownership must name one exact .py file",
                )
            )

    for value in _string_items(manifest, "integration_points"):
        file_path, separator, detail = value.partition("::")
        if not file_path.endswith(".py") or "*" in file_path or (separator and not detail.strip()):
            issues.append(
                _issue(
                    "integration_point_path",
                    module_key,
                    "integration_points",
                    value,
                    "integration point must name an exact .py file and optional non-empty detail",
                )
            )

    for value in _string_items(manifest, "templates"):
        if "/" in value or "\\" in value or value in {".", ".."}:
            issues.append(_issue("template_name", module_key, "templates", value, "template must be a flat name or pattern"))

    for value in _string_items(manifest, "static"):
        if not _is_safe_repository_path(value):
            issues.append(_issue("static_path", module_key, "static", value, "unsafe static-relative path"))

    for value in _string_items(manifest, "static_prefixes"):
        if "/" in value or "\\" in value or value in {".", ".."}:
            issues.append(_issue("static_prefix", module_key, "static_prefixes", value, "invalid static filename prefix"))

    for value in _string_items(manifest, "prompts"):
        if not value.startswith("prompts/") or not value.endswith("/") or not _is_safe_repository_path(value):
            issues.append(_issue("prompt_prefix", module_key, "prompts", value, "invalid prompt prefix"))

    for value in _string_items(manifest, "nav_node_ids"):
        if not _NAV_NODE_ID_RE.fullmatch(value):
            issues.append(_issue("nav_node_id", module_key, "nav_node_ids", value, "invalid navigation node id"))

    parent = str(manifest.get("parent") or "").strip()
    if parent and parent == module_key:
        issues.append(_issue("parent_self", module_key, "parent", parent, "module cannot parent itself"))

    for dependency in _string_items(manifest, "depends_on"):
        if not _MODULE_ID_RE.fullmatch(dependency):
            issues.append(
                _issue("dependency_id_format", module_key, "depends_on", dependency, "invalid internal module id")
            )
        if dependency == module_key:
            issues.append(_issue("dependency_self", module_key, "depends_on", dependency, "module cannot depend on itself"))

    internal_dependencies = set(_string_items(manifest, "depends_on"))
    for dependency in external_boundary_ids(manifest):
        if dependency in internal_dependencies:
            issues.append(
                _issue(
                    "dependency_class_conflict",
                    module_key,
                    "external_boundaries",
                    dependency,
                    "dependency cannot be internal and external",
                )
            )

    return tuple(sorted(issues))


def validate_module_registry(manifests: Mapping[str, Mapping[str, Any]]) -> tuple[ModuleManifestIssue, ...]:
    """Validate registry structure and exclusive metadata ownership."""

    issues: list[ModuleManifestIssue] = []
    normalized: dict[str, Mapping[str, Any]] = {}
    for raw_key, manifest in manifests.items():
        module_id = str(raw_key)
        if module_id in normalized:
            issues.append(_issue("registry_key_collision", module_id, "id", raw_key, "duplicate normalized registry key"))
            continue
        if not isinstance(manifest, Mapping):
            issues.extend(validate_module_manifest(module_id, manifest))
            continue
        normalized[module_id] = manifest
        issues.extend(validate_module_manifest(module_id, manifest))

    module_ids = set(normalized)
    for module_id in sorted(module_ids):
        manifest = normalized[module_id]
        parent = str(manifest.get("parent") or "").strip()
        if parent and parent not in module_ids:
            issues.append(_issue("parent_missing", module_id, "parent", parent, "parent module is not registered"))
        for dependency in _string_items(manifest, "depends_on"):
            if dependency not in module_ids:
                issues.append(
                    _issue(
                        "dependency_missing",
                        module_id,
                        "depends_on",
                        dependency,
                        "internal dependency is not registered",
                    )
                )
        for dependency in external_boundary_ids(manifest):
            if dependency in module_ids:
                issues.append(
                    _issue(
                        "dependency_registered_as_external",
                        module_id,
                        "external_boundaries",
                        dependency,
                        "registered module must be an internal dependency",
                    )
                )

    parent_cycles: set[tuple[str, ...]] = set()
    for start in sorted(module_ids):
        chain: list[str] = []
        current = start
        while current in normalized:
            if current in chain:
                cycle = chain[chain.index(current) :]
                rotations = [tuple(cycle[index:] + cycle[:index]) for index in range(len(cycle))]
                parent_cycles.add(min(rotations))
                break
            chain.append(current)
            current = str(normalized[current].get("parent") or "").strip()
            if not current:
                break
    for cycle in sorted(parent_cycles):
        issues.append(_issue("parent_cycle", ",".join(cycle), "parent", "->".join(cycle), "parent cycle detected"))

    for ownership_kind, fields in _EXCLUSIVE_OWNERSHIP_GROUPS.items():
        claims: dict[str, set[str]] = defaultdict(set)
        for module_id in sorted(module_ids):
            manifest = normalized[module_id]
            for field in fields:
                for value in _string_items(manifest, field):
                    claims[value].add(module_id)
        for value, owners in sorted(claims.items()):
            if len(owners) < 2:
                continue
            owner_text = ",".join(sorted(owners))
            issues.append(
                _issue(
                    "ownership_conflict",
                    owner_text,
                    ownership_kind,
                    value,
                    "exclusive metadata claimed by multiple modules",
                )
            )

    python_claims: dict[str, set[str]] = defaultdict(set)
    for module_id in sorted(module_ids):
        for value in _string_items(normalized[module_id], "python"):
            python_claims[value].add(module_id)
    for value, owners in sorted(python_claims.items()):
        if len(owners) > 1:
            issues.append(
                _issue(
                    "python_ownership_conflict",
                    ",".join(sorted(owners)),
                    "python",
                    value,
                    "python file ownership must be unique",
                )
            )

    return tuple(sorted(issues))


def validate_module_repository_claims(
    base_dir: Path,
    manifests: Mapping[str, Mapping[str, Any]],
) -> tuple[ModuleManifestIssue, ...]:
    """Validate that passive file claims point to repository files."""

    root = Path(base_dir).resolve()
    issues: list[ModuleManifestIssue] = []
    for module_id, manifest in sorted(manifests.items()):
        for field in ("python", "integration_points"):
            for value in _string_items(manifest, field):
                relative = value.split("::", 1)[0]
                candidate = (root / relative).resolve()
                try:
                    candidate.relative_to(root)
                except ValueError:
                    issues.append(_issue("repository_claim_escape", module_id, field, value, "claim escapes root"))
                    continue
                if not candidate.is_file():
                    issues.append(
                        _issue("repository_claim_missing", module_id, field, value, "claimed file does not exist")
                    )
    return tuple(sorted(issues))


def module_dependency_cycles(
    manifests: Mapping[str, Mapping[str, Any]],
) -> tuple[tuple[str, ...], ...]:
    """Return deterministic strongly connected internal dependency groups."""

    module_ids = {str(key) for key, manifest in manifests.items() if isinstance(manifest, Mapping)}
    graph = {
        module_id: tuple(
            sorted(
                dependency
                for dependency in _string_items(manifests[module_id], "depends_on")
                if dependency in module_ids
            )
        )
        for module_id in sorted(module_ids)
    }
    index = 0
    indexes: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    cycles: list[tuple[str, ...]] = []

    def visit(module_id: str) -> None:
        nonlocal index
        indexes[module_id] = index
        lowlinks[module_id] = index
        index += 1
        stack.append(module_id)
        on_stack.add(module_id)

        for dependency in graph[module_id]:
            if dependency not in indexes:
                visit(dependency)
                lowlinks[module_id] = min(lowlinks[module_id], lowlinks[dependency])
            elif dependency in on_stack:
                lowlinks[module_id] = min(lowlinks[module_id], indexes[dependency])

        if lowlinks[module_id] != indexes[module_id]:
            return
        component: list[str] = []
        while stack:
            dependency = stack.pop()
            on_stack.remove(dependency)
            component.append(dependency)
            if dependency == module_id:
                break
        if len(component) > 1 or module_id in graph[module_id]:
            cycles.append(tuple(sorted(component)))

    for module_id in sorted(graph):
        if module_id not in indexes:
            visit(module_id)
    return tuple(sorted(cycles))


def require_valid_module_registry(manifests: Mapping[str, Mapping[str, Any]]) -> tuple[ModuleManifestIssue, ...]:
    """Fail closed when registry metadata violates its passive authority contract."""

    issues = validate_module_registry(manifests)
    if issues:
        raise ModuleManifestValidationError(issues)
    return issues
