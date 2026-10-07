"""Production-shaped browser scenarios; collected only by scripts/e2e/run.sh."""

from __future__ import annotations

import time
import os
from pathlib import Path
import sqlite3

import pytest
from playwright.sync_api import expect

from .browser_driver import AriaBrowser, HarnessControl


pytestmark = pytest.mark.e2e

EXECUTE = "mcp__blender__execute_blender_code"
LOOK = "mcp__blender__look"
SEARCH_ASSETS = "mcp__blender__search_assets"
SCENE = "mcp__blender__get_scene_info"
REVIEW_EXECUTE = "mcp__review__execute_blender_code"


def _text(text: str, *, delay: float = 0.0) -> dict[str, object]:
    return {"type": "text", "text": text, "delay_seconds": delay}


def _tool(name: str, arguments: dict[str, object], *, delay: float = 0.0) -> dict[str, object]:
    return {"type": "tool_use", "name": name, "input": arguments, "delay_seconds": delay}


def _image_sources(value: object) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    if isinstance(value, dict):
        source = value.get("source")
        if value.get("type") == "image" and isinstance(source, dict):
            found.append(source)
        for item in value.values():
            found.extend(_image_sources(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_image_sources(item))
    return found


def _latest_tool_result_images(payload: object) -> int:
    messages = payload.get("messages", []) if isinstance(payload, dict) else []
    for message in reversed(messages if isinstance(messages, list) else []):
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        blocks = content if isinstance(content, list) else []
        tool_results = [row for row in blocks if isinstance(row, dict) and row.get("type") == "tool_result"]
        if tool_results:
            return len(_image_sources(tool_results[-1]))
    return 0


def test_s1_basic_chat_details_usage(
    aria_browser: AriaBrowser, controls: HarnessControl,
) -> None:
    controls.script("S1", [_text("Hallo aus dem strikten E2E-Prüfstand.")])
    aria_browser.open_chat()
    bubble = aria_browser.send_chat("Antworte kurz mit einer Begrüßung.")
    expect(bubble).to_contain_text("strikten E2E-Prüfstand")
    bubble.locator("details.msg-details").click()
    expect(bubble.locator("details.msg-details")).to_contain_text("cache_read=7")
    assert not controls.anthropic_logs()["violations"]
    aria_browser.assert_clean_js()


def test_s2_detach_completes_without_navigation(
    aria_browser: AriaBrowser, controls: HarnessControl,
) -> None:
    controls.script("S2", [_text("Der langsame Auftrag ist abgeschlossen.", delay=5.0)])
    aria_browser.open_chat()
    aria_browser.reset_navigation_evidence()
    bubble = aria_browser.send_chat("Führe einen langsamen mehrstufigen Testauftrag aus.", timeout_ms=12_000)
    expect(bubble.locator("a[href*='/jobs/panel#job-']")).to_be_visible()
    expect(bubble.locator("[data-agent-job-controls]")).to_be_visible()
    aria_browser.wait_for_job_notice("abgeschlossen", timeout_ms=25_000)
    assert aria_browser.evidence.navigations == []
    assert not controls.anthropic_logs()["violations"]
    aria_browser.assert_clean_js()


def test_s3_pause_resume_exactly_once(
    aria_browser: AriaBrowser, controls: HarnessControl,
) -> None:
    controls.mcp("reset")
    controls.script("S3", [
        _tool(EXECUTE, {"code": "name='E2E-Step-1'"}, delay=4.0),
        _tool(EXECUTE, {"code": "name='E2E-Step-2'"}),
        _text("Beide Blender-Schritte sind abgeschlossen."),
    ])
    aria_browser.open_chat()
    bubble = aria_browser.send_chat("Erzeuge zwei Testobjekte nacheinander in Blender.", timeout_ms=12_000)
    expect(bubble.locator("[data-agent-job-action='pause']")).to_be_visible()
    bubble.locator("[data-agent-job-action='pause']").click()
    aria_browser.wait_for_job_notice("paus", timeout_ms=25_000)
    calls_at_pause = [row for row in controls.mcp_logs()["calls"] if row["tool"] == "execute_blender_code"]
    time.sleep(3.0)
    assert [row for row in controls.mcp_logs()["calls"] if row["tool"] == "execute_blender_code"] == calls_at_pause

    aria_browser.page.goto(f"{aria_browser.base_url}/jobs/panel", wait_until="domcontentloaded")
    resume = aria_browser.page.locator("[data-agent-job-card] button", has_text="Fortsetzen").first
    expect(resume).to_be_visible()
    resume.click()
    aria_browser.page.wait_for_load_state("domcontentloaded")
    aria_browser.page.goto(f"{aria_browser.base_url}/", wait_until="domcontentloaded")
    aria_browser.wait_for_job_notice("abgeschlossen", timeout_ms=30_000)
    execute_calls = [row for row in controls.mcp_logs()["calls"] if row["tool"] == "execute_blender_code"]
    codes = [row["arguments"]["code"] for row in execute_calls]
    assert codes.count("name='E2E-Step-1'") == 1
    assert codes.count("name='E2E-Step-2'") == 1
    assert not controls.anthropic_logs()["violations"]
    aria_browser.assert_clean_js()


def test_s4_panel_updates_preserve_scroll_and_do_not_navigate(
    aria_browser: AriaBrowser, controls: HarnessControl,
) -> None:
    controls.script("S4", [_text("Langlauf beendet.", delay=13.0)])
    aria_browser.open_chat()
    aria_browser.send_chat("Starte einen beobachtbaren langen Auftrag.", timeout_ms=12_000)
    job = aria_browser.wait_for_job_bubble()
    job_id = job.get_attribute("data-agent-job-id")
    aria_browser.page.goto(f"{aria_browser.base_url}/jobs/panel#job-{job_id}", wait_until="domcontentloaded")
    header = aria_browser.page.locator(f"#job-{job_id} [data-agent-job-header]")
    controls_node = header.locator("[data-agent-job-controls]")
    expect(controls_node).to_be_visible()
    box = controls_node.bounding_box()
    assert box and box["y"] >= 0 and box["y"] + box["height"] <= 800
    aria_browser.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    before = aria_browser.page.evaluate("window.scrollY")
    aria_browser.reset_navigation_evidence()
    time.sleep(8.2)
    after = aria_browser.page.evaluate("window.scrollY")
    assert abs(float(after) - float(before)) <= 2
    assert aria_browser.evidence.navigations == []
    aria_browser.assert_clean_js()


def test_s5_mcp_down_footer_once_and_recovery(
    aria_browser: AriaBrowser, controls: HarnessControl,
) -> None:
    first_footer_count = -1
    second_footer_count = -1
    try:
        controls.mcp("stop")
        controls.wait_mcp_running(False)
        controls.script("S5-down", [
            _tool(SCENE, {}),
            _text("Der Blender-Server ist derzeit vorübergehend getrennt."),
            _text("Der Blender-Server bleibt vorübergehend getrennt."),
        ])
        aria_browser.open_chat()
        first = aria_browser.send_chat("Zeige den Status vom Blender MCP Server.", timeout_ms=30_000)
        first_text = first.locator(".msg-text").inner_text().lower()
        first_footer_count = first_text.count("mcp-server blender ist gerade nicht erreichbar")
        second = aria_browser.send_chat("Prüfe Blender bitte erneut.", timeout_ms=20_000)
        second_text = second.locator(".msg-text").inner_text().lower()
        second_footer_count = second_text.count("mcp-server blender ist gerade nicht erreichbar")
    finally:
        controls.mcp("start")
        controls.wait_mcp_running(True)

    time.sleep(31.0)
    controls.script("S5-recovered", [
        _tool(SCENE, {}),
        _text("Blender ist wieder verbunden."),
    ])
    recovered = aria_browser.send_chat("Prüfe Blender nach dem Neustart.", timeout_ms=30_000)
    recovered_text = recovered.locator(".msg-text").inner_text().lower()
    observed = (
        first_footer_count,
        second_footer_count,
        "wieder verbunden" in recovered_text,
    )
    assert observed == (1, 1, True), (
        "expected one honest down footer on each failed turn and successful recovery; "
        f"observed first={observed[0]} second={observed[1]} recovered={observed[2]}"
    )
    assert not controls.anthropic_logs()["violations"]
    aria_browser.assert_clean_js(allow_failed_contains=("/chat",))


def test_s6_vision_tool_result_contract(
    aria_browser: AriaBrowser, controls: HarnessControl,
) -> None:
    controls.mcp("reset")
    controls.script("S6", [
        _tool(LOOK, {}),
        _text("Das Werkzeugbild wurde sichtbar verarbeitet."),
    ])
    aria_browser.open_chat()
    bubble = aria_browser.send_chat("Schau dir die aktuelle Blender-Szene an.", timeout_ms=30_000)
    expect(bubble).to_contain_text("Werkzeugbild")
    logs = controls.anthropic_logs()
    assert not logs["violations"]
    payloads = [row["payload"] for row in logs["requests"]]
    assert any("[base64 omitted;" in str(payload) for payload in payloads)
    aria_browser.assert_clean_js()


def test_s7_action_claim_guard_and_recap_anchor(
    aria_browser: AriaBrowser, controls: HarnessControl,
) -> None:
    controls.script("S7", [
        _text("Ich habe einen blauen Würfel erstellt."),
        _text("Ich habe einen blauen Würfel erstellt."),
        _text("In diesem Chat wurde kein Werkzeugergebnis für einen Würfel aufgezeichnet."),
    ])
    aria_browser.open_chat()
    refusal = aria_browser.send_chat("Teste eine Behauptung über eine ausgeführte Blender-Aktion.", timeout_ms=30_000)
    refusal_text = refusal.locator(".msg-text").inner_text().lower()
    assert "blauen würfel erstellt" not in refusal_text
    assert "nicht ausgeführt" in refusal_text or "nicht bestätigen" in refusal_text
    recap = aria_browser.send_chat("Was geschah in diesem Chat?", timeout_ms=20_000)
    expect(recap).to_contain_text("In diesem Chat")
    assert not controls.anthropic_logs()["violations"]
    aria_browser.assert_clean_js()


def test_s8_lost_response_recovers_job_without_duplicate_history(
    aria_browser: AriaBrowser, controls: HarnessControl,
) -> None:
    controls.script("S8", [_text("Verlorene Antwort abgeschlossen.", delay=7.0)])
    aria_browser.open_chat()
    intercepted = {"done": False}

    def abort_after_server(route):  # noqa: ANN001
        route.fetch()
        intercepted["done"] = True
        route.abort("failed")

    aria_browser.page.route("**/chat", abort_after_server, times=1)
    aria_browser.page.locator("#message").fill("Starte einen Auftrag mit verlorener Browserantwort.")
    aria_browser.page.locator("#chat-form #send-btn").click()
    fallback = aria_browser.wait_for_job_bubble(timeout_ms=20_000)
    expect(fallback.locator("a[href*='/jobs/panel#job-']")).to_be_visible()
    expect(fallback.locator("[data-agent-job-controls]")).to_be_visible()
    assert intercepted["done"] is True
    aria_browser.page.unroute_all(behavior="wait")
    job_id = fallback.get_attribute("data-agent-job-id")
    aria_browser.page.wait_for_timeout(8_000)
    aria_browser.page.reload(wait_until="domcontentloaded")
    assert aria_browser.page.locator(
        f"#messages .msg-assistant[data-agent-job-id='{job_id}'][data-agent-job-notice='false']"
    ).count() == 1
    aria_browser.assert_clean_js(
        allow_failed_contains=("POST ", "/chat"),
        allow_console_contains=("net::ERR_FAILED",),
    )


def test_s9_budget_finalizer_strict_contract(
    aria_browser: AriaBrowser, controls: HarnessControl,
) -> None:
    steps = [
        _tool(EXECUTE, {"code": f"name='Budget-{index}'"})
        for index in range(1, 33)
    ] + [_text("Der Schritt-Budget-Abschluss ist ehrlich beendet.")]
    controls.mcp("reset")
    controls.script("S9", steps)
    aria_browser.open_chat()
    bubble = aria_browser.send_chat("Führe mehr Blender-Schritte aus als das Agent-Budget erlaubt.", timeout_ms=45_000)
    expect(bubble).to_be_visible()
    logs = controls.anthropic_logs()
    assert not logs["violations"], logs["violations"]
    text = bubble.locator(".msg-text").inner_text()
    assert "Der Schritt-Budget-Abschluss ist ehrlich beendet." in text
    final_request = logs["requests"][-1]["payload"]
    assert logs["requests"][-1]["accepted"] is True
    assert final_request.get("tools")
    assert "tool_choice" not in final_request
    aria_browser.assert_clean_js()


def test_s10_correction_running_and_paused(
    aria_browser: AriaBrowser, controls: HarnessControl,
) -> None:
    controls.script("S10-running", [
        _tool(EXECUTE, {"code": "name='Before-Correction'"}, delay=4.0),
        _text("Die Korrektur auf Blau wurde übernommen."),
    ])
    aria_browser.open_chat()
    bubble = aria_browser.send_chat("Erzeuge ein Objekt und arbeite danach weiter.", timeout_ms=12_000)
    bubble.locator("[data-agent-job-action='correct']").click()
    editor = bubble.locator("[data-agent-job-correction]")
    expect(editor).to_be_visible()
    editor.locator("textarea").fill("Ändere die Farbe auf Blau.")
    editor.locator(".js-agent-job-correction-submit").click()
    aria_browser.wait_for_job_notice("Korrektur", timeout_ms=30_000)
    logs = controls.anthropic_logs()
    assert not logs["violations"]
    assert any(
        "KORREKTUR VOM NUTZER" in str(row["payload"])
        and "Ändere die Farbe auf Blau" in str(row["payload"])
        for row in logs["requests"]
    )

    controls.script("S10-paused", [
        _tool(EXECUTE, {"code": "name='Pause-Before-Correction'"}, delay=4.0),
        _text("Die während der Pause gesendete Korrektur wurde übernommen."),
    ])
    second = aria_browser.send_chat("Starte noch einen korrigierbaren Auftrag.", timeout_ms=12_000)
    second.locator("[data-agent-job-action='pause']").click()
    paused = aria_browser.wait_for_job_notice("paus", timeout_ms=25_000)
    paused.locator("[data-agent-job-action='correct']").click()
    paused_editor = paused.locator("[data-agent-job-correction]")
    paused_editor.locator("textarea").fill("Nutze stattdessen Grün.")
    paused_editor.locator(".js-agent-job-correction-submit").click()
    paused.locator("[data-agent-job-action='resume']").click()
    aria_browser.wait_for_job_notice("während der Pause", timeout_ms=30_000)
    logs = controls.anthropic_logs()
    assert not logs["violations"]
    assert any("Nutze stattdessen Grün" in str(row["payload"]) for row in logs["requests"])
    aria_browser.assert_clean_js()


def test_s11_in_job_confirmation_confirm_and_decline(
    aria_browser: AriaBrowser, controls: HarnessControl,
) -> None:
    controls.mcp("reset")
    controls.script("S11-confirm", [
        _tool(REVIEW_EXECUTE, {"code": "name='Confirmed-Exactly-Once'"}, delay=4.0),
        _text("Dieses Blender-Skript ausführen?"),
        _text("Die bestätigte Aktion wurde fortgesetzt und abgeschlossen."),
    ])
    aria_browser.open_chat()
    aria_browser.send_chat("Starte einen bestätigungspflichtigen Hintergrund-Auftrag.", timeout_ms=12_000)
    notice = aria_browser.wait_for_job_notice("Bestätigung", timeout_ms=25_000)
    expect(notice.locator("[data-agent-job-action='confirm']")).to_be_visible()
    notice.locator("[data-agent-job-action='confirm']").click()
    aria_browser.wait_for_job_notice("abgeschlossen", timeout_ms=30_000)
    calls = [
        row for row in controls.mcp_logs()["calls"]
        if row["tool"] == "execute_blender_code"
        and row["arguments"].get("code") == "name='Confirmed-Exactly-Once'"
    ]
    assert len(calls) == 1
    assert not controls.anthropic_logs()["violations"]

    controls.mcp("reset")
    controls.script("S11-decline", [
        _tool(REVIEW_EXECUTE, {"code": "name='Must-Not-Run'"}, delay=4.0),
        _text("Dieses Blender-Skript ausführen?"),
        _text("Die abgelehnte Aktion wurde übersprungen; der Auftrag wurde fortgesetzt."),
    ])
    aria_browser.send_chat("Starte einen zweiten bestätigungspflichtigen Auftrag.", timeout_ms=12_000)
    decline_notice = aria_browser.wait_for_job_notice("Bestätigung", timeout_ms=25_000)
    decline_notice.locator("[data-agent-job-action='decline']").click()
    aria_browser.wait_for_job_notice("fortgesetzt", timeout_ms=30_000)
    calls = [
        row for row in controls.mcp_logs()["calls"]
        if row["tool"] == "execute_blender_code"
        and row["arguments"].get("code") == "name='Must-Not-Run'"
    ]
    assert calls == []
    assert not controls.anthropic_logs()["violations"]
    aria_browser.assert_clean_js()


def test_s12_global_header_indicator_and_terminal_toast_without_navigation(
    aria_browser: AriaBrowser, controls: HarnessControl,
) -> None:
    # Leave a deterministic observation window after the three-second detach
    # budget so the indicator is visible before the terminal transition.
    controls.script("S12", [_text("Der globale Hintergrund-Auftrag ist fertig.", delay=8.0)])
    aria_browser.open_chat()
    aria_browser.send_chat("Starte einen global sichtbaren Hintergrund-Auftrag.", timeout_ms=12_000)
    aria_browser.page.goto(f"{aria_browser.base_url}/config", wait_until="domcontentloaded")
    aria_browser.reset_navigation_evidence()
    indicator = aria_browser.page.locator("#global-agent-job-indicator")
    expect(indicator).to_be_visible(timeout=12_000)
    toast = aria_browser.page.locator(".global-agent-job-toast")
    expect(toast).to_be_visible(timeout=25_000)
    expect(toast).to_contain_text("fertig")
    assert aria_browser.evidence.navigations == []
    aria_browser.assert_clean_js()


def test_s13_incomplete_job_is_warning_with_human_summary_and_error_detail(
    aria_browser: AriaBrowser, controls: HarnessControl,
) -> None:
    steps = [
        _tool(EXECUTE, {"code": f"name='Partial-{index}'"}, delay=4.0 if index == 1 else 0.0)
        for index in range(1, 33)
    ] + [
        {"type": "error", "status": 400, "error_type": "invalid_request_error", "message": "finalizer exploded safely"},
    ]
    controls.mcp("reset")
    controls.script("S13", steps)
    aria_browser.open_chat()
    aria_browser.send_chat("Erschöpfe das Schritt-Budget mit erfolgreichen Blender-Schritten.", timeout_ms=12_000)
    budget_notice = aria_browser.wait_for_job_notice("Schritt-Budget erreicht", timeout_ms=35_000)
    budget_notice.locator("[data-agent-job-action='finish']").click()
    notice = aria_browser.wait_for_job_notice("teilweise", timeout_ms=35_000)
    text = notice.locator(".msg-text").inner_text().lower()
    assert "execute_blender_code" in text and "erfolgreich" in text
    notice.locator("details.msg-details").click()
    expect(notice.locator("details.msg-details")).to_contain_text("finalizer exploded safely")
    assert not controls.anthropic_logs()["violations"]
    aria_browser.assert_clean_js()


def test_s14_mislabeled_webp_is_corrected_inside_detached_job(
    aria_browser: AriaBrowser, controls: HarnessControl,
) -> None:
    controls.mcp("reset")
    controls.script("S14", [
        _tool(SEARCH_ASSETS, {}, delay=4.0),
        _text("Das gefundene WebP-Asset wurde anhand seiner echten Bilddaten verarbeitet."),
    ])
    aria_browser.open_chat()
    aria_browser.send_chat("Suche ein Poly-Haven-Testasset im Hintergrund.", timeout_ms=12_000)
    aria_browser.wait_for_job_bubble()
    aria_browser.wait_for_job_notice("WebP-Asset", timeout_ms=30_000)

    logs = controls.anthropic_logs()
    assert not logs["violations"]
    image_sources = _image_sources([row["payload"] for row in logs["requests"]])
    assert image_sources and all(row.get("media_type") == "image/webp" for row in image_sources)
    assert any(row["tool"] == "search_assets" for row in controls.mcp_logs()["calls"])
    aria_browser.assert_clean_js()


def test_s15_provider_image_rejection_retries_without_images(
    aria_browser: AriaBrowser, controls: HarnessControl,
) -> None:
    controls.mcp("reset")
    controls.script("S15", [
        _tool(LOOK, {}, delay=4.0),
        {
            "type": "error",
            "status": 400,
            "error_type": "invalid_request_error",
            "message": (
                "messages.4.content.1.tool_result.content.1.image.source.base64: "
                "The image was specified using the image/png media type, but the image "
                "appears to be a image/webp image"
            ),
        },
        _text("Das Ergebnis wurde nach der Bild-Ablehnung ehrlich ohne Bild fortgesetzt."),
    ])
    aria_browser.open_chat()
    aria_browser.send_chat("Prüfe die Szene trotz eines abgelehnten Bildblocks.", timeout_ms=12_000)
    aria_browser.wait_for_job_bubble()
    notice = aria_browser.wait_for_job_notice("ohne Bild fortgesetzt", timeout_ms=30_000)
    notice.locator("details.msg-details").click()
    expect(notice.locator("details.msg-details")).to_contain_text(
        "mcp_vision degraded=provider_rejected_image",
    )

    logs = controls.anthropic_logs()
    assert not logs["violations"]
    image_presence = ["'type': 'image'" in str(row["payload"]) for row in logs["requests"]]
    assert image_presence[-2:] == [True, False]
    aria_browser.assert_clean_js()


def test_s16_post_confirmation_resume_failure_is_terminal(
    aria_browser: AriaBrowser, controls: HarnessControl,
) -> None:
    controls.mcp("reset")
    controls.script("S16", [
        _tool(REVIEW_EXECUTE, {"code": "name='S16-Confirmed'"}, delay=4.0),
        _text("Dieses Blender-Skript ausführen?"),
        {
            "type": "error",
            "status": 400,
            "error_type": "invalid_request_error",
            "message": "post-confirm resume exploded safely",
        },
    ])
    aria_browser.open_chat()
    bubble = aria_browser.send_chat(
        "Starte einen bestätigungspflichtigen Auftrag mit Fehler nach Bestätigung.",
        timeout_ms=12_000,
    )
    job_id = bubble.get_attribute("data-agent-job-id")
    confirmation = aria_browser.wait_for_job_notice("Bestätigung", timeout_ms=25_000)
    confirmation.locator("[data-agent-job-action='confirm']").click()
    failure = aria_browser.wait_for_job_notice("fehlgeschlagen", timeout_ms=30_000)
    expect(failure).to_contain_text("post-confirm resume exploded safely")
    status = aria_browser.page.evaluate(
        """async (jobId) => {
          const payload = await (await fetch('/jobs', {credentials: 'same-origin'})).json();
          const job = payload.jobs.find((row) => row.job_id === jobId);
          return job ? job.status : 'missing';
        }""",
        job_id,
    )
    assert status == "error"
    assert not controls.anthropic_logs()["violations"]
    aria_browser.assert_clean_js()


def test_s17_budget_extension_and_finish_now(
    aria_browser: AriaBrowser, controls: HarnessControl,
) -> None:
    controls.mcp("reset")
    controls.script("S17-extend", [
        _tool(EXECUTE, {"code": f"name='S17-Extend-{index}'"}, delay=4.0 if index == 1 else 0.0)
        for index in range(1, 34)
    ] + [_text("S17 wurde nach der Budget-Erweiterung abgeschlossen.")])
    aria_browser.open_chat()
    aria_browser.send_chat("S17 Budget-Erweiterung mit neun Schritten.", timeout_ms=12_000)
    notice = aria_browser.wait_for_job_notice("Schritt-Budget erreicht", timeout_ms=35_000)
    expect(notice.locator("[data-agent-job-action='extend']")).to_be_visible()
    notice.locator("[data-agent-job-action='extend']").click()
    aria_browser.wait_for_job_notice("Budget-Erweiterung abgeschlossen", timeout_ms=35_000)

    controls.script("S17-finish", [
        _tool(EXECUTE, {"code": f"name='S17-Finish-{index}'"}, delay=4.0 if index == 1 else 0.0)
        for index in range(1, 33)
    ] + [_text("S17 wurde auf Wunsch jetzt abgeschlossen.")])
    aria_browser.send_chat("S17 jetzt abschließen nach dem Budget.", timeout_ms=12_000)
    finish_notice = aria_browser.wait_for_job_notice("Schritt-Budget erreicht", timeout_ms=35_000)
    expect(finish_notice.locator("[data-agent-job-action='finish']")).to_be_visible()
    finish_notice.locator("[data-agent-job-action='finish']").click()
    aria_browser.wait_for_job_notice("auf Wunsch jetzt abgeschlossen", timeout_ms=35_000)
    assert not controls.anthropic_logs()["violations"]
    aria_browser.assert_clean_js()


def test_s18_retention_delete_clear_and_active_refusal(
    aria_browser: AriaBrowser, controls: HarnessControl,
) -> None:
    controls.script("S18-terminal", [_text("S18 terminal erledigt.", delay=4.0)])
    aria_browser.open_chat()
    bubble = aria_browser.send_chat("S18 terminalen Job erzeugen.", timeout_ms=12_000)
    terminal_id = bubble.get_attribute("data-agent-job-id")
    aria_browser.wait_for_job_notice("terminal erledigt", timeout_ms=25_000)
    db_path = Path(os.environ["ARIA_E2E_DATA_DIR"]) / "runtime" / "agent_jobs.sqlite3"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "UPDATE agent_jobs SET updated_at=? WHERE job_id=?",
            (time.time() - 15 * 86400, terminal_id),
        )
        connection.execute(
            "INSERT INTO agent_jobs(job_id,user_id,goal,status,step_log,result,created_at,updated_at,worker_id) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            ("s18-running", "e2e-admin", "active", "running", "[]", "", time.time(), time.time(), "e2e"),
        )
    aria_browser.page.goto(aria_browser.base_url + "/jobs/panel?job=" + str(terminal_id), wait_until="domcontentloaded")
    expect(aria_browser.page.locator("body")).to_contain_text("Job nicht mehr vorhanden")
    assert aria_browser.page.locator("#job-s18-running").count() == 1
    active_delete = aria_browser.page.evaluate(
        """async () => {
          const csrf = document.querySelector('input[name=csrf_token]').value;
          const response = await fetch('/jobs/s18-running/delete', {method:'POST', headers:{'X-CSRF-Token':csrf,'Accept':'application/json'}});
          return await response.json();
        }"""
    )
    assert active_delete["outcome"] == "not_terminal"

    with sqlite3.connect(db_path) as connection:
        now = time.time()
        connection.execute(
            "INSERT INTO agent_jobs(job_id,user_id,goal,status,step_log,result,created_at,updated_at,worker_id) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            ("s18-done-one", "e2e-admin", "done one", "done", "[]", "ok", now, now, "e2e"),
        )
        connection.execute(
            "INSERT INTO agent_jobs(job_id,user_id,goal,status,step_log,result,created_at,updated_at,worker_id) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            ("s18-done-two", "e2e-admin", "done two", "done", "[]", "ok", now, now, "e2e"),
        )
    aria_browser.page.reload(wait_until="domcontentloaded")
    aria_browser.page.locator("#job-s18-done-one form[action$='/delete'] button").click()
    expect(aria_browser.page.locator("#job-s18-done-one")).to_have_count(0)
    aria_browser.page.locator("form[action='/jobs/clear-completed'] button").click()
    expect(aria_browser.page.locator("#job-s18-done-two")).to_have_count(0)
    assert aria_browser.page.locator("#job-s18-running").count() == 1
    aria_browser.assert_clean_js()


