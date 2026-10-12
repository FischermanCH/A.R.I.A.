"""Production-shaped browser scenarios; collected only by scripts/e2e/run.sh."""

from __future__ import annotations

import json
import time
import os
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import re
import stat
import subprocess
import urllib.error
import urllib.request
from urllib.parse import urlparse

import pytest
from fastapi.routing import APIRoute
from playwright.sync_api import expect

from aria.modules.document_ingest.ingest import prepare_uploaded_document
from aria.modules.action_confirmation.ledger import ActionConfirmationLedger
from aria.modules.chat_history_storage.store import FileChatHistoryStore
from aria.modules.inbound_event_storage.store import InboundEventStore
from aria.modules.native_agent.pending_store import NativePendingStore
from aria.modules.activity_journal.store import ActivityJournalStore
from aria.main import app as local_aria_app
from aria.modules.config_ui.ui_audit import build_ui_route_inventory
from aria.modules.config_ui.page_linter import (
    detect_german_ui_terms,
    lint_page_snapshots,
    lint_theme_snapshots,
    write_reports,
    write_theme_reports,
)

from .browser_driver import AriaBrowser, HarnessControl


pytestmark = pytest.mark.e2e

EXECUTE = "mcp__blender__execute_blender_code"
LOOK = "mcp__blender__look"
SEARCH_ASSETS = "mcp__blender__search_assets"
SCENE = "mcp__blender__get_scene_info"
REVIEW_EXECUTE = "mcp__review__execute_blender_code"
REVIEW_COMMAND_OUTPUT = "mcp__review__read_command_output"


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


def _latest_tool_result_content(payload: object) -> str:
    messages = payload.get("messages", []) if isinstance(payload, dict) else []
    for message in reversed(messages if isinstance(messages, list) else []):
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        blocks = content if isinstance(content, list) else []
        tool_results = [row for row in blocks if isinstance(row, dict) and row.get("type") == "tool_result"]
        if tool_results:
            return str(tool_results[-1].get("content") or "")
    return ""


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
    # The server-side request is deliberately completed while its browser
    # response is discarded.  Leave enough time for the independent status
    # poll under a fully loaded scenario run; the isolated path normally
    # recovers in about 13 seconds.
    fallback = aria_browser.wait_for_job_bubble(timeout_ms=30_000)
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
    aria_browser.page.once("dialog", lambda dialog: dialog.accept())
    aria_browser.page.locator("#job-s18-done-one form[action$='/delete'] button").click()
    expect(aria_browser.page.locator("#job-s18-done-one")).to_have_count(0)
    aria_browser.page.once("dialog", lambda dialog: dialog.accept())
    aria_browser.page.locator("form[action='/jobs/clear-completed'] button").click()
    expect(aria_browser.page.locator("#job-s18-done-two")).to_have_count(0)
    assert aria_browser.page.locator("#job-s18-running").count() == 1
    aria_browser.assert_clean_js()


def test_st8_jobs_panel_presents_seeded_states_safely(aria_browser: AriaBrowser) -> None:
    """ST8: jobs page keeps telemetry in technical details and markdown responsive."""

    db_path = Path(os.environ["ARIA_E2E_DATA_DIR"]) / "runtime" / "agent_jobs.sqlite3"
    now = time.time()
    states = ("running", "detached", "paused", "awaiting_confirmation", "done", "error", "cancelled")
    technical = 'bounded outcome bytes=802 sha256=' + ('a' * 64) + ' {"mcp":"raw"}'
    markdown = "## Übersicht\n\n| Name | Status | Hinweis |\n|---|---|---|\n" + "\n".join(
        f"| Element {index} | erledigt | Eine absichtlich lange Tabellenzelle {index} |" for index in range(12)
    )
    with sqlite3.connect(db_path) as connection:
        for index, status in enumerate(states):
            connection.execute(
                "INSERT OR REPLACE INTO agent_jobs(job_id,user_id,goal,status,step_log,result,created_at,updated_at,worker_id,pause_reason,pause_event_key) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (
                    f"st8-{status}", "e2e-admin", f"ST8 {status}", status,
                    json.dumps([{"step_index": 1, "tool_names": ["mcp__blender__get_scene_info"], "outcome_summary": technical}]),
                    markdown if status == "done" else "", now - 120, now - index, "e2e",
                    "budget_reached" if status == "paused" else "", "budget_paused#1" if status == "paused" else "",
                ),
            )
        connection.execute(
            "INSERT OR REPLACE INTO agent_jobs(job_id,user_id,goal,status,step_log,result,created_at,updated_at,worker_id) VALUES(?,?,?,?,?,?,?,?,?)",
            ("st8-other", "e2e-other", "ST8 other user", "done", "[]", "hidden", now, now, "e2e"),
        )
    page = aria_browser.page
    page.goto(f"{aria_browser.base_url}/jobs/panel", wait_until="domcontentloaded")
    cards = page.locator("[data-agent-job-card]")
    marker = int(page.locator("[data-agent-job-inventory-expected]").get_attribute("data-agent-job-inventory-expected") or "0")
    assert marker == cards.count()
    for status in states:
        assert page.locator(f"#job-st8-{status}").count() == 1
    expect(page.locator("body")).not_to_contain_text("st8-other")
    leaked_technical = page.evaluate(
        """() => Array.from(document.querySelectorAll('body *')).filter((node) => {
          if (node.closest('[data-ui-technical-content]')) return false;
          const direct = Array.from(node.childNodes)
            .filter((child) => child.nodeType === Node.TEXT_NODE)
            .map((child) => child.textContent || '').join(' ');
          return direct.includes('sha256=') || direct.includes('{\"mcp\":\"raw\"}');
        }).length"""
    )
    assert leaked_technical == 0
    done = page.locator("#job-st8-done")
    expect(done.locator("[data-agent-job-result] table")).to_be_visible()
    assert done.locator("[data-agent-job-result] pre").count() == 0
    steps = done.locator("[data-agent-job-steps]")
    if steps.get_attribute("open") is None:
        steps.locator(":scope > summary").click()
    technical_details = done.locator("[data-agent-job-technical]").first
    technical_details.locator("summary").click()
    expect(technical_details).to_contain_text("sha256=")
    delete = done.locator("form[action$='/delete'] button")
    assert "ui-danger-action" in str(delete.get_attribute("class") or "")
    cleanup = page.locator("form[action='/jobs/clear-completed']")
    assert cleanup.count() == 1
    assert cleanup.bounding_box()["y"] > cards.last.bounding_box()["y"]
    aria_browser.assert_clean_js()


def test_st8a_terminal_notice_survives_fast_post_detach_finish_and_reload(
    aria_browser: AriaBrowser, controls: HarnessControl,
) -> None:
    """ST8a: finish shortly after detach is persisted and displayed exactly once."""

    controls.script("ST8a", [_text("ST8a Ergebnis **dauerhaft zugestellt**.", delay=3.6)])
    aria_browser.open_chat()
    detached = aria_browser.send_chat("ST8a schnelle Fertigstellung nach Detach.", timeout_ms=12_000)
    job_id = str(detached.get_attribute("data-agent-job-id") or "")
    assert job_id
    notice = aria_browser.wait_for_job_notice("dauerhaft zugestellt", timeout_ms=20_000)
    expect(notice.locator("strong")).to_contain_text("dauerhaft zugestellt")
    selector = f'[data-agent-job-id="{job_id}"][data-agent-job-event-key="terminal"]'
    expect(aria_browser.page.locator(selector)).to_have_count(1)
    history_path = Path(os.environ["ARIA_E2E_DATA_DIR"]) / "chat_history" / "e2e-admin.json"
    _make_isolated_data_writable()
    history = json.loads(history_path.read_text(encoding="utf-8"))
    assert len([
        row for row in history
        if row.get("agent_job_id") == job_id and row.get("agent_job_event_key") == "terminal"
    ]) == 1
    aria_browser.page.reload(wait_until="domcontentloaded")
    expect(aria_browser.page.locator(selector)).to_have_count(1)
    aria_browser.page.wait_for_timeout(3500)
    expect(aria_browser.page.locator(selector)).to_have_count(1)
    history = json.loads(history_path.read_text(encoding="utf-8"))
    assert len([
        row for row in history
        if row.get("agent_job_id") == job_id and row.get("agent_job_event_key") == "terminal"
    ]) == 1
    aria_browser.assert_clean_js()


def test_alpha998_long_polled_notice_keeps_composer_reachable_in_every_theme(
    aria_browser: AriaBrowser, controls: HarnessControl,
) -> None:
    """R31: long Markdown notices never displace the composer or widen the page."""

    _make_isolated_data_writable()
    history = FileChatHistoryStore(Path(os.environ["ARIA_E2E_DATA_DIR"]) / "chat_history")
    for index in range(20):
        history.append_exchange(
            "e2e-admin",
            user_message=f"Langer Verlauf, Frage {index + 1}",
            assistant_message=f"Langer Verlauf, Antwort {index + 1}",
            badge_icon="💬",
            badge_intent="chat",
            badge_tokens=2,
            badge_cost_usd="n/a",
            badge_duration="0.0",
        )

    # Keep all 15 rows within the bounded persisted job result while making
    # every cell wide enough to exercise bubble-local horizontal scrolling.
    wide_value = "result_" + ("0123456789abcdef" * 4)
    rows = "\n".join(
        f"| Prüfschritt {index + 1} | {wide_value}_{index + 1} |" for index in range(15)
    )
    completion = "Job-Tabelle **vollständig**.\n\n| Schritt | Ergebnis |\n|---|---|\n" + rows
    controls.script("alpha998-layout", [_text(completion, delay=5.0)])

    page = aria_browser.page
    aria_browser.open_chat()
    detached = aria_browser.send_chat(
        "Erzeuge die lange Ergebnistabelle als Hintergrundauftrag.", timeout_ms=12_000,
    )
    expect(detached.locator("a[href*='/jobs/panel#job-']")).to_be_visible()
    notice = aria_browser.wait_for_job_notice("vollständig", timeout_ms=25_000)
    expect(notice.locator('[data-safe-markdown="true"] table')).to_be_visible()
    assert notice.locator(".assistant-table-wrap tr").count() == 16

    themes = (
        "matrix", "crt-amber", "cyberpunk", "cyberpunk-neo", "deep-space", "harbor",
        "nyan-cat", "paper", "pixel", "puke-unicorn", "sunset",
    )

    def assert_chat_geometry(*, phone_document_scroll: bool) -> None:
        geometry = page.evaluate("""() => {
          const composer = document.querySelector('#chat-form');
          const messages = document.querySelector('#messages');
          const tableWrap = document.querySelector('[data-agent-job-notice="true"] .assistant-table-wrap');
          const box = composer.getBoundingClientRect();
          const top = window.visualViewport ? window.visualViewport.offsetTop : 0;
          const bottom = top + (window.visualViewport ? window.visualViewport.height : window.innerHeight);
          return {
            composerVisible: box.top >= top - 1 && box.bottom <= bottom + 1,
            messageScrolls: messages.scrollHeight > messages.clientHeight,
            documentScrolls: document.documentElement.scrollHeight > (window.visualViewport ? window.visualViewport.height : window.innerHeight),
            atLatest: messages.scrollHeight - messages.scrollTop - messages.clientHeight <= 14,
            pageWide: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
            tableScrolls: tableWrap.scrollWidth > tableWrap.clientWidth,
          };
        }""")
        assert geometry == {
            "composerVisible": True,
            "messageScrolls": not phone_document_scroll,
            "documentScrolls": phone_document_scroll,
            "atLatest": True,
            "pageWide": False,
            "tableScrolls": True,
        }

    for width, height in ((1280, 800), (390, 844)):
        page.set_viewport_size({"width": width, "height": height})
        page.goto(f"{aria_browser.base_url}/", wait_until="domcontentloaded")
        page.wait_for_function("""() => {
          const messages = document.querySelector('#messages');
          return messages && messages.scrollHeight - messages.scrollTop - messages.clientHeight <= 14;
        }""")
        for theme in themes:
            # A live palette change must not alter component geometry.
            page.locator("body").evaluate("""(node, value) => new Promise((resolve) => {
              node.dataset.theme = value;
              requestAnimationFrame(() => requestAnimationFrame(resolve));
            })""", theme)
            page.wait_for_function("""() => {
              const messages = document.querySelector('#messages');
              return messages && messages.scrollHeight - messages.scrollTop - messages.clientHeight <= 14;
            }""")
            assert_chat_geometry(phone_document_scroll=(width <= 900 or height <= 500))
            page.locator("#message").fill(f"Theme {theme} ist bedienbar")
            expect(page.locator("#message")).to_be_focused()

            # The persisted change and full history render exercise the reload path.
            status = page.evaluate("""async ({theme}) => {
              const token = document.querySelector('meta[name="csrf-token"]')?.content || '';
              const response = await fetch('/config/appearance/save', {
                method: 'POST', credentials: 'same-origin', redirect: 'follow',
                headers: {'X-CSRF-Token': token, 'Content-Type': 'application/x-www-form-urlencoded'},
                body: new URLSearchParams({theme, background: 'grid-signal', return_to: '/'}),
              });
              await response.text();
              return response.status;
            }""", {"theme": theme})
            assert status == 200
            page.goto(f"{aria_browser.base_url}/", wait_until="domcontentloaded")
            expect(page.locator("body")).to_have_attribute("data-theme", theme)
            expect(page.locator('[data-agent-job-notice="true"] table')).to_be_visible()
            page.wait_for_function("""() => {
              const messages = document.querySelector('#messages');
              return messages && messages.scrollHeight - messages.scrollTop - messages.clientHeight <= 14;
            }""")
            assert_chat_geometry(phone_document_scroll=(width <= 900 or height <= 500))

    controls.script("alpha998-send", [_text("Composer send remains operational.")])
    sent = aria_browser.send_chat("Nach dem Theme-Wechsel weiter schreiben.", timeout_ms=20_000)
    expect(sent).to_contain_text("Composer send remains operational")
    page.wait_for_function("""() => {
      const messages = document.querySelector('#messages');
      return messages && messages.scrollHeight - messages.scrollTop - messages.clientHeight <= 14;
    }""")
    assert_chat_geometry(phone_document_scroll=True)
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
    aria_browser.page.locator("#llm-profiles").evaluate("node => { node.open = true; }")
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
    toast = other.locator(
        f".global-agent-job-toast:has(a[href='/jobs/panel#job-{job_id}'])"
    )
    expect(toast).to_contain_text("Schritt-Budget", timeout=45_000)
    toast.locator("button").click()
    other.wait_for_timeout(60_000)
    assert toast.count() == 0
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


def test_s24_document_inventory_lists_all_five_imported_documents(
    aria_browser: AriaBrowser, controls: HarnessControl,
) -> None:
    names = [f"s24-beipackzettel-{index}.txt" for index in range(1, 6)]
    for index, name in enumerate(names, start=1):
        aria_browser.page.goto(f"{aria_browser.base_url}/memories/import", wait_until="domcontentloaded")
        aria_browser.page.locator("#import_document_file").set_input_files({
            "name": name,
            "mimeType": "text/plain",
            "buffer": f"S24 Dokument {index}: deterministischer Testinhalt.".encode(),
        })
        aria_browser.page.locator("#import_document_new_collection").fill("s24_leaflets")
        aria_browser.page.locator("form.memory-upload-form button[type='submit']").click()
        aria_browser.page.wait_for_url(
            lambda url: "/memories/import" in url and "info=" in url,
            timeout=30_000,
        )
        expect(aria_browser.page.locator("body")).to_contain_text(name)

    controls.script("S24", [
        _tool("documents_read_search_inventory", {"action": "inventory"}),
        _text("S24 Inventar enthält alle fünf Beipackzettel."),
    ])
    aria_browser.open_chat()
    bubble = aria_browser.send_chat(
        "Welche Dokumente hast du in deinem Gedächtnis?",
        timeout_ms=30_000,
    )
    expect(bubble).to_contain_text("alle fünf Beipackzettel")
    logs = controls.anthropic_logs()
    assert len(logs["requests"]) == 2
    tool_result_request = str(logs["requests"][1]["payload"])
    assert all(name in tool_result_request for name in names), tool_result_request
    assert '"shown": 5' in tool_result_request or "'shown': 5" in tool_result_request
    assert not logs["violations"]
    aria_browser.assert_clean_js()


def test_s25_catalog_inventory_is_fast_and_observable(
    aria_browser: AriaBrowser, controls: HarnessControl,
) -> None:
    controls.script("S25", [
        _tool("documents_read_search_inventory", {"action": "inventory"}),
        _text("S25 Kataloginventar wurde vollständig gelesen."),
    ])
    aria_browser.open_chat()
    bubble = aria_browser.send_chat("S25 liste alle importierten Dokumente.", timeout_ms=30_000)
    expect(bubble).to_contain_text("Kataloginventar")
    bubble.locator("details.msg-details").click()
    details = bubble.locator("details.msg-details")
    expect(details).to_contain_text("document_inventory")
    expect(details).to_contain_text("source=catalog")
    expect(details).to_contain_text("tool_timing documents_read_search_inventory=")
    logs = controls.anthropic_logs()
    assert not logs["violations"]
    payload = str(logs["requests"][-1]["payload"])
    assert all(f"s24-beipackzettel-{index}.txt" in payload for index in range(1, 6))
    aria_browser.assert_clean_js()


def test_s26_collection_name_never_overrides_stored_document_owner(
    aria_browser: AriaBrowser, controls: HarnessControl,
) -> None:
    marker = "S26-OWNER-ONLY-CONTENT"
    aria_browser.page.goto(f"{aria_browser.base_url}/memories/import", wait_until="domcontentloaded")
    aria_browser.page.locator("#import_document_file").set_input_files({
        "name": "s26-private.txt", "mimeType": "text/plain",
        "buffer": f"{marker}: owner e2e-admin only.".encode(),
    })
    aria_browser.page.locator("#import_document_new_collection").fill("whity_medikamente")
    aria_browser.page.locator("form.memory-upload-form button[type='submit']").click()
    aria_browser.page.wait_for_url(lambda url: "info=" in url, timeout=30_000)

    controls.script("S26-owner", [
        _tool("documents_read_search_inventory", {"action": "answer", "query": marker}),
        _text("S26 Owner-Inhalt wurde aus dem eigenen Dokument gelesen."),
    ])
    aria_browser.open_chat()
    owner = aria_browser.send_chat("Was steht im S26-Owner-Dokument?", timeout_ms=30_000)
    expect(owner).to_contain_text("Owner-Inhalt")
    owner_payload = controls.anthropic_logs()["requests"][-1]["payload"]
    assert marker in _latest_tool_result_content(owner_payload)

    aria_browser.page.goto(f"{aria_browser.base_url}/config/users", wait_until="domcontentloaded")
    user_form = aria_browser.page.locator('form[action="/config/users/create"]')
    user_form.locator('[name="create_username"]').fill("whity")
    user_form.locator('[name="create_password"]').fill(os.environ["ARIA_E2E_PASSWORD"])
    user_form.locator('[name="create_role"]').select_option("user")
    user_form.locator('button[type="submit"]').click()
    aria_browser.page.wait_for_load_state("domcontentloaded")
    expect(aria_browser.page.locator("body")).to_contain_text("whity")
    from .browser_driver import AriaBrowser as SecondBrowser

    context = aria_browser.page.context.browser.new_context(viewport={"width": 1280, "height": 800})
    try:
        second = SecondBrowser(context.new_page(), aria_browser.base_url, aria_browser.artifact_dir)
        second.login("whity", os.environ["ARIA_E2E_PASSWORD"])
        controls.script("S26-foreign", [
            _tool("documents_read_search_inventory", {"action": "answer", "query": marker}),
            _text("S26 Für diesen Nutzer ist kein passendes Dokument sichtbar."),
        ])
        second.open_chat()
        foreign = second.send_chat("Was steht im S26-Owner-Dokument?", timeout_ms=30_000)
        expect(foreign).to_contain_text("kein passendes Dokument")
        foreign_payload = controls.anthropic_logs()["requests"][-1]["payload"]
        assert marker not in _latest_tool_result_content(foreign_payload)
        second.assert_clean_js()
    finally:
        context.close()
    aria_browser.assert_clean_js()


