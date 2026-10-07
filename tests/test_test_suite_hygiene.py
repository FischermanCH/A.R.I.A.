from __future__ import annotations

import ast
from pathlib import Path

from aria.modules import MODULE_MANIFESTS


ROOT = Path(__file__).resolve().parents[1]


def _manifest_test_path_exists(test_path: object) -> bool:
    pattern = str(test_path).split("::", 1)[0]
    return any(ROOT.glob(pattern))


def test_tests_do_not_import_one_module_under_multiple_aliases() -> None:
    findings: list[str] = []

    for path in sorted((ROOT / "tests").glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports: dict[str, list[tuple[int, str]]] = {}
        for node in tree.body:
            if not isinstance(node, ast.Import):
                continue
            for alias in node.names:
                imports.setdefault(alias.name, []).append(
                    (node.lineno, alias.asname or alias.name)
                )

        findings.extend(
            f"{path.relative_to(ROOT)}: {module} imported as {aliases}"
            for module, rows in imports.items()
            if len(rows) > 1
            for aliases in [", ".join(alias for _, alias in rows)]
        )

    assert findings == []


def test_manifests_do_not_claim_retired_private_aliases_still_exist() -> None:
    stale_claims = (
        "legacy core path is an identity-preserving compatibility alias",
        "legacy core paths are identity-preserving compatibility aliases",
        "legacy core paths are compatibility module aliases",
    )
    findings = [
        str(path.relative_to(ROOT))
        for path in sorted((ROOT / "aria" / "modules").glob("*/manifest.py"))
        if any(
            claim in path.read_text(encoding="utf-8").lower()
            for claim in stale_claims
        )
    ]

    assert findings == []


def test_manifest_test_evidence_paths_exist() -> None:
    findings = [
        f"{module_id}: {test_path}"
        for module_id, manifest in sorted(MODULE_MANIFESTS.items())
        for test_path in manifest.get("tests", ())
        if not _manifest_test_path_exists(test_path)
    ]

    assert findings == []