def test_s19_optional_temperature_rejection_memory_and_empty_config(
    aria_browser: AriaBrowser, controls: HarnessControl,
) -> None:
    temperature_free = ("claude-sonnet-5",)
    controls.script(
        "S19-numeric",
        [_text("S19 Temperatur-Kompatibilität aktiv.")],
        temperature_free_models=temperature_free,
    )
    aria_browser.open_chat()
    first = aria_browser.send_chat("S19 prüfe die Modell-Kompatibilität.", timeout_ms=20_000)
    expect(first).to_contain_text("Temperatur-Kompatibilität aktiv")
    first.locator("details.msg-details").click()
    expect(first.locator("details.msg-details")).to_contain_text(
        "llm_param_compat model=anthropic/claude-sonnet-5 omitted=temperature"
    )
    first_logs = controls.anthropic_logs()
    assert len(first_logs["requests"]) == 2
    assert first_logs["requests"][0]["accepted"] is False
    assert first_logs["requests"][0]["payload"]["temperature"] == 0.0
    assert first_logs["requests"][1]["accepted"] is True
    assert "temperature" not in first_logs["requests"][1]["payload"]

    controls.mcp("reset")
    controls.script(
        "S19-remembered-detached",
        [
            _tool(EXECUTE, {"code": "name='S19-Temperature-Free'"}, delay=4.0),
            _text("S19 detached ohne Temperatur abgeschlossen."),
        ],
        temperature_free_models=temperature_free,
    )
    bubble = aria_browser.send_chat(
        "S19 starte einen langsamen Blender-Schritt ohne erneute Temperatur-Ablehnung.",
        timeout_ms=12_000,
    )
    expect(bubble.locator("[data-agent-job-controls]")).to_be_visible()
    aria_browser.wait_for_job_notice("detached ohne Temperatur abgeschlossen", timeout_ms=30_000)
    detached_logs = controls.anthropic_logs()
    assert detached_logs["requests"]
    assert all(row["accepted"] is True for row in detached_logs["requests"])
    assert all("temperature" not in row["payload"] for row in detached_logs["requests"])

    aria_browser.page.goto(f"{aria_browser.base_url}/config/llm", wait_until="domcontentloaded")
    aria_browser.page.locator("#model").fill("anthropic/claude-sonnet-5-empty")
    aria_browser.page.locator("#temperature").fill("")
    aria_browser.page.locator("#profile_name_save").fill("temperature-empty")
    api_key = aria_browser.page.locator("#api_key")
    if not api_key.input_value():
        api_key.fill("e2e-fake-key")
    aria_browser.page.locator("input[name='activate_main']").evaluate(
        "element => { element.value = '1'; }"
    )
    aria_browser.page.locator("form.llm-profile-editor button[type='submit']").click()
    aria_browser.page.wait_for_url(lambda url: "saved=1" in url, timeout=15_000)

    controls.script(
        "S19-empty",
        [_text("S19 leere Temperatur wurde ohne Ablehnung akzeptiert.")],
        temperature_free_models=("claude-sonnet-5-empty",),
    )
    aria_browser.open_chat()
    empty = aria_browser.send_chat("S19 prüfe das leere Temperaturfeld.", timeout_ms=20_000)
    expect(empty).to_contain_text("ohne Ablehnung akzeptiert")
    empty_logs = controls.anthropic_logs()
    assert len(empty_logs["requests"]) == 1
    assert empty_logs["requests"][0]["accepted"] is True
    assert "temperature" not in empty_logs["requests"][0]["payload"]
    assert not empty_logs["violations"]
    aria_browser.assert_clean_js()