def test_s27_friendly_host_resolves_and_ambiguity_clarifies(
    aria_browser: AriaBrowser, controls: HarnessControl,
) -> None:
    controls.script("S27-resolve", [
        _tool("lookup_connection", {"connection_kind": "ssh", "connection_ref": "DEBDEV-SRV02"}),
        _text("S27 Host wurde auf srv-dev02 aufgelöst."),
    ])
    aria_browser.open_chat()
    resolved = aria_browser.send_chat("S27 prüfe df -h auf debdev-srv02.", timeout_ms=30_000)
    expect(resolved).to_contain_text("srv-dev02")
    payload = str(controls.anthropic_logs()["requests"][-1]["payload"])
    assert "srv-dev02" in payload

    controls.script("S27-ambiguous", [
        _tool("lookup_connection", {"connection_kind": "ssh", "connection_ref": "Duplicate host"}),
        _text("S27 Der Name ist mehrdeutig; bitte srv-duplicate-a oder srv-duplicate-b wählen."),
    ])
    ambiguous = aria_browser.send_chat("S27 prüfe den Duplicate host.", timeout_ms=30_000)
    expect(ambiguous).to_contain_text("mehrdeutig")
    ambiguous_payload = str(controls.anthropic_logs()["requests"][-1]["payload"])
    assert "connection_ambiguous" in ambiguous_payload
    assert "srv-duplicate-a" in ambiguous_payload and "srv-duplicate-b" in ambiguous_payload
    aria_browser.assert_clean_js()


def test_s28_read_only_then_action_claim_is_blocked(
    aria_browser: AriaBrowser, controls: HarnessControl,
) -> None:
    controls.mcp("reset")
    controls.script("S28", [
        _tool(SCENE, {}),
        _text("Ich habe einen blauen Würfel erstellt."),
        _text("Ich habe einen blauen Würfel erstellt."),
    ])
    aria_browser.open_chat()
    bubble = aria_browser.send_chat(
        "S28 lies zuerst die Szene und erstelle danach einen blauen Würfel.", timeout_ms=30_000,
    )
    text = bubble.locator(".msg-text").inner_text().lower()
    assert "nicht ausgeführt" in text or "nicht bestätigen" in text
    logs = controls.anthropic_logs()
    assert len(logs["requests"]) == 3
    assert [row["tool"] for row in controls.mcp_logs()["calls"]] == ["get_scene_info"]
    assert not logs["violations"]
    aria_browser.assert_clean_js()


def test_s29_two_chunk_leaflet_dosage_reaches_the_model(
    aria_browser: AriaBrowser, controls: HarnessControl,
) -> None:
    username = "s29-reader"
    password = os.environ["ARIA_E2E_PASSWORD"]
    aria_browser.page.goto(f"{aria_browser.base_url}/config/users", wait_until="domcontentloaded")
    user_form = aria_browser.page.locator('form[action="/config/users/create"]')
    user_form.locator('[name="create_username"]').fill(username)
    user_form.locator('[name="create_password"]').fill(password)
    user_form.locator('[name="create_role"]').select_option("user")
    user_form.locator('button[type="submit"]').click()
    aria_browser.page.wait_for_load_state("domcontentloaded")

    context = aria_browser.page.context.browser.new_context(viewport={"width": 1280, "height": 800})
    try:
        from .browser_driver import AriaBrowser as SecondBrowser

        reader = SecondBrowser(context.new_page(), aria_browser.base_url, aria_browser.artifact_dir)
        reader.login(username, password)
        reader.page.goto(f"{aria_browser.base_url}/memories/import", wait_until="domcontentloaded")
        heading = "In welcher Dosierung wird Simponi angewendet?"
        dosage = "Die empfohlene Dosis ist 50 mg einmal im Monat. Ändern Sie die Dosis nicht selbstständig."
        leaflet = heading + "\n\n" + ("Hinweis zum Abschnitt. " * 65) + "\n\n" + dosage
        leaflet_bytes = leaflet.encode("utf-8")
        prepared = prepare_uploaded_document(
            filename="s29-simponi-beipackzettel.txt",
            data=leaflet_bytes,
            content_type="text/plain",
        )
        assert len(prepared.chunks) == 2
        reader.page.locator("#import_document_file").set_input_files({
            "name": "s29-simponi-beipackzettel.txt",
            "mimeType": "text/plain",
            "buffer": leaflet_bytes,
        })
        reader.page.locator("#import_document_new_collection").fill("s29_leaflet")
        reader.page.locator("form.memory-upload-form button[type='submit']").click()
        reader.page.wait_for_url(lambda url: "info=" in url, timeout=30_000)

        controls.script("S29", [
            _tool("documents_read_search_inventory", {
                "action": "answer", "query": prepared.chunks[0].text,
            }),
            _text("S29: Die empfohlene Dosis ist 50 mg einmal im Monat."),
        ])
        reader.open_chat()
        bubble = reader.send_chat("Was steht im Simponi-Beipackzettel zur Dosierung?", timeout_ms=30_000)
        expect(bubble).to_contain_text("50 mg einmal im Monat")
        payload = controls.anthropic_logs()["requests"][-1]["payload"]
        tool_content = _latest_tool_result_content(payload)
        tool_payload = json.loads(tool_content)
        rows = tool_payload["documents"]
        assert [row["chunk_index"] for row in rows] == ["1", "2"]
        assert heading in rows[0]["excerpt"]
        assert dosage in rows[1]["excerpt"]
        assert rows[1]["neighbor"] == "true"
        assert all(row["document_name"] == "s29-simponi-beipackzettel.txt" for row in rows)
        reader.assert_clean_js()
    finally:
        context.close()


def test_s30_permanently_down_mcp_uses_backoff_snapshots(
    aria_browser: AriaBrowser, controls: HarnessControl,
) -> None:
    try:
        controls.mcp("stop")
        controls.wait_mcp_running(False)
        controls.script("S30", [
            _tool(SCENE, {}),
            _text("S30 Blender ist nicht erreichbar."),
            *[_text(f"S30 Blender bleibt nicht erreichbar ({index}).") for index in range(2, 6)],
        ])
        aria_browser.open_chat()
        bubbles = []
        for index in range(1, 6):
            bubble = aria_browser.send_chat(
                f"S30 prüfe Blender erneut, Versuch {index}.", timeout_ms=30_000,
            )
            bubbles.append(bubble)
            bubble.locator("details.msg-details").click()
        assert all("blocked=no" in bubble.locator("details.msg-details").inner_text() for bubble in bubbles)
        assert "mcp-server blender" in bubbles[-1].locator(".msg-text").inner_text().lower()
        assert len(controls.mcp_logs()["calls"]) <= 1
        assert not controls.anthropic_logs()["violations"]
    finally:
        controls.mcp("start")
        controls.wait_mcp_running(True)
    aria_browser.assert_clean_js()


def _qdrant_request(path: str, *, method: str = "GET", payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        os.environ["ARIA_E2E_QDRANT_URL"] + path, data=data, method=method,
        headers={"Content-Type": "application/json"},
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=10) as response:
        return json.load(response)


def _make_isolated_data_writable() -> None:
    """Normalize only the disposable aria-e2e-* data mount for host fixtures."""
    container_name = os.environ.get("ARIA_E2E_CONTAINER_NAME", "")
    assert container_name.startswith("aria-e2e-") and container_name.endswith("-aria")
    subprocess.run(
        ["docker", "exec", container_name, "chmod", "-R", "a+rwX", "/app/data"],
        check=True,
    )


def _seed_stats_alpha999() -> None:
    _make_isolated_data_writable()
    data = Path(os.environ["ARIA_E2E_DATA_DIR"])
    now = time.time()
    log = data / "logs" / "tokens.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for day in range(35):
        stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - day * 86400))
        rows.append(json.dumps({
            "timestamp": stamp, "request_id": f"st-usage-{day}", "user_id": "e2e-admin",
            "total_tokens": 1000 + day, "prompt_tokens": 800, "completion_tokens": 200,
            "chat_model": "demo/chat-a" if day % 2 else "demo/chat-b",
            "embedding_model": "demo/embed", "embedding_total_tokens": 50,
            "chat_cost_usd": 0.10 + day * 0.001, "embedding_cost_usd": 0.001,
            "total_cost_usd": 0.101 + day * 0.001, "source": "agent_job" if day % 3 == 0 else "chat",
        }))
    log.write_text("\n".join(rows) + "\n", encoding="utf-8")
    store = ActivityJournalStore(data / "runtime" / "activity_journal.sqlite3")
    for index in range(12):
        store.write({
            "id": f"st-journal-{index}", "user_id": "e2e-admin", "started_at": now - index * 3600 - 2,
            "finished_at": now - index * 3600, "kind": "turn", "goal": "Synthetic stats fixture",
            "tools": {"document_content_read": 1}, "connection_kinds": ["http_api"],
            "connection_refs": ["e2e-api"], "mcp_servers": [],
            "outcome_status": "error" if index == 5 else "ok", "confirmations": {},
            "corrected": index == 2, "outcome_phrase": "Synthetic result", "source": "live",
            "input_tokens": 500, "output_tokens": 100, "embedding_tokens": 20, "cost_usd": 0.03,
        })


def test_st1_stats_owner_overview_de_and_en(aria_browser: AriaBrowser) -> None:
    _seed_stats_alpha999()
    page = aria_browser.page
    for language, purpose in (
        ("de", "Gesundheit, Kosten, Aktivitäten und Speicherbedarf auf einen Blick."),
        ("en", "Health, costs, activity and storage at a glance."),
    ):
        page.goto(f"{aria_browser.base_url}/stats?lang={language}", wait_until="domcontentloaded")
        expect(page.locator('[data-stats-owner-sections="4"]')).to_be_visible()
        expect(page.locator("[data-stats-section]")).to_have_count(4)
        expect(page.locator(".ui-page-purpose")).to_have_text(purpose)
        expect(page.locator(".stats-overview__tech")).not_to_have_attribute("open", "")


def test_st2_stats_cost_periods_and_server_svg(aria_browser: AriaBrowser) -> None:
    _seed_stats_alpha999()
    page = aria_browser.page
    page.goto(f"{aria_browser.base_url}/stats", wait_until="domcontentloaded")
    expect(page.locator('[data-stats-section="costs"] svg[role="img"]')).to_be_visible()
    expect(page.locator('[data-stats-section="costs"] svg rect')).to_have_count(30)
    expect(page.locator('[data-stats-section="costs"]')).to_contain_text("Heute")
    expect(page.locator('[data-stats-section="costs"]')).to_contain_text("Dieser Monat")


def test_st3_stats_get_has_no_provider_connection_or_mcp_calls(
    aria_browser: AriaBrowser, controls: HarnessControl,
) -> None:
    before_provider = len(controls.anthropic_logs().get("requests", []))
    before_mcp = len(controls.mcp_logs().get("calls", []))
    aria_browser.page.goto(f"{aria_browser.base_url}/stats", wait_until="domcontentloaded")
    assert len(controls.anthropic_logs().get("requests", [])) == before_provider
    assert len(controls.mcp_logs().get("calls", [])) == before_mcp
    assert "alpha999 läuft" not in aria_browser.page.locator("body").inner_text()


def test_st4_stats_activity_is_user_scoped(aria_browser: AriaBrowser) -> None:
    _seed_stats_alpha999()
    store = ActivityJournalStore(Path(os.environ["ARIA_E2E_DATA_DIR"]) / "runtime" / "activity_journal.sqlite3")
    store.write({
        "id": "st-private-other", "user_id": "other-user", "started_at": time.time() - 2,
        "finished_at": time.time(), "kind": "turn", "goal": "PRIVATE-OTHER-USER",
        "tools": {"ssh_read": 999}, "connection_kinds": ["ssh"], "connection_refs": ["private"],
        "mcp_servers": [], "outcome_status": "error", "confirmations": {}, "corrected": False,
        "outcome_phrase": "PRIVATE-OTHER-USER", "source": "live",
    })
    aria_browser.page.goto(f"{aria_browser.base_url}/stats", wait_until="domcontentloaded")
    body = aria_browser.page.locator('[data-stats-section="activity"]').inner_text()
    assert "PRIVATE-OTHER-USER" not in body
    assert "ssh_read" not in body
    assert "e2e-api" in body


def test_st5_stats_resources_cache_and_links(aria_browser: AriaBrowser) -> None:
    page = aria_browser.page
    page.goto(f"{aria_browser.base_url}/stats", wait_until="domcontentloaded")
    resources = page.locator('[data-stats-section="resources"]')
    assert "Arbeitsspeicher" in resources.inner_text()
    expect(resources.locator('a[href="/config/backup"]')).to_be_visible()
    expect(resources.locator('a[href="/config/logs"]')).to_be_visible()
    expect(resources.locator('a[href="/memories/maintenance"]')).to_be_visible()


def test_st6_stats_responsive_svg_and_locale(aria_browser: AriaBrowser) -> None:
    page = aria_browser.page
    for width in (1280, 390):
        page.set_viewport_size({"width": width, "height": 844 if width == 390 else 800})
        page.goto(f"{aria_browser.base_url}/stats", wait_until="domcontentloaded")
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
        svg = page.locator('[data-stats-section="costs"] svg')
        expect(svg.locator(":scope > title")).to_have_count(1)
        expect(svg.locator(":scope > desc")).to_have_count(1)


def test_a1006_stats_initial_get_latency_with_131_connections(
    aria_browser: AriaBrowser,
) -> None:
    """Alpha1006: live-like scale keeps the initial owner page below 500 ms."""

    page = aria_browser.page
    page.goto(f"{aria_browser.base_url}/stats", wait_until="load")
    timing = page.evaluate("""() => {
      const nav = performance.getEntriesByType('navigation')[0];
      const paints = performance.getEntriesByType('paint');
      const firstPaint = paints.find((row) => row.name === 'first-contentful-paint') || paints[0];
      return {
        server_ms: nav ? nav.responseStart - nav.requestStart : -1,
        first_paint_ms: firstPaint ? firstPaint.startTime : (nav ? nav.domContentLoadedEventEnd : -1),
        first_paint_source: firstPaint ? firstPaint.name : 'dom-content-loaded-fallback',
      };
    }""")
    technical = page.locator(".stats-overview__tech").text_content() or ""
    version_match = re.search(r"0\.1\.0-alpha\d+", technical)
    version = version_match.group(0) if version_match else "unknown"
    artifact = Path(os.environ["ARIA_E2E_ARTIFACT_DIR"]) / "stats-latency.json"
    artifact.write_text(
        json.dumps({"version": version, "connections": 131, **timing}, indent=2) + "\n",
        encoding="utf-8",
    )
    assert timing["server_ms"] >= 0
    assert timing["first_paint_ms"] >= 0
    if version == "0.1.0-alpha1007":
        assert timing["server_ms"] <= 500, timing


def test_a1005_stats_alpha983_parity_lamps_and_idle_chat_bar(aria_browser: AriaBrowser) -> None:
    """Alpha1006: cached pills remain visible; Alpha983 tiles load on demand."""

    _seed_stats_alpha999()
    page = aria_browser.page
    page.goto(f"{aria_browser.base_url}/stats", wait_until="domcontentloaded")
    blocks = page.locator("[data-stats-check-block]")
    expect(blocks).to_have_count(3)
    assert page.locator("[data-stats-check-summary]").count() == 3
    for index in range(3):
        block = blocks.nth(index)
        assert block.locator('[data-stats-count="ok"]').count() == 1
        assert block.locator('[data-stats-count="warn"]').count() == 1
        assert block.locator('[data-stats-count="error"]').count() == 1
        status = ""
        classes = str(block.get_attribute("class") or "").split()
        for candidate in ("ok", "warn", "error"):
            if f"status-{candidate}" in classes:
                status = candidate
                break
        assert status
        assert block.get_attribute("open") is None
        block.locator(":scope > summary").click()
        expect(block.locator("[data-stats-check-tile]").first).to_be_visible(timeout=10_000)
    assert page.locator("[data-stats-check-block][open]").count() == 3
    required = {
        "prompts", "qdrant_startup", "chat_llm", "embeddings",
        "aria_runtime", "model_stack", "qdrant_live", "security_store",
        "logs", "connections", "mcp_servers", "release", "module_registry",
        "model_gateway", "pricing", "cost_tracking", "recipe_memory", "updates",
    }
    rendered = set(page.locator("[data-stats-check-key]").evaluate_all(
        "nodes => nodes.map(node => node.dataset.statsCheckKey)",
    ))
    assert required <= rendered
    assert page.locator('[data-stats-count="ok"]').count() == 3
    assert page.locator('[data-stats-count="warn"]').count() == 3
    assert page.locator('[data-stats-count="error"]').count() == 3
    body_text = page.locator("body").inner_text()
    for phrase in (
        "Mindestens eine passive Prüfung braucht Aufmerksamkeit.",
        "Passiver Status",
        "ARIA verarbeitet diese Seite lokal.",
    ):
        assert phrase not in body_text

    themes = (
        "matrix", "crt-amber", "cyberpunk", "cyberpunk-neo", "deep-space",
        "harbor", "nyan-cat", "paper", "pixel", "puke-unicorn", "sunset",
    )
    expected_rgb = {
        "ok": "rgb(57, 216, 108)",
        "warn": "rgb(243, 178, 61)",
        "error": "rgb(239, 98, 98)",
    }
    for theme in themes:
        page.locator("body").evaluate("(node, value) => node.dataset.theme = value", theme)
        lamps = page.locator("[data-stats-check-tile]").evaluate_all("""nodes => nodes.map(node => {
          const status = ['ok', 'warn', 'error'].find(value => node.classList.contains(`status-${value}`));
          const lamp = node.querySelector('.health-lamp');
          return {status, background: lamp ? getComputedStyle(lamp).backgroundImage : ''};
        })""")
        assert lamps
        for row in lamps:
            assert row["status"] in expected_rgb
            assert expected_rgb[row["status"]] in row["background"]

    page.locator(".stats-overview__tech > summary").click()
    pricing = page.locator(".stats-overview__pricing")
    if pricing.get_attribute("open") is None:
        pricing.locator(":scope > summary").click()
    assert page.locator("[data-pricing-row]").count() <= 20

    aria_browser.open_chat()
    indicator = page.locator("#typing-indicator")
    idle = indicator.evaluate("node => ({hidden: node.hidden, text: node.textContent, height: node.getBoundingClientRect().height, display: getComputedStyle(node).display})")
    assert idle == {"hidden": True, "text": "", "height": 0, "display": "none"}
    expect(page.locator("#slash-menu")).to_have_count(0)
    aria_browser.assert_clean_js()


