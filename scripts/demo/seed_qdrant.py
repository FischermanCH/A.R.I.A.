#!/usr/bin/env python3
"""Seed only the isolated demo Qdrant endpoint with fictitious points."""

from __future__ import annotations

import argparse
import json
import time
import urllib.request


def _decode_response(body: bytes) -> dict:
    """Accept Qdrant's JSON APIs and its plain-text health endpoint."""
    if not body:
        return {}
    try:
        decoded = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"text": body.decode("utf-8", errors="replace")}
    return decoded if isinstance(decoded, dict) else {"value": decoded}


def request(base: str, path: str, *, method: str = "GET", payload: dict | None = None) -> dict:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(base.rstrip("/") + path, data=body, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=5) as response:
        return _decode_response(response.read())


def create(base: str, name: str, points: list[dict]) -> None:
    try:
        request(base, f"/collections/{name}", method="PUT", payload={"vectors": {"size": 3, "distance": "Cosine"}})
    except Exception:
        pass
    request(base, f"/collections/{name}/points?wait=true", method="PUT", payload={"points": points})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8091")
    args = parser.parse_args()
    deadline = time.monotonic() + 45
    while True:
        try:
            request(args.url, "/healthz")
            break
        except Exception:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.25)
    create(args.url, "aria_preferences_demo-admin", [{"id": 1001, "vector": [0.2, 0.1, 0.3], "payload": {
        "user_id": "demo-admin", "type": "preference", "text": "concise structured answers",
        "source": "personal_claim", "personal_claim_contract": "personal_claim_v1",
        "claim_id": "demo-preference-1", "claim_key": "demo-preference-style",
        "claim_kind": "preference", "claim_subject": "user", "claim_predicate": "prefers",
        "claim_value": "concise structured answers", "claim_scope": "global", "claim_scope_ref": "",
        "claim_confidence": 1.0, "claim_authority": "explicit_user", "claim_risk": "low",
        "claim_status": "active", "claim_presented_count": 6, "claim_used_count": 4,
        "claim_changed_outcome_count": 2, "claim_positive_feedback_count": 2,
        "claim_negative_feedback_count": 0, "claim_last_used_at": "2026-10-10T12:00:00Z",
    }}])
    create(args.url, "aria_facts_demo-admin", [{"id": 1002, "vector": [0.1, 0.3, 0.2], "payload": {
        "user_id": "demo-admin", "type": "fact", "text": "The demo workspace is fictional.",
        "source": "personal_claim", "personal_claim_contract": "personal_claim_v1",
        "claim_id": "demo-fact-1", "claim_key": "demo-fact-workspace", "claim_kind": "fact",
        "claim_subject": "user", "claim_predicate": "uses", "claim_value": "a fictional demo workspace",
        "claim_scope": "global", "claim_scope_ref": "", "claim_confidence": 1.0,
        "claim_authority": "explicit_user", "claim_risk": "low", "claim_status": "active",
    }}])
    create(args.url, "aria_docs_demo-admin_handbook", [
        {"id": 2001, "vector": [0.3, 0.2, 0.1], "payload": {"user_id": "demo-admin", "type": "knowledge", "source": "document", "document_id": "demo-handbook", "title": "Synthetic Demo Handbook", "text": "This fictitious handbook explains the public ARIA demo without personal data.", "chunk_index": 0}},
        {"id": 2002, "vector": [0.2, 0.3, 0.1], "payload": {"user_id": "demo-admin", "type": "knowledge", "source": "document", "document_id": "demo-guide", "title": "Workshop Checklist", "text": "A synthetic checklist for the example workshop connection.", "chunk_index": 0}},
    ])
    create(args.url, "aria_notes_demo-admin", [{"id": 3001, "vector": [0.1, 0.2, 0.3], "payload": {"user_id": "demo-admin", "type": "note", "source": "manual_ui", "title": "Demo note", "text": "A completely fictitious note for screenshots."}}])


if __name__ == "__main__":
    main()