def test_s20_budget_pause_notice_exactly_once_for_sixty_seconds(
    aria_browser: AriaBrowser, controls: HarnessControl,
) -> None:
    controls.mcp("reset")
    controls.script("S20", [
        _tool(EXECUTE, {"code": f"name='S20-{index}'"}, delay=4.0 if index == 1 else 0.0)
        for index in range(1, 33)
    ])
    aria_browser.open_chat()
    bubble = aria_browser.send_chat("S20 lasse die Budget-Pause unbeantwortet.", timeout_ms=12_000)
    job_id = bubble.get_attribute("data-agent-job-id")
    other = aria_browser.page.context.new_page()
    other.goto(aria_browser.base_url + "/config", wait_until="domcontentloaded")
    toast = other.locator(".global-agent-job-toast")
    expect(toast).to_contain_text("Schritt-Budget", timeout=45_000)
    toast.locator("button").click()
    other.wait_for_timeout(60_000)
    assert other.locator(".global-agent-job-toast").count() == 0
    other.close()

    aria_browser.page.bring_to_front()
    notice_selector = (
        f"#messages .msg-assistant[data-agent-job-id='{job_id}']"
        "[data-agent-job-notice='true'][data-agent-job-state='agent_job_budget_reached']"
    )
    expect(aria_browser.page.locator(notice_selector)).to_have_count(1, timeout=20_000)
    aria_browser.page.reload(wait_until="domcontentloaded")
    expect(aria_browser.page.locator(notice_selector)).to_have_count(1)
    notice = aria_browser.page.locator(notice_selector)
    notice.locator("[data-agent-job-action='cancel']").click()
    aria_browser.assert_clean_js()


