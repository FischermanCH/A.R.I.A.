from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


PUBLIC_UPGRADE_DOCS = [
    ROOT / "README.md",
    ROOT / "docs/wiki/Releases-and-Upgrades.md",
    ROOT / "docs/wiki/Releases-and-Upgrades.de.md",
    ROOT / "docs/setup/setup-overview.md",
    ROOT / "docs/release/docker-hub-overview.md",
    ROOT / "docs/release/alpha981-upgrade-note.md",
]


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_public_upgrade_docs_use_provider_native_websearch_guidance() -> None:
    combined = "\n".join(_text(path) for path in PUBLIC_UPGRADE_DOCS[:-1])

    assert "provider" in combined.lower()
    assert "web" in combined.lower()


def test_public_upgrade_docs_describe_provider_web_tooling_transition() -> None:
    readme = _text(ROOT / "README.md")
    changelog = _text(ROOT / "CHANGELOG.md")
    setup_overview = _text(ROOT / "docs/setup/setup-overview.md")
    docker_hub_overview = _text(ROOT / "docs/release/docker-hub-overview.md")

    assert "0.1.0-alpha604" in readme
    assert "0.1.0-alpha808" in changelog
    assert "major architecture upgrade" in changelog
    assert "major ARIA architecture upgrade" in docker_hub_overview
    assert "not the same internal shape as the last public Docker Hub alpha" in docker_hub_overview
    assert "monolith-style alpha line to a modular ARIA runtime" in docker_hub_overview
    assert "provider web tooling or managed web-search capability" in setup_overview
    assert "provider-native Web-LLM" in readme


def test_normal_update_scripts_recreate_aria_only() -> None:
    setup_script = _text(ROOT / "docker/setup-compose-stack.sh")
    local_update = _text(ROOT / "docker/update-local-aria.sh")
    host_update = _text(ROOT / "docker/aria-host-update.sh")

    managed_update_branch = setup_script.split("    update)", 1)[1].split("    update-all)", 1)[0]
    assert "run_compose up -d --no-deps --force-recreate aria" in managed_update_branch

    assert 'up -d --no-deps --force-recreate "$SERVICE_NAME"' in local_update
    assert "Qdrant und Volumes bleiben unberuehrt" in local_update

    assert 'run_compose_recreate "$project" "$stack_file" "$env_file" "$DEFAULT_SERVICE_NAME"' in host_update
    assert "nur ARIA neu erstellen" in host_update
