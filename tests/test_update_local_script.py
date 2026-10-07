from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "docker" / "update-local-aria.sh"


def _script_text() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_local_update_uses_one_shared_health_deadline() -> None:
    text = _script_text()

    assert 'HEALTH_TIMEOUT_SECONDS="${ARIA_UPDATE_HEALTH_TIMEOUT_SECONDS:-300}"' in text
    assert "wait_for_aria_health" in text
    assert "wait_for_host_health" not in text
    assert "wait_for_container_health" not in text
    assert "container_health_ok || host_health_ok" in text


def test_local_update_fails_fast_for_terminal_or_restarting_container() -> None:
    text = _script_text()

    assert "exited|dead|missing" in text
    assert "restarting_checks >= 5" in text
    assert "container_state_snapshot" in text


def test_local_update_prints_failure_context() -> None:
    text = _script_text()

    assert "print_aria_failure_context" in text
    assert 'docker logs --tail 120 "$SERVICE_NAME"' in text
    assert "State.ExitCode" in text


def test_local_update_recreates_aria_only_and_leaves_sidecars_untouched() -> None:
    text = _script_text()

    aria_recreate = (
        'compose_cmd "${COMPOSE_ARGS[@]}" -f "$STACK_FILE" '
        'up -d --no-deps --force-recreate "$SERVICE_NAME"'
    )
    assert aria_recreate in text
    update_tail = text[text.index("COMPOSE_ARGS=()") : text.index("Pruefe ARIA-Health")]
    compose_lines = [line for line in update_tail.splitlines() if line.startswith("compose_cmd ")]
    assert compose_lines == [aria_recreate]
    assert all("qdrant" not in line.lower() for line in compose_lines)
    assert all("searxng" not in line.lower() for line in compose_lines)
    assert all("searxng-valkey" not in line for line in compose_lines)