def test_a1006_stats_lazy_fragments_timeout_and_connections(aria_browser: AriaBrowser) -> None:
    """Alpha1006: shells are cheap; fragments load once and timeouts stay local."""

    _seed_stats_alpha999()
    page = aria_browser.page
    operation_calls = 0

    def timeout_fragment(route) -> None:  # type: ignore[no-untyped-def]
        nonlocal operation_calls
        operation_calls += 1
        route.fulfill(
            status=200,
            content_type="text/html",
            body="""
            <div class="stats-check-grid">
              <article class="stats-check-tile status-warn" data-stats-check-tile data-stats-check-key="routing_index">
                <div class="stats-check-tile__head"><span class="health-lamp status-warn"></span><strong>Routing-Index</strong></div>
                <p>Routing-Index ist derzeit nicht erreichbar.</p><small>Timeout nach 3 Sekunden.</small>
              </article>
              <article class="stats-check-tile status-warn" data-stats-check-tile data-stats-check-key="recipe_memory">
                <div class="stats-check-tile__head"><span class="health-lamp status-warn"></span><strong>Rezept-Gedächtnis</strong></div>
                <p>Rezept-Gedächtnis ist derzeit nicht erreichbar.</p><small>Timeout nach 3 Sekunden.</small>
              </article>
            </div>""",
        )

    page.route("**/stats/blocks/operations", timeout_fragment)
    try:
        page.goto(f"{aria_browser.base_url}/stats", wait_until="domcontentloaded")
        expect(page.locator("[data-stats-check-block]")).to_have_count(3)
        expect(page.locator("[data-stats-check-block][open]")).to_have_count(0)
        expect(page.locator("[data-stats-check-tile]")).to_have_count(0)
        expect(page.locator(".stats-overview__issues")).to_be_visible()

        runtime = page.locator('[data-stats-check-block="runtime"]')
        runtime.locator(":scope > summary").click()
        expect(runtime.locator('[data-stats-check-key="connections"]')).to_be_visible()
        expect(runtime.locator('a[href="/connections/status"]')).to_be_visible()

        operations = page.locator('[data-stats-check-block="operations"]')
        operations.locator(":scope > summary").click()
        expect(operations.locator('[data-stats-check-key="routing_index"]')).to_contain_text("Timeout")
        expect(operations.locator('[data-stats-check-key="recipe_memory"]')).to_contain_text("nicht erreichbar")
        assert operation_calls == 1
        operations.locator(":scope > summary").click()
        operations.locator(":scope > summary").click()
        expect(operations.locator('[data-stats-check-key="routing_index"]')).to_be_visible()
        assert operation_calls == 1
        expect(page.locator("#stats-cost-title")).to_be_visible()
    finally:
        page.unroute("**/stats/blocks/operations", timeout_fragment)
    aria_browser.assert_clean_js()


def test_a1007_stats_owner_polish_resources_and_axes(aria_browser: AriaBrowser) -> None:
    """Alpha1007: concrete checks, readable axes and container-backed resources."""

    _seed_stats_alpha999()
    page = aria_browser.page
    page.goto(f"{aria_browser.base_url}/stats", wait_until="domcontentloaded")
    startup = page.locator('[data-stats-check-block="startup"]')
    expect(startup.locator("time")).to_have_count(1)
    assert re.fullmatch(r"\d{2}:\d{2}", startup.locator("time").inner_text())
    for block in page.locator("[data-stats-check-block]").all():
        block.locator(":scope > summary").click()
        expect(block.locator("[data-stats-check-tile]").first).to_be_visible(timeout=10_000)
    keys = set(page.locator("[data-stats-check-key]").evaluate_all(
        "nodes => nodes.map(node => node.dataset.statsCheckKey)",
    ))
    assert not {"startup_time", "preflight", "runtime_health", "memory_live", "sidecars"} & keys
    assert {"qdrant_startup", "qdrant_live"} <= keys
    connection = page.locator('[data-stats-check-key="connections"]')
    assert "status-warn" not in str(connection.get_attribute("class") or "")
    expect(page.locator(".stats-chart-y-axis text")).to_have_count(3)
    assert page.locator(".stats-chart-x-axis text").count() >= 6
    expect(page.locator(".stats-overview__chart rect[tabindex='0']")).to_have_count(30)
    resources = page.locator('[data-stats-section="resources"]')
    assert "Wachstum: noch keine Daten seit" in resources.inner_text() or "Growth: not enough data since" in resources.inner_text()
    assert "GefahrenzoneLokale" not in page.locator("body").inner_text()
    aria_browser.assert_clean_js()


def test_a1007_chat_actions_full_width_and_terminal_job_controls(aria_browser: AriaBrowser) -> None:
    """Alpha1007: compact actions, full-width assistant output, terminal view-only jobs."""

    _make_isolated_data_writable()
    history_path = Path(os.environ["ARIA_E2E_DATA_DIR"]) / "chat_history" / "e2e-admin.json"
    rows = [
        {
            "role": "assistant", "text": "Detached job", "badge_icon": "⏳",
            "badge_intent": "agent_job_detached", "badge_tokens": 0,
            "badge_cost_usd": "n/a", "badge_duration": "0.0", "badge_details": [],
            "agent_job_id": "a1007-terminal", "agent_job_notice": False,
            "agent_job_event_key": "detached", "timestamp": "2026-10-12T20:00:00Z",
        },
        {
            "role": "assistant",
            "text": "| Server | Status | Detail |\n|---|---|---|\n" + "\n".join(
                f"| host-{index:02d} | ok | completed without errors |" for index in range(13)
            ),
            "badge_icon": "✅", "badge_intent": "agent_job_done", "badge_tokens": 1,
            "badge_cost_usd": "n/a", "badge_duration": "1.0", "badge_details": [],
            "agent_job_id": "a1007-terminal", "agent_job_notice": True,
            "agent_job_event_key": "terminal", "timestamp": "2026-10-12T20:00:01Z",
        },
    ]
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(json.dumps(rows), encoding="utf-8")
    page = aria_browser.page
    aria_browser.open_chat()
    expect(page.locator(".chat-tools")).to_have_count(0)
    expect(page.locator("#chat-toolbox-panel")).to_have_count(0)
    toggle = page.locator("#chat-actions-toggle")
    expect(toggle).to_be_visible()
    toggle.focus()
    page.keyboard.press("ArrowDown")
    expect(page.locator("#chat-actions-panel")).to_be_visible()
    expect(page.locator("#chat-actions-panel [role='menuitem']")).to_have_count(5)
    page.keyboard.press("Escape")
    expect(page.locator("#chat-actions-panel")).to_be_hidden()
    bubble = page.locator('.msg-assistant[data-agent-job-id="a1007-terminal"][data-agent-job-notice="false"]')
    expect(bubble.locator("[data-agent-job-action]")).to_have_count(0)
    expect(bubble.locator('a[href="/jobs/panel#job-a1007-terminal"]')).to_be_visible()
    assistant_width = page.locator('.msg-assistant[data-agent-job-notice="true"]').evaluate(
        """node => {
          const parent = node.parentElement;
          const style = getComputedStyle(parent);
          return {
            bubble: node.getBoundingClientRect().width,
            chat: parent.getBoundingClientRect().width - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight),
            page: document.documentElement.scrollWidth,
            viewport: window.innerWidth,
          };
        }""",
    )
    assert assistant_width["bubble"] >= assistant_width["chat"] - 4
    assert assistant_width["page"] <= assistant_width["viewport"] + 1
    expect(page.locator('.msg-assistant[data-agent-job-notice="true"] table')).to_be_visible()
    aria_browser.assert_clean_js()


def test_a1000_stats_aliases_chart_and_four_digit_release(aria_browser: AriaBrowser) -> None:
    """Alpha1000: aliases collapse and the chart baseline fills its SVG card."""

    _make_isolated_data_writable()
    log = Path(os.environ["ARIA_E2E_DATA_DIR"]) / "logs" / "tokens.jsonl"
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    rows = (
        {"request_id": "a1000-1", "chat_model": "claude-sonnet-5", "chat_cost_usd": 1.0, "total_cost_usd": 1.0, "source": "web_chat"},
        {"request_id": "a1000-2", "chat_model": "anthropic/claude-sonnet-5", "chat_cost_usd": 1.0, "total_cost_usd": 1.0, "source": "native_agent"},
        {"request_id": "a1000-3", "embedding_model": "embed-small", "embedding_cost_usd": 0.2, "total_cost_usd": 0.2, "source": "meta_catalog"},
        {"request_id": "a1000-4", "embedding_model": "openai/embed-small", "embedding_cost_usd": 0.2, "total_cost_usd": 0.2, "source": "meta_catalog"},
    )
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text("".join(json.dumps({"timestamp": now, **row}) + "\n" for row in rows), encoding="utf-8")
    page = aria_browser.page
    page.goto(f"{aria_browser.base_url}/stats", wait_until="domcontentloaded")
    assert page.locator(".stats-overview__breakdown").inner_text().count("claude-sonnet-5") == 1
    assert page.locator(".stats-overview__breakdown").inner_text().count("embed-small") == 1
    expect(page.locator(".stats-overview__breakdown")).to_contain_text("Agent-Aufträge")
    expect(page.locator(".stats-overview__breakdown")).to_contain_text("Katalog-Suche")
    svg = page.locator('[data-stats-section="costs"] svg')
    assert svg.get_attribute("viewBox") == "0 0 640 180"
    assert svg.locator(".stats-chart-y-axis text").count() == 3
    assert svg.locator(".stats-chart-x-axis text").count() >= 6
    page.locator(".stats-overview__tech > summary").click()
    expect(page.locator(".stats-overview__tech")).to_contain_text("0.1.0-alpha1007")


def test_a1000_jobs_markdown_poll_and_journal_plain_single_entry(aria_browser: AriaBrowser) -> None:
    """Alpha1000: polled job Markdown is safe and its journal projection is singular/plain."""

    _make_isolated_data_writable()
    data = Path(os.environ["ARIA_E2E_DATA_DIR"])
    store = ActivityJournalStore(data / "runtime" / "activity_journal.sqlite3")
    store.write({
        "id": "job-a1000", "user_id": "e2e-admin", "started_at": time.time() - 3,
        "finished_at": time.time(), "kind": "job", "job_id": "a1000-poll",
        "goal": "Inspect host", "tools": {"ssh_read": 1},
        "connection_kinds": ["ssh"], "connection_refs": ["srv-dev02"],
        "mcp_servers": [], "outcome_status": "ok", "confirmations": {},
        "corrected": False, "outcome_phrase": "Disk: root; Free: 4.3G",
        "source": "live",
    })
    page = aria_browser.page
    page.goto(f"{aria_browser.base_url}/jobs/panel", wait_until="domcontentloaded")
    db_path = data / "runtime" / "agent_jobs.sqlite3"
    markdown = "## Result\n\n| Disk | Free |\n|---|---|\n| root | **4.3G** |\n\n- complete"
    now = time.time()
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "INSERT OR REPLACE INTO agent_jobs(job_id,user_id,goal,status,step_log,result,created_at,updated_at,worker_id) VALUES(?,?,?,?,?,?,?,?,?)",
            ("a1000-poll", "e2e-admin", "Inspect host", "done", "[]", markdown, now, now, "e2e"),
        )
    expect(page.locator("#job-a1000-poll")).to_be_visible(timeout=8_000)
    result = page.locator("#job-a1000-poll [data-agent-job-result-text]")
    expect(result.locator("table")).to_be_visible()
    expect(result.locator("strong")).to_have_text("4.3G")
    expect(result.locator("li")).to_have_text("complete")
    assert result.get_attribute("data-safe-markdown-rendered") == "poll"
    page.goto(f"{aria_browser.base_url}/memories/activity-journal", wait_until="domcontentloaded")
    assert page.locator("#journal-since").input_value() == ""
    assert page.locator("#journal-until").input_value() == ""
    expect(page.locator('[data-entry-id="job-a1000"]')).to_have_count(1)
    entry = page.locator('[data-entry-id="job-a1000"]')
    expect(entry).to_contain_text("srv-dev02")
    expect(entry).to_contain_text("Disk: root; Free: 4.3G")
    assert "**" not in entry.inner_text() and "|" not in entry.inner_text()


def test_a1000_unreachable_mcp_first_turn_is_cache_only(
    aria_browser: AriaBrowser, controls: HarnessControl,
) -> None:
    """Alpha1000: a cold unreachable MCP endpoint cannot consume the chat budget."""

    container = os.environ["ARIA_E2E_CONTAINER_NAME"]
    assert container.startswith("aria-e2e-") and container.endswith("-aria")
    try:
        controls.mcp("stop")
        controls.wait_mcp_running(False)
        controls.script("A1000-mcp-cold", [_text("Lokale Antwort ohne MCP-Wartezeit.")])
        subprocess.run(["docker", "restart", container], check=True, capture_output=True, text=True)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                with opener.open(f"{aria_browser.base_url}/health", timeout=1) as response:
                    if response.status == 200:
                        break
            except Exception:
                time.sleep(0.2)
        aria_browser.login(os.environ["ARIA_E2E_USERNAME"], os.environ["ARIA_E2E_PASSWORD"])
        aria_browser.open_chat()
        started = time.perf_counter()
        bubble = aria_browser.send_chat("Antworte lokal und kurz.", timeout_ms=12_000)
        elapsed = time.perf_counter() - started
        assert not str(bubble.get_attribute("data-agent-job-id") or "")
        assert elapsed < 3.0
        bubble.locator("details.msg-details > summary").click()
        details = bubble.locator("details.msg-details").inner_text()
        match = re.search(r"mcp_discovery_ms=(\d+) blocked=no", details)
        assert match and int(match.group(1)) <= 50, details
    finally:
        controls.mcp("start")
        controls.wait_mcp_running(True)


