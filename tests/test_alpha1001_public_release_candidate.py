from __future__ import annotations

import asyncio
import json
from pathlib import Path
import subprocess
import time
from types import SimpleNamespace

from aria.modules.recipe_runtime.pipeline_helpers import PipelineRecipeHelpersMixin
from aria.modules.release_update.release_meta import read_release_meta


ROOT = Path(__file__).resolve().parents[1]


class _RecipePipeline(PipelineRecipeHelpersMixin):
    def __init__(self, root: Path) -> None:
        self._stored_recipes_dir = root / "data" / "recipes"
        self._config_path = root / "config" / "config.yaml"
        self._stored_recipe_cache: dict[str, object] = {
            "sign": None,
            "rows": [],
            "ready": False,
        }


def _write_recipes(root: Path, count: int = 160) -> None:
    recipes = root / "data" / "recipes"
    recipes.mkdir(parents=True)
    config = root / "config" / "config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text("skills: {}\n", encoding="utf-8")
    for index in range(count):
        (recipes / f"recipe-{index:03d}.json").write_text(
            json.dumps({
                "id": f"recipe-{index:03d}",
                "name": f"Recipe {index:03d}",
                "steps": [{"type": "ssh_run", "params": {"command": "true"}}],
            }),
            encoding="utf-8",
        )


def test_recipe_turn_snapshot_does_not_touch_slow_persistent_storage(
    monkeypatch, tmp_path: Path,
) -> None:
    _write_recipes(tmp_path)
    pipeline = _RecipePipeline(tmp_path)
    rows = pipeline._refresh_stored_recipe_runtime()
    assert len(rows) == 160

    touches = 0
    original_stat = Path.stat

    def slow_stat(path: Path, *args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        nonlocal touches
        if path.parent == pipeline._stored_recipes_dir:
            touches += 1
            time.sleep(0.025)
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", slow_stat)
    started = time.perf_counter()
    snapshot = pipeline._stored_recipe_runtime_snapshot()
    elapsed = time.perf_counter() - started

    assert len(snapshot) == 160
    assert touches == 0
    assert elapsed < 0.05


def test_recipe_startup_warmup_is_background_bounded_and_provider_free() -> None:
    from aria.main import _schedule_recipe_startup_warmup

    class _SlowPipeline:
        def __init__(self) -> None:
            self.provider_calls = 0
            self.embedding_calls = 0

        def _refresh_stored_recipe_runtime(self):  # noqa: ANN202
            time.sleep(0.35)
            return [{"id": "daily-check"}]

        def _stored_recipe_runtime_snapshot(self):  # noqa: ANN202
            return [{"id": "daily-check"}]

    async def scenario() -> None:
        pipeline = _SlowPipeline()
        started = time.perf_counter()
        task = _schedule_recipe_startup_warmup(pipeline)
        assert task is not None
        assert time.perf_counter() - started < 0.05
        assert pipeline._native_recipe_warmup_task is task
        await task
        assert pipeline._native_recipe_warmup == {
            "loaded": 1,
            "cold_ms": pipeline._native_recipe_warmup["cold_ms"],
            "warm_ms": pipeline._native_recipe_warmup["warm_ms"],
            "provider_calls": 0,
            "embedding_calls": 0,
        }

    asyncio.run(scenario())


def test_journal_default_period_hides_custom_dates() -> None:
    source = (ROOT / "aria/templates/activity_journal.html").read_text(encoding="utf-8")
    assert 'id="journal-period"' in source
    assert '<option value="all"' in source
    assert 'id="journal-custom-range"' in source
    assert 'id="journal-since" type="date" name="since" autocomplete="off"' in source
    assert 'id="journal-until" type="date" name="until" autocomplete="off"' in source
    assert '{% if filters.since %} value="{{ filters.since|e }}"{% endif %}' in source
    assert '{% if filters.until %} value="{{ filters.until|e }}"{% endif %}' in source
    assert "toggleCustomRange" in source
    assert "input.required = custom" in source


def test_alpha1002_release_candidate_metadata_and_public_pin() -> None:
    meta = read_release_meta(ROOT)
    assert meta["label"] == "0.1.0-alpha1007"
    assert 'version = "0.1.0-alpha1007"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").startswith(
        "# Changelog\n\n## 0.1.0-alpha1007"
    )
    assert (ROOT / "CHANGELOG.de.md").read_text(encoding="utf-8").startswith(
        "# Changelog\n\n## 0.1.0-alpha1007"
    )
    assert meta["version"] == "0.1.0"
    public_stack = (ROOT / "docker-compose.public.yml").read_text(encoding="utf-8")
    assert "0.1.0-alpha.1007" not in public_stack


def test_public_release_documents_and_screenshot_directories_exist() -> None:
    required = (
        ROOT / "docs/release/github-release-v0.1.0-alpha.1007.md",
        ROOT / "docs/release/publish-runbook-alpha1006.md",
        ROOT / "docs/release/public-release-summary-alpha1006.md",
        ROOT / "docs/assets/screenshots/de",
        ROOT / "docs/assets/screenshots/en",
        ROOT / "scripts/release/capture_public_screenshots.py",
        ROOT / "scripts/release/check_public_candidate.py",
    )
    assert all(path.exists() for path in required)


def test_public_upgrade_harness_supports_604_and_983_sources() -> None:
    source = (ROOT / "scripts/e2e/upgrade_604.sh").read_text(encoding="utf-8")
    assert "ARIA_E2E_UPGRADE_SOURCE_IMAGE" in source
    assert "fischermanch/aria:0.1.0-alpha.604" in source
    assert "upgrade-${SOURCE_LABEL}-to-${TARGET_LABEL}.json" in source


def test_publish_candidate_has_no_concrete_private_host_or_path_literals() -> None:
    tracked = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True,
    ).stdout.split(b"\0")
    forbidden = (b"172.31.", b".example.lan", b"/home/fischerman", b"/Users/")
    offenders: list[str] = []
    for raw in tracked:
        if not raw:
            continue
        path = ROOT / raw.decode("utf-8", "surrogateescape")
        if not path.is_file():
            continue
        data = path.read_bytes()
        if any(token in data for token in forbidden):
            offenders.append(path.relative_to(ROOT).as_posix())
    assert offenders == []
