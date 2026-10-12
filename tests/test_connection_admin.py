from __future__ import annotations

import yaml

from aria.modules.connections_profiles.admin import (
    ConnectionAdminError,
    create_connection_profile,
    friendly_connection_admin_error_text,
    resolve_connection_target,
    update_connection_profile,
)
import aria.modules.chat_admin_composition.actions as chat_admin_actions
from aria.modules.chat_surface.actions import build_chat_quick_actions
from aria.modules.config_ui.routes import _normalize_rss_feed_url_for_dedupe


def test_resolve_connection_target_handles_unique_ref_without_kind() -> None:
    kind, ref = resolve_connection_target(
        {
            "rss": ["heise-online-news"],
            "smb": ["nas-docker"],
        },
        ref_hint="nas-docker",
    )
    assert kind == "smb"
    assert ref == "nas-docker"


def test_resolve_connection_target_maps_smtp_to_email() -> None:
    kind, ref = resolve_connection_target(
        {
            "email": ["alerts-mail"],
        },
        ref_hint="alerts-mail",
        kind_hint="smtp",
    )
    assert kind == "email"
    assert ref == "alerts-mail"


def test_friendly_connection_admin_error_uses_field_label() -> None:
    text = friendly_connection_admin_error_text(
        ConnectionAdminError("required_field", field="base_url"),
        kind="http_api",
        action="create",
    )
    assert text == "Pflichtfeld fehlt: Base-URL."


def test_friendly_connection_admin_error_hides_security_store_implementation_detail() -> None:
    text = friendly_connection_admin_error_text(
        ConnectionAdminError("security_store_required"),
        kind="http_api",
        action="create",
    )
    assert "HTTP API-Profil kann nur gespeichert werden" in text


def test_friendly_connection_admin_error_for_missing_config_is_short() -> None:
    text = friendly_connection_admin_error_text(ConnectionAdminError("config_missing", config_path="/tmp/x/config.yaml"))
    assert text == "config.yaml fehlt."


