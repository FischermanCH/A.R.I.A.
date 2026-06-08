from __future__ import annotations

from pathlib import Path

import aria.core.chat_learn_mode as chat_learn_mode


def test_chat_learn_mode_records_and_cancels_session(tmp_path: Path) -> None:
    chat_learn_mode.start_chat_learn_mode(tmp_path, username="neo", session_id="s1")

    assert chat_learn_mode.chat_learn_mode_active(tmp_path, username="neo", session_id="s1")
    assert chat_learn_mode.append_chat_learn_observation(
        tmp_path,
        username="neo",
        session_id="s1",
        user_message="wie fit sind meine server?",
        assistant_text="Mehrere SSH-Ziele geprueft.",
        intent_label="ssh_command",
        badge_details=[
            "Routing Debug: agentic_runtime ref=dev-node-01 kind=ssh capability=ssh_command operation=run_command command=df -h boundary=runtime_execution",
            "Ausgeführt via SSH-Profil `dev-node-01`",
            "Befehl: df -h",
        ],
    )
    assert chat_learn_mode.chat_learn_mode_event_count(tmp_path, username="neo", session_id="s1") == 1

    discarded = chat_learn_mode.cancel_chat_learn_mode(tmp_path, username="neo", session_id="s1")

    assert discarded == 1
    assert not chat_learn_mode.chat_learn_mode_active(tmp_path, username="neo", session_id="s1")


async def _fake_curate(*, llm_client, entry, language, user_id, request_id):  # noqa: ANN001, ARG001
    return {**entry, "curation_status": "ok", "confidence": 0.72}, "fake"


def test_finish_chat_learn_mode_creates_review_only_candidate(monkeypatch, tmp_path: Path) -> None:
    saved_entries: list[dict[str, object]] = []

    def fake_save(entry: dict[str, object], previous_id: str | None = None) -> dict[str, object]:  # noqa: ARG001
        saved_entries.append(dict(entry))
        return dict(entry)

    monkeypatch.setattr(chat_learn_mode, "save_learned_recipe_store_entry", fake_save)
    monkeypatch.setattr(chat_learn_mode, "curate_learned_recipe_entry", _fake_curate)
    chat_learn_mode.start_chat_learn_mode(tmp_path, username="neo", session_id="s1")
    chat_learn_mode.append_chat_learn_observation(
        tmp_path,
        username="neo",
        session_id="s1",
        user_message="haben meine dev-server genug festplattenspeicher",
        assistant_text="Festplattencheck fuer dev-node-01.",
        intent_label="ssh_command",
        badge_details=[
            "Routing Debug: agentic_runtime ref=dev-node-01 kind=ssh capability=ssh_command operation=run_command command=df -h boundary=runtime_execution",
            "Ausgeführt via SSH-Profil `dev-node-01`",
            "Befehl: df -h",
        ],
    )

    import asyncio

    entry, count, status = asyncio.run(
        chat_learn_mode.finish_chat_learn_mode(tmp_path, username="neo", session_id="s1", llm_client=None, language="de")
    )

    assert status == "stored"
    assert count == 1
    assert entry is not None
    assert str(entry["recipe_id"]).startswith("chat-learn-")
    assert entry["curation_status"] == "ok"
    assert saved_entries
    assert saved_entries[0]["curation_policy"] == "context_only_not_executable"
    assert saved_entries[0]["recipe_scope"]["learning_origin"] == "chat_learn_mode"