def test_s21_budget_extension_multi_click_is_exactly_once(
    aria_browser: AriaBrowser, controls: HarnessControl,
) -> None:
    controls.mcp("reset")
    controls.script("S21", [
        *[
            _tool(EXECUTE, {"code": f"name='S21-{index}'"}, delay=4.0 if index == 1 else 0.0)
            for index in range(1, 34)
        ],
        _text("S21 wurde nach genau einer Erweiterung abgeschlossen."),
    ])
    aria_browser.open_chat()
    bubble = aria_browser.send_chat("S21 Budget-Erweiterung genau einmal.", timeout_ms=12_000)
    job_id = bubble.get_attribute("data-agent-job-id")
    notice = aria_browser.wait_for_job_notice("Schritt-Budget erreicht", timeout_ms=45_000)
    event_key = notice.get_attribute("data-agent-job-event-key")
    second = aria_browser.page.context.new_page()
    second.goto(aria_browser.base_url + "/jobs/panel", wait_until="domcontentloaded")

    async_post = """async ({jobId, eventKey}) => {
      const token = document.querySelector('meta[name="csrf-token"]').content;
      const response = await fetch('/jobs/' + jobId + '/extend', {
        method: 'POST', credentials: 'same-origin',
        headers: {'X-CSRF-Token': token, 'Accept': 'application/json', 'Content-Type': 'application/x-www-form-urlencoded'},
        body: new URLSearchParams({event_key: eventKey}).toString()
      });
      return await response.json();
    }"""
    results = [
        aria_browser.page.evaluate(async_post, {"jobId": job_id, "eventKey": event_key}),
        second.evaluate(async_post, {"jobId": job_id, "eventKey": event_key}),
        second.evaluate(async_post, {"jobId": job_id, "eventKey": event_key}),
    ]
    assert [row["outcome"] for row in results].count("started") == 1
    assert [row["outcome"] for row in results].count("already_handled") == 2
    second.close()
    aria_browser.page.bring_to_front()
    aria_browser.wait_for_job_notice("genau einer Erweiterung", timeout_ms=45_000)
    execute_calls = [
        row for row in controls.mcp_logs()["calls"]
        if row["tool"] == "execute_blender_code"
    ]
    assert len(execute_calls) == 33
    aria_browser.assert_clean_js()


