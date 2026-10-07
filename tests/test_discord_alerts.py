from unittest.mock import patch

from aria.modules.configuration_foundations.config import Settings
from aria.modules.discord_alerting.alerts import runtime_host_line, send_discord_alerts


def test_send_discord_alerts_respects_category_flags() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "connections": {
                "discord": {
                    "ops": {
                        "webhook_url": "https://discord.example/ops",
                        "alert_skill_errors": True,
                    },
                    "audit": {
                        "webhook_url": "https://discord.example/audit",
                        "alert_skill_errors": False,
                    },
                }
            },
        }
    )

    with patch("aria.modules.discord_alerting.alerts._post_webhook_message") as send_mock:
        sent = send_discord_alerts(
            settings,
            category="recipe_errors",
            title="Rezept-Fehler erkannt",
            lines=["User: demo"],
            level="warn",
        )

    assert sent == 1
    assert send_mock.call_count == 1
    first_call = send_mock.call_args_list[0]
    assert "https://discord.example/ops" in first_call.args[0]


def test_send_discord_alerts_routes_configured_event_categories() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "connections": {
                "discord": {
                    "ops": {
                        "webhook_url": "https://discord.example/ops",
                        "alert_skill_errors": True,
                        "alert_connection_changes": True,
                        "alert_system_events": True,
                    }
                }
            },
        }
    )

    with patch("aria.modules.discord_alerting.alerts._post_webhook_message") as send_mock:
        categories = ("recipe_errors", "skill_errors", "connection_changes", "system_events")
        sent = [
            send_discord_alerts(settings, category=category, title="event", lines=["demo"], level="info")
            for category in categories
        ]

    assert sent == [1, 1, 1, 1]
    assert send_mock.call_count == len(categories)


def test_legacy_alert_safe_fix_config_key_is_ignored_without_enabling_an_alert() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "connections": {
                "discord": {
                    "ops": {
                        "webhook_url": "https://discord.example/ops",
                        "alert_safe_fix": True,
                    }
                }
            },
        }
    )

    profile = settings.connections.discord["ops"]
    assert not hasattr(profile, "alert_safe_fix")
    with patch("aria.modules.discord_alerting.alerts._post_webhook_message") as send_mock:
        assert send_discord_alerts(
            settings, category="safe_fix", title="retired", lines=["ignored"], level="info",
        ) == 0
    send_mock.assert_not_called()


def test_send_discord_alerts_returns_zero_when_nothing_matches() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "connections": {"discord": {"ops": {"webhook_url": "https://discord.example/ops"}}},
        }
    )

    with patch("aria.modules.discord_alerting.alerts._post_webhook_message") as send_mock:
        sent = send_discord_alerts(
            settings,
            category="system_events",
            title="ARIA gestartet",
            lines=["Host: 0.0.0.0:8800"],
            level="info",
        )

    assert sent == 0
    send_mock.assert_not_called()


def test_runtime_host_line_treats_configured_url_as_optional_basis_url() -> None:
    configured = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "aria": {"public_url": "http://aria.example.lan/"},
        }
    )
    wildcard = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "aria": {"host": "0.0.0.0", "port": 8800},
        }
    )

    assert runtime_host_line(configured) == "Host: http://aria.example.lan"
    with patch("aria.modules.integration_support.runtime_endpoint._detect_lan_ip", return_value="192.0.2.29"):
        assert runtime_host_line(wildcard) == "Host: http://192.0.2.29:8800"
    assert "Public URL" not in runtime_host_line(wildcard)
