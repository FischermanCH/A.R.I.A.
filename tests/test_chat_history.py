from __future__ import annotations

from pathlib import Path

from aria.core.chat_history import FileChatHistoryStore


def test_chat_history_append_and_load(tmp_path: Path) -> None:
    store = FileChatHistoryStore(tmp_path, max_messages=6)

    store.append_exchange(
        "DemoUser",
        user_message="Hallo",
        assistant_message="Hi",
        badge_icon="💬",
        badge_intent="chat",
        badge_tokens=12,
        badge_cost_usd="$0.000001",
        badge_duration="0.2",
    )

    history = store.load_history("DemoUser")
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[0]["text"] == "Hallo"
    assert history[1]["role"] == "assistant"
    assert history[1]["text"] == "Hi"
    assert history[1]["badge_intent"] == "chat"


def test_chat_history_trim_and_clear(tmp_path: Path) -> None:
    store = FileChatHistoryStore(tmp_path, max_messages=4)

    for idx in range(3):
        store.append_exchange(
            "DemoUser",
            user_message=f"u{idx}",
            assistant_message=f"a{idx}",
            badge_icon="💬",
            badge_intent="chat",
            badge_tokens=1,
            badge_cost_usd="n/a",
            badge_duration="0.1",
        )

    history = store.load_history("DemoUser")
    assert len(history) == 4
    assert [item["text"] for item in history] == ["u1", "a1", "u2", "a2"]

    store.clear_history("DemoUser")
    assert store.load_history("DemoUser") == []
