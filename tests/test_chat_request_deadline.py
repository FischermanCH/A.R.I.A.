from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEADLINE_SCRIPT = ROOT / "aria" / "static" / "chat-request-deadline.js"
CHAT_TEMPLATE = ROOT / "aria" / "templates" / "chat.html"


def _run_node(assertions: str) -> None:
    script = f"""
const deadlineApi = require({str(DEADLINE_SCRIPT)!r});
const assert = require("node:assert/strict");
let nowMs = 1000;
let aborted = 0;
let timerId = 0;
const timers = new Map();
const cleared = [];
const lifecycle = deadlineApi.createRequestDeadline({{
  controller: {{ abort() {{ aborted += 1; }} }},
  timeoutMs: 90000,
  now() {{ return nowMs; }},
  setTimeout(callback, delay) {{ timerId += 1; timers.set(timerId, {{ callback, delay }}); return timerId; }},
  clearTimeout(id) {{ cleared.push(id); timers.delete(id); }},
}});
{assertions}
"""
    subprocess.run(["node", "-e", script], cwd=ROOT, check=True)


def test_normal_request_records_monotonic_browser_phases() -> None:
    _run_node(
        """
assert.equal(timers.size, 1);
assert.equal(Array.from(timers.values())[0].delay, 90000);
nowMs = 1100;
assert.equal(lifecycle.checkpoint("headers"), true);
nowMs = 1250;
assert.equal(lifecycle.checkpoint("body"), true);
nowMs = 1275;
assert.equal(lifecycle.checkpoint("dom"), true);
const snapshot = lifecycle.snapshot();
assert.equal(snapshot.headersMs, 100);
assert.equal(snapshot.bodyMs, 250);
assert.equal(snapshot.domMs, 275);
assert.equal(snapshot.totalMs, 275);
assert.equal(snapshot.deadlineMs, 90000);
assert.equal(snapshot.timedOut, false);
lifecycle.finish();
assert.equal(timers.size, 0);
assert.equal(cleared.length, 1);
assert.equal(aborted, 0);
"""
    )


def test_late_response_is_rejected_even_when_timeout_callback_was_throttled() -> None:
    _run_node(
        """
nowMs = 92001;
assert.equal(lifecycle.checkpoint("headers"), false);
assert.equal(lifecycle.timedOut(), true);
assert.equal(aborted, 1);
assert.equal(lifecycle.snapshot().totalMs, 91001);
"""
    )


def test_deadline_callback_aborts_once() -> None:
    _run_node(
        """
nowMs = 91000;
Array.from(timers.values())[0].callback();
assert.equal(lifecycle.timedOut(), true);
assert.equal(aborted, 1);
assert.equal(lifecycle.checkpoint("headers"), false);
assert.equal(aborted, 1);
"""
    )


def test_catch_path_detects_elapsed_deadline_when_timer_was_throttled() -> None:
    _run_node(
        """
nowMs = 92001;
assert.equal(lifecycle.timedOut(), true);
assert.equal(aborted, 1);
assert.equal(lifecycle.timedOut(), true);
assert.equal(aborted, 1);
"""
    )


def test_chat_template_enforces_deadline_and_stops_queue_after_timeout() -> None:
    template = CHAT_TEMPLATE.read_text(encoding="utf-8")

    assert 'src="/static/chat-request-deadline.js?v=' in template
    assert "createRequestDeadline" in template
    assert "chatRequestDeadlineMs = 90000" in template
    assert 'requestLifecycle.checkpoint("headers")' in template
    assert 'requestLifecycle.checkpoint("body")' in template
    assert 'requestLifecycle.checkpoint("dom")' in template
    assert "appendClientRequestTiming" in template
    assert "requestTimedOut" in template
    assert "if (!requestTimedOut)" in template
    assert "startNextQueuedPrompt();" in template
