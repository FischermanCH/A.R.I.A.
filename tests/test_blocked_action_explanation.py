import asyncio

from aria.core.blocked_action_explanation import explain_blocked_action


class _Response:
    content = (
        "Die Aktion wurde durch eine Sicherheitsrichtlinie blockiert.\n\n"
        "**Geplante Aktion:** SSH-Befehl `sudo systemctl restart pihole-FTL` auf Ziel `ssh/pihole1`\n\n"
        "Der Befehl zum Neustart des DNS-Servers ist durch die aktive Guardrail-Konfiguration nicht erlaubt.\n\n"
        "Guardrail pruefen/anpassen: ssh-healtcheck"
    )


class _LLM:
    async def chat(self, *_args, **_kwargs):
        return _Response()


class _SlowLLM:
    async def chat(self, *_args, **_kwargs):
        await asyncio.sleep(0.05)
        return _Response()


def test_blocked_action_explanation_deduplicates_preview_and_canonicalizes_guardrail_link() -> None:
    async def _run() -> None:
        result = await explain_blocked_action(
            llm_client=_LLM(),
            user_message="starte meinen dns server neu",
            fallback_text="ARIA kann diese Aktion auf ssh/pihole1 nicht ausfuehren: SSH command: sudo systemctl restart pihole-FTL",
            language="de",
            user_id="u1",
            request_id="r1",
            target="ssh/pihole1",
            preview="SSH command: sudo systemctl restart pihole-FTL",
            capability="ssh_command",
            policy_reason="ssh_command_not_in_allow_list",
            policy_reason_label="This SSH command does not match the configured allowlist for this profile.",
            guardrail_ref="ssh-healtcheck",
            guardrail_kind="ssh_command",
        )

        assert result.used_llm is True
        assert result.text.count("Geplante Aktion") == 1
        assert "Geplante Aktion: SSH command:" not in result.text
        assert "Guardrail pruefen/anpassen: ssh-healtcheck" not in result.text
        assert "Guardrail pruefen/anpassen: [ssh-healtcheck](/config/security?guardrail_ref=ssh-healtcheck)" in result.text
        assert "(/config/security?guardrail_ref=ssh-healtcheck)" in result.text

    asyncio.run(_run())


def test_blocked_action_explanation_times_out_to_fast_fallback() -> None:
    async def _run() -> None:
        result = await explain_blocked_action(
            llm_client=_SlowLLM(),
            user_message="starte meinen dns server neu",
            fallback_text="ARIA kann diese Aktion auf ssh/pihole1 nicht ausfuehren: SSH command: sudo systemctl restart pihole-FTL",
            language="de",
            user_id="u1",
            request_id="r1",
            target="ssh/pihole1",
            preview="SSH command: sudo systemctl restart pihole-FTL",
            capability="ssh_command",
            policy_reason="ssh_command_not_in_allow_list",
            policy_reason_label="This SSH command does not match the configured allowlist for this profile.",
            guardrail_ref="ssh-healtcheck",
            guardrail_kind="ssh_command",
            timeout_seconds=0.001,
        )

        assert result.used_llm is False
        assert "reason=llm_timeout" in result.debug_line
        assert "sudo systemctl restart pihole-FTL" in result.text
        assert "[ssh-healtcheck](/config/security?guardrail_ref=ssh-healtcheck)" in result.text
        assert "(/config/security?guardrail_ref=ssh-healtcheck)" in result.text

    asyncio.run(_run())


def test_blocked_action_explanation_timeout_uses_guardrail_security_fallback_for_webhook() -> None:
    async def _run() -> None:
        result = await explain_blocked_action(
            llm_client=_SlowLLM(),
            user_message="sende an webhook : delete user record",
            fallback_text="ARIA kann diese Aktion auf webhook/n8n-test-webhook nicht ausfuehren: Webhook payload: delete user record",
            language="de",
            user_id="u1",
            request_id="r1",
            target="webhook/n8n-test-webhook",
            preview="Webhook payload: delete user record",
            capability="webhook_send",
            policy_reason="guardrail_denied",
            policy_reason_label="Guardrail profile blocks this action.",
            guardrail_ref="webhook-status-benachrichtigung",
            guardrail_kind="http_request",
            timeout_seconds=0.001,
        )

        assert result.used_llm is False
        assert "reason=llm_timeout" in result.debug_line
        assert "wurde durch das Guardrail-Profil `webhook-status-benachrichtigung` blockiert" in result.text
        assert "aktive Sicherheitsregel" in result.text
        assert "WebHook payload" not in result.text
        assert "Geplante Aktion: Webhook payload: delete user record" in result.text
        assert "[webhook-status-benachrichtigung](/config/security?guardrail_ref=webhook-status-benachrichtigung)" in result.text

    asyncio.run(_run())


def test_blocked_action_explanation_can_skip_llm_for_safety_fast_path() -> None:
    async def _run() -> None:
        result = await explain_blocked_action(
            llm_client=_LLM(),
            user_message="starte meinen dns server neu",
            fallback_text="ARIA kann diese Aktion auf ssh/pihole1 nicht ausfuehren: SSH command: sudo systemctl restart pihole-FTL",
            language="de",
            user_id="u1",
            request_id="r1",
            target="ssh/pihole1",
            preview="SSH command: sudo systemctl restart pihole-FTL",
            capability="ssh_command",
            policy_reason="ssh_command_not_in_allow_list",
            policy_reason_label="This SSH command does not match the configured allowlist for this profile.",
            guardrail_ref="ssh-healtcheck",
            guardrail_kind="ssh_command",
            skip_llm_reason="ssh_policy_block_fast_path",
        )

        assert result.used_llm is False
        assert "reason=ssh_policy_block_fast_path" in result.debug_line
        assert "sudo systemctl restart pihole-FTL" in result.text
        assert "[ssh-healtcheck](/config/security?guardrail_ref=ssh-healtcheck)" in result.text
        assert "(/config/security?guardrail_ref=ssh-healtcheck)" in result.text

    asyncio.run(_run())
