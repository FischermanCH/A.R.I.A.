from __future__ import annotations

import importlib
from pathlib import Path
import re
import sys

from aria.modules.pipeline_orchestrator import pipeline as canonical_pipeline


def test_pipeline_canonical_module_identity_is_stable() -> None:
    assert importlib.import_module("aria.modules.pipeline_orchestrator.pipeline") is canonical_pipeline


def test_pipeline_canonical_module_registers_itself() -> None:
    assert sys.modules["aria.modules.pipeline_orchestrator.pipeline"] is canonical_pipeline
    assert not hasattr(canonical_pipeline, "PipelineLearningHelpersMixin")
    assert all(base.__name__ != "PipelineLearningHelpersMixin" for base in canonical_pipeline.Pipeline.__mro__)


def test_production_code_uses_canonical_pipeline_import() -> None:
    blocked_import = re.compile(r"^(?:from|import)\s+aria\.core\.pipeline(?:\s|$)", re.MULTILINE)
    alias = Path("aria/core/pipeline.py")
    offenders: list[str] = []

    for path in sorted(Path("aria").rglob("*.py")):
        if path == alias:
            continue
        if blocked_import.search(path.read_text(encoding="utf-8")):
            offenders.append(str(path))

    assert offenders == []


def test_pipeline_relative_roots_survive_move() -> None:
    repository_root = Path(__file__).resolve().parents[1]

    assert canonical_pipeline._PIPELINE_I18N.base_dir == repository_root / "aria" / "i18n"
    source = Path(canonical_pipeline.__file__).read_text(encoding="utf-8")
    assert "Path(__file__).resolve().parents[3]" in source
