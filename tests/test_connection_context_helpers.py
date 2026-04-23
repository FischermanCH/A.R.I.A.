from aria.web.connection_context_helpers import _secret_status_card
from aria.web.connection_context_helpers import _sftp_auth_status_card


def test_secret_status_card_uses_connected_state_when_secret_exists() -> None:
    card = _secret_status_card(
        label_key="config_conn.password_status",
        label="Password status",
        secret_present=True,
        connected_hint_key="config_conn.email_password_hint",
        connected_hint="Password is stored in the secure store, not in config.yaml.",
    )

    assert card["value_key"] == "config_conn.connected"


def test_secret_status_card_uses_sign_in_needed_without_secret() -> None:
    card = _secret_status_card(
        label_key="config_conn.password_status",
        label="Password status",
        secret_present=False,
        connected_hint_key="config_conn.email_password_hint",
        connected_hint="Password is stored in the secure store, not in config.yaml.",
    )

    assert card["value_key"] == "config_conn.sign_in_needed"


def test_sftp_auth_status_card_uses_sign_in_needed_without_key_or_password() -> None:
    card = _sftp_auth_status_card({})

    assert card["value_key"] == "config_conn.sign_in_needed"
