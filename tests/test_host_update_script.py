from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
HOST_UPDATE_SCRIPT = REPO_ROOT / "docker" / "aria-host-update.sh"


def test_host_update_supports_safe_target_image_refresh() -> None:
    script = HOST_UPDATE_SCRIPT.read_text(encoding="utf-8")

    assert "--target-image IMG" in script
    assert "target_image=" in script
    assert 'export ARIA_IMAGE="$target_image"' in script
    assert "persist_env_value \"$env_file\" ARIA_IMAGE \"$target_image\"" in script
    assert "refresh_managed_stack_files" in script
    assert "setup-compose-stack.sh --install-dir /managed --upgrade-existing --force --no-start" in script
    assert "chown ${owner}" in script
    assert "run_compose_recreate" in script
    assert "Qdrant, SearXNG und Volumes bleiben unberuehrt" in script


def test_host_update_lock_cleanup_uses_global_lock_path() -> None:
    script = HOST_UPDATE_SCRIPT.read_text(encoding="utf-8")

    assert 'HOST_UPDATE_LOCK_DIR=""' in script
    assert 'HOST_UPDATE_LOCK_DIR="$lock_dir"' in script
    assert 'trap \'rm -rf "${HOST_UPDATE_LOCK_DIR:-}"\' EXIT' in script


def test_host_update_preflights_host_ports_before_recreate() -> None:
    script = HOST_UPDATE_SCRIPT.read_text(encoding="utf-8")

    assert "compose_service_published_tcp_ports" in script
    assert "host_tcp_port_available" in script
    assert "validate_host_ports_before_recreate" in script
    assert "Host-Port $desired_port ist bereits belegt" in script
    assert "validate_host_ports_before_recreate \"$project\" \"$stack_file\" \"$env_file\" \"$DEFAULT_SERVICE_NAME\" \"$aria_container\"" in script
    assert script.index("validate_host_ports_before_recreate") < script.index("run_compose_recreate \"$project\"")
