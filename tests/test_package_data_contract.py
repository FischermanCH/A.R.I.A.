from __future__ import annotations

from pathlib import Path
from fnmatch import fnmatch
import tomllib


def test_setuptools_package_data_includes_runtime_assets() -> None:
    config = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    package_data = config["tool"]["setuptools"]["package-data"]["aria"]

    expected_patterns = {
        "contracts/*.json",
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
        Path("aria/contracts"),
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


def test_config_hub_exposes_llm_prompt_debug_directly() -> None:
    template = Path("aria/templates/config_hub.html").read_text(encoding="utf-8")

    assert "config_hub_groups(request)" in template
