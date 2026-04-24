from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import aria.update_helper as update_helper


def test_managed_target_image_prefers_install_env(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".env").write_text("ARIA_IMAGE=fischermanch/aria:0.1.0-alpha108\n", encoding="utf-8")
    monkeypatch.setattr(update_helper, "INSTALL_DIR", tmp_path)

    assert update_helper._managed_target_image() == "fischermanch/aria:0.1.0-alpha108"


def test_refresh_managed_stack_files_from_target_image_uses_target_image(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".env").write_text("ARIA_IMAGE=fischermanch/aria:0.1.0-alpha108\n", encoding="utf-8")
    monkeypatch.setattr(update_helper, "INSTALL_DIR", tmp_path)
    monkeypatch.setattr(update_helper, "_managed_install_host_dir", lambda: str(tmp_path))

    calls: list[tuple[str, list[str]]] = []

    def _capture(command: list[str], *, step: str) -> None:
        calls.append((step, command))

    monkeypatch.setattr(update_helper, "_run_logged", _capture)

    update_helper._refresh_managed_stack_files_from_target_image()

    assert calls == [
        ("Pull ARIA target image for stack refresh", ["docker", "pull", "fischermanch/aria:0.1.0-alpha108"]),
        (
            "Refresh managed stack files",
            [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{tmp_path}:/managed",
                "fischermanch/aria:0.1.0-alpha108",
                "/app/docker/setup-compose-stack.sh",
                "--install-dir",
                "/managed",
                "--upgrade-existing",
                "--force",
                "--no-start",
            ],
        ),
    ]


