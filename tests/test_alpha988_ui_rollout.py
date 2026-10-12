from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_connection_clarity_composition_is_shared_by_ssh_and_webhook() -> None:
    shared = (ROOT / "aria/templates/_connection_clarity.html").read_text(encoding="utf-8")
    ssh = (ROOT / "aria/templates/config_connections_ssh.html").read_text(encoding="utf-8")
    webhook = (ROOT / "aria/templates/config_connections_webhook.html").read_text(encoding="utf-8")

    for macro in (
        "connection_inventory",
        "connection_settings",
        "connection_test_action",
        "connection_danger_zone",
    ):
        assert f"macro {macro}" in shared
        assert macro in ssh
        assert macro in webhook
    assert "data-ui-pattern=\"info\"" not in shared or "<button" not in shared.split(
        'data-ui-pattern="info"', 1
    )[-1].split("endmacro", 1)[0]


def test_migrated_connection_templates_preserve_form_contracts() -> None:
    ssh = (ROOT / "aria/templates/config_connections_ssh.html").read_text(encoding="utf-8")
    webhook = (ROOT / "aria/templates/config_connections_webhook.html").read_text(encoding="utf-8")

    assert 'name="original_ref" value="{{ selected_ref }}"' in ssh
    assert 'name="original_ref" value=""' in ssh
    assert 'name="run_key_exchange" value="1"' in ssh
    assert "ssh_key_exchange_path" in ssh and "ssh_keygen_path" in ssh
    assert "ssh_test_path" in ssh
    assert "_connection_delete_inline.html" in ssh

    assert 'name="original_ref" value="{{ selected_webhook_ref }}"' in webhook
    assert 'name="original_ref" value=""' in webhook
    assert "webhook_test_path" in webhook
    assert "_connection_delete_inline.html" in webhook


def test_german_catalog_has_no_reviewed_ascii_transliterations() -> None:
    catalog = json.loads((ROOT / "aria/i18n/de.json").read_text(encoding="utf-8"))
    values: list[str] = []

    def collect(node: object) -> None:
        if isinstance(node, str):
            values.append(node)
        elif isinstance(node, dict):
            for value in node.values():
                collect(value)
        elif isinstance(node, list):
            for value in node:
                collect(value)

    collect(catalog)
    allowed = {
        "access", "adresse", "adressen", "aes", "aktuell", "aktuelle", "aktuellem", "aktuellen", "aktueller",
        "aktuelles", "aktuellster", "aufbauen", "baue", "bauen", "bauer", "blue", "css", "dass", "dauer", "dauerhaft", "dauerhafte",
        "dauerhaftes", "flusss", "issues", "manuell", "manuelle", "manuellen", "manueller",
        "manuelles", "muss", "müssen", "neue", "neuem", "neuen", "neuer", "neues", "neueste",
        "neuest", "neuesten", "neuester", "neuerer", "neueingabe", "prozess", "quelle", "quellen", "preisquellen", "quellenauftrag", "quellenbasis", "quellenname", "query", "queue", "request",
        "requested", "requests", "rss", "sequence", "steuerst", "steuerung", "steuern",
        "success", "value", "values", "vertrauen", "zuerst", "dauern", "genauer", "gesteuert", "lernquelle", "sequenz", "steuert", "visueller", "webquelle",
    }
    suspicious: set[str] = set()
    ascii_ss_words = {
        "ausser", "ausserhalb", "ausschliesslich", "gross", "grosse", "grossen",
        "heisst", "schliesst", "stösst", "anstossen",
    }
    for value in values:
        for token in re.findall(r"[A-Za-zÄÖÜäöüß]+", value):
            word = token.casefold()
            if word in allowed:
                continue
            if any(part in word for part in ("ae", "oe", "ue")) or token.lower() in ascii_ss_words:
                suspicious.add(token)
    assert sorted(suspicious, key=str.casefold) == []


def test_backup_and_logs_polish_contract() -> None:
    backup = (ROOT / "aria/templates/config_backup.html").read_text(encoding="utf-8")
    logs = (ROOT / "aria/templates/config_logs.html").read_text(encoding="utf-8")

    assert "backup_summary_included" in backup
    assert "ui-caution-action" in backup
    assert "config_logs.retention_and_logs_title" in logs
    assert "config_logs.usage_settings_title" in logs
    assert "config_logs.trace_title" in logs
    assert logs.count('type="submit" class="ui-primary-action"') >= 2


def test_alpha990_release_metadata_keeps_public_channel_on_alpha983() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    release_meta = (ROOT / "aria/modules/release_update/release_meta.py").read_text(encoding="utf-8")
    changelog_en = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    changelog_de = (ROOT / "CHANGELOG.de.md").read_text(encoding="utf-8")
    assert 'version = "0.1.0-alpha1007"' in pyproject
    assert 'DEFAULT_RELEASE_LABEL = "0.1.0-alpha1007"' in release_meta
    assert changelog_en.startswith("# Changelog\n\n## 0.1.0-alpha1007")
    assert changelog_de.startswith("# Changelog\n\n## 0.1.0-alpha1007")
    assert "0.1.0-alpha983" in changelog_en
    assert "0.1.0-alpha983" in changelog_de
