from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUSY_STATE = ROOT / "aria" / "static" / "app-busy-state.js"


def _run_node(assertions: str) -> None:
    script = f"""
require({str(BUSY_STATE)!r});
const assert = require("node:assert/strict");
const classes = new Set();
const classList = {{
  toggle(name, active) {{ active ? classes.add(name) : classes.delete(name); }},
  contains(name) {{ return classes.has(name); }},
}};
const timers = new Map();
let timerId = 0;
const controller = globalThis.AriaBusyState.create({{
  body: {{ classList }},
  brandMark: {{ classList }},
  delayMs: 220,
  setTimeout(callback) {{ timerId += 1; timers.set(timerId, callback); return timerId; }},
  clearTimeout(id) {{ timers.delete(id); }},
}});
function flushTimers() {{
  const callbacks = Array.from(timers.values());
  timers.clear();
  callbacks.forEach((callback) => callback());
}}
{assertions}
"""
    subprocess.run(["node", "-e", script], cwd=ROOT, check=True)


def test_named_busy_owner_is_idempotent_and_stops_after_response() -> None:
    _run_node(
        """
controller.begin("chat-request");
controller.begin("chat-request");
assert.equal(controller.ownerCount(), 1);
flushTimers();
assert.equal(classes.has("logo-busy"), true);
assert.equal(controller.end("chat-request"), true);
assert.equal(controller.end("chat-request"), false);
assert.equal(controller.ownerCount(), 0);
assert.equal(classes.has("logo-busy"), false);
assert.equal(classes.has("app-busy"), false);
"""
    )


def test_one_completed_owner_does_not_stop_parallel_work() -> None:
    _run_node(
        """
controller.begin("chat-request", { immediate: true });
controller.begin("other-request", { immediate: true });
controller.end("chat-request");
assert.equal(controller.ownerCount(), 1);
assert.equal(classes.has("logo-busy"), true);
controller.end("other-request");
assert.equal(classes.has("logo-busy"), false);
"""
    )


def test_reset_clears_pending_and_visible_busy_state() -> None:
    _run_node(
        """
controller.begin("chat-request");
assert.equal(timers.size, 1);
controller.reset();
assert.equal(timers.size, 0);
assert.equal(controller.ownerCount(), 0);
assert.equal(classes.has("logo-busy"), false);
"""
    )


def test_templates_bind_chat_and_htmx_to_owned_busy_lifecycles() -> None:
    base = (ROOT / "aria" / "templates" / "base.html").read_text(encoding="utf-8")
    chat = (ROOT / "aria" / "templates" / "chat.html").read_text(encoding="utf-8")

    assert "window.ariaSetBusyOwner = setBusyOwner" in base
    assert 'document.body.addEventListener("htmx:afterRequest", finishHtmxRequest)' in base
    assert 'document.body.addEventListener("htmx:responseError", finishHtmxRequest)' in base
    assert 'if (event.defaultPrevented) return;' in base
    assert 'const chatBusyOwner = "chat-request";' in chat
    assert "window.ariaSetBusyOwner(chatBusyOwner, isBusy, false)" in chat
    assert "setBusy(false);" in chat


def test_chat_template_replaces_request_local_pending_assistant_instead_of_tail_append() -> None:
    chat = (ROOT / "aria" / "templates" / "chat.html").read_text(encoding="utf-8")

    assert "pendingAssistantNode.insertAdjacentHTML(\"beforebegin\", assistantHtml);" in chat
    assert "pendingAssistantNode.remove();" in chat
    assert "messages.insertAdjacentHTML(\"beforeend\", assistantHtml);" not in chat