def test_create_connection_profile_writes_rss_config(tmp_path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.yaml"
    config_path.write_text("connections: {}\n", encoding="utf-8")

    result = create_connection_profile(
        tmp_path,
        "rss",
        "heise-news",
        {
            "feed_url": "https://example.org/feed.xml",
            "title": "Heise News",
            "description": "Aktuelle Headlines",
            "aliases": ["heise online", "tech news"],
            "tags": ["news", "tech"],
        },
    )

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    row = raw["connections"]["rss"]["heise-news"]
    assert result["kind"] == "rss"
    assert result["ref"] == "heise-news"
    assert row["feed_url"] == "https://example.org/feed.xml"
    assert row["title"] == "Heise News"
    assert row["description"] == "Aktuelle Headlines"
    assert row["aliases"] == ["heise online", "tech news"]
    assert row["tags"] == ["news", "tech"]


def test_create_connection_profile_writes_ssh_service_url(tmp_path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.yaml"
    config_path.write_text("connections: {}\n", encoding="utf-8")

    result = create_connection_profile(
        tmp_path,
        "ssh",
        "mgmt-ssh",
        {
            "host": "10.0.1.7",
            "user": "ops",
            "service_url": "https://grafana.example.local",
            "key_path": "data/ssh_keys/mgmt_ed25519",
            "title": "Management SSH",
        },
    )

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    row = raw["connections"]["ssh"]["mgmt-ssh"]
    assert result["kind"] == "ssh"
    assert row["host"] == "10.0.1.7"
    assert row["service_url"] == "https://grafana.example.local"
    assert row["title"] == "Management SSH"


def test_create_connection_profile_writes_sftp_service_url(tmp_path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.yaml"
    config_path.write_text("connections: {}\n", encoding="utf-8")

    result = create_connection_profile(
        tmp_path,
        "sftp",
        "files-sftp",
        {
            "host": "10.0.1.8",
            "user": "backup",
            "service_url": "https://minio.example.local",
            "key_path": "data/ssh_keys/files_ed25519",
            "root_path": "/data",
            "title": "Files SFTP",
        },
    )

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    row = raw["connections"]["sftp"]["files-sftp"]
    assert result["kind"] == "sftp"
    assert row["host"] == "10.0.1.8"
    assert row["service_url"] == "https://minio.example.local"
    assert row["root_path"] == "/data"
    assert row["title"] == "Files SFTP"


def test_normalize_rss_feed_url_for_dedupe_merges_slash_and_tracking_variants() -> None:
    assert _normalize_rss_feed_url_for_dedupe("https://Example.org/feed/") == "https://example.org/feed"
    assert (
        _normalize_rss_feed_url_for_dedupe(
            "https://example.org/feed/?utm_source=newsletter&fbclid=abc&id=42"
        )
        == "https://example.org/feed?id=42"
    )


def test_normalize_rss_feed_url_for_dedupe_drops_default_port_and_fragment() -> None:
    assert (
        _normalize_rss_feed_url_for_dedupe("https://example.org:443/feed.xml#section")
        == "https://example.org/feed.xml"
    )


def test_create_connection_profile_writes_discord_and_secret(tmp_path, monkeypatch) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.yaml"
    config_path.write_text("connections: {}\n", encoding="utf-8")

    class FakeStore:
        def __init__(self) -> None:
            self.secrets: dict[str, str] = {}

        def set_secret(self, key: str, value: str) -> None:
            self.secrets[key] = value

    fake_store = FakeStore()
    monkeypatch.setattr("aria.modules.connections_profiles.admin.get_secure_store_for_config", lambda base_dir, raw: fake_store)

    result = create_connection_profile(
        tmp_path,
        "discord",
        "alerts-bot",
        {
            "webhook_url": "https://discord.example/webhook",
            "title": "Alerts Bot",
            "tags": ["alerts", "discord"],
        },
    )

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    row = raw["connections"]["discord"]["alerts-bot"]
    assert result["kind"] == "discord"
    assert row["allow_skill_messages"] is True
    assert row["send_test_messages"] is True
    assert row["title"] == "Alerts Bot"
    assert row["tags"] == ["alerts", "discord"]
    assert fake_store.secrets["connections.discord.alerts-bot.webhook_url"] == "https://discord.example/webhook"


def test_create_connection_profile_writes_webhook_and_secret(tmp_path, monkeypatch) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.yaml"
    config_path.write_text("connections: {}\n", encoding="utf-8")

    class FakeStore:
        def __init__(self) -> None:
            self.secrets: dict[str, str] = {}

        def set_secret(self, key: str, value: str) -> None:
            self.secrets[key] = value

    fake_store = FakeStore()
    monkeypatch.setattr("aria.modules.connections_profiles.admin.get_secure_store_for_config", lambda base_dir, raw: fake_store)

    result = create_connection_profile(
        tmp_path,
        "webhook",
        "n8n-demo",
        {
            "url": "https://example.org/hook",
            "method": "POST",
            "content_type": "application/json",
            "title": "n8n Demo",
            "aliases": ["automation hook"],
            "tags": ["n8n"],
        },
    )

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    row = raw["connections"]["webhook"]["n8n-demo"]
    assert result["kind"] == "webhook"
    assert row["method"] == "POST"
    assert row["content_type"] == "application/json"
    assert row["title"] == "n8n Demo"
    assert row["aliases"] == ["automation hook"]
    assert row["tags"] == ["n8n"]
    assert fake_store.secrets["connections.webhook.n8n-demo.url"] == "https://example.org/hook"


def test_create_connection_profile_provisions_inbound_webhook_token(tmp_path, monkeypatch) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.yaml"
    config_path.write_text("connections: {}\n", encoding="utf-8")

    class FakeStore:
        def __init__(self) -> None:
            self.secrets: dict[str, str] = {}

        def set_secret(self, key: str, value: str) -> None:
            self.secrets[key] = value

    fake_store = FakeStore()
    monkeypatch.setattr("aria.modules.connections_profiles.admin.get_secure_store_for_config", lambda base_dir, raw: fake_store)

    result = create_connection_profile(
        tmp_path,
        "inbound_webhook",
        "sensecap-watcher",
        {
            "provider_profile": "senscap_watcher",
            "max_body_bytes": 32768,
            "max_events": 250,
            "title": "SenseCAP Watcher",
        },
    )

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    row = raw["connections"]["inbound_webhook"]["sensecap-watcher"]
    assert row["provider_profile"] == "senscap_watcher"
    assert row["routing_policy"] == "log_only"
    assert row["max_body_bytes"] == 32768
    assert row["max_events"] == 250
    assert result["generated_token"]
    assert fake_store.secrets["connections.inbound_webhook.sensecap-watcher.token"] == result["generated_token"]


def test_create_connection_profile_writes_smb_config_and_optional_secret(tmp_path, monkeypatch) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.yaml"
    config_path.write_text("connections: {}\n", encoding="utf-8")

    class FakeStore:
        def __init__(self) -> None:
            self.secrets: dict[str, str] = {}

        def set_secret(self, key: str, value: str) -> None:
            self.secrets[key] = value

    fake_store = FakeStore()
    monkeypatch.setattr("aria.modules.connections_profiles.admin.get_secure_store_for_config", lambda base_dir, raw: fake_store)

    result = create_connection_profile(
        tmp_path,
        "smb",
        "nas-share",
        {
            "host": "nas-demo",
            "share": "docker",
            "user": "aria",
            "root_path": "/docker",
            "password": "smb-secret",
            "title": "NAS Share",
            "tags": ["nas", "docker"],
        },
    )

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    row = raw["connections"]["smb"]["nas-share"]
    assert result["kind"] == "smb"
    assert row["host"] == "nas-demo"
    assert row["share"] == "docker"
    assert row["root_path"] == "/docker"
    assert row["title"] == "NAS Share"
    assert row["tags"] == ["nas", "docker"]
    assert fake_store.secrets["connections.smb.nas-share.password"] == "smb-secret"


def test_create_connection_profile_writes_sftp_config_and_optional_secret(tmp_path, monkeypatch) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.yaml"
    config_path.write_text("connections: {}\n", encoding="utf-8")

    class FakeStore:
        def __init__(self) -> None:
            self.secrets: dict[str, str] = {}

        def set_secret(self, key: str, value: str) -> None:
            self.secrets[key] = value

    fake_store = FakeStore()
    monkeypatch.setattr("aria.modules.connections_profiles.admin.get_secure_store_for_config", lambda base_dir, raw: fake_store)

    result = create_connection_profile(
        tmp_path,
        "sftp",
        "mgmt-sftp",
        {
            "host": "10.0.1.1",
            "user": "aria",
            "root_path": "/data",
            "key_path": "PROJECT_ROOT/data/ssh_keys/mgmt_ed25519",
            "password": "sftp-secret",
            "title": "SFTP Server",
        },
    )

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    row = raw["connections"]["sftp"]["mgmt-sftp"]
    assert result["kind"] == "sftp"
    assert row["host"] == "10.0.1.1"
    assert row["user"] == "aria"
    assert row["root_path"] == "/data"
    assert row["key_path"] == "PROJECT_ROOT/data/ssh_keys/mgmt_ed25519"
    assert row["title"] == "SFTP Server"
    assert fake_store.secrets["connections.sftp.mgmt-sftp.password"] == "sftp-secret"


def test_create_connection_profile_writes_ssh_config(tmp_path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.yaml"
    config_path.write_text("connections: {}\n", encoding="utf-8")

    result = create_connection_profile(
        tmp_path,
        "ssh",
        "mgmt-ssh",
        {
            "host": "10.0.1.1",
            "user": "aria",
            "key_path": "PROJECT_ROOT/data/ssh_keys/mgmt_ed25519",
            "strict_host_key_checking": "accept-new",
            "allow_commands": ["uptime", "df -h"],
            "title": "SSH Server",
        },
    )

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    row = raw["connections"]["ssh"]["mgmt-ssh"]
    assert result["kind"] == "ssh"
    assert row["host"] == "10.0.1.1"
    assert row["user"] == "aria"
    assert row["key_path"] == "PROJECT_ROOT/data/ssh_keys/mgmt_ed25519"
    assert row["strict_host_key_checking"] == "accept-new"
    assert row["allow_commands"] == ["uptime", "df -h"]
    assert row["title"] == "SSH Server"


def test_create_connection_profile_writes_http_api_and_optional_token(tmp_path, monkeypatch) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.yaml"
    config_path.write_text("connections: {}\n", encoding="utf-8")

    class FakeStore:
        def __init__(self) -> None:
            self.secrets: dict[str, str] = {}

        def set_secret(self, key: str, value: str) -> None:
            self.secrets[key] = value

    fake_store = FakeStore()
    monkeypatch.setattr("aria.modules.connections_profiles.admin.get_secure_store_for_config", lambda base_dir, raw: fake_store)

    result = create_connection_profile(
        tmp_path,
        "http_api",
        "inventory-api",
        {
            "base_url": "https://example.org/api",
            "health_path": "/health",
            "method": "GET",
            "auth_token": "secret-token",
            "title": "Inventory API",
            "tags": ["inventory", "ops"],
        },
    )

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    row = raw["connections"]["http_api"]["inventory-api"]
    assert result["kind"] == "http_api"
    assert row["base_url"] == "https://example.org/api"
    assert row["health_path"] == "/health"
    assert row["method"] == "GET"
    assert row["title"] == "Inventory API"
    assert row["tags"] == ["inventory", "ops"]
    assert fake_store.secrets["connections.http_api.inventory-api.auth_token"] == "secret-token"


def test_create_connection_profile_writes_mqtt_config_and_optional_secret(tmp_path, monkeypatch) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.yaml"
    config_path.write_text("connections: {}\n", encoding="utf-8")

    class FakeStore:
        def __init__(self) -> None:
            self.secrets: dict[str, str] = {}

        def set_secret(self, key: str, value: str) -> None:
            self.secrets[key] = value

    fake_store = FakeStore()
    monkeypatch.setattr("aria.modules.connections_profiles.admin.get_secure_store_for_config", lambda base_dir, raw: fake_store)

    result = create_connection_profile(
        tmp_path,
        "mqtt",
        "event-bus",
        {
            "host": "mqtt.example.local",
            "topic": "aria/events",
            "password": "mqtt-secret",
            "title": "Event Bus",
            "tags": ["events", "mqtt"],
        },
    )

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    row = raw["connections"]["mqtt"]["event-bus"]
    assert result["kind"] == "mqtt"
    assert row["host"] == "mqtt.example.local"
    assert row["topic"] == "aria/events"
    assert row["title"] == "Event Bus"
    assert row["tags"] == ["events", "mqtt"]
    assert fake_store.secrets["connections.mqtt.event-bus.password"] == "mqtt-secret"


def test_create_connection_profile_writes_smtp_and_imap_config_and_secrets(tmp_path, monkeypatch) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.yaml"
    config_path.write_text("connections: {}\n", encoding="utf-8")

    class FakeStore:
        def __init__(self) -> None:
            self.secrets: dict[str, str] = {}

        def set_secret(self, key: str, value: str) -> None:
            self.secrets[key] = value

    fake_store = FakeStore()
    monkeypatch.setattr("aria.modules.connections_profiles.admin.get_secure_store_for_config", lambda base_dir, raw: fake_store)

    smtp_result = create_connection_profile(
        tmp_path,
        "email",
        "alerts-mail",
        {
            "smtp_host": "smtp.example.local",
            "user": "ops@example.local",
            "from_email": "ops@example.local",
            "to_email": "admin@example.local",
            "password": "smtp-secret",
            "title": "Alerts Mail",
        },
    )
    imap_result = create_connection_profile(
        tmp_path,
        "imap",
        "ops-inbox",
        {
            "host": "imap.example.local",
            "user": "ops@example.local",
            "mailbox": "INBOX",
            "password": "imap-secret",
            "title": "Ops Inbox",
        },
    )

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    smtp_row = raw["connections"]["email"]["alerts-mail"]
    imap_row = raw["connections"]["imap"]["ops-inbox"]
    assert smtp_result["kind"] == "email"
    assert smtp_row["smtp_host"] == "smtp.example.local"
    assert smtp_row["from_email"] == "ops@example.local"
    assert smtp_row["to_email"] == "admin@example.local"
    assert imap_result["kind"] == "imap"
    assert imap_row["host"] == "imap.example.local"
    assert imap_row["mailbox"] == "INBOX"
    assert fake_store.secrets["connections.email.alerts-mail.password"] == "smtp-secret"
    assert fake_store.secrets["connections.imap.ops-inbox.password"] == "imap-secret"


def test_update_connection_profile_updates_rss_metadata_and_url(tmp_path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "connections": {
                    "rss": {
                        "heise-news": {
                            "feed_url": "https://old.example/feed.xml",
                            "timeout_seconds": 10,
                            "title": "Alt",
                        }
                    }
                }
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    result = update_connection_profile(
        tmp_path,
        "rss",
        "heise-news",
        {
            "feed_url": "https://new.example/feed.xml",
            "title": "Heise News",
            "tags": ["news", "tech"],
        },
    )

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    row = raw["connections"]["rss"]["heise-news"]
    assert result["kind"] == "rss"
    assert row["feed_url"] == "https://new.example/feed.xml"
    assert row["title"] == "Heise News"
    assert row["tags"] == ["news", "tech"]


def test_update_connection_profile_updates_discord_secret_and_metadata(tmp_path, monkeypatch) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "connections": {
                    "discord": {
                        "alerts-bot": {
                            "timeout_seconds": 10,
                            "send_test_messages": True,
                            "allow_skill_messages": True,
                            "alert_skill_errors": False,
                            "alert_connection_changes": False,
                            "alert_system_events": False,
                        }
                    }
                }
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    class FakeStore:
        def __init__(self) -> None:
            self.secrets: dict[str, str] = {}

        def set_secret(self, key: str, value: str) -> None:
            self.secrets[key] = value

    fake_store = FakeStore()
    monkeypatch.setattr("aria.modules.connections_profiles.admin.get_secure_store_for_config", lambda base_dir, raw: fake_store)

    result = update_connection_profile(
        tmp_path,
        "discord",
        "alerts-bot",
        {
            "webhook_url": "https://discord.example/new-webhook",
            "title": "Alerts Bot",
            "tags": ["alerts"],
        },
    )

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    row = raw["connections"]["discord"]["alerts-bot"]
    assert result["kind"] == "discord"
    assert row["title"] == "Alerts Bot"
    assert row["tags"] == ["alerts"]
    assert fake_store.secrets["connections.discord.alerts-bot.webhook_url"] == "https://discord.example/new-webhook"


def test_update_connection_profile_updates_webhook_secret(tmp_path, monkeypatch) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "connections": {
                    "webhook": {
                        "n8n-demo": {
                            "timeout_seconds": 10,
                            "method": "POST",
                            "content_type": "application/json",
                        }
                    }
                }
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    class FakeStore:
        def __init__(self) -> None:
            self.secrets: dict[str, str] = {}

        def set_secret(self, key: str, value: str) -> None:
            self.secrets[key] = value

    fake_store = FakeStore()
    monkeypatch.setattr("aria.modules.connections_profiles.admin.get_secure_store_for_config", lambda base_dir, raw: fake_store)

    result = update_connection_profile(
        tmp_path,
        "webhook",
        "n8n-demo",
        {
            "url": "https://example.org/new-hook",
            "title": "n8n Demo",
        },
    )

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    row = raw["connections"]["webhook"]["n8n-demo"]
    assert result["kind"] == "webhook"
    assert row["title"] == "n8n Demo"
    assert fake_store.secrets["connections.webhook.n8n-demo.url"] == "https://example.org/new-hook"


def test_update_connection_profile_updates_smb_and_password(tmp_path, monkeypatch) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "connections": {
                    "smb": {
                        "nas-share": {
                            "host": "old-host",
                            "share": "old",
                            "user": "aria",
                            "root_path": "/old",
                            "title": "Alt",
                        }
                    }
                }
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    class FakeStore:
        def __init__(self) -> None:
            self.secrets: dict[str, str] = {}

        def set_secret(self, key: str, value: str) -> None:
            self.secrets[key] = value

    fake_store = FakeStore()
    monkeypatch.setattr("aria.modules.connections_profiles.admin.get_secure_store_for_config", lambda base_dir, raw: fake_store)

    result = update_connection_profile(
        tmp_path,
        "smb",
        "nas-share",
        {
            "host": "nas-demo",
            "share": "docker",
            "root_path": "/docker",
            "password": "smb-secret",
            "title": "NAS Share",
        },
    )

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    row = raw["connections"]["smb"]["nas-share"]
    assert result["kind"] == "smb"
    assert row["host"] == "nas-demo"
    assert row["share"] == "docker"
    assert row["root_path"] == "/docker"
    assert row["title"] == "NAS Share"
    assert fake_store.secrets["connections.smb.nas-share.password"] == "smb-secret"


def test_update_connection_profile_updates_sftp_and_password(tmp_path, monkeypatch) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "connections": {
                    "sftp": {
                        "mgmt-sftp": {
                            "host": "old-host",
                            "user": "old-user",
                            "root_path": "/old",
                            "title": "Alt",
                        }
                    }
                }
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    class FakeStore:
        def __init__(self) -> None:
            self.secrets: dict[str, str] = {}

        def set_secret(self, key: str, value: str) -> None:
            self.secrets[key] = value

    fake_store = FakeStore()
    monkeypatch.setattr("aria.modules.connections_profiles.admin.get_secure_store_for_config", lambda base_dir, raw: fake_store)

    result = update_connection_profile(
        tmp_path,
        "sftp",
        "mgmt-sftp",
        {
            "host": "10.0.1.1",
            "user": "aria",
            "root_path": "/data",
            "key_path": "PROJECT_ROOT/data/ssh_keys/mgmt_ed25519",
            "password": "sftp-secret",
            "title": "SFTP Server",
        },
    )

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    row = raw["connections"]["sftp"]["mgmt-sftp"]
    assert result["kind"] == "sftp"
    assert row["host"] == "10.0.1.1"
    assert row["user"] == "aria"
    assert row["root_path"] == "/data"
    assert row["key_path"] == "PROJECT_ROOT/data/ssh_keys/mgmt_ed25519"
    assert row["title"] == "SFTP Server"
    assert fake_store.secrets["connections.sftp.mgmt-sftp.password"] == "sftp-secret"


def test_update_connection_profile_updates_ssh_fields(tmp_path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "connections": {
                    "ssh": {
                        "mgmt-ssh": {
                            "host": "old-host",
                            "user": "old-user",
                            "strict_host_key_checking": "no",
                            "allow_commands": [],
                            "title": "Alt",
                        }
                    }
                }
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    result = update_connection_profile(
        tmp_path,
        "ssh",
        "mgmt-ssh",
        {
            "host": "10.0.1.1",
            "user": "aria",
            "key_path": "PROJECT_ROOT/data/ssh_keys/mgmt_ed25519",
            "strict_host_key_checking": "accept-new",
            "allow_commands": ["uptime", "df -h"],
            "title": "SSH Server",
        },
    )

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    row = raw["connections"]["ssh"]["mgmt-ssh"]
    assert result["kind"] == "ssh"
    assert row["host"] == "10.0.1.1"
    assert row["user"] == "aria"
    assert row["key_path"] == "PROJECT_ROOT/data/ssh_keys/mgmt_ed25519"
    assert row["strict_host_key_checking"] == "accept-new"
    assert row["allow_commands"] == ["uptime", "df -h"]
    assert row["title"] == "SSH Server"


def test_update_connection_profile_updates_mqtt_host_topic_and_secret(tmp_path, monkeypatch) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "connections": {
                    "mqtt": {
                        "event-bus": {
                            "host": "old-broker.local",
                            "port": 1883,
                            "topic": "old/topic",
                            "timeout_seconds": 10,
                        }
                    }
                }
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    class FakeStore:
        def __init__(self) -> None:
            self.secrets: dict[str, str] = {}

        def set_secret(self, key: str, value: str) -> None:
            self.secrets[key] = value

    fake_store = FakeStore()
    monkeypatch.setattr("aria.modules.connections_profiles.admin.get_secure_store_for_config", lambda base_dir, raw: fake_store)

    result = update_connection_profile(
        tmp_path,
        "mqtt",
        "event-bus",
        {
            "host": "mqtt.example.local",
            "topic": "aria/events",
            "password": "mqtt-secret",
            "title": "Event Bus",
        },
    )

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    row = raw["connections"]["mqtt"]["event-bus"]
    assert result["kind"] == "mqtt"
    assert row["host"] == "mqtt.example.local"
    assert row["topic"] == "aria/events"
    assert row["title"] == "Event Bus"
    assert fake_store.secrets["connections.mqtt.event-bus.password"] == "mqtt-secret"


def test_update_connection_profile_updates_smtp_and_imap_fields(tmp_path, monkeypatch) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "connections": {
                    "email": {
                        "alerts-mail": {
                            "smtp_host": "old-smtp.local",
                            "port": 587,
                            "user": "old@example.local",
                            "from_email": "old@example.local",
                            "to_email": "ops@example.local",
                            "timeout_seconds": 10,
                            "starttls": True,
                            "use_ssl": False,
                        }
                    },
                    "imap": {
                        "ops-inbox": {
                            "host": "old-imap.local",
                            "port": 993,
                            "user": "old@example.local",
                            "mailbox": "OLD",
                            "timeout_seconds": 10,
                            "use_ssl": True,
                        }
                    },
                }
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    class FakeStore:
        def __init__(self) -> None:
            self.secrets: dict[str, str] = {}

        def set_secret(self, key: str, value: str) -> None:
            self.secrets[key] = value

    fake_store = FakeStore()
    monkeypatch.setattr("aria.modules.connections_profiles.admin.get_secure_store_for_config", lambda base_dir, raw: fake_store)

    smtp_result = update_connection_profile(
        tmp_path,
        "email",
        "alerts-mail",
        {
            "smtp_host": "smtp.example.local",
            "from_email": "ops@example.local",
            "to_email": "admin@example.local",
            "password": "smtp-secret",
            "title": "Alerts Mail",
        },
    )
    imap_result = update_connection_profile(
        tmp_path,
        "imap",
        "ops-inbox",
        {
            "host": "imap.example.local",
            "mailbox": "INBOX",
            "password": "imap-secret",
            "title": "Ops Inbox",
        },
    )

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    smtp_row = raw["connections"]["email"]["alerts-mail"]
    imap_row = raw["connections"]["imap"]["ops-inbox"]
    assert smtp_result["kind"] == "email"
    assert smtp_row["smtp_host"] == "smtp.example.local"
    assert smtp_row["from_email"] == "ops@example.local"
    assert smtp_row["to_email"] == "admin@example.local"
    assert imap_result["kind"] == "imap"
    assert imap_row["host"] == "imap.example.local"
    assert imap_row["mailbox"] == "INBOX"
    assert fake_store.secrets["connections.email.alerts-mail.password"] == "smtp-secret"
    assert fake_store.secrets["connections.imap.ops-inbox.password"] == "imap-secret"



def test_parse_connection_create_confirm_token_supports_german_and_ascii() -> None:
    assert chat_admin_actions._parse_connection_create_confirm_token("bestätige verbindung erstellen abc123") == "abc123"
    assert chat_admin_actions._parse_connection_create_confirm_token("bestaetige verbindung erstellen abc123") == "abc123"



def test_parse_connection_update_confirm_token_supports_german_and_ascii() -> None:
    assert chat_admin_actions._parse_connection_update_confirm_token("bestätige verbindung aktualisieren abc123") == "abc123"
    assert chat_admin_actions._parse_connection_update_confirm_token("bestaetige verbindung aktualisieren abc123") == "abc123"


def test_connection_create_pending_roundtrip_keeps_complex_ssh_fields(monkeypatch) -> None:
    raw = chat_admin_actions._encode_connection_create_pending(
        {
            "token": "abc123",
            "user_id": "admin",
            "kind": "ssh",
            "ref": "mgmt-ssh",
            "payload": {
                "host": "10.0.1.1",
                "user": "aria",
                "key_path": "/keys/mgmt_ed25519",
                "strict_host_key_checking": "accept-new",
                "allow_commands": ["uptime", "df -h"],
                "ignored_field": "nope",
            },
        },
        signing_secret="test-secret",
        sanitize_username=lambda value: str(value or "").strip(),
        now_provider=lambda: 1000,
    )

    decoded = chat_admin_actions._decode_connection_create_pending(
        raw,
        signing_secret="test-secret",
        sanitize_username=lambda value: str(value or "").strip(),
        max_age_seconds=60 * 10,
        now_provider=lambda: 1000,
    )

    assert decoded is not None
    assert decoded["kind"] == "ssh"
    assert decoded["payload"]["host"] == "10.0.1.1"
    assert decoded["payload"]["key_path"] == "/keys/mgmt_ed25519"
    assert decoded["payload"]["allow_commands"] == ["uptime", "df -h"]
    assert "ignored_field" not in decoded["payload"]


def test_connection_delete_pending_expires_after_max_age(monkeypatch) -> None:
    raw = chat_admin_actions._encode_connection_delete_pending(
        {
            "token": "abc123",
            "user_id": "admin",
            "kind": "rss",
            "ref": "heise-news",
        },
        signing_secret="test-secret",
        sanitize_username=lambda value: str(value or "").strip(),
        sanitize_connection_name=lambda value: str(value or "").strip(),
        now_provider=lambda: 1000,
    )

    assert (
        chat_admin_actions._decode_connection_delete_pending(
            raw,
            signing_secret="test-secret",
            sanitize_username=lambda value: str(value or "").strip(),
            sanitize_connection_name=lambda value: str(value or "").strip(),
            max_age_seconds=60 * 10,
            now_provider=lambda: 1000 + (60 * 10) + 1,
        )
        is None
    )


def test_chat_quick_actions_keep_only_ui_capabilities() -> None:
    rows = build_chat_quick_actions("de")
    assert [row["key"] for row in rows] == [
        "new_chat", "import_document", "save_chat_note", "open_notes",
    ]
    assert not any("connection" in str(row).lower() for row in rows)


def test_chat_quick_actions_are_localized_in_english() -> None:
    rows = build_chat_quick_actions("en")
    assert [row["label"] for row in rows] == [
        "New chat", "Import document", "Save chat as note", "Open notes",
    ]
