from __future__ import annotations

import json
from pathlib import Path

from aria.core.i18n import I18NStore


def test_i18n_store_reads_flat_dotted_keys(tmp_path: Path) -> None:
    path = tmp_path / "de.json"
    path.write_text(json.dumps({"stats.preflight_title": "Startprüfung"}), encoding="utf-8")

    store = I18NStore(tmp_path)

    assert store.t("de", "stats.preflight_title", "fallback") == "Startprüfung"


def test_i18n_store_keeps_nested_lookup_support(tmp_path: Path) -> None:
    path = tmp_path / "de.json"
    path.write_text(json.dumps({"stats": {"preflight_title": "Startprüfung"}}), encoding="utf-8")

    store = I18NStore(tmp_path)

    assert store.t("de", "stats.preflight_title", "fallback") == "Startprüfung"
