from unittest.mock import patch

from aria.core.config import Settings
from aria.core.discord_alerts import send_discord_alerts


def test_send_discord_alerts_respects_category_flags() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "connections": {
                "discord": {
                    "ops": {
                        "webhook_url": "https://discord.example/ops",
                        "alert_skill_errors": True,
                        "alert_safe_fix": False,
                    },
                    "audit": {
                        "webhook_url": "https://discord.example/audit",
                        "alert_skill_errors": False,
                        "alert_safe_fix": True,
                    },
                }
            },
        }
    )

    with patch("aria.core.discord_alerts._post_webhook_message") as send_mock:
        sent = send_discord_alerts(
            settings,
            category="skill_errors",
            title="Skill-Fehler erkannt",
            lines=["User: demo"],
            level="warn",
        )

    assert sent == 1
    assert send_mock.call_count == 1
    first_call = send_mock.call_args_list[0]
    assert "https://discord.example/ops" in first_call.args[0]


def test_send_discord_alerts_returns_zero_when_nothing_matches() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "connections": {"discord": {"ops": {"webhook_url": "https://discord.example/ops"}}},
        }
    )

    with patch("aria.core.discord_alerts._post_webhook_message") as send_mock:
        sent = send_discord_alerts(
            settings,
            category="system_events",
            title="ARIA gestartet",
            lines=["Host: 0.0.0.0:8800"],
            level="info",
        )

    assert sent == 0
    send_mock.assert_not_called()
