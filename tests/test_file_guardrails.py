from __future__ import annotations

from types import SimpleNamespace

from aria.core.skill_runtime import CustomSkillRuntime


def _runtime(*, sftp: object | None = None, smb: object | None = None, guardrails: dict[str, object] | None = None) -> CustomSkillRuntime:
    settings = SimpleNamespace(
        connections=SimpleNamespace(
            sftp={"ops-sftp": sftp} if sftp is not None else {},
            smb={"nas-share": smb} if smb is not None else {},
        ),
        security=SimpleNamespace(guardrails=guardrails or {}),
    )
    return CustomSkillRuntime(
        settings=settings,
        llm_client=None,
        memory_skill_getter=lambda: None,
        web_search_skill_getter=lambda: None,
        execute_custom_ssh_command=lambda **_: None,
        extract_memory_store_text=lambda *args, **kwargs: "",
        extract_memory_recall_query=lambda *args, **kwargs: "",
        extract_web_search_query=lambda *args, **kwargs: "",
        facts_collection_for_user=lambda user: f"facts-{user}",
        preferences_collection_for_user=lambda user: f"prefs-{user}",
        normalize_spaces=lambda text: " ".join(str(text or "").split()),
        truncate_text=lambda text, limit=4000: str(text or "")[:limit],
    )


def test_sftp_read_blocks_on_file_guardrail() -> None:
    runtime = _runtime(
        sftp=SimpleNamespace(
            host="sftp.example.local",
            user="aria",
            port=22,
            timeout_seconds=10,
            password="secret",
            key_path="",
            root_path="/srv/data",
            guardrail_ref="readonly-docs",
        ),
        guardrails={
            "readonly-docs": {
                "kind": "file_access",
                "allow_terms": ["/srv/data/docs"],
                "deny_terms": ["/srv/data/private"],
            }
        },
    )

    try:
        runtime.execute_sftp_read("ops-sftp", "/private/secrets.txt")
    except ValueError as exc:
        assert "Datei-Guardrail erlaubt diese Anfrage nicht" in str(exc)
        assert "readonly-docs" in str(exc)
    else:
        raise AssertionError("SFTP read should have been blocked by guardrail")


def test_smb_write_blocks_on_file_guardrail_allowlist_miss() -> None:
    runtime = _runtime(
        smb=SimpleNamespace(
            host="nas.local",
            share="docs",
            user="aria",
            password="secret",
            port=445,
            timeout_seconds=10,
            root_path="/team",
            guardrail_ref="team-readonly",
        ),
        guardrails={
            "team-readonly": {
                "kind": "file_access",
                "allow_terms": ["/team/reports"],
                "deny_terms": [],
            }
        },
    )

    try:
        runtime.execute_smb_write("nas-share", "/finance/budget.txt", "classified")
    except ValueError as exc:
        assert "Datei-Guardrail erlaubt diese Anfrage nicht" in str(exc)
        assert "team-readonly" in str(exc)
    else:
        raise AssertionError("SMB write should have been blocked by guardrail allowlist")
