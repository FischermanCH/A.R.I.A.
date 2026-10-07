from __future__ import annotations

from pathlib import Path

from aria.modules.loader import build_module_registry
from aria.modules.loader import configured_plugin_paths
from aria.modules.loader import discover_plugin_path_manifests


def _manifest(module_id: str) -> dict[str, object]:
    return {
        "id": module_id,
        "name": module_id.replace("_", " ").title(),
        "status": "loaded",
        "lifecycle": "declarative_runtime",
        "risk": "low",
        "description": "External reference module fixture.",
        "python": [f"aria/modules/{module_id}/manifest.py"],
        "tests": ["tests/test_module_loader.py"],
        "depends_on": [],
        "external_boundaries": [],
        "explicitly_excluded": [],
        "acceptance": ".codex/aria_acceptance/module-dispatch-confidence-authority-alpha818.json",
        "build_allowed": False,
        "runtime_access_allowed": False,
    }


def test_module_registry_can_be_built_from_injected_external_manifest() -> None:
    registry = build_module_registry(entry_point_manifests=[_manifest("external_reference")])

    assert registry["external_reference"]["id"] == "external_reference"


def test_configured_plugin_paths_uses_path_separator() -> None:
    paths = configured_plugin_paths(f"/tmp/one{__import__('os').pathsep}/tmp/two")

    assert paths == (Path("/tmp/one"), Path("/tmp/two"))


def test_plugin_path_manifest_loads_without_core_registry_edit(tmp_path: Path) -> None:
    module_dir = tmp_path / "reference_echo"
    module_dir.mkdir()
    (module_dir / "manifest.py").write_text(
        "MODULE_MANIFEST = {\n"
        "  'id': 'reference_echo',\n"
        "  'name': 'Reference Echo',\n"
        "  'status': 'loaded',\n"
        "  'lifecycle': 'declarative_runtime',\n"
        "  'risk': 'low',\n"
        "  'description': 'External reference module fixture.',\n"
        "  'python': ['aria/modules/reference_echo/manifest.py'],\n"
        "  'tests': ['tests/test_module_loader.py'],\n"
        "  'depends_on': [],\n"
        "  'external_boundaries': [],\n"
        "  'explicitly_excluded': [],\n"
        "  'acceptance': '.codex/aria_acceptance/module-dispatch-confidence-authority-alpha818.json',\n"
        "  'build_allowed': False,\n"
        "  'runtime_access_allowed': False,\n"
        "}\n",
        encoding="utf-8",
    )

    manifests = discover_plugin_path_manifests((tmp_path,))
    registry = build_module_registry(plugin_path_manifests=manifests)

    assert registry["reference_echo"]["id"] == "reference_echo"
