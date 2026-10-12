from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from aria.modules.configuration_foundations.config import Settings
from aria.modules.config_ui.page_linter import lint_page_snapshots
from aria.modules.stats_ui import routes as stats_routes
from aria.modules.stats_ui.routes import _build_pricing_meta, _build_stats_check_blocks


ROOT = Path(__file__).resolve().parents[1]

ALPHA983_REQUIRED_CHECKS = {
    "prompts",
    "qdrant_startup",
    "chat_llm",
    "embeddings",
    "aria_runtime",
    "model_stack",
    "qdrant_live",
    "security_store",
    "logs",
    "connections",
    "mcp_servers",
    "release",
    "module_registry",
    "model_gateway",
    "pricing",
    "cost_tracking",
    "recipe_memory",
    "updates",
}


def _fixture(tmp_path: Path):
    settings = Settings.model_validate(
        {
            "llm": {
                "model": "anthropic/claude-sonnet-5",
                "api_base": "http://chat-gateway.example/v1",
            },
            "web_llm": {
                "enabled": True,
                "model": "openai/gpt-5-search",
                "api_base": "http://web-gateway.example/v1",
                "capability_verified_at": "2026-10-12T01:00:00Z",
            },
            "embeddings": {
                "model": "openai/text-embedding-3-small",
                "api_base": "http://embed-gateway.example/v1",
            },
            "token_tracking": {
                "enabled": True,
                "log_file": str(tmp_path / "tokens.jsonl"),
            },
            "security": {"enabled": False},
            "mcp_servers": {
                "blender-mac-ronny": {
                    "enabled": True,
                    "url": "http://mcp.example/sse",
                }
            },
            "pricing": {
                "enabled": True,
                "chat_models": {
                    "anthropic/claude-sonnet-5": {
                        "input_per_million": 1.0,
                        "output_per_million": 2.0,
                    },
                    "openai/gpt-5-search": {
                        "input_per_million": 3.0,
                        "output_per_million": 4.0,
                    },
                },
                "embedding_models": {
                    "openai/text-embedding-3-small": {"input_per_million": 0.1},
                },
            },
        }
    )
    meter = object()
    embedder = SimpleNamespace(usage_meter=meter, model="openai/text-embedding-3-small")
    pipeline = SimpleNamespace(
        usage_meter=meter,
        llm_client=SimpleNamespace(usage_meter=meter, model="anthropic/claude-sonnet-5"),
        embedding_client=embedder,
        memory_skill=SimpleNamespace(embedding_client=embedder),
        web_llm_gateway=SimpleNamespace(usage_meter=meter),
        _native_mcp_client=SimpleNamespace(
            statuses=lambda: (
                SimpleNamespace(
                    server_name="blender-mac-ronny",
                    connected=False,
                    tool_count=0,
                    error="ConnectError",
                ),
            )
        ),
    )
    preflight = {
        "status": "ok",
        "checked_at": "2026-10-12T01:12:00Z",
        "checks": [
            {"id": "prompts", "status": "ok", "summary_key": "prompts_ok", "skill_prompt_count": 4, "detail": "4"},
            {"id": "qdrant", "status": "ok", "summary_key": "qdrant_ok", "collection_count": 8, "detail": "8"},
            {"id": "llm", "status": "ok", "summary_key": "llm_ok", "detail": "anthropic/claude-sonnet-5"},
            {"id": "embeddings", "status": "ok", "summary_key": "embeddings_ok", "detail": "openai/text-embedding-3-small"},
        ],
    }
    technical_stats = {
        "model_total_tokens": 80,
        "chat_tokens_by_model": {
            "anthropic/claude-sonnet-5": 50,
            "openai/gpt-5-search": 20,
        },
        "embedding_tokens_by_model": {"openai/text-embedding-3-small": 10},
        "llm_requests_by_role": {"chat": 3, "web": 2},
        "native_web_search_uses": 4,
        "native_web_search_cost_usd": 0.012,
        "native_web_search_unpriced_requests": 1,
    }
    pricing = _build_pricing_meta(
        technical_stats, settings, lambda table, model: table.get(model),
    )
    return settings, pipeline, preflight, technical_stats, pricing


