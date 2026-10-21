#!/usr/bin/env python3
"""Deterministic offline chat-completions stub for the isolated ARIA demo.

It never contacts a provider. Every answer is fixed, fictitious demo content so
LLM buttons (guardrail draft, connection metadata) render real ARIA UI states
for screenshots. Requests are told apart only by the fixed ARIA system prompt
of the calling feature, never by user wording.
"""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import time
from typing import Any


GUARDRAIL_DRAFT = {
    "de": {
        "ref": "demo-kein-sudo",
        "kind": "ssh_command",
        "connection_kinds": ["ssh"],
        "title": "Keine sudo-Befehle",
        "description": "Blockiert Befehle mit Root-Rechten auf den Demo-Linux-Hosts.",
        "allow_terms": [],
        "deny_terms": ["sudo", "su -", "doas"],
        "scope_summary": "An SSH-Verbindungen zu Ubuntu-Hosts anhängen, z. B. Demo Workshop.",
        "review_notes": [
            "Prüfen, ob Wartungsrezepte ohne Root-Rechte auskommen.",
            "Allow-Liste bleibt leer, weil nur blockiert werden soll.",
        ],
        "examples": [
            {"text": "sudo apt upgrade", "expected": "block", "reason": "verlangt Root-Rechte"},
            {"text": "uptime", "expected": "allow", "reason": "nur lesend"},
        ],
        "confidence": 0.92,
    },
    "en": {
        "ref": "demo-no-sudo",
        "kind": "ssh_command",
        "connection_kinds": ["ssh"],
        "title": "No sudo commands",
        "description": "Blocks commands that need root privileges on the demo Linux hosts.",
        "allow_terms": [],
        "deny_terms": ["sudo", "su -", "doas"],
        "scope_summary": "Attach to SSH connections to Ubuntu hosts, e.g. Demo Workshop.",
        "review_notes": [
            "Check that maintenance recipes work without root privileges.",
            "The allow list stays empty because the rule only blocks.",
        ],
        "examples": [
            {"text": "sudo apt upgrade", "expected": "block", "reason": "needs root privileges"},
            {"text": "uptime", "expected": "allow", "reason": "read-only"},
        ],
        "confidence": 0.92,
    },
}
CONNECTION_METADATA = {
    "de": {
        "title": "Demo Workshop",
        "description": "Fiktiver Werkstatt-Server mit Docker-Diensten und Monitoring für die Demo.",
        "aliases": ["werkstatt", "workshop-server", "docker-host"],
        "tags": ["linux", "docker", "monitoring", "demo"],
    },
    "en": {
        "title": "Demo Workshop",
        "description": "Fictitious workshop server with Docker services and monitoring for the demo.",
        "aliases": ["workshop", "workshop-server", "docker-host"],
        "tags": ["linux", "docker", "monitoring", "demo"],
    },
}
FALLBACK = {
    "de": "Demo-Antwort: Diese Demo nutzt ein Offline-Modell ohne Provider.",
    "en": "Demo answer: this demo uses an offline model without a provider.",
}


def _language(messages: list[dict[str, Any]]) -> str:
    text = "\n".join(str(row.get("content", "")) for row in messages)
    return "de" if ("Language for user-facing fields: German" in text or "Preferred language: de" in text) else "en"


def answer(messages: list[dict[str, Any]]) -> str:
    system = next((str(row.get("content", "")) for row in messages if row.get("role") == "system"), "")
    lang = _language(messages)
    if system.startswith("You create security guardrail drafts for ARIA."):
        return json.dumps(GUARDRAIL_DRAFT[lang], ensure_ascii=False)
    if system.startswith("You generate concise metadata for an"):
        return json.dumps(CONNECTION_METADATA[lang], ensure_ascii=False)
    return FALLBACK[lang]


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/").endswith("/models"):
            self._send(200, {"object": "list", "data": [{"id": "demo-offline", "object": "model", "owned_by": "aria-demo"}]})
        else:
            self._send(200, {"status": "ok"})

    def do_POST(self) -> None:  # noqa: N802
        if not self.path.rstrip("/").endswith("/chat/completions"):
            self._send(404, {"error": {"message": "not found"}})
            return
        try:
            request = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        except ValueError:
            self._send(400, {"error": {"message": "invalid json"}})
            return
        messages = request.get("messages") if isinstance(request.get("messages"), list) else []
        content = answer(messages)
        prompt_tokens = sum(len(str(row.get("content", ""))) for row in messages) // 4
        completion_tokens = len(content) // 4
        self._send(200, {
            "id": "chatcmpl-demo",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": str(request.get("model") or "demo-offline"),
            "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens, "total_tokens": prompt_tokens + completion_tokens},
        })

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8099)
    args = parser.parse_args()
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
