from __future__ import annotations

from importlib import metadata
import os
import tomllib
from pathlib import Path


DEFAULT_RELEASE_SUFFIX = "alpha108"


def _read_installed_package_version(default: str = "0.1.0") -> str:
    try:
        return str(metadata.version("aria-agent") or default).strip() or default
    except metadata.PackageNotFoundError:
        return default
    except Exception:
        return default


def read_release_meta(base_dir: Path) -> dict[str, str]:
    version = _read_installed_package_version()
    try:
        pyproject = base_dir / "pyproject.toml"
        payload = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        project = payload.get("project", {})
        if isinstance(project, dict):
            version = str(project.get("version", version) or version).strip() or version
    except Exception:
        pass

    release_label = str(os.getenv("ARIA_RELEASE_LABEL", "") or "").strip()
    if not release_label:
        release_label = f"{version}-{DEFAULT_RELEASE_SUFFIX}"

    return {
        "version": version,
        "label": release_label,
    }
