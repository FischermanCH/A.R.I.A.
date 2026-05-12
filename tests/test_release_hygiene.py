from __future__ import annotations

import json
import re
from pathlib import Path

from aria.core.release_meta import DEFAULT_RELEASE_LABEL


ROOT = Path(__file__).resolve().parents[1]


def test_gitignore_blocks_generated_packaging_outputs() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()

    for pattern in {"*.egg-info/", "build/", "dist/", "*.whl"}:
        assert pattern in gitignore


def test_release_label_matches_current_alpha_backlog_build() -> None:
    backlog = (ROOT / "docs" / "backlog" / "alpha-backlog.md").read_text(encoding="utf-8")
    match = re.search(r"aktuell gebaut: `([^`]+)`", backlog)

    assert match is not None
    assert DEFAULT_RELEASE_LABEL == match.group(1)


def test_source_runtime_assets_are_present_for_container_builds() -> None:
    required_files = [
        ROOT / "prompts" / "persona.md",
        ROOT / "prompts" / "recipes" / "memory.md",
        ROOT / "prompts" / "recipes" / "memory_compress.md",
        ROOT / "samples" / "recipes" / "ssh-healthcheck-template.json",
        ROOT / "samples" / "security" / "guardrails.sample.yaml",
        ROOT / "config" / "config.example.yaml",
        ROOT / "config" / "secrets.env.example",
    ]

    missing = [path.relative_to(ROOT).as_posix() for path in required_files if not path.exists()]

    assert missing == []


def test_sample_recipe_manifests_are_recipe_first() -> None:
    sample_dir = ROOT / "samples" / "recipes"
    manifests = sorted(sample_dir.glob("*.json"))

    assert manifests
    for path in manifests:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(payload, dict), path.name
        assert str(payload.get("id", "")).strip(), path.name
        assert str(payload.get("name", "")).strip(), path.name
        prompt_file = str(payload.get("prompt_file", "") or "").strip()
        if prompt_file:
            assert prompt_file.startswith("prompts/recipes/"), path.name
