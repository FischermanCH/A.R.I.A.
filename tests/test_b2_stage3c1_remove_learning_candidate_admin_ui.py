from pathlib import Path

from aria.modules import MODULE_MANIFESTS, module_route_path, module_template_name


ROOT = Path(__file__).resolve().parents[1]
ROUTES = ROOT / "aria/modules/memory_admin_ui/routes.py"
PREVIEW = ROOT / "aria/templates/memories_learning_candidate_apply_preview.html"

RETIRED_ROUTES = {
    "/memories/learning-candidate/status",
    "/memories/learning-candidate/apply",
    "/memories/learning-candidate/apply-preview",
    "/memories/learning-candidate/regression",
    "/memories/learning-candidate/pytest/prepare-write",
    "/memories/learning-candidate/artifact/review",
    "/memories/learning-candidate/regression/verify",
    "/memories/learning-candidate/regression/run",
    "/memories/learning-candidate/activation-preflight",
    "/memories/learning-candidate/activate",
}


def test_memory_admin_has_no_learning_candidate_admin_routes() -> None:
    source = ROUTES.read_text(encoding="utf-8")

    for route in RETIRED_ROUTES:
        assert route not in source
        assert module_route_path("memory_admin_ui", route) is None


def test_memory_admin_has_no_learning_ring_imports_or_dependencies() -> None:
    source = ROUTES.read_text(encoding="utf-8")
    manifest = MODULE_MANIFESTS["memory_admin_ui"]

    assert "aria.modules.learning_candidates" not in source
    assert "aria.modules.learning_artifacts" not in source
    assert "aria.modules.prepared_artifacts" not in source
    assert not {"learning_candidates", "learning_artifacts", "prepared_artifacts"} & set(manifest["depends_on"])


def test_learning_candidate_and_artifact_importers_are_confined_to_dead_ring() -> None:
    allowed_roots = {
        "learning_artifacts",
        "learning_candidates",
        "learning_feedback",
        "learning_runtime",
        "prepared_artifacts",
        "recipe_learning",
    }
    retained_importers: list[str] = []
    modules_root = ROOT / "aria/modules"
    for path in modules_root.rglob("*.py"):
        relative = path.relative_to(modules_root)
        if relative.as_posix() == "registry.py" or relative.parts[0] in allowed_roots:
            continue
        source = path.read_text(encoding="utf-8")
        if "aria.modules.learning_candidates" in source or "aria.modules.learning_artifacts" in source:
            retained_importers.append(relative.as_posix())

    assert retained_importers == []


def test_learning_candidate_preview_template_is_removed() -> None:
    assert not PREVIEW.exists()
    assert module_template_name("memory_admin_ui", PREVIEW.name) is None


def test_core_memory_admin_surfaces_remain_registered() -> None:
    manifest = MODULE_MANIFESTS["memory_admin_ui"]

    assert module_route_path("memory_admin_ui", "/memories") == "/memories"
    assert module_route_path("memory_admin_ui", "/memories/auto-memory") == "/memories/auto-memory"
    assert module_route_path("memory_admin_ui", "/memories/auto-memory/claim-action") == "/memories/auto-memory/claim-action"
    assert module_route_path("memory_admin_ui", "/memories/auto-memory/candidate-action") is None
    assert "memories_overview.html" in manifest["templates"]
    assert "memories_auto_memory.html" in manifest["templates"]


def test_learning_ring_modules_are_removed_by_stage3c2() -> None:
    assert not {"learning_artifacts", "learning_candidates", "prepared_artifacts"} & set(MODULE_MANIFESTS)
