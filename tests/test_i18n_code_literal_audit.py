from __future__ import annotations

import ast
import importlib.util
import subprocess
import sys
from pathlib import Path


def _load_audit_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "audit_i18n_code_literals.py"
    spec = importlib.util.spec_from_file_location("audit_i18n_code_literals", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


audit = _load_audit_module()


def test_i18n_code_literal_audit_current_runtime_has_no_findings() -> None:
    assert audit.audit_python_files() == []


def test_i18n_code_literal_audit_strict_cli_passes_current_runtime() -> None:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "audit_i18n_code_literals.py"

    result = subprocess.run(
        [sys.executable, str(script_path), "--strict"],
        check=False,
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Strict mode passed" in result.stdout


def test_i18n_code_literal_audit_classifies_german_runtime_literal(tmp_path: Path) -> None:
    sample = tmp_path / "sample.py"
    sample.write_text('MESSAGE = "Verbindung fehlgeschlagen"\n', encoding="utf-8")

    tree = ast.parse(sample.read_text(encoding="utf-8"))
    parents = audit.parent_map(tree)
    constant = next(node for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str))

    assert audit.classify(sample, constant, parents) == "raw_runtime_literal"


def test_i18n_code_literal_audit_classifies_german_regex_as_input_lexicon(tmp_path: Path) -> None:
    sample = tmp_path / "sample.py"
    sample.write_text('PATTERN = r"^(?:öffne|zeige)\\s+(.+)$"\n', encoding="utf-8")

    tree = ast.parse(sample.read_text(encoding="utf-8"))
    parents = audit.parent_map(tree)
    constant = next(node for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str))

    assert audit.classify(sample, constant, parents) == "input_lexicon"
