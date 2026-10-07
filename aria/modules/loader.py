"""Dynamic discovery for installable ARIA module manifests."""

from __future__ import annotations

import importlib
import importlib.metadata
import importlib.util
import os
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any

from aria.modules.validation import require_valid_module_registry

ENTRY_POINT_GROUP = "aria.modules"
PLUGIN_PATH_ENV = "ARIA_MODULE_PLUGIN_PATHS"


def _manifest_from_object(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if callable(value):
        return _manifest_from_object(value())
    manifest = getattr(value, "MODULE_MANIFEST", None)
    if isinstance(manifest, Mapping):
        return manifest
    raise TypeError("module entry point did not expose a manifest mapping")


def _load_module_from_path(path: Path, module_name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load module manifest from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _plugin_manifest_files(plugin_paths: Sequence[Path]) -> tuple[Path, ...]:
    files: list[Path] = []
    for root in plugin_paths:
        if not root.exists():
            continue
        if root.is_file() and root.name == "manifest.py":
            files.append(root)
            continue
        for candidate in sorted(root.glob("*/manifest.py")):
            if candidate.is_file():
                files.append(candidate)
    return tuple(files)


def configured_plugin_paths(raw: str | None = None) -> tuple[Path, ...]:
    value = os.environ.get(PLUGIN_PATH_ENV, "") if raw is None else raw
    paths = []
    for item in value.split(os.pathsep):
        clean = item.strip()
        if clean:
            paths.append(Path(clean))
    return tuple(paths)


def discover_entry_point_manifests(group: str = ENTRY_POINT_GROUP) -> tuple[Mapping[str, Any], ...]:
    entry_points = importlib.metadata.entry_points()
    if hasattr(entry_points, "select"):
        selected = entry_points.select(group=group)
    else:
        selected = entry_points.get(group, ())
    manifests: list[Mapping[str, Any]] = []
    for entry_point in selected:
        manifests.append(_manifest_from_object(entry_point.load()))
    return tuple(manifests)


def discover_plugin_path_manifests(plugin_paths: Sequence[Path]) -> tuple[Mapping[str, Any], ...]:
    manifests: list[Mapping[str, Any]] = []
    for index, manifest_file in enumerate(_plugin_manifest_files(plugin_paths)):
        module = _load_module_from_path(
            manifest_file,
            f"_aria_external_module_{index}_{manifest_file.parent.name}",
        )
        manifests.append(_manifest_from_object(module))
    return tuple(manifests)


def build_module_registry(
    builtin_manifests: Iterable[Mapping[str, Any]] = (),
    *,
    entry_point_manifests: Iterable[Mapping[str, Any]] = (),
    plugin_path_manifests: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Mapping[str, Any]]:
    registry: dict[str, Mapping[str, Any]] = {}
    for manifest in (*tuple(builtin_manifests), *tuple(entry_point_manifests), *tuple(plugin_path_manifests)):
        module_id = str(manifest.get("id") or "").strip()
        registry[module_id] = manifest
    require_valid_module_registry(registry)
    return registry


def discover_module_registry(
    builtin_manifests: Iterable[Mapping[str, Any]] = (),
    *,
    plugin_paths: Sequence[Path] | None = None,
    include_entry_points: bool = True,
) -> dict[str, Mapping[str, Any]]:
    entry_point_manifests = discover_entry_point_manifests() if include_entry_points else ()
    local_plugin_manifests = discover_plugin_path_manifests(
        configured_plugin_paths() if plugin_paths is None else plugin_paths
    )
    return build_module_registry(
        builtin_manifests,
        entry_point_manifests=entry_point_manifests,
        plugin_path_manifests=local_plugin_manifests,
    )