def test_s22_detached_vision_rolling_window_eight_looks(
    aria_browser: AriaBrowser, controls: HarnessControl,
) -> None:
    controls.mcp("reset")
    controls.script("S22", [
        *[_tool(LOOK, {}, delay=4.0 if index == 0 else 0.0) for index in range(8)],
        _text("S22 acht Sichtprüfungen abgeschlossen."),
    ])
    aria_browser.open_chat()
    aria_browser.send_chat("S22 schaue achtmal nacheinander auf die Szene.", timeout_ms=12_000)
    notice = aria_browser.wait_for_job_notice("acht Sichtprüfungen", timeout_ms=45_000)
    logs = controls.anthropic_logs()
    requests_with_tool_results = [
        row["payload"] for row in logs["requests"]
        if _latest_tool_result_images(row["payload"]) > 0
    ]
    assert len(requests_with_tool_results) == 8
    assert all(_latest_tool_result_images(payload) >= 1 for payload in requests_with_tool_results)
    assert all(len(_image_sources(payload)) <= 4 for payload in requests_with_tool_results)
    notice.locator("details.msg-details").click()
    expect(notice.locator("details.msg-details")).to_contain_text("images=8 live=4 replaced=4")
    assert not logs["violations"]
    aria_browser.assert_clean_js()


def test_s23_truncated_response_retries_once_with_finish_reason(
    aria_browser: AriaBrowser, controls: HarnessControl,
) -> None:
    controls.script("S23", [
        {"type": "text", "text": "", "stop_reason": "max_tokens"},
        _text("S23 wurde nach kleineren Schritten abgeschlossen."),
    ])
    aria_browser.open_chat()
    bubble = aria_browser.send_chat("S23 simuliere eine abgeschnittene Antwort.", timeout_ms=30_000)
    expect(bubble).to_contain_text("kleineren Schritten")
    logs = controls.anthropic_logs()
    assert len(logs["requests"]) == 2
    assert "split the work into smaller steps" in str(logs["requests"][1]["payload"])
    bubble.locator("details.msg-details").click()
    expect(bubble.locator("details.msg-details")).to_contain_text("native_finish_reason=")
    assert not logs["violations"]
    aria_browser.assert_clean_js()
