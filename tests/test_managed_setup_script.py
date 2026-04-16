from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SETUP_SCRIPT = REPO_ROOT / "docker" / "setup-compose-stack.sh"


def _write_fake_docker(bin_dir: Path) -> None:
    target = bin_dir / "docker"
    target.write_text(
        """#!/usr/bin/env bash
set -e

if [[ "$1" == "compose" && "${2:-}" == "version" ]]; then
  exit 0
fi

if [[ "$1" == "compose" ]]; then
  shift
  while [[ "$#" -gt 0 ]]; do
    case "$1" in
      --env-file|-f)
        shift 2
        ;;
      config)
        exit 0
        ;;
      *)
        shift
        ;;
    esac
  done
  exit 0
fi

exit 0
""",
        encoding="utf-8",
    )
    target.chmod(target.stat().st_mode | stat.S_IEXEC)


def test_managed_setup_writes_repair_capable_stack_helper(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir(parents=True, exist_ok=True)
    _write_fake_docker(fake_bin)

    install_dir = tmp_path / "managed"
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env['PATH']}"

    subprocess.run(
        [
            str(SETUP_SCRIPT),
            "--install-dir",
            str(install_dir),
            "--stack-name",
            "white-aria-managed",
            "--http-port",
            "8810",
            "--public-url",
            "http://aria.black.lan:8810",
            "--force",
            "--no-start",
        ],
        check=True,
        cwd=str(REPO_ROOT),
        env=env,
    )

    helper_text = (install_dir / "aria-stack.sh").read_text(encoding="utf-8")
    install_text = (install_dir / "INSTALL.txt").read_text(encoding="utf-8")

    assert "./aria-stack.sh repair" in helper_text
    assert 'validate_file_sync "Config-Sync-Check"' in helper_text
    assert 'validate_file_sync "Prompts-Sync-Check"' in helper_text
    assert "Data-Sync-Check fehlgeschlagen" in helper_text
    assert 'validate_mount_binding "Config-Mount-Check"' in helper_text
    assert 'validate_mount_binding "Prompts-Mount-Check"' in helper_text
    assert 'validate_mount_binding "Data-Mount-Check"' in helper_text
    assert 'docker run --rm -v "$STACK_DIR:/managed"' in helper_text
    assert "./aria-stack.sh repair" in install_text
