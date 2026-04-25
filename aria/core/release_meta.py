from __future__ import annotations

from importlib import metadata
import os
import tomllib
from pathlib import Path

DEFAULT_RELEASE_LABEL = "0.1.0-alpha167"


def _read_installed_package_version(default: str = "0.1.0") -> str:
    try:
        return str(metadata.version("aria-agent") or default).strip() or default
    except metadata.PackageNotFoundError:
        return default
    except Exception:
        return default


def _version_from_release_label(release_label: str) -> str:
    text = str(release_label or "").strip()
    if not text:
        return ""
    return text.split("-", 1)[0].strip()


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

    release_label = str(os.getenv("ARIA_RELEASE_LABEL", "") or "").strip() or DEFAULT_RELEASE_LABEL
    version_from_label = _version_from_release_label(release_label)
    if version_from_label:
        version = version_from_label

    return {
        "version": version,
        "label": release_label,
    }
