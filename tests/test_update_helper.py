from __future__ import annotations

import sys
from pathlib import Path

import pytest

import aria.update_helper as update_helper


def test_managed_target_image_prefers_install_env(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".env").write_text("ARIA_IMAGE=fischermanch/aria:0.1.0-alpha108\n", encoding="utf-8")
    monkeypatch.setattr(update_helper, "INSTALL_DIR", tmp_path)

    assert update_helper._managed_target_image() == "fischermanch/aria:0.1.0-alpha108"


def test_refresh_managed_stack_files_from_target_image_uses_target_image(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".env").write_text("ARIA_IMAGE=fischermanch/aria:0.1.0-alpha108\n", encoding="utf-8")
    monkeypatch.setattr(update_helper, "INSTALL_DIR", tmp_path)

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
