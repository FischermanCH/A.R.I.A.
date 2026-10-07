from __future__ import annotations

from pathlib import Path

from aria.modules import MODULE_MANIFESTS


ROOT = Path(__file__).resolve().parents[1]


def test_dead_pre_public_modules_are_removed_from_code_and_registry() -> None:
    removed = {
        "ssh_resolution",
        "auto_memory",
        "agentic_content_access",
        "agentic_content_access_registry",
    }

    assert removed.isdisjoint(MODULE_MANIFESTS)
    for module_id in removed:
        assert not (ROOT / "aria" / "modules" / module_id).exists()

    pipeline_source = (ROOT / "aria" / "modules" / "pipeline_orchestrator" / "pipeline.py").read_text(
        encoding="utf-8"
    )
    ssh_helpers_source = (ROOT / "aria" / "modules" / "ssh_runtime" / "pipeline_helpers.py").read_text(
        encoding="utf-8"
    )
    assert "AgenticContentAccessRegistry" not in pipeline_source
    assert "aria.modules.ssh_resolution" not in ssh_helpers_source


def test_public_deployment_surface_has_no_legacy_search_sidecar_dependency() -> None:
    shipped_paths = (
        ROOT / ".env.example",
        ROOT / "aria-setup",
        ROOT / "docker-compose.yml",
        ROOT / "docker-compose.public.yml",
        ROOT / "docker-compose.managed.yml",
        ROOT / "docker" / "portainer-stack.public.yml",
        ROOT / "docker" / "portainer-stack.alpha3.local.yml",
        ROOT / "docker" / "setup-compose-stack.sh",
        ROOT / "docker" / "update-local-aria.sh",
        ROOT / "docker" / "aria-host-update.sh",
        ROOT / "docs" / "release" / "docker-hub-overview.md",
        ROOT / "README.md",
        ROOT / "THIRD_PARTY_NOTICES.md",
    )
    retired_service = "sear" + "xng"
    for path in shipped_paths:
        assert retired_service not in path.read_text(encoding="utf-8").lower(), path

    assert not (ROOT / "docker" / f"{retired_service}.settings.yml").exists()


def test_public_repo_ignore_rules_cover_internal_and_runtime_artifacts() -> None:
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    expected = {
        ".codex/",
        ".claude/",
        ".cache/",
        "test-results/",
        "config/config.yaml",
        "config/secrets.env",
        "data/",
        "*.tar",
        "*.tar.gz",
        ".idea/",
        ".vscode/",
    }
    assert expected.issubset({line.strip() for line in ignore})


def test_live_memory_browser_and_legacy_collection_cleanup_stay_registered() -> None:
    routes = (ROOT / "aria" / "modules" / "memory_admin_ui" / "routes.py").read_text(encoding="utf-8")
    template = (ROOT / "aria" / "templates" / "memories_maintenance.html").read_text(encoding="utf-8")

    assert '@app.get("/memories"' in routes
    assert "/memories/maintenance/cleanup-legacy-learning" in routes
    assert "/memories/maintenance/cleanup-legacy-learning" in template
