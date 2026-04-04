from __future__ import annotations

import json

from aria.core import connection_health
from aria.core.secure_store import SecureConfigStore, SecureStoreConfig, decode_master_key, generate_master_key_b64


def test_secure_store_delete_secret_removes_value(tmp_path) -> None:
    db_path = tmp_path / "secure.sqlite"
    store = SecureConfigStore(
        SecureStoreConfig(db_path=db_path),
        decode_master_key(generate_master_key_b64()),
    )

    store.set_secret("connections.discord.alerts.webhook_url", "https://example.org/hook")
    assert store.get_secret("connections.discord.alerts.webhook_url") == "https://example.org/hook"

    store.delete_secret("connections.discord.alerts.webhook_url")

    assert store.get_secret("connections.discord.alerts.webhook_url", default="") == ""


def test_delete_connection_health_removes_cached_entry(monkeypatch, tmp_path) -> None:
    health_path = tmp_path / "connection_health.json"
    monkeypatch.setattr(connection_health, "_health_store_path", lambda: health_path)

    connection_health.record_connection_health(
        "sftp:nas-share",
        status="ok",
        target="backup@example:22",
        message="ok",
    )
    before = json.loads(health_path.read_text(encoding="utf-8"))
    assert "sftp:nas-share" in before["connections"]

    connection_health.delete_connection_health("sftp:nas-share")

    after = json.loads(health_path.read_text(encoding="utf-8"))
    assert "sftp:nas-share" not in after["connections"]
