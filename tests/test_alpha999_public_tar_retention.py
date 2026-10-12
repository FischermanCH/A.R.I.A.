from __future__ import annotations

import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def test_export_retention_permanently_preserves_public_release_tars(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    for version in (604, 982, 983, 990, 991, 992, 993, 994, 995, 996, 997, 998, 999, 1000):
        (artifact_dir / f"aria-alpha{version}-local.tar").write_text(
            f"fixture-{version}", encoding="utf-8"
        )

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker = bin_dir / "docker"
    docker.write_text(
        """#!/usr/bin/env bash
set -e
if [[ "$1 $2" == "image inspect" ]]; then exit 0; fi
if [[ "$1" == "save" && "$2" == "-o" ]]; then
  printf 'exported-%s' "$4" > "$3"
  exit 0
fi
exit 1
""",
        encoding="utf-8",
    )
    docker.chmod(0o755)

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{bin_dir}:{env['PATH']}",
            "ARTIFACT_DIR": str(artifact_dir),
            "IMAGE_REF": "fischermanch/aria:0.1.0-alpha.1003",
            "KEEP_TARS": "2",
            "SAMPLES_DIR": str(tmp_path / "missing-samples"),
            "DOCKER_HELPER_DIR": str(tmp_path / "missing-helpers"),
            "FALLBACK_ARTIFACT_DIR": str(tmp_path / "fallback"),
        }
    )
    subprocess.run(
        ["bash", str(ROOT / "docker/export-local-build.sh")],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    retained = {
        path.name
        for path in artifact_dir.glob("aria-alpha*-local.tar")
        if path.name != "aria-alpha-local.tar"
    }
    assert retained == {
        "aria-alpha604-local.tar",
        "aria-alpha982-local.tar",
        "aria-alpha983-local.tar",
        "aria-alpha1000-local.tar",
        "aria-alpha1003-local.tar",
    }