def test_a1001_first_turn_recipe_snapshot_is_bounded_after_restart(
    aria_browser: AriaBrowser, controls: HarnessControl,
) -> None:
    """Alpha1002: 160 recipes and a real MetaCatalog never block the first turn."""

    _make_isolated_data_writable()
    recipe_dir = Path(os.environ["ARIA_E2E_DATA_DIR"]) / "recipes"
    recipe_dir.mkdir(parents=True, exist_ok=True)
    for index in range(160):
        (recipe_dir / f"a1001-live-recipe-{index:03d}.json").write_text(
            json.dumps({
                "schema_version": "1.1",
                "id": f"a1001-live-recipe-{index:03d}",
                "name": f"A1001 live-shaped recipe {index:03d}",
                "description": "Synthetic E2E catalog card",
                "enabled_default": False,
                "steps": [{
                    "id": "s1", "type": "ssh_run", "connection_ref": "srv-dev02",
                    "params": {"command": f"printf fixture-{index:03d}"},
                }],
            }, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    assert len(tuple(recipe_dir.glob("a1001-live-recipe-*.json"))) == 160
    qdrant_url = os.environ["ARIA_E2E_QDRANT_URL"].rstrip("/")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    catalog_name = "aria_a1001_recipe_catalog"
    request = urllib.request.Request(
        f"{qdrant_url}/collections/{catalog_name}",
        data=json.dumps({"vectors": {"size": 3, "distance": "Cosine"}}).encode(),
        headers={"Content-Type": "application/json"}, method="PUT",
    )
    with opener.open(request, timeout=10) as response:
        assert response.status < 300
    points = [{
        "id": index + 1,
        "vector": [1.0, float(index % 7) / 10.0, float(index % 11) / 10.0],
        "payload": {
            "catalog_id": f"recipe:a1001-live-recipe-{index:03d}",
            "module_id": "recipe_runtime", "operation_id": "recipes_execute",
            "title": f"Synthetic recipe card {index:03d}",
        },
    } for index in range(160)]
    request = urllib.request.Request(
        f"{qdrant_url}/collections/{catalog_name}/points?wait=true",
        data=json.dumps({"points": points}).encode(),
        headers={"Content-Type": "application/json"}, method="PUT",
    )
    with opener.open(request, timeout=10) as response:
        assert response.status < 300
    with opener.open(f"{qdrant_url}/collections/{catalog_name}", timeout=5) as response:
        catalog = json.load(response)
    assert int(catalog["result"]["points_count"]) == 160

    container = os.environ["ARIA_E2E_CONTAINER_NAME"]
    controls.script("A1001-recipe-cold", [_text("Lokale Antwort nach dem Neustart.")])
    subprocess.run(["docker", "restart", container], check=True, capture_output=True, text=True)
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            with opener.open(f"{aria_browser.base_url}/health", timeout=1) as response:
                if response.status == 200:
                    break
        except Exception:
            time.sleep(0.1)
    else:
        raise AssertionError("ARIA did not recover after the isolated restart")

    aria_browser.login(os.environ["ARIA_E2E_USERNAME"], os.environ["ARIA_E2E_PASSWORD"])
    aria_browser.open_chat()
    bubble = aria_browser.send_chat("Antworte nach dem Neustart lokal und kurz.", timeout_ms=12_000)
    assert not str(bubble.get_attribute("data-agent-job-id") or "")
    bubble.locator("details.msg-details > summary").click()
    details = bubble.locator("details.msg-details").inner_text()
    match = re.search(r"pre_loop_timing .*recipes=(\d+)ms", details)
    assert match and int(match.group(1)) <= 300, details
    for path in recipe_dir.glob("a1001-live-recipe-*.json"):
        path.unlink()


def test_st7_chat_user_turn_survives_detach_notice_and_reload_in_two_themes(
    aria_browser: AriaBrowser, controls: HarnessControl,
) -> None:
    """ST7: the server-confirmed user bubble remains ordered through a detached job."""

    page = aria_browser.page

    def persist_theme(theme: str) -> None:
        status = page.evaluate("""async (theme) => {
          const token = document.querySelector('meta[name="csrf-token"]')?.content || '';
          const response = await fetch('/config/appearance/save', {
            method: 'POST', credentials: 'same-origin', redirect: 'follow',
            headers: {'X-CSRF-Token': token, 'Content-Type': 'application/x-www-form-urlencoded'},
            body: new URLSearchParams({theme, background: 'grid-signal', return_to: '/'}),
          });
          await response.text();
          return response.status;
        }""", theme)
        assert status == 200

    def assert_order(message: str, job_id: str, *, require_notice: bool) -> None:
        row = page.evaluate("""({message, jobId}) => {
          const rows = Array.from(document.querySelectorAll('#messages > .msg'));
          const user = rows.findIndex((node) => node.matches('.msg-user[data-chat-user-turn="true"]') && node.textContent.includes(message));
          const detached = rows.findIndex((node) => node.matches(`.msg-assistant[data-agent-job-id="${CSS.escape(jobId)}"][data-agent-job-notice="false"]`));
          const notice = rows.findIndex((node) => node.matches(`.msg-assistant[data-agent-job-id="${CSS.escape(jobId)}"][data-agent-job-notice="true"]`));
          return {user, detached, notice};
        }""", {"message": message, "jobId": job_id})
        assert row["user"] >= 0
        assert row["detached"] > row["user"]
        if require_notice:
            assert row["notice"] > row["detached"]

    for index, (theme, width, height) in enumerate((
        ("matrix", 1280, 800), ("paper", 390, 844),
    ), start=1):
        persist_theme(theme)
        page.set_viewport_size({"width": width, "height": height})
        page.goto(f"{aria_browser.base_url}/", wait_until="domcontentloaded")
        expect(page.locator("body")).to_have_attribute("data-theme", theme)
        message = f"ST7 Nutzerfrage {index} bleibt sichtbar"
        result = f"ST7 Ergebnis {index} dauerhaft zugestellt."
        controls.script(f"ST7-{theme}", [_text(result, delay=7.0)])

        previous_job_bubbles = page.locator(
            '#messages .msg-assistant[data-agent-job-id][data-agent-job-notice="false"]'
        ).count()
        page.locator("#message").fill(message)
        page.locator("#chat-form #send-btn").click()
        user = page.locator('#messages .msg-user[data-chat-user-turn="true"]').filter(has_text=message)
        expect(user).to_be_visible(timeout=2_000)
        page.wait_for_function(
            "count => document.querySelectorAll('#messages .msg-assistant[data-agent-job-id][data-agent-job-notice=\"false\"]').length > count",
            arg=previous_job_bubbles,
            timeout=12_000,
        )
        bubble = page.locator(
            '#messages .msg-assistant[data-agent-job-id][data-agent-job-notice="false"]'
        ).last
        job_id = str(bubble.get_attribute("data-agent-job-id") or "")
        assert job_id
        expect(user).to_have_count(1)
        assert_order(message, job_id, require_notice=False)

        notice = aria_browser.wait_for_job_notice(result, timeout_ms=25_000)
        expect(notice).to_be_visible()
        expect(user).to_have_count(1)
        assert_order(message, job_id, require_notice=True)

        page.reload(wait_until="domcontentloaded")
        reloaded_user = page.locator('#messages .msg-user[data-chat-user-turn="true"]').filter(has_text=message)
        expect(reloaded_user).to_have_count(1)
        assert_order(message, job_id, require_notice=True)
        expected = int(page.locator("#messages").get_attribute("data-chat-user-turns-expected") or "0")
        assert page.locator('#messages .msg-user[data-chat-user-turn="true"]').count() == expected

    aria_browser.assert_clean_js()


def test_s31_legacy_context_rollup_freeze_survives_restart(
    aria_browser: AriaBrowser, controls: HarnessControl,
) -> None:
    """S31: startup preserves legacy day collections and rollups byte-for-byte."""

    daily = "aria_sessions_e2e-admin_2020-01-01"
    empty_daily = "aria_sessions_e2e-admin_2020-01-02"
    rollups = (
        "aria_context-mem_e2e-admin",
        "aria_context-mem_e2e-admin_dim_3",
    )
    for name in (daily, empty_daily, *rollups):
        try:
            _qdrant_request(
                f"/collections/{name}", method="PUT",
                payload={"vectors": {"size": 3, "distance": "Cosine"}},
            )
        except Exception:
            pass
    _qdrant_request(
        f"/collections/{daily}/points?wait=true", method="PUT",
        payload={"points": [{
            "id": 995001,
            "vector": [0.1, 0.2, 0.3],
            "payload": {
                "user_id": "e2e-admin", "type": "session",
                "text": "S31 legacy daily context sentinel",
                "timestamp": "2020-01-01T00:00:00+00:00",
            },
        }]},
    )
    for index, name in enumerate(rollups, start=1):
        _qdrant_request(
            f"/collections/{name}/points?wait=true", method="PUT",
            payload={"points": [{
                "id": 995010 + index,
                "vector": [0.3, 0.2, 0.1],
                "payload": {
                    "user_id": "e2e-admin", "type": "knowledge",
                    "text": f"S31 immutable rollup {index}",
                    "source": "compression", "rollup_level": "week",
                    "rollup_bucket": f"2020-W0{index}",
                    "rollup_period_start": "2020-01-01",
                    "rollup_period_end": "2020-01-07",
                },
            }]},
        )

        def snapshot(name: str) -> dict:
            response = _qdrant_request(
                f"/collections/{name}/points/scroll", method="POST",
                payload={"limit": 20, "with_payload": True, "with_vector": True},
            )
            # Qdrant's top-level response time is transport telemetry, not
            # persisted collection state.  Compare only the durable scroll
            # result so a restart cannot pass or fail based on request latency.
            return response.get("result", {})

    before = {name: snapshot(name) for name in (daily, empty_daily, *rollups)}
    embedding_calls_before = len(controls.anthropic_logs().get("embedding_requests", []))
    container_name = os.environ["ARIA_E2E_CONTAINER_NAME"]
    assert container_name.startswith("aria-e2e-") and container_name.endswith("-aria")
    subprocess.run(["docker", "restart", container_name], check=True, capture_output=True, text=True)

    deadline = time.monotonic() + 45
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    while True:
        try:
            with opener.open(f"{aria_browser.base_url}/health", timeout=2) as response:
                if response.status < 500:
                    break
        except Exception:
            if time.monotonic() >= deadline:
                raise AssertionError("S31 timed out waiting for isolated ARIA restart")
            time.sleep(0.25)

    after = {name: snapshot(name) for name in (daily, empty_daily, *rollups)}
    assert after == before
    assert len(controls.anthropic_logs().get("embedding_requests", [])) == embedding_calls_before

    aria_browser.page.goto(f"{aria_browser.base_url}/memories/maintenance", wait_until="domcontentloaded")
    expect(aria_browser.page.locator("main")).to_contain_text("Ältere Kontext-Rollups: 2 Einträge")
    expect(aria_browser.page.locator('form[action="/memories/maintenance"]')).to_have_count(0)
    aria_browser.assert_clean_js()


def _e2e_activity_journal_store() -> ActivityJournalStore:
    _make_isolated_data_writable()
    return ActivityJournalStore(
        Path(os.environ["ARIA_E2E_DATA_DIR"]) / "runtime" / "activity_journal.sqlite3"
    )


def _journal_row(*, entry_id: str, user_id: str, finished_at: float, keep: bool = False) -> dict[str, object]:
    return {
        "id": entry_id,
        "user_id": user_id,
        "started_at": finished_at - 2,
        "finished_at": finished_at,
        "kind": "turn",
        "job_id": "",
        "goal": f"J1 Blender activity {entry_id}",
        "tools": {SCENE: 1},
        "connection_kinds": ["mcp"],
        "connection_refs": [],
        "mcp_servers": ["blender"],
        "outcome_status": "ok",
        "confirmations": {"asked": 0, "approved": 0, "rejected": 0},
        "corrected": False,
        "outcome_phrase": "Blender scene inspected.",
        "source": "live",
        "keep": keep,
    }


def test_j1_activity_journal_page_and_store_are_user_scoped(aria_browser: AriaBrowser) -> None:
    """J1: seeded users never see one another's compact entries."""

    store = _e2e_activity_journal_store()
    now = time.time()
    for index in range(25):
        store.write(_journal_row(
            entry_id=f"j1-alice-{index:02d}", user_id="e2e-admin",
            finished_at=now - (index % 5) * 86400 - index,
        ))
    store.write(_journal_row(
        entry_id="j1-bob-only", user_id="e2e-other", finished_at=now,
    ))
    assert store.get("e2e-admin", "j1-bob-only") is None
    assert store.get("e2e-other", "j1-bob-only") is not None

    page = aria_browser.page
    page.goto(f"{aria_browser.base_url}/memories/activity-journal", wait_until="domcontentloaded")
    expect(page.get_by_role("heading", name="Aktivitätsjournal", exact=True)).to_be_visible()
    expect(page.locator(".activity-journal-entry")).to_have_count(len(store.query("e2e-admin", limit=200)))
    expect(page.locator("body")).not_to_contain_text("j1-bob-only")
    assert page.locator(".activity-journal-day").count() >= 5
    aria_browser.assert_clean_js()


def test_alpha1002_journal_period_and_local_day_are_visible_in_browser(
    aria_browser: AriaBrowser,
) -> None:
    """The browser sees All by default and a Zurich-local day boundary."""

    instant = datetime(2026, 10, 11, 23, 30, tzinfo=timezone.utc).timestamp()
    store = _e2e_activity_journal_store()
    store.write(_journal_row(
        entry_id="alpha1002-zurich-boundary",
        user_id="e2e-admin",
        finished_at=instant,
    ))
    page = aria_browser.page
    page.context.add_cookies([{
        "name": "aria_display_timezone",
        "value": "Europe/Zurich",
        "url": aria_browser.base_url,
    }])
    page.goto(f"{aria_browser.base_url}/memories/activity-journal", wait_until="domcontentloaded")
    expect(page.locator("#journal-period")).to_have_value("all")
    expect(page.locator("#journal-custom-range")).to_be_hidden()
    expect(page.locator("#journal-since")).to_be_hidden()
    row = page.locator('[data-entry-id="alpha1002-zurich-boundary"]')
    expect(row).to_contain_text("01:30")
    expect(row.locator("xpath=ancestor::section[contains(@class, 'activity-journal-day')]/h2")).to_have_text("12.10.2026")

    page.locator("#journal-period").select_option("custom")
    expect(page.locator("#journal-custom-range")).to_be_visible()
    expect(page.locator("#journal-since")).to_have_attribute("required", "")


def test_j2_agent_reads_activity_journal_only_on_demand(
    aria_browser: AriaBrowser, controls: HarnessControl,
) -> None:
    """J2: the strict fake requests the journal tool and grounds the answer in it."""

    controls.script("J2", [
        _tool("activity_journal_read", {"query": "Blender", "since": "last_week", "limit": 20}),
        _text("Letzte Woche haben wir Blender-Szenen mit get_scene_info geprüft."),
    ])
    aria_browser.open_chat()
    bubble = aria_browser.send_chat(
        "Was haben wir letzte Woche mit Blender gemacht?", timeout_ms=30_000,
    )
    expect(bubble.locator(".msg-text")).to_contain_text("Blender-Szenen")
    bubble.locator("details.msg-details").click()
    expect(bubble.locator("details.msg-details")).to_contain_text("activity_journal_read")
    assert not controls.anthropic_logs()["violations"]
    aria_browser.assert_clean_js()


def test_j3_cancelled_detached_job_writes_exactly_one_terminal_entry(
    aria_browser: AriaBrowser, controls: HarnessControl,
) -> None:
    """J3: cancellation is terminal and journal projection stays idempotent."""

    controls.script("J3", [
        _tool(EXECUTE, {"code": "name='J3-Cancelled'"}, delay=12.0),
        _text("J3 should not complete normally."),
    ])
    aria_browser.open_chat()
    aria_browser.send_chat("J3 starte einen langen Blender-Auftrag.", timeout_ms=12_000)
    bubble = aria_browser.wait_for_job_bubble()
    job_id = str(bubble.get_attribute("data-agent-job-id") or "")
    expect(bubble.locator("[data-agent-job-action='cancel']")).to_be_visible()
    bubble.locator("[data-agent-job-action='cancel']").click()
    aria_browser.wait_for_job_notice("abgebrochen", timeout_ms=30_000)
    deadline = time.monotonic() + 8
    store = _e2e_activity_journal_store()
    matches: list[dict[str, object]] = []
    while time.monotonic() < deadline:
        matches = [row for row in store.query("e2e-admin", limit=500) if row.get("job_id") == job_id]
        if matches:
            break
        time.sleep(0.2)
    assert len(matches) == 1
    assert matches[0]["outcome_status"] == "cancelled"
    aria_browser.assert_clean_js()


def test_st7_j4_legacy_rollup_preview_import_and_scoped_delete(aria_browser: AriaBrowser) -> None:
    """ST7/J4: grouped base + _dim_N re-import in place, then scoped delete."""

    current_user_rollups = (
        ("aria_context-mem_e2e-admin", 996001, "# Memory Compression Template\n- J4 gemeinsamer Rollup.\n- J4 Marketing-"),
        ("aria_context-mem_e2e-admin_dim_3", 996002, "Einträge:\n# Memory Compression Template\n- J4 gemeinsamer Rollup.\n- J4 Marketing-Kampagne geplant."),
    )
    for collection, point_id, text_value in current_user_rollups:
        try:
            _qdrant_request(
                f"/collections/{collection}", method="PUT",
                payload={"vectors": {"size": 3, "distance": "Cosine"}},
            )
        except Exception:
            pass
        _qdrant_request(
            f"/collections/{collection}/points?wait=true", method="PUT",
            payload={"points": [{"id": point_id, "vector": [0.2, 0.2, 0.2], "payload": {
                "user_id": "e2e-admin", "type": "knowledge", "source": "compression",
                "rollup_level": "week", "rollup_bucket": "2020-W08",
                "rollup_period_start": "2020-02-17", "rollup_period_end": "2020-02-23",
                "text": text_value,
            }}]},
        )
    other = "aria_context-mem_e2e-other"
    try:
        _qdrant_request(
            f"/collections/{other}", method="PUT",
            payload={"vectors": {"size": 3, "distance": "Cosine"}},
        )
    except Exception:
        pass
    _qdrant_request(
        f"/collections/{other}/points?wait=true", method="PUT",
        payload={"points": [{"id": 996099, "vector": [0.1, 0.1, 0.1], "payload": {
            "user_id": "e2e-other", "type": "knowledge", "source": "compression",
            "rollup_level": "week", "rollup_bucket": "2020-W09",
            "rollup_period_start": "2020-02-24", "rollup_period_end": "2020-03-01",
            "text": "J4 other user rollup",
        }}]},
    )
    page = aria_browser.page
    page.goto(f"{aria_browser.base_url}/memories/activity-journal", wait_until="domcontentloaded")
    expect(page.locator("body")).to_contain_text("Alte Kontext-Rollups übernehmen")
    migrate = page.locator('form[action="/memories/activity-journal/legacy/migrate"]')
    expect(page.locator("body")).to_contain_text("J4 gemeinsamer Rollup")
    migrate.locator('input[name="confirmed"]').check()
    migrate.locator('button[type="submit"]').click()
    page.wait_for_load_state("domcontentloaded")
    expect(page.locator("body")).to_contain_text("bereits übernommen")
    store = _e2e_activity_journal_store()
    legacy = store.query("e2e-admin", source="legacy_context_rollup", limit=500)
    grouped = [row for row in legacy if row["period_start"] == "2020-02-17"]
    assert len(grouped) == 1
    assert {(source["collection"], source["point_id"]) for source in grouped[0]["legacy_sources"]} == {
        ("aria_context-mem_e2e-admin", "996001"),
        ("aria_context-mem_e2e-admin_dim_3", "996002"),
    }
    stable_id = grouped[0]["id"]
    page.goto(f"{aria_browser.base_url}/memories/activity-journal", wait_until="domcontentloaded")
    migrate = page.locator('form[action="/memories/activity-journal/legacy/migrate"]')
    migrate.locator('input[name="confirmed"]').check()
    migrate.locator('button[type="submit"]').click()
    page.wait_for_load_state("domcontentloaded")
    remigrated = [row for row in store.query("e2e-admin", source="legacy_context_rollup", limit=500) if row["period_start"] == "2020-02-17"]
    assert len(remigrated) == 1 and remigrated[0]["id"] == stable_id
    delete_form = page.locator('form[action="/memories/activity-journal/legacy/delete"]')
    expect(delete_form).to_be_visible()
    delete_form.locator('input[name="confirmation"]').fill("ALTE ROLLUPS LÖSCHEN")
    delete_form.locator('button[type="submit"]').click()
    page.wait_for_load_state("domcontentloaded")
    for collection in ("aria_context-mem_e2e-admin", "aria_context-mem_e2e-admin_dim_3"):
        try:
            remaining = _qdrant_request(
                f"/collections/{collection}/points/scroll", method="POST",
                payload={"limit": 20, "with_payload": True, "with_vector": False},
            ).get("result", {}).get("points", [])
        except urllib.error.HTTPError as exc:
            assert exc.code == 404
            remaining = []
        remaining_compression = [
            row for row in remaining
            if str(row.get("payload", {}).get("source")) == "compression"
        ]
        assert not remaining_compression, {
            "collection": collection,
            "remaining_compression": remaining_compression,
        }
    other_rows = _qdrant_request(
        f"/collections/{other}/points/scroll", method="POST",
        payload={"limit": 20, "with_payload": True, "with_vector": False},
    ).get("result", {}).get("points", [])
    assert any(row.get("id") == 996099 for row in other_rows)
    aria_browser.assert_clean_js()


def test_j5_retention_sweep_preserves_keep_and_legacy_entries() -> None:
    """J5: only expired unkept live journal projections are swept."""

    store = _e2e_activity_journal_store()
    now = time.time()
    old = now - 100 * 86400
    store.write(_journal_row(entry_id="j5-expired", user_id="e2e-admin", finished_at=old))
    store.write(_journal_row(entry_id="j5-kept", user_id="e2e-admin", finished_at=old, keep=True))
    legacy = _journal_row(entry_id="j5-legacy", user_id="e2e-admin", finished_at=old)
    legacy.update({"source": "legacy_context_rollup", "keep": True, "kind": "legacy"})
    store.write(legacy)
    assert store.sweep(retention_days=90, now=now) >= 1
    assert store.get("e2e-admin", "j5-expired") is None
    assert store.get("e2e-admin", "j5-kept") is not None
    assert store.get("e2e-admin", "j5-legacy") is not None


def test_u19_alpha994_bilingual_page_linter_and_connection_inventory(
    aria_browser: AriaBrowser,
) -> None:
    """Run inventory completeness before the later destructive reset scenario."""
    _assert_u19_alpha994_bilingual_page_linter_and_connection_inventory(aria_browser)


def test_r1_operational_retention_preserves_long_lived_user_data(
    aria_browser: AriaBrowser,
) -> None:
    _make_isolated_data_writable()
    data_dir = Path(os.environ["ARIA_E2E_DATA_DIR"])
    notes = data_dir / "notes" / "r1-note.json"
    recipe = data_dir / "recipes" / "r1-recipe.json"
    notes.parent.mkdir(parents=True, exist_ok=True)
    recipe.parent.mkdir(parents=True, exist_ok=True)
    notes.write_text('{"sentinel":"R1-note"}\n', encoding="utf-8")
    recipe_payload = {
        "id": "r1-recipe", "name": "R1 protected recipe",
        "description": "R1-recipe sentinel", "steps": [
            {"id": "s1", "type": "chat_send", "params": {"message": "R1"}},
        ],
    }
    recipe.write_text(json.dumps(recipe_payload) + "\n", encoding="utf-8")

    trace = data_dir / "modules" / "native_agent" / "r1-old.jsonl"
    trace.parent.mkdir(parents=True, exist_ok=True)
    trace.write_text('{"old":true}\n', encoding="utf-8")
    old = time.time() - 10 * 86400
    os.utime(trace, (old, old))
    logs = data_dir / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    for index in range(5):
        archive = logs / f"tokens-archive-2020010{index + 1}T000000Z.jsonl"
        archive.write_text("{}\n", encoding="utf-8")
        os.utime(archive, (old - index, old - index))
    audit = data_dir / "runtime" / "llm_audit.jsonl"
    audit.parent.mkdir(parents=True, exist_ok=True)
    audit.write_text('{"created_at":"2020-01-01T00:00:00+00:00"}\n', encoding="utf-8")

    pending_db = data_dir / "runtime" / "native_pending_actions.sqlite3"
    NativePendingStore(pending_db)
    with sqlite3.connect(pending_db) as connection:
        connection.execute(
            "INSERT OR REPLACE INTO native_pending_actions VALUES(?,?,?,?,?,?,?)",
            ("e2e-admin", "r1-expired", "x", "{}", "x", "", 1.0),
        )
    ledger_db = data_dir / "runtime" / "action_confirmations.sqlite3"
    ActionConfirmationLedger(ledger_db)
    with sqlite3.connect(ledger_db) as connection:
        connection.execute(
            "INSERT OR REPLACE INTO action_confirmation_claims VALUES(?,?,?,?)",
            ("e2e-admin", "r1-expired", "fingerprint", 1.0),
        )
    inbound_db = data_dir / "runtime" / "inbound_events.sqlite3"
    InboundEventStore(inbound_db)
    with sqlite3.connect(inbound_db) as connection:
        connection.execute(
            """INSERT OR REPLACE INTO inbound_events(
            event_id,contract,source_kind,source_ref,provider_profile,received_at,observed_at,
            content_type,headers_json,remote_fingerprint,body_digest,preview,technical_fields_json,
            routing_policy,source_event_id,raw_body) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "r1-expired", "inbound_event_v1", "inbound_webhook", "r1-source", "",
                "2020-01-01T00:00:00+00:00", "", "text/plain", "{}", "", "digest",
                "expired", "{}", "log_only", "", "",
            ),
        )

    try:
        _qdrant_request(
            "/collections/aria_web_evidence", method="PUT",
            payload={"vectors": {"size": 1, "distance": "Cosine"}},
        )
    except Exception:
        pass
    _qdrant_request(
        "/collections/aria_web_evidence/points?wait=true", method="PUT",
        payload={"points": [{"id": 986001, "vector": [0.0], "payload": {"expires_at": "2020-01-01T00:00:00+00:00"}}]},
    )
    _qdrant_request(
        "/collections/aria_r1_protected", method="PUT",
        payload={"vectors": {"size": 1, "distance": "Cosine"}},
    )
    _qdrant_request(
        "/collections/aria_r1_protected/points?wait=true", method="PUT",
        payload={"points": [{"id": 986002, "vector": [0.0], "payload": {"sentinel": "memory-document-protected"}}]},
    )

    aria_browser.page.goto(f"{aria_browser.base_url}/config/logs", wait_until="domcontentloaded")
    aria_browser.page.locator('form[action="/config/logs/cleanup"] button').click()
    aria_browser.page.wait_for_url(lambda url: "pruned=" in url, timeout=30_000)
    _make_isolated_data_writable()
    assert not trace.exists()
    assert len(list(logs.glob("tokens-archive-*.jsonl"))) <= 3
    assert "2020-01-01" not in audit.read_text(encoding="utf-8") if audit.exists() else True
    if pending_db.exists():
        with sqlite3.connect(f"file:{pending_db}?mode=ro", uri=True) as connection:
            assert connection.execute("SELECT COUNT(*) FROM native_pending_actions WHERE token='r1-expired'").fetchone()[0] == 0
    if ledger_db.exists():
        with sqlite3.connect(f"file:{ledger_db}?mode=ro", uri=True) as connection:
            assert connection.execute("SELECT COUNT(*) FROM action_confirmation_claims WHERE token='r1-expired'").fetchone()[0] == 0
    if inbound_db.exists():
        with sqlite3.connect(f"file:{inbound_db}?mode=ro", uri=True) as connection:
            assert connection.execute("SELECT COUNT(*) FROM inbound_events WHERE event_id='r1-expired'").fetchone()[0] == 0
    assert notes.read_text(encoding="utf-8") == '{"sentinel":"R1-note"}\n'
    assert json.loads(recipe.read_text(encoding="utf-8")) == recipe_payload
    scroll = _qdrant_request(
        "/collections/aria_web_evidence/points/scroll", method="POST",
        payload={"limit": 20, "with_payload": True, "with_vector": False},
    )
    assert all(row.get("id") != 986001 for row in scroll.get("result", {}).get("points", []))
    protected = _qdrant_request(
        "/collections/aria_r1_protected/points/scroll", method="POST",
        payload={"limit": 20, "with_payload": True, "with_vector": False},
    )
    assert any(row.get("payload", {}).get("sentinel") == "memory-document-protected" for row in protected["result"]["points"])
    aria_browser.assert_clean_js()


def test_r5_trace_minimization_and_full_warning(
    aria_browser: AriaBrowser, controls: HarnessControl,
) -> None:
    data_dir = Path(os.environ["ARIA_E2E_DATA_DIR"])
    medical_sentence = "R5 synthetic medical sentence: take 50 mg once monthly."
    aria_browser.page.goto(f"{aria_browser.base_url}/memories/import", wait_until="domcontentloaded")
    aria_browser.page.locator("#import_document_file").set_input_files({
        "name": "r5-medical.txt", "mimeType": "text/plain",
        "buffer": medical_sentence.encode("utf-8"),
    })
    aria_browser.page.locator("#import_document_new_collection").fill("r5_medical")
    aria_browser.page.locator("form.memory-upload-form button[type='submit']").click()
    aria_browser.page.wait_for_url(lambda url: "info=" in url, timeout=30_000)
    controls.script("R5-minimal", [
        _tool("documents_read_search_inventory", {"action": "answer", "query": medical_sentence}),
        _tool(REVIEW_COMMAND_OUTPUT, {}, delay=5.0),
        _text("R5 minimal trace completed safely."),
    ])
    aria_browser.open_chat()
    aria_browser.send_chat("R5 run the canary command.", timeout_ms=12_000)
    aria_browser.wait_for_job_notice("fertig", timeout_ms=30_000)
    _make_isolated_data_writable()
    trace_root = data_dir / "modules" / "native_agent"
    minimal_text = "\n".join(path.read_text(encoding="utf-8") for path in trace_root.glob("*.jsonl"))
    assert "SECRET-CANARY-986" not in minimal_text
    assert medical_sentence not in minimal_text
    assert any(row["tool"] == "read_command_output" for row in controls.mcp_logs()["calls"])
    jobs = data_dir / "runtime" / "agent_jobs.sqlite3"
    if jobs.exists():
        with sqlite3.connect(jobs) as connection:
            rows = connection.execute(
                "SELECT step_log,result,resume_state,correction_queue FROM agent_jobs "
                "WHERE status IN ('done','error','cancelled')"
            ).fetchall()
        assert "SECRET-CANARY-986" not in json.dumps(rows)

    aria_browser.page.goto(f"{aria_browser.base_url}/config/logs", wait_until="domcontentloaded")
    expect(aria_browser.page.locator("body")).to_contain_text("sensible Dokumenttexte")
    aria_browser.page.locator("#trace-settings").evaluate("node => { node.open = true; }")
    aria_browser.page.locator("#trace-detail-level").select_option("full")
    aria_browser.page.locator('form[action="/config/logs/save"] button[type="submit"]').click()
    aria_browser.page.wait_for_load_state("domcontentloaded")
    controls.script("R5-full", [
        _tool("documents_read_search_inventory", {"action": "answer", "query": medical_sentence}),
        _tool(REVIEW_COMMAND_OUTPUT, {}),
        _text("R5 full trace completed."),
    ])
    aria_browser.open_chat()
    aria_browser.send_chat("R5 run the full canary command.", timeout_ms=30_000)
    _make_isolated_data_writable()
    full_text = "\n".join(path.read_text(encoding="utf-8") for path in trace_root.glob("*.jsonl"))
    assert "SECRET-CANARY-986" in full_text
    assert medical_sentence in full_text
    aria_browser.assert_clean_js()


def test_r8a_secret_free_and_encrypted_config_backups(
    aria_browser: AriaBrowser,
) -> None:
    page = aria_browser.page
    page.goto(f"{aria_browser.base_url}/config/backup", wait_until="domcontentloaded")
    with page.expect_download() as default_info:
        page.locator('#backup-export-form button[type="submit"]').click()
    default_path = Path(default_info.value.path())
    default_bytes = default_path.read_bytes()
    default_payload = json.loads(default_bytes)
    default_raw = json.dumps(default_payload)
    assert "password_hash" not in default_raw and "e2e-only-password" not in default_raw
    assert default_payload["manifest"]["secrets"] == "excluded"
    assert default_payload["manifest"]["persistent_volumes_are_a_backup"] is False

    passphrase = "R8a correct passphrase 986"
    page.locator('input[name="include_secrets"]').check()
    expect(page.locator("#backup-bundle-fields")).to_be_visible()
    page.locator('#backup-passphrase').fill(passphrase)
    page.locator('#backup-passphrase-confirm').fill(passphrase)
    with page.expect_download() as encrypted_info:
        page.locator('form[action="/config/backup/export"] button[type="submit"]').click()
    encrypted_path = Path(encrypted_info.value.path())
    encrypted_bytes = encrypted_path.read_bytes()
    encrypted_payload = json.loads(encrypted_bytes)
    assert encrypted_payload["manifest"]["secrets"] == "encrypted"
    assert "encrypted_secrets_bundle" in encrypted_payload

    def import_backup(payload: bytes, supplied_passphrase: str, name: str):
        csrf_token = page.locator('meta[name="csrf-token"]').get_attribute("content") or ""
        response = page.context.request.post(
            f"{aria_browser.base_url}/config/backup/import",
            multipart={
                "backup_file": {"name": name, "mimeType": "application/json", "buffer": payload},
                "passphrase": supplied_passphrase,
                "csrf_token": csrf_token,
            },
        )
        assert response.ok, response.text()
        return response

    wrong_response = import_backup(encrypted_bytes, "wrong passphrase", "aria-config-encrypted.json")
    assert "error=" in wrong_response.url and "wrong or the file is damaged" in wrong_response.text()
    restored_response = import_backup(encrypted_bytes, passphrase, "aria-config-encrypted.json")
    assert "saved=1" in restored_response.url and "info=backup_imported" in restored_response.url
    secret_free_response = import_backup(default_bytes, "", "aria-config-secret-free.json")
    assert "saved=1" in secret_free_response.url
    assert "info=backup_imported_needs_secrets" in secret_free_response.url
    aria_browser.assert_clean_js(allow_failed_contains=("/config/backup/export",))


def test_r8b_upgrade_backup_retention_contract(tmp_path: Path) -> None:
    script = (Path(__file__).resolve().parents[2] / "docker" / "setup-compose-stack.sh").read_text(encoding="utf-8")
    backup_fn = re.search(r"backup_if_exists\(\) \{.*?^\}", script, re.MULTILINE | re.DOTALL)
    prune_fn = re.search(r"prune_upgrade_backups\(\) \{.*?^\}", script, re.MULTILINE | re.DOTALL)
    assert backup_fn and prune_fn
    install = tmp_path / "stack"
    install.mkdir()
    target = install / ".env"
    target.write_text("one", encoding="utf-8")
    subprocess.run(
        ["bash", "-c", f'{backup_fn.group(0)}\nbackup_if_exists "$1"', "bash", str(target)],
        check=True,
    )
    first = next(install.glob(".env.bak.*"))
    assert stat.S_IMODE(first.stat().st_mode) == 0o600
    for index in range(4):
        path = install / f".env.bak.2000010100000{index}"
        path.write_text(str(index), encoding="utf-8")
        os.utime(path, (index + 1, index + 1))
    subprocess.run(
        ["bash", "-c", f'{prune_fn.group(0)}\nINSTALL_DIR="$1"\nprune_upgrade_backups', "bash", str(install)],
        check=True,
    )
    assert len(list(install.glob(".env.bak.*"))) == 2


def test_r10_factory_reset_covers_operational_files_but_not_host(
    aria_browser: AriaBrowser,
) -> None:
    data_dir = Path(os.environ["ARIA_E2E_DATA_DIR"])
    for rel in (
        "notes/r10.txt", "modules/native_agent/r10.jsonl", "logs/tokens-archive-r10.jsonl",
        "pricing/r10.json", "runtime/r10.json",
    ):
        path = data_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("R10", encoding="utf-8")
    host_sentinel = Path(os.environ["ARIA_E2E_ARTIFACT_DIR"]) / "r10-host-sentinel.txt"
    host_sentinel.write_text("outside ARIA mounts", encoding="utf-8")
    aria_browser.page.goto(f"{aria_browser.base_url}/config/logs", wait_until="domcontentloaded")
    expect(aria_browser.page.locator("body")).to_contain_text("Host-Dateien außerhalb")
    aria_browser.page.locator('#confirm-factory-reset').fill("FACTORY RESET")
    aria_browser.page.locator('form[action="/config/logs/factory-reset"] button').click()
    aria_browser.page.wait_for_url(lambda url: "/login" in url, timeout=30_000)
    for rel in (
        "notes/r10.txt", "modules/native_agent/r10.jsonl", "logs/tokens-archive-r10.jsonl",
        "pricing/r10.json", "runtime/r10.json",
    ):
        assert not (data_dir / rel).exists()
    assert host_sentinel.read_text(encoding="utf-8") == "outside ARIA mounts"


def test_u1_backup_page_clarity_and_encrypted_option(aria_browser: AriaBrowser) -> None:
    page = aria_browser.page
    page.goto(f"{aria_browser.base_url}/config/backup", wait_until="domcontentloaded")
    primary = page.locator('#backup-download button[type="submit"]')
    expect(primary).to_be_visible()
    box = primary.bounding_box()
    assert box and box["y"] + box["height"] <= 800
    toggle = page.locator("#backup-bundle-toggle")
    expect(toggle).not_to_be_checked()
    expect(page.locator("#backup-bundle-fields")).to_be_hidden()

    with page.expect_download() as default_info:
        primary.click()
    default_payload = json.loads(Path(default_info.value.path()).read_text(encoding="utf-8"))
    default_raw = json.dumps(default_payload)
    assert default_payload["manifest"]["secrets"] == "excluded"
    assert "password_hash" not in default_raw and "e2e-only-password" not in default_raw

    toggle.check()
    fields = page.locator("#backup-bundle-fields")
    expect(fields).to_be_visible()
    passphrase = "U1 encrypted backup passphrase"
    page.locator("#backup-passphrase").fill(passphrase)
    page.locator("#backup-passphrase-confirm").fill(passphrase)
    with page.expect_download() as encrypted_info:
        primary.click()
    encrypted = json.loads(Path(encrypted_info.value.path()).read_text(encoding="utf-8"))
    assert encrypted["manifest"]["secrets"] == "encrypted"
    assert "encrypted_secrets_bundle" in encrypted

    info = page.locator('[data-ui-pattern="info"]')
    expect(info).to_have_count(1)
    assert info.locator("button, .button-like").count() == 0
    info.locator("summary").click()
    expect(info).to_have_attribute("open", "")
    aria_browser.assert_clean_js(allow_failed_contains=("/config/backup/export",))


def test_u2_logs_page_clarity_and_typed_danger(aria_browser: AriaBrowser) -> None:
    page = aria_browser.page
    page.goto(f"{aria_browser.base_url}/config/logs", wait_until="domcontentloaded")
    settings = page.locator('#trace-settings[data-ui-pattern="settings"]')
    expect(settings).to_be_visible()
    assert settings.locator('button[type="submit"]').count() == 1
    patterns = page.locator("main > [data-ui-pattern]")
    assert patterns.last.get_attribute("data-ui-pattern") == "danger"
    danger = page.locator("#logs-danger-zone")
    expect(danger).to_be_visible()
    assert danger.locator("[data-typed-confirmation]").count() == 2
    assert danger.locator("#confirm-reset").get_attribute("required") == ""
    assert danger.locator("#confirm-factory-reset").get_attribute("required") == ""
    csrf_token = page.locator('meta[name="csrf-token"]').get_attribute("content") or ""
    response = page.context.request.post(
        f"{aria_browser.base_url}/config/logs/reset",
        form={"confirm_text": "not-reset"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert response.ok and "error=" in response.url
    aria_browser.assert_clean_js()


def test_u3_backup_navigation_is_under_security_and_route_stays_stable(
    aria_browser: AriaBrowser,
) -> None:
    page = aria_browser.page
    page.goto(f"{aria_browser.base_url}/config", wait_until="domcontentloaded")
    security = page.locator('[data-config-hub-group="security_access"]')
    operations = page.locator('[data-config-hub-group="operations"]')
    expect(security.locator('a[href^="/config/backup"]')).to_have_count(1)
    expect(operations.locator('a[href^="/config/backup"]')).to_have_count(0)
    page.goto(f"{aria_browser.base_url}/config/backup", wait_until="domcontentloaded")
    assert page.url.endswith("/config/backup")
    expect(page.locator("#backup-download")).to_be_visible()
    aria_browser.assert_clean_js()


def test_u4_ssh_connection_clarity_flow(aria_browser: AriaBrowser) -> None:
    page = aria_browser.page
    page.goto(f"{aria_browser.base_url}/config/connections/ssh/new", wait_until="domcontentloaded")
    expect(page.locator(".connection-page-purpose")).to_be_visible()
    create = page.locator('#connection-settings-create form[action="/config/connections/save"]')
    expect(create).to_be_visible()
    box = create.bounding_box()
    assert box and box["y"] <= 800
    create.locator('[name="connection_ref"]').fill("e2e-ui-ssh")
    create.locator('[name="host"]').fill("127.0.0.1")
    create.locator('[name="user"]').fill("aria")
    create.locator('[name="port"]').fill("9")
    create.locator('button[type="submit"]').click()
    page.wait_for_url(lambda url: "/config/connections/ssh/e2e-ui-ssh" in url, timeout=20_000)

    settings = page.locator('#manage-existing[data-ui-pattern="settings"]')
    expect(settings).to_be_visible()
    assert settings.locator('button[type="submit"]').count() == 1
    settings.locator('[name="connection_title"]').fill("E2E SSH")
    settings.locator('button[type="submit"]').click()
    page.wait_for_url(lambda url: "/config/connections/ssh/e2e-ui-ssh" in url, timeout=20_000)
    page.locator('#connection-test-action button[type="submit"]').click()
    page.wait_for_url(lambda url: "test_status=error" in url or "test_status=ok" in url, timeout=20_000)

    danger = page.locator("#connection-danger-zone")
    assert page.locator("main > [data-ui-pattern]").last.get_attribute("data-ui-pattern") == "danger"
    page.once("dialog", lambda dialog: dialog.accept())
    danger.locator('button[type="submit"]').click()
    page.wait_for_url(lambda url: "/config/connections/ssh" in url and "e2e-ui-ssh" not in url, timeout=20_000)
    aria_browser.assert_clean_js()


def test_u5_webhook_connection_clarity_flow(aria_browser: AriaBrowser) -> None:
    page = aria_browser.page
    page.goto(f"{aria_browser.base_url}/config/connections/webhook/new", wait_until="domcontentloaded")
    create = page.locator('#connection-settings-create form[action="/config/connections/webhook/save"]')
    create.locator('[name="connection_ref"]').fill("e2e-ui-webhook")
    create.locator('[name="url"]').fill("http://127.0.0.1:9/hook")
    create.locator('button[type="submit"]').click()
    page.wait_for_url(lambda url: "/config/connections/webhook/e2e-ui-webhook" in url, timeout=20_000)

    settings = page.locator('#manage-existing[data-ui-pattern="settings"]')
    expect(settings).to_be_visible()
    assert settings.locator('button[type="submit"]').count() == 1
    settings.locator('[name="connection_title"]').fill("E2E Webhook")
    settings.locator('button[type="submit"]').click()
    page.wait_for_url(lambda url: "/config/connections/webhook/e2e-ui-webhook" in url, timeout=20_000)
    page.locator('#connection-test-action button[type="submit"]').click()
    page.wait_for_url(lambda url: "webhook_test_status=" in url, timeout=20_000)

    assert page.locator('[data-ui-pattern="info"] button').count() == 0
    page.once("dialog", lambda dialog: dialog.accept())
    page.locator('#connection-danger-zone button[type="submit"]').click()
    page.wait_for_url(lambda url: "/config/connections/webhook" in url and "e2e-ui-webhook" not in url, timeout=20_000)
    aria_browser.assert_clean_js()


def test_u6_german_ui_uses_real_umlauts(aria_browser: AriaBrowser) -> None:
    page = aria_browser.page
    page.context.add_cookies([
        {"name": "aria_lang", "value": "de", "url": aria_browser.base_url},
    ])
    expected = {
        "/config": "Über",
        "/config/backup": "verschlüsselt",
        "/config/logs": "Größen",
        "/config/connections/ssh/new": "Schlüsselaustausch",
        "/": "Gedächtnis",
    }
    for path, word in expected.items():
        page.goto(f"{aria_browser.base_url}{path}", wait_until="domcontentloaded")
        expect(page.locator("body")).to_contain_text(word)
    page.context.add_cookies([
        {"name": "aria_lang", "value": "en", "url": aria_browser.base_url},
    ])
    aria_browser.assert_clean_js()


def test_u7_connection_create_detail_secret_and_action_contracts(
    aria_browser: AriaBrowser,
) -> None:
    """U7: every representative connection family exposes the canonical safe split."""

    page = aria_browser.page
    cases = {
        "ssh": ("connection_ref", "key_path"),
        "webhook": ("connection_ref", "url"),
        "smtp": ("connection_ref", "password"),
        "imap": ("connection_ref", "password"),
        "mcp": ("server_name", "url"),
    }
    for segment, (identity, secret) in cases.items():
        page.goto(f"{aria_browser.base_url}/config/connections/{segment}", wait_until="domcontentloaded")
        expect(page.locator('main[data-ui-page-type="overview"]')).to_be_visible()
        # Inventory-level action forms may carry a hidden reference (for example
        # reconnect). They must never expose the create/edit secret field.
        assert page.locator(f'[data-ui-page-type="overview"] input[name="{secret}"]').count() == 0
        page.goto(f"{aria_browser.base_url}/config/connections/{segment}/new", wait_until="domcontentloaded")
        expect(page.locator('main[data-ui-page-type="create"]')).to_be_visible()
        expect(page.locator(f'[name="{identity}"]')).to_be_visible()
        expect(page.locator(f'[name="{secret}"]')).to_be_visible()

    # The complete create/edit/test/delete browser lifecycle remains covered for SSH and
    # webhook above. These representative mail/MCP checks additionally freeze the secret
    # boundary without making real network calls from this strict-fake harness.
    aria_browser.assert_clean_js()


def test_u8_all_non_memory_pages_render_dark_and_light_with_index(
    aria_browser: AriaBrowser,
) -> None:
    """U8: owner-review screenshot index for all current non-/memories routes."""

    page = aria_browser.page
    page.set_viewport_size({"width": 1280, "height": 800})
    artifact_root = Path(__file__).resolve().parents[2] / "test-results" / "ui-ia-alpha989"
    artifact_root.mkdir(parents=True, exist_ok=True)
    for previous in artifact_root.glob("*.png"):
        previous.unlink()
    routes = [
        row for row in build_ui_route_inventory(local_aria_app)
        if row.owner_module != "auth_ui" and not row.path.startswith("/memories")
    ]
    assert len(routes) == 54
    rows: list[dict[str, str]] = []
    for theme in ("matrix", "paper"):
        for route in routes:
            response = page.goto(
                f"{aria_browser.base_url}{route.path}",
                wait_until="domcontentloaded",
                timeout=20_000,
            )
            assert response is not None and response.status < 500
            page.locator("body").evaluate("(node, value) => node.dataset.theme = value", theme)
            slug = re.sub(r"[^a-z0-9]+", "-", route.path.lower()).strip("-") or "home"
            screenshot = artifact_root / f"{theme}-{slug}.png"
            page.screenshot(path=str(screenshot), full_page=True)
            rows.append({"theme": theme, "path": route.path, "file": screenshot.name})
    links = "\n".join(
        f'<li><a href="{row["file"]}">{row["theme"]}: {row["path"]}</a></li>'
        for row in rows
    )
    (artifact_root / "index.html").write_text(
        "<!doctype html><meta charset=\"utf-8\"><title>ARIA Alpha990 UI index</title>"
        f"<h1>ARIA Alpha990 — 54 pages, dark and light</h1><ul>{links}</ul>\n",
        encoding="utf-8",
    )
    assert len(rows) == 108
    assert len(list(artifact_root.glob("*.png"))) == 108
    aria_browser.assert_clean_js()


def test_u9_legacy_connection_urls_redirect_to_canonical_pages(
    aria_browser: AriaBrowser,
) -> None:
    """U9: legacy query/anchor entry points keep their selected target."""

    page = aria_browser.page
    legacy_cases = {
        "ssh": ("ref", "alpha989-ssh"),
        "sftp": ("sftp_ref", "alpha989-sftp"),
        "smb": ("smb_ref", "alpha989-smb"),
        "webhook": ("webhook_ref", "alpha989-webhook"),
        "smtp": ("email_ref", "alpha989-smtp"),
        "imap": ("imap_ref", "alpha989-imap"),
        "mcp": ("server", "alpha989-mcp"),
    }
    for segment, (parameter, reference) in legacy_cases.items():
        page.goto(
            f"{aria_browser.base_url}/config/connections/{segment}?{parameter}={reference}#manage-existing",
            wait_until="domcontentloaded",
        )
        assert page.url.split("#", 1)[0].split("?", 1)[0].rstrip("/").endswith(
            f"/config/connections/{segment}/{reference}"
        )
        expect(page.locator('main[data-ui-page-type="detail"]')).to_be_visible()
    page.goto(f"{aria_browser.base_url}/config/connections/ssh?mode=create", wait_until="domcontentloaded")
    assert page.url.split("?", 1)[0].endswith("/config/connections/ssh/new")
    aria_browser.assert_clean_js()


def test_u10_mockup_fidelity_and_seeded_dark_light_review_index(
    aria_browser: AriaBrowser,
) -> None:
    """U10: approved mockup pages keep their structural order with real rows."""

    page = aria_browser.page
    page.set_viewport_size({"width": 1280, "height": 800})
    ssh_refs = ("alpha990-seed-a", "alpha990-seed-b", "alpha990-seed-failing")
    for index, ref in enumerate(ssh_refs):
        page.goto(f"{aria_browser.base_url}/config/connections/ssh/new", wait_until="domcontentloaded")
        create = page.locator('#connection-settings-create form[action="/config/connections/save"]')
        create.locator('[name="connection_ref"]').fill(ref)
        create.locator('[name="host"]').fill("127.0.0.1" if index < 2 else "connection-fails.invalid")
        create.locator('[name="user"]').fill("e2e")
        create.locator('[name="port"]').fill("9")
        create.locator('[name="run_key_exchange"]').uncheck()
        create.locator('button[type="submit"]').click()
        page.wait_for_url(lambda url, ref=ref: f"/config/connections/ssh/{ref}" in url, timeout=20_000)
    page.locator('#connection-test-action button[type="submit"]').click()
    page.wait_for_url(lambda url: "test_status=" in url, timeout=20_000)

    webhook_ref = "alpha990-seed-webhook"
    page.goto(f"{aria_browser.base_url}/config/connections/webhook/new", wait_until="domcontentloaded")
    webhook = page.locator('#connection-settings-create form[action="/config/connections/webhook/save"]')
    webhook.locator('[name="connection_ref"]').fill(webhook_ref)
    webhook.locator('[name="url"]').fill("http://127.0.0.1:9/hook")
    webhook.locator('button[type="submit"]').click()
    page.wait_for_url(lambda url: f"/config/connections/webhook/{webhook_ref}" in url, timeout=20_000)

    paths = (
        "/config/connections/ssh",
        f"/config/connections/ssh/{ssh_refs[0]}",
        "/config/connections/ssh/new",
        f"/config/connections/webhook/{webhook_ref}",
        "/config/llm",
        "/config/embeddings",
        "/config/llm/debug",
        "/config/language",
        "/memories/auto-memory",
        "/memories/create",
        "/memories/import",
        "/memories/maintenance",
        "/memories/config",
        "/help",
    )
    artifact_root = Path(__file__).resolve().parents[2] / "test-results" / "ui-fidelity-alpha990"
    artifact_root.mkdir(parents=True, exist_ok=True)
    for previous in artifact_root.glob("*.png"):
        previous.unlink()
    rows: list[dict[str, str]] = []
    for theme in ("matrix", "paper"):
        for path in paths:
            response = page.goto(f"{aria_browser.base_url}{path}", wait_until="domcontentloaded")
            assert response is not None and response.status < 500
            page.locator("body").evaluate("(node, value) => node.dataset.theme = value", theme)
            slug = re.sub(r"[^a-z0-9]+", "-", path.lower()).strip("-") or "home"
            screenshot = artifact_root / f"{theme}-{slug}.png"
            page.screenshot(path=str(screenshot), full_page=True)
            rows.append({"theme": theme, "path": path, "file": screenshot.name})
    ssh = page.goto(f"{aria_browser.base_url}/config/connections/ssh", wait_until="domcontentloaded")
    assert ssh and ssh.status < 500
    expect(page.locator(".connection-overview-header h1")).to_be_visible()
    expect(page.locator(".connection-overview-create")).to_be_visible()
    expect(page.locator(".connection-overview-summary")).to_be_visible()
    assert page.locator(".connection-profile-card").count() >= 3
    (artifact_root / "index.json").write_text(
        json.dumps({"seeded": True, "viewport": [1280, 800], "pages": rows}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    assert len(rows) == len(paths) * 2
    aria_browser.assert_clean_js()


def test_u11_page_specific_purpose_lines_and_clean_chat(aria_browser: AriaBrowser) -> None:
    """U11: no generic purpose is injected and Chat remains intentionally clean."""

    page = aria_browser.page
    page.goto(f"{aria_browser.base_url}/", wait_until="domcontentloaded")
    assert page.locator("main .ui-page-purpose, main .authenticated-page-purpose").count() == 0
    purposes: list[str] = []
    for path in ("/config/llm", "/config/embeddings", "/config/language", "/memories/auto-memory"):
        page.goto(f"{aria_browser.base_url}{path}", wait_until="domcontentloaded")
        purpose = page.locator("main .ui-page-purpose").first
        expect(purpose).to_be_visible()
        purposes.append(purpose.inner_text().strip())
    assert len(set(purposes)) == len(purposes)
    assert all("diesen Bereich ansehen" not in purpose for purpose in purposes)
    aria_browser.assert_clean_js()


def test_u12_personal_model_actions_and_memory_browser_are_separate(
    aria_browser: AriaBrowser,
) -> None:
    """U12: a seeded claim is readable/correctable/deletable; browser stays separate."""

    page = aria_browser.page
    # R10 intentionally clears the disposable secure store. Restore only the
    # strict-fake embedding credential before exercising the real claim path.
    page.goto(f"{aria_browser.base_url}/config/embeddings", wait_until="domcontentloaded")
    page.locator("#embedding-profile-settings").evaluate("node => { node.open = true; }")
    embedding_form = page.locator('#embedding-profile-settings form[action="/config/embeddings/save"]')
    embedding_form.locator('[name="api_key"]').fill("e2e-fake-key")
    embedding_form.locator('button[type="submit"]').first.click()
    page.wait_for_url(lambda url: "/config/embeddings" in url and "saved=" in url, timeout=20_000)

    page.goto(f"{aria_browser.base_url}/memories/create", wait_until="domcontentloaded")
    form = page.locator('form[action="/memories/create"]')
    form.locator('[name="kind"]').select_option("preference")
    form.locator('[name="subject"]').fill("ich")
    form.locator('[name="predicate"]').fill("mag")
    form.locator('[name="value"]').fill("Massive Attack")
    form.locator('button[type="submit"]').click()
    page.wait_for_load_state("domcontentloaded")
    page.goto(f"{aria_browser.base_url}/memories/auto-memory", wait_until="domcontentloaded")
    expect(page.locator(".learning-ledger-item").filter(has_text="Massive Attack")).to_be_visible()
    expect(page.locator("body")).to_contain_text("Vorliebe")
    expect(page.locator("body")).to_contain_text("Korrigieren")
    expect(page.locator("body")).to_contain_text("Löschen")
    page.goto(f"{aria_browser.base_url}/memories", wait_until="domcontentloaded")
    expect(page.locator(".memory-drilldown-browser")).to_be_visible()
    aria_browser.assert_clean_js()


def test_u13_help_has_four_groups_without_duplicate_system_docs(
    aria_browser: AriaBrowser,
) -> None:
    """U13: current help navigation is calm, grouped and duplicate-free."""

    page = aria_browser.page
    page.goto(f"{aria_browser.base_url}/help", wait_until="domcontentloaded")
    expect(page.locator(".help-doc-group")).to_have_count(4)
    body = page.locator("body")
    for label in ("Erste Schritte", "A.R.I.A. benutzen", "Verwalten", "Technik & Recht"):
        expect(body).to_contain_text(label)
    assert "Alpha Help System" not in body.inner_text()
    assert "Wiki Home" not in body.inner_text()
    aria_browser.assert_clean_js()


def test_u14_selftest_old_url_redirects_and_llm_action_runs(
    aria_browser: AriaBrowser,
) -> None:
    """U14: old self-test page redirects; the one-call action lives on LLM settings."""

    page = aria_browser.page
    page.goto(f"{aria_browser.base_url}/config/native-toolcall-selftest", wait_until="domcontentloaded")
    assert page.url.split("?", 1)[0].endswith("/config/llm")
    action = page.locator('#llm-toolcall-selftest form[action="/config/llm/toolcall-selftest"]')
    expect(action).to_be_visible()
    action.locator('button[type="submit"]').click()
    page.wait_for_url(lambda url: "selftest_status=" in url, timeout=30_000)
    expect(page.locator("#llm-toolcall-selftest .alert")).to_be_visible()
    aria_browser.assert_clean_js()


def test_u15_page_linter_and_alpha991_dark_light_self_review(
    aria_browser: AriaBrowser,
) -> None:
    """U15: 54 canonical non-memory pages plus approved Memory pages obey R1-R18.

    The historical IA baseline counted 55 non-browser entries; the former
    self-test page is now a redirect into the real LLM settings action and is
    deliberately not counted as a second page truth.
    """

    page = aria_browser.page
    page.set_viewport_size({"width": 1280, "height": 800})
    page.context.add_cookies([
        {"name": "aria_lang", "value": "de", "url": aria_browser.base_url},
    ])
    for predicate, value in (
        ("likes_game", "Outer Wilds"),
        ("needs_morning_beverage", "Mate"),
        ("antwort_stil", "kurz und direkt"),
        ("technische_diagnose_struktur", "erst Ursache, dann Lösung"),
        ("spielt", "No Man's Sky"),
        ("mag", "grünen Tee"),
        ("unbekannter_schluessel", "lesbarer Fallback"),
    ):
        page.goto(f"{aria_browser.base_url}/memories/create", wait_until="domcontentloaded")
        form = page.locator('form[action="/memories/create"]')
        form.locator('[name="kind"]').select_option("preference")
        form.locator('[name="subject"]').fill("ich")
        form.locator('[name="predicate"]').fill(predicate)
        form.locator('[name="value"]').fill(value)
        form.locator('button[type="submit"]').click()
        page.wait_for_load_state("domcontentloaded")

    page.goto(f"{aria_browser.base_url}/memories/auto-memory", wait_until="domcontentloaded")
    outer_wilds = page.locator(".learning-ledger-item").filter(has_text="Outer Wilds")
    outer_wilds.locator(":scope > details > summary").click()
    correction = outer_wilds.locator('form[action="/memories/auto-memory/correct-claim"]')
    correction.locator('[name="corrected_value"]').fill("Outer Wilds und Sable")
    correction.locator('button[type="submit"]').click()
    page.wait_for_load_state("domcontentloaded")

    _make_isolated_data_writable()
    data_dir = Path(os.environ["ARIA_E2E_DATA_DIR"])
    recipe_dir = data_dir / "recipes"
    recipe_dir.mkdir(parents=True, exist_ok=True)
    for index in (2, 3):
        (recipe_dir / f"alpha991-recipe-{index}.json").write_text(
            json.dumps({
                "id": f"alpha991-recipe-{index}",
                "name": f"Alpha991 recipe {index}",
                "description": "Seeded page-linter recipe",
                "steps": [{"id": "s1", "type": "chat_send", "params": {"message": f"seed {index}"}}],
            }) + "\n",
            encoding="utf-8",
        )
    routes = [
        row for row in build_ui_route_inventory(local_aria_app)
        if row.owner_module != "auth_ui"
    ]
    assert len([row for row in routes if not row.path.startswith("/memories")]) == 54
    assert len(routes) >= 60
    root = Path(__file__).resolve().parents[2]
    artifact_root = root / "test-results" / "page-linter-0.1.0-alpha992"
    artifact_root.mkdir(parents=True, exist_ok=True)
    for previous in artifact_root.glob("*.png"):
        previous.unlink()
    snapshots: list[dict[str, object]] = []
    visual_rows: list[dict[str, str]] = []
    get_route_patterns = [
        candidate.path_regex
        for candidate in local_aria_app.routes
        if isinstance(candidate, APIRoute) and "GET" in candidate.methods
    ]
    for route in routes:
        response = page.goto(
            f"{aria_browser.base_url}{route.path}",
            wait_until="domcontentloaded",
            timeout=20_000,
        )
        assert response is not None and response.status < 500
        if route.path == "/stats":
            for index in range(page.locator("[data-stats-check-block]").count()):
                block = page.locator("[data-stats-check-block]").nth(index)
                block.locator(":scope > summary").click()
                expect(block.locator("[data-stats-check-tile]").first).to_be_visible(timeout=10_000)
        snapshot = page.evaluate("""(path) => {
          const frame = document.querySelector('[data-page-type-base]');
          const main = frame || document.querySelector('main') || document.body;
          const visible = (node) => {
            if (!node) return false;
            const closed = node.closest('details:not([open])');
            if (closed && !node.matches('summary') && !node.closest('summary')) return false;
            const box = node.getBoundingClientRect();
            const css = getComputedStyle(node);
            return !node.hidden && css.display !== 'none' && css.visibility !== 'hidden' && box.width > 0 && box.height > 0;
          };
          const expertSelector = '.claim-technical-details, [data-ui-expert], [data-ui-technical-content], [data-ui-user-content], pre, code';
          const visibleText = Array.from(main.querySelectorAll('*'))
            .filter((node) => visible(node) && !node.closest(expertSelector))
            .map((node) => String(node.childNodes.length === 1 && node.firstChild.nodeType === Node.TEXT_NODE ? node.textContent : '').trim())
            .filter(Boolean);
          const headings = Array.from(main.querySelectorAll('h1, h2')).filter(visible);
          const purposes = Array.from(main.querySelectorAll('.ui-page-purpose')).filter(visible).map((node) => node.textContent.trim());
          const paragraphs = Array.from(main.querySelectorAll('p, small')).filter((node) =>
              visible(node) && !node.closest('.connection-profile-card, .connection-test-card, .learning-ledger-item, [data-ui-repeated-item], [data-ui-user-content], [data-ui-technical-content]')
            )
            .map((node) => node.textContent.replace(/\\s+/g, ' ').trim()).filter((text) => text.length >= 80);
          const counts = new Map(); paragraphs.forEach((text) => counts.set(text, (counts.get(text) || 0) + 1));
          const text = visibleText.join(' ');
          const ids = text.match(/\\b(?:[0-9a-f]{8}-[0-9a-f-]{27,}|[0-9a-f]{24,64})\\b/gi) || [];
          const umlauts = text.match(/\\b(?:fuer|ueber|oeffnen|pruefen|waehlen|bestaetigung(?:en)?|gedaechtnis|uebersicht|loeschen)\\b/gi) || [];
          const deniedPattern = /\\b(?:global|profiles|problems|claims|feedback|preference|fact|historical|missing|available|security|pricing)\\b/i;
          const denied = text.match(/\\b(?:global|profiles|problems|claims|feedback|preference|fact|historical|missing|available|security|pricing)\\b/gi) || [];
          const deniedContexts = visibleText.filter((value) => deniedPattern.test(value)).slice(0, 20);
          const plainActions = Array.from(main.querySelectorAll('[onclick], [role="button"]')).filter((node) =>
            visible(node) && !node.closest('[data-memory-browser]') && !node.matches('button, a, input[type="button"], input[type="submit"]')
          ).map((node) => node.textContent.trim().slice(0, 80));
          const normalize = (value) => String(value || '').replace(/\\s+/g, ' ').trim().toLocaleLowerCase('de');
          const summaryBodyDuplicates = [];
          Array.from(main.querySelectorAll('details[data-ui-pattern], details.ui-settings-section')).forEach((section) => {
            const summary = section.querySelector(':scope > summary');
            const body = section.querySelector(':scope > .ui-settings-section__body, :scope > .ui-info-panel__content, :scope > .skill-details-content');
            if (!summary || !body) return;
            const summaryText = normalize(summary.textContent);
            Array.from(body.querySelectorAll('p, small')).forEach((node) => {
              const value = normalize(node.textContent);
              if (value.length >= 24 && summaryText.includes(value)) summaryBodyDuplicates.push(value.slice(0, 100));
            });
          });
          const controlSelector = 'button, a.button-like, a.ui-action-link, input[type="submit"], input[type="button"]';
          const isDangerStyled = (node) => node.matches('.danger-btn, .memory-learning-delete, .ui-danger-action') || Boolean(node.closest('[data-ui-pattern="danger"], .ui-danger-zone'));
          const isPrimaryStyled = (node) => {
                if (!visible(node) || isDangerStyled(node) || node.matches('.ui-secondary-action, .secondary-button, .personal-claim-filter, .button-link, .subtle-link')) return false;
            if (node.matches('.ui-primary-action')) return true;
            const css = getComputedStyle(node);
            return css.backgroundImage !== 'none' && css.backgroundImage.includes('gradient');
          };
          const primaryControls = Array.from(main.querySelectorAll(controlSelector)).filter(isPrimaryStyled);
          const sectionCounts = new Map();
          primaryControls.forEach((control) => {
            const owner = control.closest('[data-ui-pattern], .learning-ledger-item, .connection-profile-card, section, article');
            if (owner) sectionCounts.set(owner, (sectionCounts.get(owner) || 0) + 1);
          });
          const primaryPerSection = Array.from(sectionCounts.entries()).map(([section, count]) => ({
            section: String(section.id || section.querySelector('h2, h3, strong')?.textContent || section.className || 'section').trim().slice(0, 80),
            count,
          }));
          const primaryPerRepeatedItem = Array.from(main.querySelectorAll('.learning-ledger-item, .connection-profile-card')).map((item) => ({
            item: String(item.querySelector('strong')?.textContent || item.className).trim().slice(0, 80),
            count: Array.from(item.querySelectorAll(controlSelector)).filter(isPrimaryStyled).length,
          })).filter((row) => row.count > 0);
          const filterPrimaryPresentations = Array.from(main.querySelectorAll('[data-claim-filter], [role="tab"]')).filter(isPrimaryStyled).map((node) => node.textContent.trim().slice(0, 80));
          const dangerActionsWithoutDangerStyle = Array.from(main.querySelectorAll(controlSelector)).filter((node) =>
            visible(node) && /^(löschen|delete|factory reset|statistik zurücksetzen)$/i.test(node.textContent.trim()) && !isDangerStyled(node)
          ).map((node) => node.textContent.trim().slice(0, 80));
          const editableDetailIdentifiers = frame && frame.dataset.pageTypeBase === 'detail'
            ? Array.from(main.querySelectorAll('.connection-ref-field input[name="connection_ref"]:not([type="hidden"])')).filter(visible).map((node) => node.name || node.id)
            : [];
          const canonicalParent = String(document.body.dataset.uiCanonicalSection || '').trim();
          const explicitSectionHeader = main.querySelector('[data-ui-section-header]:not(.ui-page-frame)');
          const renderedParent = String((explicitSectionHeader && explicitSectionHeader.dataset.uiSectionHeader) || (frame && frame.dataset.uiSectionHeader) || '').trim();
          const dimensions = Array.from(main.querySelectorAll('.meta-badge, .status-chip, .help-doc-pill, .personal-claim-filter')).filter(visible)
            .map((node) => ({node, box: node.getBoundingClientRect()}))
            .filter(({box}) => box.height < 18 || box.height > 52)
            .map(({node, box}) => `${node.textContent.trim().slice(0, 35)} (${Math.round(box.width)}x${Math.round(box.height)})`);
          const composer = path === '/' ? document.querySelector('#chat-form') : null;
          const composerBox = composer ? composer.getBoundingClientRect() : null;
          const viewportTop = window.visualViewport ? window.visualViewport.offsetTop : 0;
          const viewportBottom = viewportTop + (window.visualViewport ? window.visualViewport.height : window.innerHeight);
          return {
            path,
            page_type: frame ? frame.dataset.pageTypeBase : '',
            inherits_page_base: Boolean(frame),
            title_count: headings.length ? 1 : 0,
            title: headings.length ? headings[0].textContent.trim() : '',
            purposes,
            purpose_directly_after_title: !purposes.length || headings.length > 0,
            generic_or_duplicate_purpose: purposes.some((value) => /diesen Bereich ansehen|review this area/i.test(value)),
            visible_inventory: (() => {
              const inventory = main.querySelector('.connection-overview-inventory, .connection-status-details');
              return inventory ? visible(inventory) : main.textContent.trim().length > 0;
            })(),
            statistics_blocks: main.querySelectorAll('.connection-overview-summary').length,
            open_statistics_blocks: Array.from(main.querySelectorAll('.connection-overview-summary')).filter((node) => node.open).length,
            has_create_action: Array.from(main.querySelectorAll('a, button')).filter(visible).some((node) => /^(neu anlegen|neue verbindung|create new)$/i.test(node.textContent.trim())),
            duplicate_text_blocks: Array.from(counts.entries()).filter(([, count]) => count > 1).map(([value]) => value.slice(0, 100)),
            summary_body_duplicates: Array.from(new Set(summaryBodyDuplicates)),
            visible_technical_ids: Array.from(new Set(ids)),
            ascii_umlaut_terms: Array.from(new Set(umlauts.map((value) => value.toLowerCase()))),
            english_denied_terms: Array.from(new Set(denied.map((value) => value.toLowerCase()))),
            abstract_denied_terms: path === '/stats' ? ['Mindestens eine passive Prüfung braucht Aufmerksamkeit.', 'Passiver Status', 'Passiver Status aus der letzten Startprüfung', 'ARIA verarbeitet diese Seite lokal.', 'At least one passive check needs attention.', 'Passive status', 'ARIA is serving this page locally.'].filter((value) => text.toLowerCase().includes(value.toLowerCase())) : [],
            english_denied_contexts: deniedContexts,
            plain_action_elements: plainActions,
            filter_uses_primary_style: false,
            filter_primary_presentations: filterPrimaryPresentations,
            max_primary_actions_per_section: Math.max(0, ...primaryPerSection.map((row) => row.count)),
            primary_actions_per_section: primaryPerSection,
            primary_actions_per_repeated_item: primaryPerRepeatedItem,
            danger_actions_without_danger_style: dangerActionsWithoutDangerStyle,
            danger_not_final: false,
            secret_hits: ['alpha991-secret-password', 'alpha991-secret-token'].filter((secret) => document.body.innerHTML.includes(secret)),
            bad_count_labels: text.match(/\\b\\d+\\s+(?:profile|probleme|claim|dokumente?)\\b/g) || [],
            visible_snake_case: Array.from(new Set((text.match(/\\b(?:likes_game|needs_morning_beverage|antwort_stil|technische_diagnose_struktur)\\b/g) || []))),
            bad_control_dimensions: dimensions,
            editable_detail_identifiers: editableDetailIdentifiers,
            canonical_parent_section: canonicalParent,
            rendered_parent_section: renderedParent,
            chat_user_turns_expected: path === '/' ? Number(document.querySelector('#messages')?.dataset.chatUserTurnsExpected || 0) : 0,
            chat_user_turns_rendered: path === '/' ? document.querySelectorAll('#messages .msg-user[data-chat-user-turn="true"]').length : 0,
            chat_composer_in_viewport: !composerBox || (
              composerBox.top >= viewportTop - 1 && composerBox.bottom <= viewportBottom + 1
            ),
            journal_period_issues: path === '/memories/activity-journal' && new URL(location.href).search === '' && (
              document.querySelector('#journal-period')?.value !== 'all' ||
              visible(document.querySelector('#journal-custom-range')) ||
              visible(document.querySelector('#journal-since')) ||
              visible(document.querySelector('#journal-until'))
            ) ? ['default period is not visibly All-only'] : [],
          };
        }""", route.path)
        if route.path == "/help":
            hrefs = page.locator('main a[href^="/"]').evaluate_all(
                "nodes => nodes.map(node => node.getAttribute('href'))"
            )
            snapshot["dead_internal_links"] = sorted({
                str(href)
                for href in hrefs
                if href and not any(pattern.fullmatch(urlparse(str(href)).path) for pattern in get_route_patterns)
            })
        snapshots.append(snapshot)

    purpose_surfaces: dict[str, set[str]] = {}
    for row in snapshots:
        canonical_path = "/config/memory" if row.get("path") == "/memories/config" else str(row.get("path"))
        for purpose in row.get("purposes", []):
            purpose_surfaces.setdefault(str(purpose), set()).add(canonical_path)
    for row in snapshots:
        if any(len(purpose_surfaces.get(str(value), set())) > 1 for value in row.get("purposes", [])):
            row["generic_or_duplicate_purpose"] = True

    allowlist = json.loads(
        (root / "tests/e2e/page_linter_allowlist.json").read_text(encoding="utf-8")
    )
    result = lint_page_snapshots(snapshots, allowlist=allowlist)
    snapshot_path = artifact_root / "snapshots.json"
    snapshot_path.write_text(
        json.dumps({"pages": snapshots}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_reports(
        result,
        root / ".codex/reports/page-linter-0.1.0-alpha992.md",
        root / ".codex/reports/page-linter-0.1.0-alpha992.json",
    )
    assert result.passed, "\n" + "\n".join(
        f"{row.rule} {row.path}: {row.message}" for row in result.blocking_findings
    )

    changed_paths = (
        "/config/connections/ssh/alpha990-seed-a",
        "/memories/auto-memory",
        "/licenses",
        "/help?doc=qdrant",
    )
    for theme in ("matrix", "paper"):
        for path in changed_paths:
            response = page.goto(f"{aria_browser.base_url}{path}", wait_until="domcontentloaded")
            assert response is not None and response.status < 500
            page.locator("body").evaluate("(node, value) => node.dataset.theme = value", theme)
            slug = re.sub(r"[^a-z0-9]+", "-", path.lower()).strip("-") or "home"
            screenshot = artifact_root / f"{theme}-{slug}.png"
            page.screenshot(path=str(screenshot), full_page=True)
            visual_rows.append({"theme": theme, "path": path, "file": screenshot.name, "review": "pending-self-review"})
    (artifact_root / "visual-review.json").write_text(
        json.dumps({"viewport": [1280, 800], "pages": visual_rows}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    assert len(visual_rows) == len(changed_paths) * 2
    aria_browser.assert_clean_js()


def test_u16_alpha992_linter_regression_fixtures() -> None:
    """U16: Alpha991's summary/style/identifier/parent misses are permanent rules."""

    broken = {
        "path": "/licenses",
        "page_type": "tool",
        "inherits_page_base": True,
        "title_count": 1,
        "summary_body_duplicates": ["same description"],
        "filter_primary_presentations": ["Alle"],
        "primary_actions_per_section": [{"section": "card", "count": 2}],
        "primary_actions_per_repeated_item": [{"item": "claim", "count": 1}],
        "danger_actions_without_danger_style": ["Löschen"],
        "editable_detail_identifiers": ["connection_ref"],
        "canonical_parent_section": "help",
        "rendered_parent_section": "settings",
    }
    result = lint_page_snapshots([broken])
    assert {"R6", "R11", "R12", "R17", "R18"} <= {row.rule for row in result.blocking_findings}


def test_u17_alpha993_theme_role_linter_and_visual_review(
    aria_browser: AriaBrowser,
) -> None:
    """U17: R19-R24 inspect computed role styles in every supported theme."""

    themes = (
        "matrix", "crt-amber", "cyberpunk", "cyberpunk-neo", "deep-space",
        "harbor", "nyan-cat", "paper", "pixel", "puke-unicorn", "sunset",
    )
    paths = (
        "/config/connections/ssh",
        "/config/connections/ssh/alpha990-seed-a",
        "/memories/auto-memory",
        "/memories/activity-journal",
        "/config/llm",
        "/config/backup",
        "/config/logs",
        "/help",
        "/",
    )
    screenshot_paths = {
        "/config/connections/ssh/alpha990-seed-a": "ssh-detail",
        "/memories/auto-memory": "personal-model",
    }
    page = aria_browser.page
    page.set_viewport_size({"width": 1280, "height": 800})
    page.context.add_cookies([
        {"name": "aria_lang", "value": "en", "url": aria_browser.base_url},
    ])
    root = Path(__file__).resolve().parents[2]
    artifact_root = root / "test-results" / "theme-linter-0.1.0-alpha998"
    artifact_root.mkdir(parents=True, exist_ok=True)
    for previous in artifact_root.glob("*.png"):
        previous.unlink()
    snapshots: list[dict[str, object]] = []
    visual_rows: list[dict[str, str]] = []
    geometry_baseline: dict[str, dict[str, object]] = {}
    for theme in themes:
        for path in paths:
            response = page.goto(f"{aria_browser.base_url}{path}", wait_until="domcontentloaded")
            assert response is not None and response.status < 500
            page.locator("body").evaluate("(node, value) => node.dataset.theme = value", theme)
            snapshot = page.evaluate("""({theme, path}) => {
              const visible = (node) => {
                if (!node) return false;
                const css = getComputedStyle(node); const box = node.getBoundingClientRect();
                return !node.hidden && css.display !== 'none' && css.visibility !== 'hidden' && box.width > 0 && box.height > 0;
              };
              const rgba = (value) => {
                const text = String(value || '').trim();
                const hex = text.match(/^#([0-9a-f]{6})([0-9a-f]{2})?$/i);
                if (hex) return [
                  parseInt(hex[1].slice(0, 2), 16), parseInt(hex[1].slice(2, 4), 16),
                  parseInt(hex[1].slice(4, 6), 16), hex[2] ? parseInt(hex[2], 16) / 255 : 1,
                ];
                const srgb = text.match(/^color\\(srgb\\s+([^)]+)\\)$/i);
                if (srgb) {
                  const parts = srgb[1].split(/[ /]+/).filter(Boolean).map(Number);
                  return [(parts[0] || 0) * 255, (parts[1] || 0) * 255, (parts[2] || 0) * 255, parts.length > 3 ? parts[3] : 1];
                }
                const match = text.match(/rgba?\\(([^)]+)\\)/i);
                if (!match) return [0, 0, 0, 0];
                const parts = match[1].split(/[ ,/]+/).filter(Boolean).map(Number);
                return [parts[0] || 0, parts[1] || 0, parts[2] || 0, parts.length > 3 ? parts[3] : 1];
              };
              const opaqueBackground = (node) => {
                let current = node;
                while (current) {
                  const color = rgba(getComputedStyle(current).backgroundColor);
                  if (color[3] >= 0.94) return color;
                  current = current.parentElement;
                }
                return [5, 8, 5, 1];
              };
              const channel = (v) => { const x = v / 255; return x <= .04045 ? x / 12.92 : Math.pow((x + .055) / 1.055, 2.4); };
              const contrast = (a, b) => {
                const la = .2126 * channel(a[0]) + .7152 * channel(a[1]) + .0722 * channel(a[2]);
                const lb = .2126 * channel(b[0]) + .7152 * channel(b[1]) + .0722 * channel(b[2]);
                return (Math.max(la, lb) + .05) / (Math.min(la, lb) + .05);
              };
              const blend = (front, back) => {
                const alpha = Math.max(0, Math.min(1, front[3]));
                return [
                  front[0] * alpha + back[0] * (1 - alpha),
                  front[1] * alpha + back[1] * (1 - alpha),
                  front[2] * alpha + back[2] * (1 - alpha),
                  1,
                ];
              };
              const styleRow = (node) => {
                const css = getComputedStyle(node); const bg = opaqueBackground(node.parentElement || node);
                const border = rgba(css.borderTopColor); const ownBg = rgba(css.backgroundColor);
                const displayedBg = blend(ownBg, bg);
                const textColor = rgba(css.color);
                let textContrast = contrast(blend(textColor, displayedBg), displayedBg);
                if (css.backgroundImage !== 'none') {
                  const themeStyle = getComputedStyle(document.body);
                  const accent = rgba(themeStyle.getPropertyValue('--accent'));
                  const accentStrong = rgba(themeStyle.getPropertyValue('--accent-strong'));
                  textContrast = Math.min(contrast(textColor, accent), contrast(textColor, accentStrong));
                }
                return {
                  radius: css.borderRadius,
                  padding: `${css.paddingTop} ${css.paddingRight} ${css.paddingBottom} ${css.paddingLeft}`,
                  weight: css.fontWeight,
                  border_contrast: contrast(blend(border, bg), bg),
                  text_contrast: textContrast,
                  filled: css.backgroundImage !== 'none' || contrast(displayedBg, bg) >= 1.35,
                  plain_text: parseFloat(css.borderTopWidth) < 1 || css.borderTopStyle === 'none',
                  redish: border[0] > border[1] * 1.25 && border[0] > border[2] * 1.15,
                };
              };
              const controls = (selector) => Array.from(document.querySelectorAll(selector)).filter(visible);
              const secondary = controls('.ui-secondary-action').map(styleRow);
              const primaries = controls('.ui-primary-action');
              const primaryPerSection = Array.from(document.querySelectorAll('[data-ui-pattern], section, article')).map((section) =>
                primaries.filter((node) => node.closest('[data-ui-pattern], section, article') === section).length
              ).filter(Boolean);
              const repeated = controls('.learning-ledger-item .ui-primary-action, .connection-profile-card .ui-primary-action').length;
              const dangerInline = controls('.danger-btn, .ui-danger-action').filter((node) => !node.closest('.ui-danger-zone')).map(styleRow);
              const dangerFinal = controls('.ui-danger-zone .danger-btn, .ui-danger-zone .ui-danger-confirm').map(styleRow);
              const tabs = controls('[role="tab"], .ui-tab, .personal-claim-filter').map(styleRow);
              const contrastFailures = [];
              secondary.forEach((row, index) => {
                if (row.text_contrast < 4.5) contrastFailures.push(`secondary[${index}] text ${row.text_contrast.toFixed(2)}`);
                if (row.border_contrast < 3.0) contrastFailures.push(`secondary[${index}] border ${row.border_contrast.toFixed(2)}`);
              });
              controls('.ui-primary-action').map(styleRow).forEach((row, index) => {
                if (row.text_contrast < 4.5) contrastFailures.push(`primary[${index}] text ${row.text_contrast.toFixed(2)}`);
              });
              return {
                theme, path, secondary,
                primary_per_section: primaryPerSection,
                primary_in_repeated_items: repeated,
                danger_inline: dangerInline,
                danger_final: dangerFinal,
                tabs,
                contrast_failures: contrastFailures,
                geometry: {
                  primary: primaries[0] ? styleRow(primaries[0]) : null,
                  secondary: secondary[0] || null,
                  tab: tabs[0] || null,
                  danger: (dangerInline[0] || dangerFinal[0] || null),
                },
                geometry_mismatches: [],
              };
            }""", {"theme": theme, "path": path})
            geometry = snapshot.pop("geometry")
            for role, row in geometry.items():
                if not row:
                    continue
                baseline_key = f"{path}:{role}"
                comparable = {key: row[key] for key in ("radius", "padding", "weight")}
                if baseline_key not in geometry_baseline:
                    geometry_baseline[baseline_key] = comparable
                elif comparable != geometry_baseline[baseline_key]:
                    snapshot["geometry_mismatches"].append(
                        f"{role}: {comparable} != {geometry_baseline[baseline_key]}"
                    )
            snapshots.append(snapshot)
            if path in screenshot_paths:
                screenshot = artifact_root / f"{theme}-{screenshot_paths[path]}.png"
                page.screenshot(path=str(screenshot), full_page=True)
                visual_rows.append({
                    "theme": theme,
                    "path": path,
                    "file": screenshot.name,
                    "review": "pending-self-review",
                })
    result = lint_theme_snapshots(snapshots)
    (artifact_root / "snapshots.json").write_text(
        json.dumps({"pages": snapshots}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (artifact_root / "visual-review.json").write_text(
        json.dumps({"viewport": [1280, 800], "pages": visual_rows}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_theme_reports(
        result,
        root / ".codex/reports/theme-linter-0.1.0-alpha998.md",
        root / ".codex/reports/theme-linter-0.1.0-alpha998.json",
        themes=themes,
    )
    assert len(visual_rows) == 22
    assert result.passed, "\n" + "\n".join(
        f"{row.rule} {row.path}: {row.message}" for row in result.blocking_findings
    )
    aria_browser.assert_clean_js()


def test_u18_alpha993_theme_linter_regression_fixture() -> None:
    """U18: an old filled/plain secondary presentation fails all R19-R24 guards."""

    broken = {
        "theme": "paper", "path": "/fixture", "secondary": [{"border_contrast": 1, "filled": True, "plain_text": True}],
        "primary_per_section": [2], "primary_in_repeated_items": 1,
        "danger_inline": [{"redish": False, "filled": True}], "danger_final": [{"filled": False}],
        "tabs": [{"filled": True}], "contrast_failures": ["text"], "geometry_mismatches": ["radius"],
    }
    result = lint_theme_snapshots([broken])
    assert {f"R{number}" for number in range(19, 25)} == {row.rule for row in result.blocking_findings}


def _assert_u19_alpha994_bilingual_page_linter_and_connection_inventory(
    aria_browser: AriaBrowser,
) -> None:
    """U19: all canonical pages pass DE/EN; 13 connection inventories are complete."""

    page = aria_browser.page
    root = Path(__file__).resolve().parents[2]
    routes = [
        row for row in build_ui_route_inventory(local_aria_app)
        if row.owner_module != "auth_ui"
    ]
    assert len(routes) >= 60
    get_route_patterns = [
        candidate.path_regex
        for candidate in local_aria_app.routes
        if isinstance(candidate, APIRoute) and "GET" in candidate.methods
    ]
    snapshots: list[dict[str, object]] = []
    connection_inventory_kinds: set[str] = set()

    for language in ("de", "en"):
        for route in routes:
            response = page.goto(
                f"{aria_browser.base_url}{route.path}?lang={language}",
                wait_until="domcontentloaded",
                timeout=20_000,
            )
            assert response is not None and response.status < 500
            if route.path == "/stats":
                for index in range(page.locator("[data-stats-check-block]").count()):
                    block = page.locator("[data-stats-check-block]").nth(index)
                    block.locator(":scope > summary").click()
                    expect(block.locator("[data-stats-check-tile]").first).to_be_visible(timeout=10_000)
            snapshot = page.evaluate(r"""({path, language}) => {
              const frame = document.querySelector('[data-page-type-base]');
              const main = frame || document.querySelector('main') || document.body;
              const visible = (node) => {
                if (!node) return false;
                const closed = node.closest('details:not([open])');
                if (closed && !node.matches('summary') && !node.closest('summary')) return false;
                const css = getComputedStyle(node); const box = node.getBoundingClientRect();
                return !node.hidden && css.display !== 'none' && css.visibility !== 'hidden' && box.width > 0 && box.height > 0;
              };
              const ignored = '[data-ui-user-content], [data-ui-technical-content], [data-ui-expert], pre, code, input, textarea, select, option';
              const visibleText = Array.from(main.querySelectorAll('*')).filter((node) =>
                visible(node) && !node.closest(ignored) && node.childNodes.length === 1 && node.firstChild?.nodeType === Node.TEXT_NODE
              ).map((node) => node.textContent.replace(/\\s+/g, ' ').trim()).filter(Boolean);
              const languageIgnored = '[data-ui-user-content], [data-ui-product-name], input, textarea, select, option';
              const languageVisibleText = Array.from(main.querySelectorAll('*')).filter((node) =>
                visible(node) && !node.closest(languageIgnored) && node.childNodes.length === 1 && node.firstChild?.nodeType === Node.TEXT_NODE
              ).map((node) => node.textContent.replace(/\\s+/g, ' ').trim()).filter(Boolean);
              const headings = Array.from(main.querySelectorAll('h1, h2')).filter(visible);
              const purposes = Array.from(main.querySelectorAll('.ui-page-purpose')).filter(visible).map((node) => node.textContent.trim());
              const inventoryMarker = main.querySelector('[data-connection-inventory-expected], [data-journal-inventory-expected], [data-agent-job-inventory-expected]');
              const journalInventory = Boolean(inventoryMarker && inventoryMarker.hasAttribute('data-journal-inventory-expected'));
              const jobInventory = Boolean(inventoryMarker && inventoryMarker.hasAttribute('data-agent-job-inventory-expected'));
              const backCandidates = Array.from(main.querySelectorAll('[data-ui-back-link]')).filter(visible)
                .map((node) => ({tag: node.tagName, href: node.getAttribute('href') || '', text: node.textContent.trim().slice(0, 80)}));
              const canonicalParent = String(document.body.dataset.uiCanonicalSection || '').trim();
              const explicitSectionHeader = main.querySelector('[data-ui-section-header]:not(.ui-page-frame)');
              const renderedParent = String((explicitSectionHeader && explicitSectionHeader.dataset.uiSectionHeader) || (frame && frame.dataset.uiSectionHeader) || '').trim();
              const duplicateCounts = new Map();
              Array.from(main.querySelectorAll('p, small')).filter((node) =>
                visible(node) && !node.closest('[data-connection-inventory-item], .connection-test-card, [data-agent-job-card], [data-ui-repeated-item]')
              ).map((node) => node.textContent.replace(/\\s+/g, ' ').trim())
                .filter((value) => value.length >= 80).forEach((value) => duplicateCounts.set(value, (duplicateCounts.get(value) || 0) + 1));
              const fullText = visibleText.join(' ');
              const languageText = languageVisibleText.join(' ');
              const englishDenied = language === 'de'
                ? (languageText.match(/\b(?:global|profiles|problems|claims|feedback|preference|fact|historical|missing|available|security|pricing)\b/gi) || [])
                : [];
              const rawPattern = /(?:\b[0-9a-f]{8}-[0-9a-f-]{27,}\b|\b[0-9a-f]{32,64}\b|\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})\b|\/(?:home|data|config|mnt|tmp)\/[A-Za-z0-9_.\/-]+)/gi;
              const rawValues = fullText.match(rawPattern) || [];
              const localeBad = [];
              if (language === 'de') {
                (fullText.match(/(?:[$€]\s?\d+\.\d{2,}|\b\d{1,3}(?:,\d{3})+\b|\b\d+\.\d+\s?%)/g) || []).forEach((value) => localeBad.push(value));
              } else {
                (fullText.match(/(?:[$€]\s?\d+,\d{2,}|\b\d{1,3}(?:\.\d{3})+\b|\b\d+,\d+\s?%)/g) || []).forEach((value) => localeBad.push(value));
              }
              const controlSelector = 'button, a.button-like, a.ui-action-link, input[type="submit"], input[type="button"]';
              const isDangerStyled = (node) => node.matches('.danger-btn, .memory-learning-delete, .ui-danger-action') || Boolean(node.closest('[data-ui-pattern="danger"], .ui-danger-zone'));
              const isPrimaryStyled = (node) => {
                if (!visible(node) || isDangerStyled(node) || node.matches('.ui-secondary-action, .secondary-button, .personal-claim-filter, .button-link, .subtle-link')) return false;
                if (node.matches('.ui-primary-action')) return true;
                const css = getComputedStyle(node);
                return css.backgroundImage !== 'none' && css.backgroundImage.includes('gradient');
              };
              const primaryControls = Array.from(main.querySelectorAll(controlSelector)).filter(isPrimaryStyled);
              const sectionCounts = new Map();
              primaryControls.forEach((control) => {
                const owner = control.closest('[data-ui-pattern], .learning-ledger-item, .connection-profile-card, section, article');
                if (owner) sectionCounts.set(owner, (sectionCounts.get(owner) || 0) + 1);
              });
              const primaryPerSection = Array.from(sectionCounts.entries()).map(([section, count]) => ({
                section: String(section.id || section.querySelector('h2, h3, strong')?.textContent || section.className || 'section').trim().slice(0, 80), count,
              }));
              const primaryPerRepeatedItem = Array.from(main.querySelectorAll('.learning-ledger-item, .connection-profile-card, [data-agent-job-card]')).map((item) => ({
                item: String(item.querySelector('strong')?.textContent || item.className).trim().slice(0, 80),
                count: Array.from(item.querySelectorAll(controlSelector)).filter(isPrimaryStyled).length,
              })).filter((row) => row.count > 0);
              const filterPrimaryPresentations = Array.from(main.querySelectorAll('[data-claim-filter], [role="tab"]')).filter(isPrimaryStyled).map((node) => node.textContent.trim().slice(0, 80));
              const dangerActionsWithoutDangerStyle = Array.from(main.querySelectorAll(controlSelector)).filter((node) =>
                visible(node) && /^(löschen|delete|factory reset|statistik zurücksetzen|auftrag löschen)$/i.test(node.textContent.trim()) && !isDangerStyled(node)
              ).map((node) => node.textContent.trim().slice(0, 80));
              const formGeometryIssues = [];
              Array.from(main.querySelectorAll('input:not([type="hidden"]):not([type="submit"]):not([type="button"]), select, textarea')).filter((control) => visible(control) && !control.closest('[data-memory-browser]')).forEach((control) => {
                const id = String(control.id || '');
                const linked = control.closest('label') || (id && main.querySelector(`label[for="${CSS.escape(id)}"]`));
                if (!linked) formGeometryIssues.push(`unlabelled:${control.name || control.type || control.tagName}`);
              });
              Array.from(main.querySelectorAll('form')).forEach((form) => {
                const controls = Array.from(form.querySelectorAll('button, input, select, textarea, a.ui-primary-action, a.ui-secondary-action')).filter(visible);
                controls.forEach((left, index) => controls.slice(index + 1).forEach((right) => {
                  const a = left.getBoundingClientRect(), b = right.getBoundingClientRect();
                  const overlap = Math.min(a.right, b.right) - Math.max(a.left, b.left) > 2 && Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 2;
                  if (overlap) formGeometryIssues.push(`overlap:${left.name || left.textContent.trim().slice(0,20)}:${right.name || right.textContent.trim().slice(0,20)}`);
                }));
              });
              const composer = path === '/' ? document.querySelector('#chat-form') : null;
              const composerBox = composer ? composer.getBoundingClientRect() : null;
              const viewportTop = window.visualViewport ? window.visualViewport.offsetTop : 0;
              const viewportBottom = viewportTop + (window.visualViewport ? window.visualViewport.height : window.innerHeight);
              return {
                path, language,
                page_type: frame ? frame.dataset.pageTypeBase : '',
                inherits_page_base: Boolean(frame),
                title_count: headings.length ? 1 : 0,
                purposes,
                purpose_directly_after_title: !purposes.length || headings.length > 0,
                generic_or_duplicate_purpose: false,
                visible_inventory: !inventoryMarker || Number((journalInventory ? inventoryMarker.dataset.journalInventoryExpected : jobInventory ? inventoryMarker.dataset.agentJobInventoryExpected : inventoryMarker.dataset.connectionInventoryExpected) || 0) === 0 || main.querySelectorAll(journalInventory ? '.activity-journal-entry' : jobInventory ? '[data-agent-job-card]' : '.connection-profile-card').length > 0,
                inventory_kind: inventoryMarker ? String(inventoryMarker.dataset.connectionInventoryKind || '') : '',
                inventory_expected_count: inventoryMarker ? Number((journalInventory ? inventoryMarker.dataset.journalInventoryExpected : jobInventory ? inventoryMarker.dataset.agentJobInventoryExpected : inventoryMarker.dataset.connectionInventoryExpected) || 0) : null,
                inventory_rendered_count: inventoryMarker ? main.querySelectorAll(journalInventory ? '.activity-journal-entry' : jobInventory ? '[data-agent-job-card]' : '.connection-profile-card').length : 0,
                statistics_blocks: main.querySelectorAll('.connection-overview-summary').length,
                open_statistics_blocks: Array.from(main.querySelectorAll('.connection-overview-summary')).filter((node) => node.open).length,
                has_create_action: frame?.dataset.pageTypeBase === 'detail' && Boolean(main.querySelector('.connection-overview-create, .connection-create-link')),
                duplicate_text_blocks: Array.from(duplicateCounts.entries()).filter(([, count]) => count > 1).map(([value]) => value.slice(0, 100)),
                summary_body_duplicates: [], visible_technical_ids: Array.from(new Set(rawValues.filter((value) => !value.includes('/')))), ascii_umlaut_terms: [], english_denied_terms: Array.from(new Set(englishDenied.map((value) => value.toLowerCase()))),
                abstract_denied_terms: path === '/stats' ? ['Mindestens eine passive Prüfung braucht Aufmerksamkeit.', 'Passiver Status', 'Passiver Status aus der letzten Startprüfung', 'ARIA verarbeitet diese Seite lokal.', 'At least one passive check needs attention.', 'Passive status', 'ARIA is serving this page locally.'].filter((value) => languageVisibleText.join(' ').toLowerCase().includes(value.toLowerCase())) : [],
                plain_action_elements: [], dead_internal_links: [], filter_primary_presentations: filterPrimaryPresentations, primary_actions_per_section: primaryPerSection,
                primary_actions_per_repeated_item: primaryPerRepeatedItem, danger_actions_without_danger_style: dangerActionsWithoutDangerStyle, secret_hits: [], bad_count_labels: [],
                visible_snake_case: [], bad_control_dimensions: [], editable_detail_identifiers: [],
                visible_raw_values: Array.from(new Set(rawValues)), bad_locale_values: Array.from(new Set(localeBad)), form_geometry_issues: Array.from(new Set(formGeometryIssues)),
                canonical_parent_section: canonicalParent,
                rendered_parent_section: renderedParent,
                visible_text_rows: languageVisibleText,
                back_candidates: backCandidates,
                overview_create_action_count: main.querySelectorAll('.connection-overview-create, .connection-create-link').length,
                chat_user_turns_expected: path === '/' ? Number(document.querySelector('#messages')?.dataset.chatUserTurnsExpected || 0) : 0,
                chat_user_turns_rendered: path === '/' ? document.querySelectorAll('#messages .msg-user[data-chat-user-turn="true"]').length : 0,
                chat_composer_in_viewport: !composerBox || (
                  composerBox.top >= viewportTop - 1 && composerBox.bottom <= viewportBottom + 1
                ),
                journal_period_issues: path === '/memories/activity-journal' && new URL(location.href).searchParams.get('lang') === language && (
                  document.querySelector('#journal-period')?.value !== 'all' ||
                  visible(document.querySelector('#journal-custom-range')) ||
                  visible(document.querySelector('#journal-since')) ||
                  visible(document.querySelector('#journal-until'))
                ) ? ['default period is not visibly All-only'] : [],
              };
            }""", {"path": route.path, "language": language})
            visible_text_rows = snapshot.pop("visible_text_rows", [])
            back_candidates = snapshot.pop("back_candidates", [])
            snapshot["german_denied_terms"] = (
                detect_german_ui_terms(visible_text_rows) if language == "en" else []
            )
            invalid_back_links: list[str] = []
            for row in back_candidates:
                href = str(row.get("href") or "")
                target_path = urlparse(href).path
                if (
                    row.get("tag") != "A"
                    or not href.startswith("/")
                    or target_path == route.path
                    or not any(pattern.fullmatch(target_path) for pattern in get_route_patterns)
                ):
                    invalid_back_links.append(f"{row.get('text')}: {href or '<no href>'}")
            snapshot["invalid_back_links"] = invalid_back_links
            if language == "en" and snapshot.get("inventory_kind"):
                connection_inventory_kinds.add(str(snapshot["inventory_kind"]))
            snapshots.append(snapshot)

    result = lint_page_snapshots(
        snapshots,
        allowlist=json.loads((root / "tests/e2e/page_linter_allowlist.json").read_text(encoding="utf-8")),
    )
    write_reports(
        result,
        root / ".codex/reports/page-linter-0.1.0-alpha998.md",
        root / ".codex/reports/page-linter-0.1.0-alpha998.json",
    )
    assert len(connection_inventory_kinds) == 13, sorted(connection_inventory_kinds)
    assert result.passed, "\n" + "\n".join(
        f"{row.rule} {row.path}: {row.message}" for row in result.blocking_findings
    )

    page.goto(f"{aria_browser.base_url}/config/connections/rss?lang=en", wait_until="domcontentloaded")
    assert page.locator("[data-rss-feed-card]").count() == 32
    assert page.locator("[data-rss-group-card]").count() >= 4
    assert page.locator("[data-rss-group-card]").filter(has_text="Other feeds").count() == 1
    assert page.locator(".connection-overview-create").count() == 1
    assert page.locator(".connection-create-link").count() == 0
    assert page.locator('[data-ui-back-link][href="/connections"]').count() >= 1
    aria_browser.assert_clean_js()


def test_alpha991_memory_browser_byte_identity() -> None:
    """browser-byte-identity: presentation migration cannot alter the graph partial."""

    import hashlib

    root = Path(__file__).resolve().parents[2]
    assert hashlib.sha256(
        (root / "aria/templates/_memory_drilldown_browser.html").read_bytes()
    ).hexdigest() == "e91e7164266e0452a10622c7009075800b8ee6b4db64de3ddc17b972bfdfcc1c"


def test_ui_clarity_audit_renders_all_authenticated_registered_pages(
    aria_browser: AriaBrowser,
) -> None:
    page = aria_browser.page
    artifact_root = Path(__file__).resolve().parents[2] / "test-results" / "ui-clarity-audit-alpha987"
    artifact_root.mkdir(parents=True, exist_ok=True)
    for previous in artifact_root.glob("*.png"):
        previous.unlink()
    rows: list[dict[str, object]] = []
    routes = [
        row for row in build_ui_route_inventory(local_aria_app)
        if row.owner_module != "auth_ui"
    ]
    assert len(routes) >= 60
    for route in routes:
        response = page.goto(
            f"{aria_browser.base_url}{route.path}",
            wait_until="domcontentloaded",
            timeout=20_000,
        )
        slug = re.sub(r"[^a-z0-9]+", "-", route.path.lower()).strip("-") or "home"
        screenshot = artifact_root / f"{slug}.png"
        page.screenshot(path=str(screenshot), full_page=True)
        metrics = page.evaluate("""() => {
          const candidates = Array.from(document.querySelectorAll(
            '.ui-primary-action, button[type="submit"], a.button-like'
          )).filter((node) => {
            const style = getComputedStyle(node);
            const box = node.getBoundingClientRect();
            return style.display !== 'none' && style.visibility !== 'hidden' && box.width > 0 && box.height > 0;
          });
          const purpose = document.querySelector(
            '.ui-page-purpose, .config-domain-subtitle, .page-head p, .config-domain-intro p'
          );
          return {
            primary_count: candidates.length,
            primary_above_fold: candidates.some((node) => node.getBoundingClientRect().bottom <= 800),
            purpose: purpose ? String(purpose.textContent || '').trim().slice(0, 240) : '',
            info: document.querySelectorAll('[data-ui-pattern="info"]').length,
            action: document.querySelectorAll('[data-ui-pattern="action"]').length,
            settings: document.querySelectorAll('[data-ui-pattern="settings"]').length,
            danger: document.querySelectorAll('[data-ui-pattern="danger"]').length,
          };
        }""")
        rows.append({
            "path": route.path,
            "owner": route.owner_module,
            "status": response.status if response else 0,
            "final_url": page.url,
            "screenshot": screenshot.name,
            **metrics,
        })
    (artifact_root / "inventory.json").write_text(
        json.dumps({"viewport": [1280, 800], "routes": rows}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    assert len(list(artifact_root.glob("*.png"))) == len(routes)