def test_alpha983_check_and_model_role_parity_is_preserved(tmp_path: Path, monkeypatch) -> None:
    settings, pipeline, preflight, technical_stats, pricing = _fixture(tmp_path)
    monkeypatch.setattr(
        stats_routes.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("passive /stats projection must not inspect Docker")
        ),
    )

    blocks = _build_stats_check_blocks(
        settings=settings,
        pipeline=pipeline,
        preflight_payload=preflight,
        pricing_meta=pricing,
        technical_stats=technical_stats,
        release_meta={"label": "0.1.0-alpha1007", "version": "0.1.0-alpha1007"},
        update_status={"current_label": "0.1.0-alpha1007", "latest_label": "0.1.0-alpha983"},
        registry_meta={"module_count": 106, "validation_issue_count": 0, "dependency_cycle_count": 0},
        base_dir=tmp_path,
        language="de",
    )

    rows = {row["key"]: row for block in blocks for row in block["rows"]}
    assert ALPHA983_REQUIRED_CHECKS <= set(rows)
    assert "Web: openai/gpt-5-search" in rows["model_stack"]["summary"]
    assert "blender-mac-ronny" in rows["mcp_servers"]["summary"]
    assert "ConnectError" in rows["mcp_servers"]["detail"]
    assert rows["mcp_servers"]["url"] == "/config/connections/mcp/blender-mac-ronny"
    assert all(row["url"] for row in rows.values() if row["status"] != "ok")
    assert {row["model"] for row in pricing["source_rows"]} == {
        "anthropic/claude-sonnet-5",
        "openai/gpt-5-search",
        "openai/text-embedding-3-small",
    }


def test_alpha983_startup_checks_remain_visible_without_snapshot(tmp_path: Path) -> None:
    settings, pipeline, _preflight, technical_stats, pricing = _fixture(tmp_path)
    blocks = _build_stats_check_blocks(
        settings=settings,
        pipeline=pipeline,
        preflight_payload={},
        pricing_meta=pricing,
        technical_stats=technical_stats,
        release_meta={"label": "0.1.0-alpha1007", "version": "0.1.0-alpha1007"},
        update_status={},
        registry_meta={"module_count": 106, "validation_issue_count": 0, "dependency_cycle_count": 0},
        base_dir=tmp_path,
        language="de",
    )

    rows = {row["key"]: row for block in blocks for row in block["rows"]}
    for key in ("prompts", "qdrant_startup", "chat_llm", "embeddings"):
        assert rows[key]["status"] == "warn"
        assert rows[key]["summary"] == "Für diese Startprüfung ist kein gespeichertes Ergebnis verfügbar."


def test_stats_markup_reuses_alpha983_lamps_pills_and_full_text() -> None:
    template = (
        (ROOT / "aria/templates/stats.html").read_text(encoding="utf-8")
        + (ROOT / "aria/templates/_stats_check_block.html").read_text(encoding="utf-8")
    )
    css = (ROOT / "aria/static/style.css").read_text(encoding="utf-8")

    assert 'class="health-lamp status-{{ row.status }}"' in template
    assert 'data-stats-count="ok"' in template
    assert 'data-stats-count="warn"' in template
    assert 'data-stats-count="error"' in template
    assert "text-overflow: ellipsis" not in css[css.index(".stats-check-tile p {"):css.index(".stats-check-tile small")]
    assert "white-space: nowrap" not in css[css.index(".stats-check-tile p {"):css.index(".stats-check-tile small")]


def test_stats_removes_abstract_status_copy_and_documents_parity() -> None:
    template = (ROOT / "aria/templates/stats.html").read_text(encoding="utf-8")
    de = (ROOT / "aria/i18n/de.json").read_text(encoding="utf-8")
    linter = (ROOT / "aria/modules/config_ui/page_linter.py").read_text(encoding="utf-8")
    parity = ROOT / "docs/ui/stats-alpha983-parity-alpha1006.md"
    forbidden = (
        "Mindestens eine passive Prüfung braucht Aufmerksamkeit.",
        "Passiver Status",
        "Passiver Status aus der letzten Startprüfung",
        "ARIA verarbeitet diese Seite lokal.",
    )

    for phrase in forbidden:
        assert phrase not in template
        assert phrase not in de
        assert phrase.casefold() in linter.casefold()
    assert parity.exists()
    assert "Bewusst entfernt" in parity.read_text(encoding="utf-8")

    result = lint_page_snapshots([{
        "path": "/stats",
        "page_type": "overview",
        "inherits_page_base": True,
        "title_count": 1,
        "canonical_parent_section": "system",
        "rendered_parent_section": "system",
        "abstract_denied_terms": [forbidden[0]],
    }])
    assert any(
        row.rule == "R6" and "abstract status text" in row.message
        for row in result.blocking_findings
    )


def test_technical_section_exposes_all_alpha983_model_roles_and_web_usage() -> None:
    template = (ROOT / "aria/templates/stats.html").read_text(encoding="utf-8")

    for field in (
        "technical.chat_model",
        "technical.chat_api_base",
        "technical.web_model",
        "technical.web_api_base",
        "technical.embedding_model",
        "technical.embedding_api_base",
        "technical.gateway_mode",
        "technical.web_llm_requests",
        "technical.native_search_uses",
        "technical.native_search_cost_usd",
        "technical.native_search_unpriced_requests",
        "technical.token_log",
    ):
        assert field in template
