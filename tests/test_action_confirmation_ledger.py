from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from aria.modules.action_confirmation.ledger import ActionConfirmationLedger
from aria.modules.action_confirmation.ledger import CLAIMED
from aria.modules.action_confirmation.ledger import REPLAYED
from aria.modules.action_confirmation.ledger import UNAVAILABLE


def test_action_confirmation_claim_is_persistent_and_one_shot(tmp_path) -> None:
    db_path = tmp_path / "runtime" / "action_confirmations.sqlite3"
    pending = {
        "user_id": "neo",
        "token": "confirm123",
        "query": "send webhook",
        "payload": {"capability": "webhook_send", "connection_ref": "page-discovery"},
    }

    first = ActionConfirmationLedger(db_path)
    assert first.claim(user_id="neo", token="confirm123", pending_action=pending, now=1000) == CLAIMED

    restarted = ActionConfirmationLedger(db_path)
    assert restarted.claim(user_id="neo", token="confirm123", pending_action=pending, now=1001) == REPLAYED


def test_action_confirmation_tokens_are_scoped_per_user(tmp_path) -> None:
    ledger = ActionConfirmationLedger(tmp_path / "action_confirmations.sqlite3")
    pending = {"token": "same-token", "query": "send webhook"}

    assert ledger.claim(user_id="neo", token="same-token", pending_action=pending, now=1000) == CLAIMED
    assert ledger.claim(user_id="trinity", token="same-token", pending_action=pending, now=1001) == CLAIMED


def test_unavailable_ledger_fails_closed_without_breaking_construction(tmp_path) -> None:
    blocked_parent = tmp_path / "not-a-directory"
    blocked_parent.write_text("occupied", encoding="utf-8")

    ledger = ActionConfirmationLedger(blocked_parent / "claims.sqlite3")

    assert (
        ledger.claim(
            user_id="neo",
            token="abcdef12",
            pending_action={"query": "run webhook"},
        )
        == UNAVAILABLE
    )


def test_concurrent_confirmation_claim_has_exactly_one_winner(tmp_path) -> None:
    ledger = ActionConfirmationLedger(tmp_path / "action_confirmations.sqlite3")
    pending = {"token": "same-token", "query": "send webhook"}

    def claim_once() -> str:
        return ledger.claim(
            user_id="neo",
            token="same-token",
            pending_action=pending,
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _index: claim_once(), range(8)))

    assert results.count(CLAIMED) == 1
    assert results.count(REPLAYED) == 7
