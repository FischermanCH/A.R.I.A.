from __future__ import annotations

from pathlib import Path
from fnmatch import fnmatch
import tomllib


def test_setuptools_package_data_includes_runtime_assets() -> None:
    config = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    package_data = config["tool"]["setuptools"]["package-data"]["aria"]

    expected_patterns = {
        "i18n/*.json",
        "lexicons/*.json",
        "static/*",
        "static/vendor/*",
        "templates/*.html",
    }
    assert expected_patterns.issubset(set(package_data))


def test_setuptools_package_data_covers_current_runtime_assets() -> None:
    config = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    package_data = config["tool"]["setuptools"]["package-data"]["aria"]
    asset_roots = [
        Path("aria/i18n"),
        Path("aria/lexicons"),
        Path("aria/templates"),
        Path("aria/static"),
    ]

    uncovered: list[str] = []
    for root in asset_roots:
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to("aria").as_posix()
            if not any(fnmatch(relative, pattern) for pattern in package_data):
                uncovered.append(relative)

    assert uncovered == []


def test_workbench_surface_links_to_llm_prompt_debug() -> None:
    template = Path("aria/templates/_config_workbench_section.html").read_text(encoding="utf-8")

    assert "/config/llm/debug" in template
    assert "llm_debug.title" in template
    assert "llm_debug.menu_desc" in template