def test_managed_install_host_dir_prefers_mount_source_from_current_container(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(update_helper, "INSTALL_DIR", Path("/managed"))
    monkeypatch.setenv("HOSTNAME", "abc123")

    inspect_payload = json.dumps(
        [
            {
                "Mounts": [
                    {"Destination": "/other", "Source": "/srv/other"},
                    {"Destination": "/managed", "Source": str(tmp_path)},
                ]
            }
        ]
    )

    def _fake_run(command: list[str], **kwargs):  # noqa: ANN003
        assert command == ["docker", "inspect", "abc123"]
        return SimpleNamespace(returncode=0, stdout=inspect_payload)

    monkeypatch.setattr(update_helper.subprocess, "run", _fake_run)

    assert update_helper._managed_install_host_dir() == str(tmp_path)


def test_managed_update_worker_refreshes_stack_from_target_image_before_compose_pull(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".env").write_text("ARIA_IMAGE=fischermanch/aria:0.1.0-alpha108\n", encoding="utf-8")
    (tmp_path / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    (tmp_path / "aria-stack.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    monkeypatch.setattr(update_helper, "INSTALL_DIR", tmp_path)
    monkeypatch.setattr(update_helper, "LOG_PATH", tmp_path / "update.log")
    monkeypatch.setattr(update_helper, "_compose_base_command", lambda: ["docker", "compose"])
    monkeypatch.setattr(update_helper, "_compose_services", lambda: ["aria"])
    monkeypatch.setattr(update_helper, "_wait_for_health", lambda: None)
    monkeypatch.setattr(update_helper, "_write_log_line", lambda _message: None)
    monkeypatch.setattr(update_helper, "_update_state", lambda **_updates: {})

    steps: list[str] = []

    def _capture(command: list[str], *, step: str) -> None:
        steps.append(step)

    monkeypatch.setattr(update_helper, "_run_logged", _capture)

    update_helper._run_managed_update_worker()

    assert steps == [
        "Pull ARIA target image for stack refresh",
        "Refresh managed stack files",
        "Pull updated images",
        "Recreate updated services",
        "Validate managed services",
    ]


def test_try_refresh_managed_stack_files_logs_warning_and_continues_on_failure(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(update_helper, "INSTALL_DIR", tmp_path)
    monkeypatch.setattr(update_helper, "STATE_DIR", tmp_path / ".aria-updater")
    monkeypatch.setattr(update_helper, "LOG_PATH", tmp_path / "update.log")

    monkeypatch.setattr(
        update_helper,
        "_refresh_managed_stack_files_from_target_image",
        lambda: (_ for _ in ()).throw(RuntimeError("Bestehende Env-Datei nicht gefunden: /managed/.env")),
    )

    result = update_helper._try_refresh_managed_stack_files_from_target_image()

    assert result is False
    log_text = (tmp_path / "update.log").read_text(encoding="utf-8")
    assert "WARNING" in log_text
    assert "vorhandenen Managed-Dateien weiter" in log_text
    assert "Bestehende Env-Datei nicht gefunden" in log_text


def test_managed_update_worker_continues_when_stack_refresh_fails(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".env").write_text("ARIA_IMAGE=fischermanch/aria:0.1.0-alpha108\n", encoding="utf-8")
    (tmp_path / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    (tmp_path / "aria-stack.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    monkeypatch.setattr(update_helper, "INSTALL_DIR", tmp_path)
    monkeypatch.setattr(update_helper, "STATE_DIR", tmp_path / ".aria-updater")
    monkeypatch.setattr(update_helper, "LOG_PATH", tmp_path / "update.log")
    monkeypatch.setattr(update_helper, "_compose_base_command", lambda: ["docker", "compose"])
    monkeypatch.setattr(update_helper, "_compose_services", lambda: ["aria"])
    monkeypatch.setattr(update_helper, "_wait_for_health", lambda: None)
    monkeypatch.setattr(update_helper, "_update_state", lambda **_updates: {})

    steps: list[str] = []

    def _capture(command: list[str], *, step: str) -> None:
        steps.append(step)

    monkeypatch.setattr(
        update_helper,
        "_refresh_managed_stack_files_from_target_image",
        lambda: (_ for _ in ()).throw(RuntimeError("Bestehende Env-Datei nicht gefunden: /managed/.env")),
    )
    monkeypatch.setattr(update_helper, "_run_logged", _capture)

    update_helper._run_managed_update_worker()

    assert steps == [
        "Pull updated images",
        "Recreate updated services",
        "Validate managed services",
    ]
    log_text = (tmp_path / "update.log").read_text(encoding="utf-8")
    assert "WARNING" in log_text


def test_managed_update_worker_repairs_once_when_validate_fails(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".env").write_text("ARIA_IMAGE=fischermanch/aria:0.1.0-alpha108\n", encoding="utf-8")
    (tmp_path / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    (tmp_path / "aria-stack.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    monkeypatch.setattr(update_helper, "INSTALL_DIR", tmp_path)
    monkeypatch.setattr(update_helper, "STATE_DIR", tmp_path / ".aria-updater")
    monkeypatch.setattr(update_helper, "LOG_PATH", tmp_path / "update.log")
    monkeypatch.setattr(update_helper, "_compose_base_command", lambda: ["docker", "compose"])
    monkeypatch.setattr(update_helper, "_compose_services", lambda: ["aria", "qdrant"])
    monkeypatch.setattr(update_helper, "_wait_for_health", lambda: None)

    state_updates: list[dict[str, object]] = []

    def _capture_state(**updates: object) -> dict[str, object]:
        state_updates.append(dict(updates))
        return {}

    monkeypatch.setattr(update_helper, "_update_state", _capture_state)

    calls: list[str] = []

    def _capture(command: list[str], *, step: str) -> None:
        calls.append(step)
        if step == "Validate managed services":
            raise RuntimeError("Validate managed services failed with exit code 1")

    monkeypatch.setattr(update_helper, "_run_logged", _capture)

    update_helper._run_managed_update_worker()

    assert calls == [
        "Pull ARIA target image for stack refresh",
        "Refresh managed stack files",
        "Pull updated images",
        "Recreate updated services",
        "Validate managed services",
        "Repair managed services",
    ]
    assert any(update.get("current_step") == "repair_runtime" for update in state_updates)
    assert any(update.get("last_result") == "Update completed successfully after automatic repair." for update in state_updates)
    log_text = (tmp_path / "update.log").read_text(encoding="utf-8")
    assert "Running one automatic repair attempt" in log_text


def test_reconcile_stale_error_state_resets_status_when_validate_passes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(update_helper, "INSTALL_DIR", tmp_path)
    monkeypatch.setattr(update_helper, "STATE_DIR", tmp_path / ".aria-updater")
    monkeypatch.setattr(update_helper, "STATE_PATH", tmp_path / ".aria-updater" / "state.json")
    monkeypatch.setattr(update_helper, "LOG_PATH", tmp_path / ".aria-updater" / "update.log")
    monkeypatch.setattr(update_helper, "_last_status_reconcile_monotonic", 0.0)
    (tmp_path / "aria-stack.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")

    update_helper._ensure_state_dir()
    update_helper._save_state(
        {
            "status": "error",
            "running": False,
            "current_step": "",
            "last_started_at": "2026-04-24T06:42:16Z",
            "last_finished_at": "2026-04-24T06:42:52Z",
            "last_error": "Validate managed services failed with exit code 1",
            "last_result": "Update failed.",
            "log_path": str(update_helper.LOG_PATH),
            "log_tail": [],
        }
    )

    monkeypatch.setattr(update_helper, "_run_quickcheck", lambda command, timeout_seconds=120.0: (True, "ok"))  # noqa: ARG005

    state = update_helper._reconcile_stale_error_state()

    assert state["status"] == "ok"
    assert state["last_error"] == ""
    assert state["last_result"] == "Managed stack healthy after repair."
    log_text = update_helper.LOG_PATH.read_text(encoding="utf-8")
    assert "Resetting helper status to ok" in log_text


def test_run_logged_includes_last_meaningful_failure_detail(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(update_helper, "INSTALL_DIR", tmp_path)
    monkeypatch.setattr(update_helper, "STATE_DIR", tmp_path)
    monkeypatch.setattr(update_helper, "LOG_PATH", tmp_path / "update.log")

    with pytest.raises(RuntimeError) as excinfo:
        update_helper._run_logged(
            [
                sys.executable,
                "-c",
                (
                    "import sys; "
                    "print('first line'); "
                    "print('[aria-stack] ERROR: Config-Sync-Check fehlgeschlagen', file=sys.stderr); "
                    "sys.exit(7)"
                ),
            ],
            step="Validate managed services",
        )

    assert "exit code 7" in str(excinfo.value)
    assert "[aria-stack] ERROR: Config-Sync-Check fehlgeschlagen" in str(excinfo.value)
